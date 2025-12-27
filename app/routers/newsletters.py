"""
Newsletter routes: view and generate newsletters.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models import User, Topic, Newsletter, TopicPaper
from app.schemas import NewsletterResponse
from app.auth import get_current_user

router = APIRouter(prefix="/topics/{topic_id}/newsletters", tags=["Newsletters"])


@router.get("", response_model=List[NewsletterResponse])
def list_newsletters(
    topic_id: UUID,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List past newsletters for a topic."""
    
    # Verify topic ownership
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    newsletters = db.query(Newsletter).filter(
        Newsletter.topic_id == topic_id
    ).order_by(Newsletter.created_at.desc()).limit(limit).all()
    
    return newsletters


@router.get("/{newsletter_id}", response_model=NewsletterResponse)
def get_newsletter(
    topic_id: UUID,
    newsletter_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific newsletter."""
    
    # Verify topic ownership
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    newsletter = db.query(Newsletter).filter(
        Newsletter.id == newsletter_id,
        Newsletter.topic_id == topic_id
    ).first()
    
    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    
    return newsletter


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_newsletter(
    topic_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Trigger newsletter generation for a topic.
    This runs asynchronously in the background.
    """
    # Verify topic ownership
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Check if there are approved papers to include
    approved_count = db.query(TopicPaper).filter(
        TopicPaper.topic_id == topic_id,
        TopicPaper.include == True,
        TopicPaper.reviewed_at != None
    ).count()
    
    if approved_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No approved papers to include in newsletter. Review papers first."
        )
    
    # Queue the generation task
    # In production, this would call Celery:
    # from app.tasks import generate_newsletter_task
    # generate_newsletter_task.delay(str(topic_id))
    
    # For now, we'll use FastAPI background tasks
    background_tasks.add_task(
        _generate_newsletter_background,
        str(topic_id),
        db
    )
    
    return {"message": "Newsletter generation started", "topic_id": str(topic_id)}


async def _generate_newsletter_background(topic_id: str, db: Session):
    """
    Background task to generate newsletter.
    In production, this would be a Celery task.
    """
    # This is a placeholder - the actual implementation would:
    # 1. Get approved papers for the topic
    # 2. Render HTML using Jinja2
    # 3. Upload to S3
    # 4. Create Newsletter record
    # 5. Send email
    pass
