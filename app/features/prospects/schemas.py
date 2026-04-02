from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class ICPFilters(BaseModel):
    """
    Search parameters for the prospecting engine.
    Maps directly to the ICP Builder UI checkboxes and inputs.
    """
    company_industries: List[str] = Field(default_factory=list)
    company_size_min: Optional[int] = None
    company_size_max: Optional[int] = None
    company_locations: List[str] = Field(default_factory=list)
    company_tech_stack: List[str] = Field(default_factory=list)

    contact_job_titles: List[str] = Field(default_factory=list)
    contact_seniorities: List[str] = Field(default_factory=list)
    contact_departments: List[str] = Field(default_factory=list)

    target_count: int = Field(default=500, gt=0, le=5000)

class ProspectJobCreate(BaseModel):
    name: str = Field(..., max_length=150)
    filters: ICPFilters

class ProspectJobResponse(BaseModel):
    id: UUID
    status: str
    name: Optional[str] = None
    target_count: int
    found_count: int
    enriched_count: int
    credits_reserved: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ProspectResponse(BaseModel):
    id: UUID
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    industry: Optional[str] = None
    status: str
    prospect_score: Optional[int] = None
    burn_score: Optional[int] = None
    spam_filter: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
