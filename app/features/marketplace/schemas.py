from pydantic import BaseModel, UUID4

class ListingCreate(BaseModel):
    job_id: UUID4
    niche: str

class TradeConfirm(BaseModel):
    trade_id: UUID4
    confirm: bool
