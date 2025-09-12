from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from app.settings import settings
import stripe
import json
import time
import uuid

# DB
from app.db import SessionLocal, Order, init_db

# Google Sheets
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
    print("✅ APP STARTED | ENV:", settings.APP_ENV)

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

    session_id = session.get("id") or session.get("session_id")
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
        created_iso,            # 1. created_at
        event_id,               # 2. event_id
        session_id,             # 3. session_id
        pi,                     # 4. payment_intent
        mode,                   # 5. mode
        payment_status,         # 6. payment_status
        status,                 # 7. status
        amount_total or "",     # 8. amount_total_cents
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

# ---------- Utility ----------
def stripe_obj_to_dict(obj):
    # Converte lo StripeObject in dict serializzabile per salvarlo in JSON
    try:
        return obj.to_dict_recursive()  # disponibile sulle versioni moderne
    except Exception:
        try:
            return json.loads(str(obj))
        except Exception:
            return dict(obj) if isinstance(obj, dict) else {"_raw": str(obj)}

def save_order_and_sheet(session_obj: dict | object, event_id: str):
    """Salva su DB e appende su Google Sheets."""
    session_dict = stripe_obj_to_dict(session_obj)

    # campi "comodi"
    session_id = session_dict.get("id") or session_dict.get("session_id")
    payment_intent = session_dict.get("payment_intent")
    amount_total = session_dict.get("amount_total")
    currency = session_dict.get("currency") or ("eur" if amount_total else None)
    email = (session_dict.get("customer_details") or {}).get("email")
    status = session_dict.get("status")

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.session_id == session_id).one_or_none()
        if order is None:
            order = Order(
                session_id=session_id,
                payment_intent=payment_intent,
                amount_total=amount_total,
                currency=currency,
                email=email,
                status=status,
                raw=session_dict,
            )
            db.add(order)
        else:
            order.payment_intent = payment_intent
            order.amount_total = amount_total
            order.currency = currency or order.currency
            order.email = email or order.email
            order.status = status or order.status
            order.raw = session_dict

        db.commit()
        print("✅ Ordine salvato:", order.session_id, order.status, order.amount_total)
    except Exception as e:
        db.rollback()
        print("❌ Errore salvataggio ordine:", e)
        raise
    finally:
        db.close()

    # Sheets (best-effort)
    try:
        append_order_row(session_dict, event_id=event_id)
    except Exception as e:
        print("⚠️ Errore append su Google Sheets:", e)

# ---------- MODELLI ----------
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
        session_obj = event["data"]["object"]
        save_order_and_sheet(session_obj, event_id=event.get("id", ""))

    return {"status": "success", "event": event["type"]}

# ---------- DEV: simulate checkout (abilitato anche in prod con token) ----------
@app.post("/dev/simulate-checkout")
async def dev_simulate_checkout(
    body: DevSimulatedCheckout,
    token: str = Query(..., description="Your DEV_WEBHOOK_TOKEN"),
):
    if not settings.DEV_WEBHOOK_TOKEN:
        raise HTTPException(status_code=500, detail="DEV_WEBHOOK_TOKEN non configurato")
    if token != settings.DEV_WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # crea un finto 'checkout.session' compatibile
    sid = "cs_sim_" + uuid.uuid4().hex[:32]
    pi = "pi_sim_" + uuid.uuid4().hex[:24]
    now = int(time.time())

    session_like = {
        "id": sid,
        "object": "checkout.session",
        "payment_intent": pi,
        "amount_total": body.amount_total,
        "currency": body.currency or "eur",
        "payment_status": "paid",
        "status": "complete",
        "mode": "payment",
        "customer_details": body.customer_details or {"email": "test@example.com", "name": "Sim User"},
        "success_url": settings.SUCCESS_URL,
        "cancel_url": settings.CANCEL_URL,
        "livemode": False,
        "created": now,
        "metadata": {},
    }

    event_id = "evt_sim_" + uuid.uuid4().hex[:24]
    save_order_and_sheet(session_like, event_id=event_id)

    return {
        "ok": True,
        "event_id": event_id,
        "session_id": sid,
        "amount_total": body.amount_total,
        "currency": body.currency,
    }

# ---------- PAGINE DI RISULTATO ----------
@app.get("/success", response_class=HTMLResponse)
def success():
    return "<h1>Pagamento completato ✅</h1>"

@app.get("/cancel", response_class=HTMLResponse)
def cancel():
    return "<h1>Pagamento annullato ❌</h1>"

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
