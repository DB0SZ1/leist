import httpx
import hmac
import hashlib
from app.config import settings
from app.core.exceptions import PaystackException

BASE = "https://api.paystack.co"

class PaystackClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

    async def initialize_transaction(self, email: str, amount_usd: float, metadata: dict) -> dict:
        amount_kobo = int(amount_usd * 100)
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{BASE}/transaction/initialize",
                headers=self.headers,
                json={"email": email, "amount": amount_kobo, "currency": "USD",
                      "metadata": metadata, "callback_url": getattr(settings, "PAYSTACK_CALLBACK_URL", "")})
            if r.status_code != 200:
                raise PaystackException(f"Paystack error: {r.text}")
            return r.json()["data"]

    async def verify_transaction(self, reference: str) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{BASE}/transaction/verify/{reference}", headers=self.headers)
            if r.status_code != 200:
                raise PaystackException(f"Verification failed: {r.text}")
            return r.json()["data"]

    async def create_subscription(self, customer_code: str, plan_code: str) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{BASE}/subscription",
                headers=self.headers,
                json={"customer": customer_code, "plan": plan_code})
            if r.status_code not in (200, 201):
                raise PaystackException(f"Subscription failed: {r.text}")
            return r.json()["data"]

    async def disable_subscription(self, subscription_code: str, token: str) -> bool:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{BASE}/subscription/disable",
                headers=self.headers,
                json={"code": subscription_code, "token": token})
            if r.status_code != 200:
                return False
            return r.json()["status"]

def verify_webhook(payload: bytes, signature: str) -> bool:
    expected = hmac.new(settings.PAYSTACK_WEBHOOK_SECRET.encode(), payload, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
