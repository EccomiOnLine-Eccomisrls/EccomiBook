from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.settings import settings
import stripe
import json

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

if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

@app.on_event("startup")
def on_startup():
    init_db()

# ---------------- Google Sheets helpers ----------------
def get_sheet():
    if not (settings.SHEETS_SPREADSHEET_ID and settings.SHEETS_WORKSHEET_NAME and settings.GOOGLE_SERVICE_ACCOUNT_JSON):
        return None
    info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(settings.SHEETS_SPREADSHEET_ID)
    return sh.worksheet(settings.SHEETS_WORKSHEET_NAME)

def append_order_row(session_dict: dict, event_id: str):
    ws = get_sheet()
    if not ws:
        print("ℹ️ Google Sheets non configurato, salto append.")
        return

    sid = session_dict.get("id") or ""
    try:
        ws.find(sid)
        print("ℹ️ Session già presente su Sheets:", sid)
        return
    except gspread.exceptions.CellNotFound:
        pass

    pi = session_dict.get("payment_intent")
    amount_total = session_dict.get("amount_total")
    currency = session_dict.get("currency")
    payment_status = session_dict.get("payment_status")
    status = session_dict.get("status")
    mode = session_dict.get("mode")
    customer = (session_dict.get("customer_details") or {})
    email = customer.get("email")
    name = customer.get("name")
    success_url = session_dict.get("success_url")
    cancel_url = session_dict.get("cancel_url")
    livemode = bool(session_dict.get("livemode", False))

    metadata_json = json.dumps(session_dict.get("metadata") or {}, ensure_ascii=False)

    created_iso = ""
    if session_dict.get("created"):
        from datetime import datetime, timezone
        created_iso = datetime.fromtimestamp(session_dict["created"], tz=timezone.utc).isoformat()

    row = [
        created_iso, event_id, sid, pi, mode, payment_status, status,
        amount_total or "", currency or "", email or "", name or "",
        "", "", str(livemode).lower(), metadata_json, success_url or "", cancel_url or "",
    ]
    ws.append_row(row, value_input_option="RAW")
    print("✅ Inserita riga su Sheets per session:", sid)

# ---------------- Routes base ----------------
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

# ---------------- Checkout ----------------
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

# ---------------- Webhook ----------------
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
        session_obj = event["data"]["object"]   # StripeObject
        # ⬇️ IMPORTANTISSIMO: convertiamo in dict serializzabile
        if hasattr(session_obj, "to_dict_recursive"):
            session_dict = session_obj.to_dict_recursive()
        elif isinstance(session_obj, dict):
            session_dict = session_obj
        else:
            # fallback molto conservativo
            session_dict = json.loads(json.dumps(session_obj, default=str))

        # --- salva su DB con context manager (chiude sempre la connessione) ---
        from sqlalchemy import select
        with SessionLocal() as db:
            existing = db.execute(
                select(Order).where(Order.session_id == session_dict.get("id"))
            ).scalar_one_or_none()

            if existing is None:
                order = Order(
                    session_id=session_dict.get("id"),
                    payment_intent=session_dict.get("payment_intent"),
                    amount_total=session_dict.get("amount_total"),
                    currency=session_dict.get("currency") or ("eur" if session_dict.get("amount_subtotal") else None),
                    email=((session_dict.get("customer_details") or {}).get("email")),
                    status=session_dict.get("status"),
                    raw=session_dict,   # ora è un dict serializzabile
                )
                db.add(order)
            else:
                existing.payment_intent = session_dict.get("payment_intent")
                existing.amount_total = session_dict.get("amount_total")
                existing.currency = session_dict.get("currency") or existing.currency
                existing.email = ((session_dict.get("customer_details") or {}).get("email")) or existing.email
                existing.status = session_dict.get("status") or existing.status
                existing.raw = session_dict

            db.commit()

        # --- append su Google Sheets (non blocca il webhook se fallisce) ---
        try:
            append_order_row(session_dict, event_id=event.get("id", ""))
        except Exception as e:
            print("⚠️ Errore append su Google Sheets:", e)

    return {"status": "success", "event": event["type"]}

# ---------------- Pagine risultato ----------------
@app.get("/success", response_class=HTMLResponse)
def success():
    return "<h1>Pagamento completato ✅</h1>"

@app.get("/cancel", response_class=HTMLResponse)
def cancel():
    return "<h1>Pagamento annullato ❌</h1>"

# ---------------- API ispezione ----------------
@app.get("/orders")
def list_orders(limit: int = 20):
    with SessionLocal() as db:
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
