from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.settings import settings
import stripe

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in produzione limita al dominio frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configura Stripe se presente
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

@app.get("/health")
def health():
    return {"status": "ok", "service": settings.APP_NAME, "env": settings.APP_ENV}

@app.get("/")
def root():
    return {"message": "EccomiBook Backend up ✨"}

@app.post("/checkout/session")
async def create_checkout_session(request: Request):
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe non configurato")

    payload = await request.json()
    quantity = int(payload.get("quantity", 1))
    mode = payload.get("mode", "payment")
    price_id = payload.get("price_id")

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

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        print("Pagamento completato:", session)

    return {"status": "success"}

@app.get("/success", response_class=HTMLResponse)
def success():
    return "<h1>Pagamento completato ✅</h1>"

@app.get("/cancel", response_class=HTMLResponse)
def cancel():
    return "<h1>Pagamento annullato ❌</h1>"
