from dataclasses import dataclass

@dataclass
class Plan:
    name: str
    paystack_plan_code: str
    monthly_usd: int
    credits_monthly: int
    features: list[str]

PLANS = {
    "free":    Plan("Free",    "",            0,   500,     ["syntax","mx","spam_filter","infra"]),
    "starter": Plan("Starter", "PLN_starter", 10,  25000,   ["burn_score","fresh_only"]),
    "growth":  Plan("Growth",  "PLN_growth",  49,  100000,  ["marketplace","bounce_history"]),
    "pro":     Plan("Pro",     "PLN_pro",     99,  500000,  ["api_access","10_seats"]),
    "agency":  Plan("Agency",  "PLN_agency",  249, 0,       ["unlimited","white_label"]),
}

CREDIT_PACKS = [
    {"credits": 10_000,    "usd": 9},
    {"credits": 50_000,    "usd": 35},
    {"credits": 250_000,   "usd": 129},
    {"credits": 1_000_000, "usd": 389},
    {"credits": 5_000_000, "usd": 1499},
]
