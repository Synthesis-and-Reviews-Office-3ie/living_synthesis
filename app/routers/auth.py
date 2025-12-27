"""
Authentication routes: signup, login, logout, profile, password reset.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
import secrets

from app.database import get_db
from app.models import User
from app.schemas import (
    UserCreate, UserLogin, Token, UserResponse,
    PasswordResetRequest, PasswordResetConfirm
)
from app.auth import (
    hash_password, 
    verify_password, 
    create_access_token, 
    get_current_user
)
from app.config import get_settings
from slowapi import Limiter
from slowapi.util import get_remote_address

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)

# Store password reset tokens (in production, use Redis with TTL)
# Format: {token: {"user_id": uuid, "expires": datetime}}
_reset_tokens = {}


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")  # Prevent spam signups
async def signup(
    request: Request,
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new user account."""
    
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        name=user_data.name
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Send welcome email in background
    background_tasks.add_task(_send_welcome_email, user.email, user.name)
    
    return user


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")  # Prevent brute force
async def login(request: Request, credentials: UserLogin, db: Session = Depends(get_db)):
    """Login and get an access token."""
    
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    # Create token
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user's profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
def update_profile(
    name: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile."""
    if name:
        current_user.name = name
    
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/password-reset/request")
@limiter.limit("3/minute")  # Prevent abuse
async def request_password_reset(
    request: Request,
    reset_request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Request a password reset email."""
    user = db.query(User).filter(User.email == reset_request.email).first()
    
    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If an account exists, a reset email has been sent."}
    
    # Generate reset token
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=1)
    
    _reset_tokens[token] = {
        "user_id": str(user.id),
        "expires": expires
    }
    
    # Send reset email in background
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"
    background_tasks.add_task(_send_password_reset_email, user.email, reset_url)
    
    return {"message": "If an account exists, a reset email has been sent."}


@router.post("/password-reset/confirm")
@limiter.limit("5/minute")
async def confirm_password_reset(
    request: Request,
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """Reset password using the token from email."""
    token_data = _reset_tokens.get(reset_data.token)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    if datetime.utcnow() > token_data["expires"]:
        del _reset_tokens[reset_data.token]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired"
        )
    
    user = db.query(User).filter(User.id == token_data["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update password
    user.hashed_password = hash_password(reset_data.new_password)
    db.commit()
    
    # Invalidate token
    del _reset_tokens[reset_data.token]
    
    return {"message": "Password reset successfully"}


async def _send_welcome_email(email: str, name: str = None):
    """Background task to send welcome email."""
    try:
        from app.services.email import send_welcome_email
        await send_welcome_email(email, name)
    except Exception as e:
        # Log but don't fail - email is not critical
        import logging
        logging.exception(f"Failed to send welcome email: {e}")


async def _send_password_reset_email(email: str, reset_url: str):
    """Background task to send password reset email."""
    try:
        from app.services.email import send_password_reset
        await send_password_reset(email, reset_url)
    except Exception as e:
        import logging
        logging.exception(f"Failed to send password reset email: {e}")
