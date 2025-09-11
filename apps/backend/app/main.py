from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.settings import settings
import stripe
import os
import json

# DB
from app.db import SessionLocal, Order, init_db

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: limita al dominio frontend in produzione
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

print("✅ APP BOOT")

# --- DB bootstrap ---
@app.on_event("startup")
def on_startup():
    init_db()
    print("✅ DB INIT DONE")

# ---------- Helper Google Sheets ----------
def get_sheet():
    if not (settings.SHEETS_SPREADSHEET_ID and settings.SHEETS_WORKSHEET_NAME and settings.GOOGLE_SERVICE_ACCOUNT_JSON):
        return None
    info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(settings.SHEETS_SPREADSHEET_ID)
    return sh.worksheet(settings.SHEETS_WORKSHEET_NAME)

def append_order_row(session: dict, event_id: str):
    ws = get_sheet()
    if not ws:
        print("ℹ️ Google Sheets non configurato, salto append.")
        return

    # Evita duplicati: non reinserire la stessa sessione
    session_id = session.get("id")
    try:
        ws.find(session_id)
        print("ℹ️ Session già presente su Sheets:", session_id)
        return
    except gspread.exceptions.CellNotFound:
        pass

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

# ---------- HANDLER RIUTILIZZABILE (DB + Sheets) ----------
def _handle_checkout_completed(session_dict: dict, event_id: str = "evt_unknown"):
    # --- salva su DB ---
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.session_id == session_dict["id"]).one_or_none()
        if order is None:
            order = Order(
                session_id=session_dict["id"],
                payment_intent=session_dict.get("payment_intent"),
                amount_total=session_dict.get("amount_total"),
                currency=session_dict.get("currency") or "eur",
                email=(session_dict.get("customer_details") or {}).get("email"),
                status=session_dict.get("status"),
                raw=session_dict,  # <-- dict puro (non oggetto Stripe)
            )
            db.add(order)
        else:
            order.payment_intent = session_dict.get("payment_intent")
            order.amount_total = session_dict.get("amount_total")
            order.currency = session_dict.get("currency") or order.currency
            order.email = (session_dict.get("customer_details") or {}).get("email") or order.email
            order.status = session_dict.get("status") or order.status
            order.raw = session_dict

        db.commit()
        print("✅ Ordine salvato:", order.session_id, order.status, order.amount_total)
    except Exception as e:
        db.rollback()
        print("❌ Errore salvataggio ordine:", e)
        raise
    finally:
        db.close()

    # --- append su Google Sheets ---
    try:
        append_order_row(session_dict, event_id=event_id)
    except Exception as e:
        print("⚠️ Errore append su Google Sheets:", e)

# ---------- ROUTES ----------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "env": settings.APP_ENV,
        "db": settings.DATABASE_URL.split("://", 1)[0],
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

# ---------- WEBHOOK (usa il payload grezzo per avere un dict puro) ----------
@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload_bytes = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload_bytes, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print("⚠️ Webhook error:", str(e))
        raise HTTPException(status_code=400, detail=str(e))

    # payload come dict puro, per salvare 'raw' senza oggetti Stripe
    try:
        event_dict = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        event_dict = {}

    if event["type"] == "checkout.session.completed":
        # dict puro della sessione, compatibile con JSON SQLAlchemy
        session_dict = (event_dict.get("data") or {}).get("object") or {}
        if not session_dict:
            # fallback: converti oggetto Stripe in dict
            stripe_obj = event["data"]["object"]
            try:
                session_dict = json.loads(stripe_obj.to_json())  # disponibile sulle versioni recenti
            except Exception:
                session_dict = {
                    "id": stripe_obj.get("id"),
                    "payment_intent": stripe_obj.get("payment_intent"),
                    "amount_total": stripe_obj.get("amount_total"),
                    "currency": stripe_obj.get("currency"),
                    "status": stripe_obj.get("status"),
                    "payment_status": stripe_obj.get("payment_status"),
                    "mode": stripe_obj.get("mode"),
                    "customer_details": (stripe_obj.get("customer_details") or {}),
                    "livemode": stripe_obj.get("livemode"),
                    "metadata": stripe_obj.get("metadata") or {},
                    "success_url": stripe_obj.get("success_url"),
                    "cancel_url": stripe_obj.get("cancel_url"),
                }

        _handle_checkout_completed(session_dict, event_id=event["id"])

    return {"status": "success", "event": event["type"]}

# ---------- ENDPOINT DI SIMULAZIONE DEV (per test rapidi) ----------
@app.post("/dev/simulate-checkout")
async def dev_simulate_checkout(request: Request):
    token = request.query_params.get("token") or ""
    if token != settings.DEV_WEBHOOK_TOKEN and token != os.getenv("DEV_WEBHOOK_TOKEN", ""):
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    import uuid
    session_dict = {
        "id": body.get("id", "cs_test_simulated_" + uuid.uuid4().hex[:12]),
        "payment_intent": body.get("payment_intent", "pi_test_" + uuid.uuid4().hex[:8]),
        "amount_total": body.get("amount_total", 990),
        "currency": body.get("currency", "eur"),
        "status": body.get("status", "complete"),
        "payment_status": body.get("payment_status", "paid"),
        "mode": body.get("mode", "payment"),
        "customer_details": body.get("customer_details", {"email": "demo@example.com", "name": "Demo User"}),
        "livemode": False,
        "metadata": body.get("metadata", {}),
        "success_url": body.get("success_url", settings.SUCCESS_URL),
        "cancel_url": body.get("cancel_url", settings.CANCEL_URL),
    }
    _handle_checkout_completed(session_dict, event_id="evt_dev_simulated")
    return {"ok": True, "session_id": session_dict["id"]}

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

# ---------- API di ispezione ----------
@app.get("/orders")
def list_orders(limit: int = 20):
    db = SessionLocal()
    try:
        rows = db.query(Order).order_by(Order.id.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "session_id": r.session_id,
                "payment_intent": r.payment_intent,
                "amount_total": r.amount_total,
                "currency": r.currency,
                "email": r.email,
                "status": r.status,
                "created_at": str(r.created_at),
            }
            for r in rows
        ]
    finally:
        db.close()
