from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.settings import settings
import stripe

# DB
from app.db import SessionLocal, Order, init_db

# Google Sheets
import json
import gspread
from google.oauth2.service_account import Credentials

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

# --- DB bootstrap ---
@app.on_event("startup")
def on_startup():
    init_db()

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
        ws.find(session_id)  # cerca il session_id
        print("ℹ️ Session già presente su Sheets:", session_id)
        return
    except gspread.exceptions.CellNotFound:
        pass

    # Estrazioni utili
    pi = session.get("payment_intent")
    amount_total = session.get("amount_total")
    currency = session.get("currency")
    payment_status = session.get("payment_status")
    status = session.get("status")
    mode = session.get("mode")
    customer_details = session.get("customer_details") or {}
    email = customer_details.get("email")
    name = customer_details.get("name")
    success_url = session.get("success_url")
    cancel_url = session.get("cancel_url")
    livemode = bool(session.get("livemode", False))

    # Items / price ids (opzionale: qui lasciamo vuoto)
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

    # Price fisso da env se presente, altrimenti parametri dal client
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

    # (1) LOG EVENTO
    print("📦 Stripe event:", event.get("type"))

    if event["type"] == "checkout.session.completed":
        # Stripe ritorna StripeObject; convertiamolo in dict serializzabile
        stripe_obj = event["data"]["object"]
        session = (
            stripe_obj
            if isinstance(stripe_obj, dict)
            else getattr(stripe_obj, "to_dict_recursive", lambda: dict(stripe_obj))()
        )

        # --- salva su DB ---
        db = SessionLocal()
        try:
            order = db.query(Order).filter(Order.session_id == session["id"]).one_or_none()
            if order is None:
                order = Order(
                    session_id=session.get("id"),
                    payment_intent=session.get("payment_intent"),
                    amount_total=session.get("amount_total"),
                    currency=session.get("currency") or ("eur" if session.get("amount_subtotal") else None),
                    email=(session.get("customer_details") or {}).get("email"),
                    status=session.get("status"),
                    raw=session,  # <-- ora è un dict
                )
                db.add(order)
            else:
                order.payment_intent = session.get("payment_intent")
                order.amount_total = session.get("amount_total")
                order.currency = session.get("currency") or order.currency
                order.email = (session.get("customer_details") or {}).get("email") or order.email
                order.status = session.get("status") or order.status
                order.raw = session

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

# ---------- DEBUG EXTRA ----------
@app.get("/debug/sheets")
def debug_sheets():
    try:
        ws = get_sheet()
        if not ws:
            return {"ok": False, "msg": "Sheets non configurato (controlla env: GOOGLE_SERVICE_ACCOUNT_JSON, SHEETS_SPREADSHEET_ID, SHEETS_WORKSHEET_NAME)"}
        ws.append_row(["DEBUG", "now"], value_input_option="RAW")
        return {"ok": True, "msg": "Append riuscito (riga DEBUG)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/debug/db")
def debug_db():
    db = SessionLocal()
    try:
        count = db.query(Order).count()
        return {"ok": True, "orders_count": count, "db": settings.DATABASE_URL}
    finally:
        db.close()
