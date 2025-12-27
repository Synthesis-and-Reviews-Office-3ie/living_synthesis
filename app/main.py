"""
Evidence Synthesis Newsletter API

Main FastAPI application entry point.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.config import get_settings
from app.database import init_db
from app.routers import auth, topics, review, newsletters, billing, subscriptions


settings = get_settings()

# Initialize Sentry for error monitoring
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment="production" if not settings.debug else "development",
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.1,  # 10% of requests for performance monitoring
        send_default_pii=False,  # Don't send PII
    )

# Rate limiter using Redis
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    default_limits=["100/minute"],  # Global default
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    init_db()
    yield
    # Shutdown
    pass


# Create app
app = FastAPI(
    title="Evidence Synthesis Newsletter API",
    description="Automated literature monitoring with human-in-the-loop review",
    version="1.0.0",
    lifespan=lifespan
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(topics.router)
app.include_router(review.router)
app.include_router(newsletters.router)
app.include_router(billing.router)
app.include_router(subscriptions.router)


@app.get("/")
def root():
    """API health check."""
    return {"status": "ok", "service": "evidence-synthesis-api"}


@app.get("/health")
def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": "production" if not settings.debug else "development"
    }
