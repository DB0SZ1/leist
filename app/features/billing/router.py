from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import ok, fail
from app.features.auth.models import User
from app.features.billing.schemas import CreditPurchaseRequest
from app.features.billing import service, webhook
from app.features.billing.paystack.client import verify_webhook
import json

router = APIRouter()
page_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.post("/buy-credits")
async def buy_credits(
    req: CreditPurchaseRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    try:
        data = await service.initialize_credit_purchase(db, user, req.amount_usd, req.credits)
        return ok(data)
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)).model_dump())

@router.post("/webhook")
async def paystack_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")
    if not signature or not verify_webhook(body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    event = payload.get("event")
    data = payload.get("data", {})
    
    if event == "charge.success":
        await webhook.handle_charge_success(db, data)
    elif event == "subscription.create":
        await webhook.handle_subscription_create(db, data)
    elif event == "subscription.disable":
        await webhook.handle_subscription_disable(db, data)
        
    return {"status": "success"}

@page_router.get("/billing", response_class=HTMLResponse)
async def billing_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    history = await service.get_billing_history(db, user.id)
    from app.features.billing.paystack.plans import PLANS, CREDIT_PACKS
    
    total_spent = sum([h.amount for h in history if h.amount]) / 100 if history else 0
    
    return templates.TemplateResponse("billing/billing.html", {
        "request": request,
        "user": user,
        "history": history,
        "plans": PLANS,
        "credit_packs": CREDIT_PACKS,
        "total_spent": total_spent
    })
