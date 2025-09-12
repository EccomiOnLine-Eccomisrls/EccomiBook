# app/main.py — SOLO GOOGLE SHEETS (niente DB)

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Any, Dict, List
import json
import os

from app.settings import settings

# -------- Stripe (opzionale: serve per /checkout/session e /webhook/stripe) --------
import stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

# -------- Google Sheets --------
import gspread
from google.oauth2.service_account import Credentials

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restringi in produzione se vuoi
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------- Costante intestazioni Sheets ----------------------
HEADERS = [
    "created_at",       # A
    "event_id",         # B
    "session_id",       # C
    "payment_intent",   # D
    "mode",             # E
    "payment_status",   # F
    "status",           # G
    "amount_total",     # H (cents)
    "currency",         # I
    "customer_email",   # J
    "customer_name",    # K
    "items",            # L (string)
    "price_ids",        # M (string)
    "livemode",         # N (true/false)
    "metadata_json",    # O (string JSON)
    "success_url",      # P
    "cancel_url",       # Q
]

# ---------------------- Helpers Google Sheets (con diagnostica) ----------------------
def get_sheet():
    """
    Ritorna il worksheet pronto. Se qualcosa va storto, solleva 500 con dettaglio esplicito.
    """
    try:
        if not settings.SHEETS_SPREADSHEET_ID:
            raise RuntimeError("SHEETS_SPREADSHEET_ID mancante")
        if not settings.SHEETS_WORKSHEET_NAME:
            raise RuntimeError("SHEETS_WORKSHEET_NAME mancante")
        if not settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON mancante")

        # 1) Parse credenziali
        try:
            info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
        except Exception as e:
            raise RuntimeError(f"JSON credenziali non valido: {repr(e)}")

        # 2) Auth
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_info(info, scopes=scopes)
            client = gspread.authorize(creds)
        except Exception as e:
            raise RuntimeError(f"Auth fallita: {repr(e)}")

        # 3) Apri spreadsheet
        try:
            sh = client.open_by_key(settings.SHEETS_SPREADSHEET_ID)
        except Exception as e:
            raise RuntimeError(f"Apertura spreadsheet fallita (ID?): {repr(e)}")

        # 4) Apri worksheet/tab
        try:
            ws = sh.worksheet(settings.SHEETS_WORKSHEET_NAME)
        except Exception as e:
            try:
                tabs = [w.title for w in sh.worksheets()]
            except Exception:
                tabs = []
            raise RuntimeError(
                f"Worksheet '{settings.SHEETS_WORKSHEET_NAME}' non trovato. "
                f"Tab disponibili: {tabs} | err={repr(e)}"
            )

        # 5) Assicura intestazioni
        try:
            first_row = ws.row_values(1)
            if [h.strip().lower() for h in first_row] != HEADERS:
                ws.resize(rows=1)  # reset header
                ws.update("A1:Q1", [HEADERS])
        except Exception as e:
            raise RuntimeError(f"Update header fallito: {repr(e)}")

        return ws

    except Exception as e:
        # Propaga come HTTP 500 con dettaglio utile
        raise HTTPException(status_code=500, detail=f"Sheets error: {e}")


def append_order_row(session: dict, event_id: str):
    """
    Aggiunge una riga su Sheets, evitando duplicati per session_id.
    """
    ws = get_sheet()

    session_id = session.get("id") or session.get("session_id")
    if not session_id:
        print("⚠️ Nessun session_id, salto append.")
        return

    # Evita duplicati
    try:
        ws.find(str(session_id))
        print("ℹ️ Session già presente su Sheets:", session_id)
        return
    except gspread.exceptions.CellNotFound:
        pass

    pi = session.get("payment_intent")
    amount_total = session.get("amount_total")
    currency = session.get("currency")
    payment_status = session.get("payment_status")
    status = session.get("status")
    mode = session.get("mode") or "payment"
    email = (session.get("customer_details") or {}).get("email")
    name = (session.get("customer_details") or {}).get("name")
    success_url = session.get("success_url") or settings.SUCCESS_URL
    cancel_url = session.get("cancel_url") or settings.CANCEL_URL
    livemode = bool(session.get("livemode", False))
    metadata_json = json.dumps(session.get("metadata") or {}, ensure_ascii=False)

    # created_at ISO
    created_iso = ""
    if session.get("created"):
        from datetime import datetime, timezone
        created_iso = datetime.fromtimestamp(int(session["created"]), tz=timezone.utc).isoformat()

    # (per ora non estraiamo items/price_ids in dettaglio)
    items_str = ""
    price_ids = ""

    row = [
        created_iso,            # 1. created_at
        event_id,               # 2. event_id
        session_id,             # 3. session_id
        pi,                     # 4. payment_intent
        mode,                   # 5. mode
        payment_status,         # 6. payment_status
        status,                 # 7. status
        amount_total or "",     # 8. amount_total
        currency or "",         # 9. currency
        email or "",            # 10. customer_email
        name or "",             # 11. customer_name
        items_str,              # 12. items
        price_ids,              # 13. price_ids
        str(livemode).lower(),  # 14. livemode
        metadata_json,          # 15. metadata_json
        success_url or "",      # 16. success_url
        cancel_url or "",       # 17. cancel_url
    ]
    ws.append_row(row, value_input_option="RAW")
    print("✅ Inserita riga su Sheets per session:", session_id)


def sheet_rows_to_objects(values: List[List[str]]) -> List[Dict[str, Any]]:
    """
    Converte le righe del foglio (A:Q) in oggetti dict con chiavi HEADERS.
    """
    out: List[Dict[str, Any]] = []
    for r in values:
        row = (r + [""] * 17)[:17]  # pad/trim a 17 colonne
        obj = {HEADERS[i]: row[i] for i in range(17)}
        out.append(obj)
    return out


# ---------------------- Modelli ----------------------
class DevSimulatedCheckout(BaseModel):
    amount_total: int = 990
    currency: str = "eur"
    customer_details: Dict[str, Any] | None = None


# ---------------------- Routes ----------------------
@app.on_event("startup")
def on_startup():
    print(f"✅ APP STARTED | ENV: {settings.APP_ENV}")


@app.get("/health")
def health():
    # Stato app e Sheets
    ok = True
    sheets = "ok"
    try:
        _ = get_sheet()
    except Exception as e:
        sheets = f"error: {e}"
        ok = False
    return {
        "status": "ok" if ok else "degraded",
        "service": settings.APP_NAME,
        "env": settings.APP_ENV,
        "sheets": sheets,
    }


@app.get("/")
def root():
    return {"message": "EccomiBook Backend (solo Google Sheets) ✨"}


# ---------- Checkout (crea la sessione Stripe e reindirizza) ----------
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


# ---------- Webhook Stripe → scrive su Google Sheets ----------
@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret mancante")

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
        session = event["data"]["object"]
        try:
            append_order_row(session, event_id=event.get("id", ""))
        except Exception as e:
            print("⚠️ Errore append su Google Sheets:", e)
            # non rompiamo il webhook: rispondiamo comunque 200
    return {"status": "success", "event": event["type"]}


# ---------- Endpoint di simulazione (senza Stripe) ----------
@app.post("/dev/simulate-checkout")
async def dev_simulate_checkout(
    body: DevSimulatedCheckout,
    token: str = Query(..., description="DEV_WEBHOOK_TOKEN"),
):
    if not settings.DEV_WEBHOOK_TOKEN or token != settings.DEV_WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from datetime import datetime, timezone
    import time
    now_ts = int(time.time())

    fake_session = {
        "id": f"cs_sim_{now_ts}",
        "object": "checkout.session",
        "payment_intent": f"pi_sim_{now_ts}",
        "amount_total": body.amount_total,
        "currency": body.currency,
        "customer_details": body.customer_details or {},
        "status": "complete",
        "payment_status": "paid",
        "mode": "payment",
        "success_url": settings.SUCCESS_URL,
        "cancel_url": settings.CANCEL_URL,
        "livemode": False,
        "created": now_ts,
        "metadata": {},
    }
    fake_event_id = f"evt_sim_{now_ts}"

    try:
        append_order_row(fake_session, event_id=fake_event_id)
    except Exception as e:
        # Ora l'errore è dettagliato
        raise HTTPException(status_code=500, detail=f"Sheets error: {e}")

    return {"status": "ok", "session_id": fake_session["id"]}


# ---------- DEBUG SHEETS ----------
@app.get("/dev/check-sheets")
def check_sheets(token: str):
    if token != settings.DEV_WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        ws = get_sheet()
        return {
            "status": "ok",
            "title": ws.title,
            "rows": ws.row_count,
            "cols": ws.col_count,
            "first_row": ws.row_values(1),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sheets error: {e}")


@app.get("/dev/list-worksheets")
def list_worksheets(token: str):
    if token != settings.DEV_WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        sh = client.open_by_key(settings.SHEETS_SPREADSHEET_ID)
        tabs = [w.title for w in sh.worksheets()]
        return {"status": "ok", "tabs": tabs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sheets error: {repr(e)}")


@app.get("/dev/check-sheets-steps")
def check_sheets_steps(token: str):
    if token != settings.DEV_WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    out: Dict[str, Any] = {}
    try:
        out["has_env"] = all([
            bool(settings.SHEETS_SPREADSHEET_ID),
            bool(settings.SHEETS_WORKSHEET_NAME),
            bool(settings.GOOGLE_SERVICE_ACCOUNT_JSON),
        ])

        info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
        out["json_ok"] = True

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        out["auth_ok"] = True

        sh = client.open_by_key(settings.SHEETS_SPREADSHEET_ID)
        out["open_ok"] = True
        out["spreadsheet_title"] = sh.title
        out["tabs"] = [w.title for w in sh.worksheets()]

        ws = sh.worksheet(settings.SHEETS_WORKSHEET_NAME)
        out["worksheet_ok"] = True
        out["first_row"] = ws.row_values(1)
        return out
    except Exception as e:
        out["error"] = repr(e)
        raise HTTPException(status_code=500, detail=out)


# ---------- Pagine risultato ----------
@app.get("/success", response_class=HTMLResponse)
def success():
    return "<h1>Pagamento completato ✅</h1>"

@app.get("/cancel", response_class=HTMLResponse)
def cancel():
    return "<h1>Pagamento annullato ❌</h1>"


# ---------- Pagina test checkout ----------
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


# ---------- API lettura ordini (da Sheets) ----------
@app.get("/orders")
def list_orders(limit: int = 20):
    """
    Legge le ultime `limit` righe dal Google Sheet e restituisce un array di oggetti.
    """
    ws = get_sheet()
    values = ws.get_all_values()
    if not values or len(values) <= 1:
        return []

    data_rows = values[1:]          # salta header
    data_rows = data_rows[-limit:]  # ultime N
    objs = sheet_rows_to_objects(data_rows)
    for i, o in enumerate(objs, 1):
        o["id"] = i
    return objs
