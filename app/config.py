"""
Application configuration using Pydantic Settings.
Loads from environment variables or .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # App
    app_name: str = "Evidence Synthesis Newsletter"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/evidence_synthesis"
    
    # Redis (for Celery and caching)
    redis_url: str = "redis://localhost:6379/0"
    
    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week
    
    # LLM Providers - Users can choose their preferred model
    # OpenRouter (unified access to multiple models)
    openrouter_api_key: Optional[str] = None
    
    # OpenAI Direct
    openai_api_key: Optional[str] = None
    
    # Anthropic
    anthropic_api_key: Optional[str] = None
    
    # Google Gemini
    google_ai_api_key: Optional[str] = None
    
    # Perplexity (Pro feature - research-focused)
    perplexity_api_key: Optional[str] = None
    
    # Default model for new users
    default_llm_model: str = "gpt-4o"
    
    # Legacy support (maps to openrouter)
    openai_base_url: Optional[str] = "https://openrouter.ai/api/v1"
    openai_model: str = "openai/gpt-4o"
    
    unpaywall_email: Optional[str] = None
    google_search_api_key: Optional[str] = None
    google_search_cx: Optional[str] = None
    github_token: Optional[str] = None
    pubmed_api_key: Optional[str] = None
    
    # Stripe
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    stripe_price_pro: Optional[str] = None  # Price ID for Pro tier
    stripe_price_team: Optional[str] = None  # Price ID for Team tier
    
    # Email (Resend)
    resend_api_key: Optional[str] = None
    from_email: str = "newsletter@yourdomain.com"
    
    # S3/R2 Storage
    s3_endpoint: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_bucket: str = "newsletters"
    
    # Frontend URL (for email links)
    frontend_url: str = "http://localhost:3000"
    
    # CORS
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Monitoring
    sentry_dsn: Optional[str] = None


@lru_cache()
def get_settings() -> Settings:
    return Settings()
