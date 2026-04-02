from pydantic import BaseModel
from typing import List

class FilterConfig(BaseModel):
    max_burn_score: int
    exclude_spam_filters: List[str]
    min_domain_age_days: int
    max_bounce_score: int
    exclude_syntax_tags: List[str]
    exclude_invalid_mx: bool

class ExportPreset(BaseModel):
    name: str
    filters: FilterConfig
