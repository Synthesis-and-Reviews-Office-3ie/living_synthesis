"""
Review queue routes: Human-in-the-loop paper review.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from typing import List
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.models import User, Topic, TopicPaper, Paper
from app.schemas import TopicPaperResponse, BulkReviewRequest
from app.auth import get_current_user

router = APIRouter(prefix="/topics/{topic_id}/review", tags=["Review"])


@router.get("", response_model=List[TopicPaperResponse])
def get_review_queue(
    topic_id: UUID,
    include_reviewed: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get papers pending review for a topic.
    Set include_reviewed=true to see all papers (including already reviewed).
    """
    # Verify topic ownership
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Query papers with eager loading
    query = db.query(TopicPaper).options(
        joinedload(TopicPaper.paper)
    ).filter(TopicPaper.topic_id == topic_id)
    
    if not include_reviewed:
        query = query.filter(TopicPaper.reviewed_at == None)
    
    # Order by relevance score descending
    papers = query.order_by(TopicPaper.relevance_score.desc()).all()
    
    return papers


@router.put("", status_code=status.HTTP_200_OK)
def submit_review(
    topic_id: UUID,
    review_data: BulkReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit review decisions for multiple papers at once."""
    
    # Verify topic ownership
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Process each decision
    updated_count = 0
    for decision in review_data.decisions:
        topic_paper = db.query(TopicPaper).filter(
            TopicPaper.topic_id == topic_id,
            TopicPaper.id == decision.paper_id
        ).first()
        
        if topic_paper:
            topic_paper.include = decision.include
            topic_paper.reviewed_at = datetime.utcnow()
            if decision.reviewer_notes:
                topic_paper.reviewer_notes = decision.reviewer_notes
            updated_count += 1
    
    db.commit()
    
    return {"message": f"Updated {updated_count} papers"}


@router.post("/approve-all", status_code=status.HTTP_200_OK)
def approve_all_pending(
    topic_id: UUID,
    min_relevance: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Auto-approve all pending papers with relevance >= min_relevance.
    Auto-reject papers below threshold.
    """
    # Verify topic ownership
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Get pending papers
    pending = db.query(TopicPaper).filter(
        TopicPaper.topic_id == topic_id,
        TopicPaper.reviewed_at == None
    ).all()
    
    approved = 0
    rejected = 0
    
    for paper in pending:
        paper.reviewed_at = datetime.utcnow()
        if paper.relevance_score and paper.relevance_score >= min_relevance:
            paper.include = True
            approved += 1
        else:
            paper.include = False
            rejected += 1
    
    db.commit()
    
    return {
        "message": f"Processed {len(pending)} papers",
        "approved": approved,
        "rejected": rejected
    }
