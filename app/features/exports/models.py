from sqlalchemy import Column, String, JSON, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid

class ExportPreset(Base):
    __tablename__ = "export_presets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    filters = Column(JSON, nullable=False)
    is_default = Column(Boolean, default=False)
