from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class Listing(Base):
    __tablename__ = "marketplace_listings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    niche = Column(String, nullable=False)
    list_size = Column(Integer, nullable=False)
    avg_burn_score = Column(Integer, nullable=False)
    email_hashes = Column(JSON, nullable=False)
    status = Column(String, default="open") # open, matched, completed, expired
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))

class Trade(Base):
    __tablename__ = "marketplace_trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_a_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"))
    listing_b_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"))
    status = Column(String, default="pending") # pending, confirmed, processing, complete, cancelled
    matched_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

class MarketplaceFee(Base):
    __tablename__ = "marketplace_fees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_trades.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    credits_charged = Column(Integer, nullable=False)
    charged_at = Column(DateTime(timezone=True), server_default=func.now())
