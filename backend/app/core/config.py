from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from pathlib import Path

class Settings(BaseSettings):
    APP_NAME: str = "B2B CRM API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "https://b2-b-crm.vercel.app", "http://127.0.0.1:5500", "http://localhost:5500", "http://127.0.0.1:8000", "http://localhost:8000"]
    
    DATABASE_URL: str
    
    # JWT Auth Configuration
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    AUTH_PROVIDER: str = "legacy"
    SUPABASE_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "crm-attachments"
    FRONTEND_URL: str = "http://localhost:5173"
    SESSION_COOKIE_NAME: str = "crm_session"
    SESSION_HOURS: int = 8
    REMEMBER_DAYS: int = 30
    COOKIE_SECURE: bool = False
    ALLOW_SELF_REGISTRATION: bool = True
    LOGIN_RATE_LIMIT: int = 10
    RATE_WINDOW_SECONDS: int = 900
    DUE_NOTIFICATIONS_ENABLED: bool = False
    TENANT_ISOLATION_ENABLED: bool = False
    BUSINESS_REGISTRATION_ENABLED: bool = False
    AUTH_EMAIL_CONFIGURATION_VERIFIED: bool = False

    @model_validator(mode="after")
    def production_safety(self):
        if self.AUTH_PROVIDER not in {"legacy", "supabase"}:
            raise ValueError("AUTH_PROVIDER must be legacy or supabase")
        if self.ENVIRONMENT == "production":
            if self.AUTH_PROVIDER != "supabase" or not self.SUPABASE_URL or not self.SUPABASE_PUBLISHABLE_KEY:
                raise ValueError("Production requires configured Supabase Auth")
            if self.DEBUG or not self.COOKIE_SECURE or not self.FRONTEND_URL.startswith("https://"):
                raise ValueError("Production requires DEBUG=false, secure cookies and HTTPS FRONTEND_URL")
            if not self.DATABASE_URL.startswith("postgresql"):
                raise ValueError("Production requires persistent PostgreSQL")
            if len(self.JWT_SECRET_KEY)<32 or not self.SUPABASE_URL.startswith("https://"):
                raise ValueError("Production requires a strong session encryption key and HTTPS identity provider")
            if any(not origin.startswith('https://') or '*' in origin for origin in self.CORS_ORIGINS):
                raise ValueError('Production CORS origins must be explicit HTTPS origins')
            self.ALLOW_SELF_REGISTRATION = False
        return self
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2]/".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        hide_input_in_errors=True
    )

settings = Settings()
