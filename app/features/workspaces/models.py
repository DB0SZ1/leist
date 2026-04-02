from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    owner_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan = Column(String(50), default="free")
    credits_remaining = Column(Integer, default=500)
    
    brand_company_name = Column(String(255), nullable=True)
    brand_color = Column(String(20), default="#1b6015")
    brand_logo_url = Column(String(1024), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False, default="viewer") # owner, admin, analyst, viewer
    created_at = Column(DateTime(timezone=True), server_default=func.now())
