from pydantic import BaseModel
from typing import Any, Optional

class PlanOut(BaseModel):
    name: str
    paystack_plan_code: str
    monthly_usd: int
    credits_monthly: int
    features: list[str]

class CreditPurchaseRequest(BaseModel):
    amount_usd: int
    credits: int

class WebhookPayload(BaseModel):
    event: str
    data: dict[str, Any]
