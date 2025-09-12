from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Any, Dict

from fastapi import FastAPI, HTTPException, Request, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

import stripe
import gspread
from google.oauth2.service_account import Credentials

from app.settings import settings
from app.db import SessionLocal, Order, init_db


# ---------- App ----------
app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],              # limita al dominio frontend in produzione
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


# ---------- Startup: crea tabelle ----------
@app.on_event("startup")
def on_startup() -> None:
    init_db()
    print("✅ APP STARTED - DB ready")


# ---------- Helpers ----------
def stripe_obj_to_dict(obj: Any) -> Dict[str, Any]:
    """
    Converte in dict gli oggetti Stripe (evita l'errore sqlite 'type Session not supported').
    """
    try:
        return obj.to_dict_recursive()  # Stripe v10
    except Exception:
        try:
            return json.loads(obj.to_json())
        except Exception:
            # Fallback molto difensivo
            return json.loads(json.dumps(obj, default=str))


# --- Google Sheets ---
def get_sheet():
    if not (
        settings.SHEETS_SPREADSHEET_ID
        and settings.SHEETS_WORKSHEET_NAME
        and settings.GOOGLE_SERVICE_ACCOUNT_JSON
    ):
        return None
    info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(settings.SHEETS_SPREADSHEET_ID)
    return sh.worksheet(settings.SHEETS_WORKSHEET_NAME)


def append_order_row(session: dict, event_id: str) -> None:
    ws = get_sheet()
    if not ws:
        print("ℹ️ Google Sheets non configurato, salto append.")
        return

    sid = session.get("id") or session.get("session_id")
    if not sid:
        print("ℹ️ Session senza id, salto append.")
        return

    # evita duplicati
    try:
        ws.find(str(sid))
        print("ℹ️ Session già presente su Sheets:", sid)
        return
    except gspread.exceptions.CellNotFound:
        pass

    created_iso = ""
    if session.get("created"):
        created_iso = datetime.fromtimestamp(session["created"], tz=timezone.utc).isoformat()

    row = [
        created_iso,                              # 1  created_at
        event_id,                                 # 2  event_id
        sid,                                      # 3  session_id
        session.get("payment_intent") or "",      # 4  payment_intent
        session.get("mode") or "",                # 5  mode
        session.get("payment_status") or "",      # 6  payment_status
        session.get("status") or "",              # 7  status
        session.get("amount_total") or "",        # 8  amount_total_cents
        session.get("currency") or "",            # 9  currency
        (session.get("customer_details") or {}).get("email") or "",  # 10 email
        (session.get("customer_details") or {}).get("name") or "",   # 11 name
        "",                                       # 12 items (placeholder)
        "",                                       # 13 price_ids (placeholder)
        str(bool(session.get("livemode", False))).lower(),           # 14 livemode
        json.dumps(session.get("metadata") or {}, ensure_ascii=False),  # 15 metadata_json
        session.get("success_url") or "",         # 16 success_url
        session.get("cancel_url") or "",          # 17 cancel_url
    ]
    ws.append_row(row, value_input_option="RAW")
    print("✅ Inserita riga su Sheets per session:", sid)


# ---------- Health / Root ----------
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
        session_dict = stripe_obj_to_dict(session_obj)  # <-- FIX principale

        # --- salva su DB ---
        db = SessionLocal()
        try:
            order = db.query(Order).filter(Order.session_id == session_dict["id"]).one_or_none()
            if order is None:
                order = Order(
                    session_id=session_dict["id"],
                    payment_intent=session_dict.get("payment_intent"),
                    amount_total=session_dict.get("amount_total"),
                    currency=session_dict.get("currency")
                             or (session_dict.get("amount_subtotal") and "eur"),
                    email=(session_dict.get("customer_details") or {}).get("email"),
                    status=session_dict.get("status") or session_dict.get("payment_status"),
                    raw=session_dict,   # <-- ora è un dict serializzabile
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

        # --- Sheets ---
        try:
            append_order_row(session_dict, event_id=event.get("id", ""))
        except Exception as e:
            print("⚠️ Errore append su Google Sheets:", e)

    return {"status": "success", "event": event["type"]}


# ---------- Pagine risultato ----------
@app.get("/success", response_class=HTMLResponse)
def success():
    return "<h1>Pagamento completato ✅</h1>"


@app.get("/cancel", response_class=HTMLResponse)
def cancel():
    return "<h1>Pagamento annullato ❌</h1>"


# ---------- Pagina test ----------
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


# ---------- Dev: Simula checkout.session.completed ----------
from pydantic import BaseModel

class DevSimulatedCheckout(BaseModel):
    amount_total: int = 990
    currency: str = "eur"
    customer_details: Optional[dict] = None

@app.post("/dev/simulate-checkout")
def dev_simulate_checkout(
    payload: DevSimulatedCheckout = Body(...),
    token: str = Query("", description="Dev token"),
):
    """
    Solo per test in locale/staging: crea un finto evento checkout.session.completed
    passa ?token=<DEV_WEBHOOK_TOKEN>
    """
    if settings.APP_ENV == "production":
        raise HTTPException(status_code=403, detail="Disabled in production")

    if not token or token != settings.DEV_WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # componi un finto 'session'
    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    fake_session = {
        "id": f"cs_dev_{now_ts}",
        "payment_intent": f"pi_dev_{now_ts}",
        "amount_total": payload.amount_total,
        "currency": payload.currency,
        "status": "complete",
        "payment_status": "paid",
        "mode": "payment",
        "livemode": False,
        "created": now_ts,
        "customer_details": payload.customer_details or {
            "email": "dev@example.com",
            "name": "Dev User",
        },
        "success_url": settings.SUCCESS_URL,
        "cancel_url": settings.CANCEL_URL,
        "metadata": {},
    }

    # salva come se fosse arrivato dal webhook
    db = SessionLocal()
    try:
        order = Order(
            session_id=fake_session["id"],
            payment_intent=fake_session["payment_intent"],
            amount_total=fake_session["amount_total"],
            currency=fake_session["currency"],
            email=(fake_session["customer_details"] or {}).get("email"),
            status=fake_session["status"],
            raw=fake_session,
        )
        db.add(order)
        db.commit()
        print("✅ [DEV] Ordine simulato salvato:", order.session_id)
    except Exception as e:
        db.rollback()
        print("❌ [DEV] Errore salvataggio ordine simulato:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

    try:
        append_order_row(fake_session, event_id=f"evt_dev_{now_ts}")
    except Exception as e:
        print("⚠️ [DEV] Errore append Sheets simulato:", e)

    return {"ok": True, "session_id": fake_session["id"]}
