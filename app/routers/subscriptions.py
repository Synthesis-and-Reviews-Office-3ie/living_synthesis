"""
Email subscription routes: subscribe/unsubscribe to topic newsletters.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models import Topic, EmailSubscriber
from app.schemas import EmailSubscribe, EmailUnsubscribe
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

# Get limiter from app state
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")  # Prevent spam signups
async def subscribe_to_topic(
    request: Request,
    subscription: EmailSubscribe,
    db: Session = Depends(get_db)
):
    """
    Subscribe an email to a topic's newsletter.
    Sends a confirmation email that must be clicked.
    """
    # Check if topic exists and is active
    topic = db.query(Topic).filter(
        Topic.id == subscription.topic_id,
        Topic.is_active == True
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found or inactive")
    
    # Check if already subscribed
    existing = db.query(EmailSubscriber).filter(
        EmailSubscriber.topic_id == subscription.topic_id,
        EmailSubscriber.email == subscription.email
    ).first()
    
    if existing:
        if existing.confirmed:
            return {"message": "Already subscribed"}
        else:
            # Resend confirmation email
            await _send_confirmation_email(existing)
            return {"message": "Confirmation email resent"}
    
    # Create subscriber
    subscriber = EmailSubscriber(
        topic_id=subscription.topic_id,
        email=subscription.email,
        confirmed=False
    )
    db.add(subscriber)
    db.commit()
    db.refresh(subscriber)
    
    # Send confirmation email
    await _send_confirmation_email(subscriber)
    
    return {"message": "Confirmation email sent. Please check your inbox."}


@router.get("/confirm/{token}")
async def confirm_subscription(
    token: str,
    db: Session = Depends(get_db)
):
    """Confirm email subscription via token from confirmation email."""
    subscriber = db.query(EmailSubscriber).filter(
        EmailSubscriber.unsubscribe_token == token
    ).first()
    
    if not subscriber:
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    
    subscriber.confirmed = True
    db.commit()
    
    return {"message": "Subscription confirmed! You'll receive newsletters for this topic."}


@router.delete("/unsubscribe/{token}")
async def unsubscribe(
    token: str,
    db: Session = Depends(get_db)
):
    """Unsubscribe from a topic using the token from the email footer."""
    subscriber = db.query(EmailSubscriber).filter(
        EmailSubscriber.unsubscribe_token == token
    ).first()
    
    if not subscriber:
        raise HTTPException(status_code=404, detail="Invalid token")
    
    subscriber.is_active = False
    db.commit()
    
    return {"message": "Successfully unsubscribed"}


@router.post("/resubscribe/{token}")
async def resubscribe(
    token: str,
    db: Session = Depends(get_db)
):
    """Re-subscribe a previously unsubscribed email."""
    subscriber = db.query(EmailSubscriber).filter(
        EmailSubscriber.unsubscribe_token == token
    ).first()
    
    if not subscriber:
        raise HTTPException(status_code=404, detail="Invalid token")
    
    subscriber.is_active = True
    db.commit()
    
    return {"message": "Successfully resubscribed"}


async def _send_confirmation_email(subscriber: EmailSubscriber):
    """Send confirmation email to new subscriber."""
    from app.services.email import send_email
    
    confirm_url = f"{settings.frontend_url}/confirm/{subscriber.unsubscribe_token}"
    
    await send_email(
        to=subscriber.email,
        subject="Confirm your newsletter subscription",
        html=f"""
        <h2>Confirm your subscription</h2>
        <p>Click the link below to confirm your subscription:</p>
        <p><a href="{confirm_url}">Confirm Subscription</a></p>
        <p>If you didn't request this, you can safely ignore this email.</p>
        """
    )
