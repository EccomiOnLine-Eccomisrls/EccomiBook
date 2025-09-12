from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from app.settings import settings
import json
import time

# Stripe
import stripe

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in produzione puoi limitarlo al tuo dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Stripe bootstrap ----------
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


# ---------- Google Sheets helpers ----------
SHEETS_HEADERS = [
    "created_at",         # A
    "event_id",           # B
    "session_id",         # C
    "payment_intent",     # D
    "mode",               # E
    "payment_status",     # F
    "status",             # G
    "amount_total_cents", # H
    "currency",           # I
    "customer_email",     # J
    "customer_name",      # K
    "items",              # L
    "price_ids",          # M
    "livemode",           # N
    "metadata_json",      # O
    "success_url",        # P
    "cancel_url",         # Q
]

def get_sheet():
    """
    Restituisce la worksheet configurata (o None se non configurata).
    Assicurati che:
    - SHEETS_SPREADSHEET_ID sia corretto
    - SHEETS_WORKSHEET_NAME esista (es. 'Foglio1')
    - Hai condiviso il foglio con l'email del service account
    """
    if not (settings.SHEETS_SPREADSHEET_ID and settings.SHEETS_WORKSHEET_NAME and settings.GOOGLE_SERVICE_ACCOUNT_JSON):
        return None
    info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(settings.SHEETS_SPREADSHEET_ID)
    ws = sh.worksheet(settings.SHEETS_WORKSHEET_NAME)

    # Verifica/inizializza header
    values = ws.get_values("A1:Q1")
    if not values or values[0] != SHEETS_HEADERS:
        ws.update("A1", [SHEETS_HEADERS])

    return ws


def append_order_row(session: dict, event_id: str):
    """
    Aggiunge una riga su Google Sheets. Evita duplicati per session_id.
    """
    ws = get_sheet()
    if not ws:
        print("ℹ️ Google Sheets non configurato, salto append.")
        return

    session_id = session.get("id") or session.get("session_id")
    if not session_id:
        print("⚠️ Session senza id, salto append.")
        return

    # Evita duplicati
    try:
        ws.find(session_id)
        print("ℹ️ Session già presente su Sheets:", session_id)
        return
    except gspread.exceptions.CellNotFound:
        pass

    # Campi utili
    pi = session.get("payment_intent")
    amount_total = session.get("amount_total")
    currency = session.get("currency")
    payment_status = session.get("payment_status")
    status = session.get("status")
    mode = session.get("mode")
    email = (session.get("customer_details") or {}).get("email")
    name = (session.get("customer_details") or {}).get("name")
    success_url = session.get("success_url")
    cancel_url = session.get("cancel_url")
    livemode = bool(session.get("livemode", False))

    items_str = ""
    price_ids = ""
    metadata_json = json.dumps(session.get("metadata") or {}, ensure_ascii=False)

    # created_at ISO
    created_iso = ""
    if session.get("created"):
        from datetime import datetime, timezone
        created_iso = datetime.fromtimestamp(session["created"], tz=timezone.utc).isoformat()

    row = [
        created_iso,            # created_at
        event_id,               # event_id
        session_id,             # session_id
        pi,                     # payment_intent
        mode,                   # mode
        payment_status,         # payment_status
        status,                 # status
        amount_total or "",     # amount_total_cents
        currency or "",         # currency
        email or "",            # customer_email
        name or "",             # customer_name
        items_str,              # items
        price_ids,              # price_ids
        str(livemode).lower(),  # livemode
        metadata_json,          # metadata_json
        success_url or "",      # success_url
        cancel_url or "",       # cancel_url
    ]
    ws.append_row(row, value_input_option="RAW")
    print("✅ Inserita riga su Sheets per session:", session_id)


def read_orders_from_sheet(limit: int = 20):
    """
    Legge le ultime `limit` righe dal foglio e le restituisce come JSON, mappando con gli header.
    """
    ws = get_sheet()
    if not ws:
        return []

    all_values = ws.get_all_values()
    if not all_values or len(all_values) <= 1:
        return []

    headers = all_values[0]
    rows = all_values[1:]
    # prendi le ultime `limit`
    rows = rows[-limit:]
    results = []
    for r in rows:
        obj = {}
        for i, h in enumerate(headers):
            obj[h] = r[i] if i < len(r) else ""
        results.append(obj)
    # Ordine decrescente per created_at (ultimo in alto)
    results.reverse()
    return results


# ---------- MODELS ----------
class DevSimulatedCheckout(BaseModel):
    amount_total: int = 990
    currency: str = "eur"
    customer_details: dict | None = None


# ---------- ROUTES ----------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "env": settings.APP_ENV,
        "sheets": bool(settings.SHEETS_SPREADSHEET_ID and settings.SHEETS_WORKSHEET_NAME and settings.GOOGLE_SERVICE_ACCOUNT_JSON),
    }


@app.get("/")
def root():
    return {"message": "EccomiBook Backend up ✨"}


# ---------- CHECKOUT ----------
@app.post("/checkout/session")
async def create_checkout_session(request: Request):
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe non configurato")

    payload = await request.json()
    quantity = int(payload.get("quantity", 1))
    mode = payload.get("mode", "payment")
    price_id = payload.get("price_id") or settings.STRIPE_PRICE_ID or None

    try:
        if price_id:
            line_items = [{"price": price_id, "quantity": quantity}]
        else:
            price_data = payload.get("price_data")
            if not price_data:
                raise HTTPException(status_code=400, detail="price_data o price_id richiesto")

            currency = price_data.get("currency", "eur")
            unit_amount = price_data.get("unit_amount")
            product_name = price_data.get("product_name", "EccomiBook Product")
            if unit_amount is None:
                raise HTTPException(status_code=400, detail="unit_amount mancante")

            line_items = [{
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": product_name},
                    "unit_amount": unit_amount
                },
                "quantity": quantity
            }]

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode=mode,
            success_url=settings.SUCCESS_URL,
            cancel_url=settings.CANCEL_URL,
        )
        return {"checkout_url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- WEBHOOK ----------
@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print("⚠️ Webhook error:", str(e))
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        # Stripe fornisce StripeObject; qui lo uso già come dict serializzabile
        session = event["data"]["object"]
        # append su Google Sheets (niente DB)
        try:
            append_order_row(session, event_id=event.get("id", ""))
        except Exception as e:
            print("⚠️ Errore append su Google Sheets:", e)

    return {"status": "success", "event": event["type"]}


# ---------- PAGINE DI RISULTATO ----------
@app.get("/success", response_class=HTMLResponse)
def success():
    return "<h1>Pagamento completato ✅</h1>"

@app.get("/cancel", response_class=HTMLResponse)
def cancel():
    return "<h1>Pagamento annullato ❌</h1>"


# ---------- PAGINA DI TEST ----------
@app.get("/test-checkout", response_class=HTMLResponse)
def test_checkout_page():
    return """
<!doctype html>
<html>
  <head><meta charset="utf-8"><title>Test Checkout</title></head>
  <body style="font-family:system-ui;margin:40px">
    <h1>Test Stripe Checkout</h1>
    <p>Crea una sessione “una tantum” da 9,90€ (test mode).</p>
    <button id="go">Vai al checkout</button>
    <script>
      document.getElementById('go').onclick = async () => {
        const res = await fetch('/checkout/session', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({
            mode: 'payment',
            quantity: 1,
            price_data: {
              currency: 'eur',
              unit_amount: 990,
              product_name: 'EccomiBook - Test'
            }
          })
        });
        const data = await res.json();
        if (data.checkout_url) window.location.href = data.checkout_url;
        else alert('Errore: ' + JSON.stringify(data));
      };
    </script>
  </body>
</html>
"""


# ---------- API di ispezione basata su Sheets ----------
@app.get("/orders")
def list_orders(limit: int = Query(20, ge=1, le=200)):
    """
    Restituisce gli ultimi ordini letti dal Google Sheet.
    """
    try:
        return read_orders_from_sheet(limit=limit)
    except Exception as e:
        print("⚠️ Errore lettura orders da Sheets:", e)
        return []


# ---------- DEV: Simulazione checkout per testare Sheets senza Stripe ----------
@app.post("/dev/simulate-checkout")
async def dev_simulate_checkout(body: DevSimulatedCheckout, token: str = Query("")):
    if token != settings.DEV_WEBHOOK_TOKEN:
        raise HTTPException(status_code=403, detail="Token non valido")

    now = int(time.time())
    fake_session = {
        "id": f"cs_sim_{now}",
        "object": "checkout.session",
        "payment_intent": f"pi_sim_{now}",
        "amount_total": body.amount_total,
        "currency": body.currency,
        "payment_status": "paid",
        "status": "complete",
        "mode": "payment",
        "customer_details": body.customer_details or {"email": "prova@example.com", "name": "Test User"},
        "success_url": settings.SUCCESS_URL,
        "cancel_url": settings.CANCEL_URL,
        "livemode": False,
        "created": now,
        "metadata": {},
    }

    append_order_row(fake_session, event_id=f"evt_sim_{now}")
    return {"ok": True, "session_id": fake_session["id"]}
