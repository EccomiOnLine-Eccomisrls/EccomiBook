# app/main.py — SOLO GOOGLE SHEETS (no DB)

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Any, Dict, List
import json
import time

from app.settings import settings

# ---------- Stripe (opzionale: usato da /checkout/session e /webhook/stripe) ----------
import stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

# ---------- Google Sheets ----------
import gspread
from google.oauth2.service_account import Credentials

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # restringi se vuoi
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Intestazioni Google Sheet ----------
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

# ---------- Helpers Google Sheets ----------
def _authorize_client():
    if not settings.GOOGLE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON mancante")
    try:
        info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
    except Exception as e:
        raise RuntimeError(f"JSON credenziali non valido: {repr(e)}")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        raise RuntimeError(f"Auth fallita: {repr(e)}")


def get_sheet():
    """Apre lo spreadsheet e il worksheet configurati; assicura gli header."""
    try:
        if not settings.SHEETS_SPREADSHEET_ID:
            raise RuntimeError("SHEETS_SPREADSHEET_ID mancante")
        if not settings.SHEETS_WORKSHEET_NAME:
            raise RuntimeError("SHEETS_WORKSHEET_NAME mancante")

        client = _authorize_client()

        # Spreadsheet
        try:
            sh = client.open_by_key(settings.SHEETS_SPREADSHEET_ID)
        except Exception as e:
            raise RuntimeError(f"Apertura spreadsheet fallita (ID?): {repr(e)}")

        # Worksheet
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

        # Header
        try:
            first_row = ws.row_values(1)
            if [h.strip().lower() for h in first_row] != HEADERS:
                ws.resize(rows=1)  # reset
                ws.update("A1:Q1", [HEADERS])
        except Exception as e:
            raise RuntimeError(f"Update header fallito: {repr(e)}")

        return ws

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sheets error: {e}")


def append_order_row(session: dict, event_id: str):
    """Aggiunge una riga su Sheets; evita duplicati per session_id."""
    ws = get_sheet()

    session_id = session.get("id") or session.get("session_id")
    if not session_id:
        print("⚠️ Nessun session_id, salto append.")
        return

    # evita duplicati
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

    created_iso = ""
    if session.get("created"):
        from datetime import datetime, timezone
        created_iso = datetime.fromtimestamp(int(session["created"]), tz=timezone.utc).isoformat()

    # (non estraiamo items/price_ids in dettaglio per ora)
    items_str = ""
    price_ids = ""

    row = [
        created_iso,            # A
        event_id,               # B
        session_id,             # C
        pi,                     # D
        mode,                   # E
        payment_status,         # F
        status,                 # G
        amount_total or "",     # H
        currency or "",         # I
        email or "",            # J
        name or "",             # K
        items_str,              # L
        price_ids,              # M
        str(livemode).lower(),  # N
        metadata_json,          # O
        success_url or "",      # P
        cancel_url or "",       # Q
    ]
    ws.append_row(row, value_input_option="RAW")
    print("✅ Inserita riga su Sheets per session:", session_id)


def sheet_rows_to_objects(values: List[List[str]]) -> List[Dict[str, Any]]:
    """Converte righe (A:Q) in oggetti con chiavi HEADERS."""
    out: List[Dict[str, Any]] = []
    for r in values:
        row = (r + [""] * 17)[:17]
        obj = {HEADERS[i]: row[i] for i in range(17)}
        out.append(obj)
    return out


# ---------- Modelli richieste ----------
class DevSimulatedCheckout(BaseModel):
    amount_total: int = 990
    currency: str = "eur"
    customer_details: Dict[str, Any] | None = None


# ---------- Lifecycle ----------
@app.on_event("startup")
def on_startup():
    print(f"✅ APP STARTED | ENV: {settings.APP_ENV}")


# ---------- Routes ----------
@app.get("/")
def root():
    return {"message": "EccomiBook Backend (solo Google Sheets) ✨"}


@app.get("/health")
def health():
    status = "ok"
    try:
        _ = get_sheet()
        sheets = "ok"
    except Exception as e:
        sheets = f"error: {e}"
        status = "degraded"
    return {"status": status, "service": settings.APP_NAME, "env": settings.APP_ENV, "sheets": sheets}


# --- Crea sessione di checkout Stripe (facoltativo) ---
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
            price_data = payload.get("price_data") or {}
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


# --- Webhook Stripe -> scrive su Google Sheets ---
@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret mancante")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        print("⚠️ Webhook error:", str(e))
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        try:
            append_order_row(session, event_id=event.get("id", ""))
        except Exception as e:
            # non rompiamo il webhook
            print("⚠️ Errore append su Google Sheets:", e)
    return {"status": "success", "event": event["type"]}


# --- Endpoint di simulazione (senza Stripe) — utile per test veloci ---
@app.post("/dev/simulate-checkout")
async def dev_simulate_checkout(
    body: DevSimulatedCheckout,
    token: str = Query(..., description="DEV_WEBHOOK_TOKEN"),
):
    if not settings.DEV_WEBHOOK_TOKEN or token != settings.DEV_WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

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
        raise HTTPException(status_code=500, detail=f"Sheets error: {e}")

    return {"status": "ok", "session_id": fake_session["id"]}


# --- Pagine risultato semplici ---
@app.get("/success", response_class=HTMLResponse)
def success():
    return "<h1>Pagamento completato ✅</h1>"

@app.get("/cancel", response_class=HTMLResponse)
def cancel():
    return "<h1>Pagamento annullato ❌</h1>"


# --- API lettura ordini (da Sheets) ---
@app.get("/orders")
def list_orders(limit: int = 20):
    ws = get_sheet()
    values = ws.get_all_values()
    if not values or len(values) <= 1:
        return []
    data_rows = values[1:][-limit:]  # ultime N (salta header)
    objs = sheet_rows_to_objects(data_rows)
    for i, o in enumerate(objs, 1):
        o["id"] = i
    return objs
