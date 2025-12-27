"""
Topic management routes: CRUD for user topics.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models import User, Topic, UserTier
from app.schemas import TopicCreate, TopicUpdate, TopicResponse
from app.auth import get_current_user

router = APIRouter(prefix="/topics", tags=["Topics"])

# Topic limits per tier
TOPIC_LIMITS = {
    UserTier.FREE: 1,
    UserTier.PRO: 3,
    UserTier.TEAM: 10
}


@router.get("", response_model=List[TopicResponse])
def list_topics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all topics for the current user."""
    topics = db.query(Topic).filter(Topic.user_id == current_user.id).all()
    return topics


@router.post("", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
def create_topic(
    topic_data: TopicCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new topic."""
    
    # Check topic limit
    current_count = db.query(Topic).filter(Topic.user_id == current_user.id).count()
    limit = TOPIC_LIMITS.get(current_user.tier, 1)
    
    if current_count >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Topic limit reached ({limit}). Upgrade to add more topics."
        )
    
    # Check frequency limit for free tier
    if current_user.tier == UserTier.FREE and topic_data.frequency == "daily":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Daily frequency is only available for Pro and Team tiers."
        )
    
    topic = Topic(
        user_id=current_user.id,
        name=topic_data.name,
        description=topic_data.description,
        queries=topic_data.queries,
        frequency=topic_data.frequency
    )
    
    db.add(topic)
    db.commit()
    db.refresh(topic)
    
    return topic


@router.get("/{topic_id}", response_model=TopicResponse)
def get_topic(
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific topic."""
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    return topic


@router.put("/{topic_id}", response_model=TopicResponse)
def update_topic(
    topic_id: UUID,
    topic_data: TopicUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a topic."""
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Check frequency limit for free tier
    if (current_user.tier == UserTier.FREE and 
        topic_data.frequency and 
        topic_data.frequency == "daily"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Daily frequency is only available for Pro and Team tiers."
        )
    
    # Update fields
    if topic_data.name is not None:
        topic.name = topic_data.name
    if topic_data.description is not None:
        topic.description = topic_data.description
    if topic_data.queries is not None:
        topic.queries = topic_data.queries
    if topic_data.frequency is not None:
        topic.frequency = topic_data.frequency
    if topic_data.is_active is not None:
        topic.is_active = topic_data.is_active
    
    db.commit()
    db.refresh(topic)
    
    return topic


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a topic."""
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    db.delete(topic)
    db.commit()
    
    return None
