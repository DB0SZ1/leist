import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "List Intel"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENV: str = "development"
    DATABASE_URL: str = "sqlite+aiosqlite:///./listintel.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    SECRET_KEY: str = "supersecret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    CORS_ORIGINS: List[str] = ["*"]
    
    PAYSTACK_SECRET_KEY: str = "sk_test_..."
    PAYSTACK_CALLBACK_URL: str = "http://localhost:8000/billing/callback"
    
    RESEND_API_KEY: str = "re_..."
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.ENV == "development":
            # Force SQLite in development unless explicitly overridden with another SQLite URL
            if not self.DATABASE_URL.startswith("sqlite"):
                self.DATABASE_URL = "sqlite+aiosqlite:///./listintel.db"

settings = Settings()
