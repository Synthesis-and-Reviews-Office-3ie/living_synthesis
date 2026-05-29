"""
Living Reviews API Router

Endpoints for managing Living Systematic Reviews and Evidence Gap Maps.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from uuid import UUID
import re
import unicodedata

from app.database import get_db
from app.models import (
    User, Topic, Paper, LivingReview, ReviewUpdate, ReviewTeamMember, 
    PaperScreening, TopicPaper, LivingReviewStatus, ReviewTeamRole, ScreeningDecision
)
from app.schemas import (
    LivingReviewCreate, LivingReviewUpdate, LivingReviewResponse, LivingReviewPublic,
    ReviewUpdateCreate, ReviewUpdateResponse,
    TeamMemberInvite, TeamMemberUpdate, TeamMemberResponse,
    ScreeningDecisionSubmit, ScreeningBatchSubmit, PaperScreeningResponse, ScreeningQueueResponse,
    ExportRequest, ExportFormat
)
from app.routers.auth import get_current_user

router = APIRouter(prefix="/reviews", tags=["Living Reviews"])


# ============== Utility Functions ==============

def generate_slug(title: str) -> str:
    """Generate a URL-friendly slug from a title."""
    # Normalize unicode characters
    title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('ascii')
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')
    return slug[:250]  # Limit length


def check_review_access(
    review_id: UUID, 
    user: User, 
    db: Session, 
    require_role: Optional[List[ReviewTeamRole]] = None
) -> LivingReview:
    """Check if user has access to a living review."""
    review = db.query(LivingReview).filter(LivingReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Living review not found")
    
    # Check if user is the direct owner (for standalone reviews)
    if review.owner_id and review.owner_id == user.id:
        return review
    
    # Check if user is topic owner
    if review.topic_id:
        topic = db.query(Topic).filter(Topic.id == review.topic_id).first()
        if topic and topic.user_id == user.id:
            return review
    
    # Check if user is a team member
    membership = db.query(ReviewTeamMember).filter(
        ReviewTeamMember.living_review_id == review_id,
        ReviewTeamMember.user_id == user.id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if require_role and membership.role not in require_role:
        raise HTTPException(status_code=403, detail=f"Insufficient permissions. Required: {require_role}")
    
    return review


# ============== Living Review CRUD ==============

@router.get("", response_model=List[LivingReviewResponse])
def list_living_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all living reviews the user has access to."""
    # Get reviews where user is the direct owner
    owned_by_user = db.query(LivingReview).filter(
        LivingReview.owner_id == current_user.id
    ).all()
    
    # Get reviews where user owns the topic
    owned_topic_ids = db.query(Topic.id).filter(Topic.user_id == current_user.id).scalar_subquery()
    owned_via_topic = db.query(LivingReview).filter(
        LivingReview.topic_id.in_(db.query(Topic.id).filter(Topic.user_id == current_user.id))
    ).all()
    
    # Get reviews where user is a team member
    member_review_ids = db.query(ReviewTeamMember.living_review_id).filter(
        ReviewTeamMember.user_id == current_user.id
    ).scalar_subquery()
    member_reviews = db.query(LivingReview).filter(
        LivingReview.id.in_(db.query(ReviewTeamMember.living_review_id).filter(ReviewTeamMember.user_id == current_user.id))
    ).all()
    
    # Combine and deduplicate
    all_reviews = {r.id: r for r in owned_by_user + owned_via_topic + member_reviews}
    return list(all_reviews.values())


@router.post("", response_model=LivingReviewResponse, status_code=status.HTTP_201_CREATED)
def create_living_review(
    review: LivingReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new living review, optionally linked to a topic."""
    # Check tier limits (Team tier only for living reviews)
    if current_user.tier.value not in ("pro", "team"):
        raise HTTPException(
            status_code=403, 
            detail="Living Reviews require Pro or Team tier"
        )
    
    # If topic_id provided, verify it exists and user owns it
    topic = None
    if review.topic_id:
        topic = db.query(Topic).filter(
            Topic.id == review.topic_id,
            Topic.user_id == current_user.id
        ).first()
        
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found or access denied")
    
    # Generate unique slug
    base_slug = generate_slug(review.title)
    slug = base_slug
    counter = 1
    while db.query(LivingReview).filter(LivingReview.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    # Create the living review
    db_review = LivingReview(
        topic_id=review.topic_id,
        owner_id=current_user.id,  # Set owner for standalone reviews
        title=review.title,
        slug=slug,
        description=review.description,
        review_type=review.review_type.value,
        protocol_url=review.protocol_url,
        publication_doi=review.publication_doi,
        prospero_id=review.prospero_id,
        osf_id=getattr(review, 'osf_id', None),
        is_public=review.is_public,
        # PICO criteria
        pico_population=getattr(review, 'population', None),
        pico_intervention=getattr(review, 'intervention', None),
        pico_comparator=getattr(review, 'comparator', None),
        pico_outcome=getattr(review, 'outcomes', None),
    )
    
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    
    # Add owner as team member
    owner_member = ReviewTeamMember(
        living_review_id=db_review.id,
        user_id=current_user.id,
        role=ReviewTeamRole.OWNER
    )
    db.add(owner_member)
    db.commit()
    
    # Auto-sync papers from topic if linked
    if review.topic_id:
        topic_papers = db.query(TopicPaper).filter(TopicPaper.topic_id == review.topic_id).all()
        for tp in topic_papers:
            screening = PaperScreening(
                living_review_id=db_review.id,
                paper_id=tp.paper_id,
            )
            db.add(screening)
        db.commit()
        
        # Update stats
        db_review.total_screened = len(topic_papers)
        db.commit()
        db.refresh(db_review)
    
    return db_review


@router.get("/{review_id}", response_model=LivingReviewResponse)
def get_living_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific living review."""
    review = check_review_access(review_id, current_user, db)
    return review


@router.put("/{review_id}", response_model=LivingReviewResponse)
def update_living_review(
    review_id: UUID,
    update: LivingReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a living review's metadata."""
    review = check_review_access(review_id, current_user, db, 
                                  require_role=[ReviewTeamRole.OWNER, ReviewTeamRole.ADMIN])
    
    update_data = update.model_dump(exclude_unset=True)
    
    # Handle nested objects
    if 'inclusion_criteria' in update_data and update_data['inclusion_criteria']:
        update_data['inclusion_criteria'] = [c.model_dump() if hasattr(c, 'model_dump') else c 
                                              for c in update_data['inclusion_criteria']]
    if 'exclusion_criteria' in update_data and update_data['exclusion_criteria']:
        update_data['exclusion_criteria'] = [c.model_dump() if hasattr(c, 'model_dump') else c 
                                              for c in update_data['exclusion_criteria']]
    
    for key, value in update_data.items():
        if hasattr(review, key):
            setattr(review, key, value)
    
    db.commit()
    db.refresh(review)
    return review


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_living_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a living review (owner only)."""
    review = check_review_access(review_id, current_user, db, 
                                  require_role=[ReviewTeamRole.OWNER])
    db.delete(review)
    db.commit()


# ============== PICO & Criteria ==============

@router.put("/{review_id}/pico", response_model=LivingReviewResponse)
def update_pico(
    review_id: UUID,
    pico: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update PICO criteria for AI-assisted screening."""
    review = check_review_access(review_id, current_user, db,
                                  require_role=[ReviewTeamRole.OWNER, ReviewTeamRole.ADMIN])
    
    if 'population' in pico:
        review.pico_population = pico['population']
    if 'intervention' in pico:
        review.pico_intervention = pico['intervention']
    if 'comparator' in pico:
        review.pico_comparator = pico['comparator']
    if 'outcome' in pico:
        review.pico_outcome = pico['outcome']
    if 'study_design' in pico:
        review.pico_study_design = pico['study_design']
    
    db.commit()
    db.refresh(review)
    return review


# ============== Update Versions ==============

@router.get("/{review_id}/updates", response_model=List[ReviewUpdateResponse])
def list_updates(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all update versions for a living review."""
    review = check_review_access(review_id, current_user, db)
    return db.query(ReviewUpdate).filter(
        ReviewUpdate.living_review_id == review_id
    ).order_by(ReviewUpdate.version.desc()).all()


@router.post("/{review_id}/updates", response_model=ReviewUpdateResponse, status_code=status.HTTP_201_CREATED)
def create_update(
    review_id: UUID,
    update_data: ReviewUpdateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new update version (publish changes)."""
    review = check_review_access(review_id, current_user, db,
                                  require_role=[ReviewTeamRole.OWNER, ReviewTeamRole.ADMIN])
    
    # Calculate next version number
    next_version = review.current_version + 1
    
    # Count papers screened in this update cycle
    screenings = db.query(PaperScreening).filter(
        PaperScreening.living_review_id == review_id,
        PaperScreening.added_in_version == next_version
    ).all()
    
    papers_included = sum(1 for s in screenings if s.final_decision == ScreeningDecision.INCLUDE)
    papers_excluded = sum(1 for s in screenings if s.final_decision == ScreeningDecision.EXCLUDE)
    
    # Create update record
    db_update = ReviewUpdate(
        living_review_id=review_id,
        version=next_version,
        papers_screened=len(screenings),
        papers_included=papers_included,
        papers_excluded=papers_excluded,
        change_summary=update_data.change_summary,
        notes=update_data.notes
    )
    
    db.add(db_update)
    
    # Update review stats
    review.current_version = next_version
    review.total_screened += len(screenings)
    review.total_included += papers_included
    review.total_excluded += papers_excluded
    
    db.commit()
    db.refresh(db_update)
    return db_update


# ============== Team Management ==============

@router.get("/{review_id}/team", response_model=List[TeamMemberResponse])
def list_team_members(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List team members for a living review."""
    review = check_review_access(review_id, current_user, db)
    
    members = db.query(ReviewTeamMember).filter(
        ReviewTeamMember.living_review_id == review_id
    ).all()
    
    # Enrich with user info
    result = []
    for member in members:
        user = db.query(User).filter(User.id == member.user_id).first()
        result.append({
            "id": member.id,
            "user_id": member.user_id,
            "user_email": user.email if user else None,
            "user_name": user.name if user else None,
            "role": member.role.value,
            "invited_at": member.invited_at,
            "accepted_at": member.accepted_at
        })
    
    return result


@router.post("/{review_id}/team", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
def invite_team_member(
    review_id: UUID,
    invite: TeamMemberInvite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Invite a user to the review team."""
    review = check_review_access(review_id, current_user, db,
                                  require_role=[ReviewTeamRole.OWNER, ReviewTeamRole.ADMIN])
    
    # Find user by email
    user = db.query(User).filter(User.email == invite.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. They must create an account first.")
    
    # Check if already a member
    existing = db.query(ReviewTeamMember).filter(
        ReviewTeamMember.living_review_id == review_id,
        ReviewTeamMember.user_id == user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="User is already a team member")
    
    # Create membership
    member = ReviewTeamMember(
        living_review_id=review_id,
        user_id=user.id,
        role=ReviewTeamRole(invite.role.value),
        invited_by=current_user.id
    )
    
    db.add(member)
    db.commit()
    db.refresh(member)
    
    return {
        "id": member.id,
        "user_id": member.user_id,
        "user_email": user.email,
        "user_name": user.name,
        "role": member.role.value,
        "invited_at": member.invited_at,
        "accepted_at": member.accepted_at
    }


@router.put("/{review_id}/team/{user_id}", response_model=TeamMemberResponse)
def update_team_member_role(
    review_id: UUID,
    user_id: UUID,
    update: TeamMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a team member's role."""
    review = check_review_access(review_id, current_user, db,
                                  require_role=[ReviewTeamRole.OWNER])
    
    member = db.query(ReviewTeamMember).filter(
        ReviewTeamMember.living_review_id == review_id,
        ReviewTeamMember.user_id == user_id
    ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    # Can't change owner role
    if member.role == ReviewTeamRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot change owner role")
    
    member.role = ReviewTeamRole(update.role.value)
    db.commit()
    db.refresh(member)
    
    user = db.query(User).filter(User.id == user_id).first()
    
    return {
        "id": member.id,
        "user_id": member.user_id,
        "user_email": user.email if user else None,
        "user_name": user.name if user else None,
        "role": member.role.value,
        "invited_at": member.invited_at,
        "accepted_at": member.accepted_at
    }


@router.delete("/{review_id}/team/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_team_member(
    review_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a team member from the review."""
    review = check_review_access(review_id, current_user, db,
                                  require_role=[ReviewTeamRole.OWNER, ReviewTeamRole.ADMIN])
    
    member = db.query(ReviewTeamMember).filter(
        ReviewTeamMember.living_review_id == review_id,
        ReviewTeamMember.user_id == user_id
    ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    # Can't remove owner
    if member.role == ReviewTeamRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot remove owner")
    
    db.delete(member)
    db.commit()


# ============== Screening ==============

@router.post("/{review_id}/sync-papers", status_code=status.HTTP_200_OK)
def sync_papers_from_topic(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sync papers from the linked topic into the screening queue.
    Only adds papers that aren't already in the queue.
    """
    review = check_review_access(review_id, current_user, db, require_role=[ReviewTeamRole.OWNER, ReviewTeamRole.ADMIN])
    
    if not review.topic_id:
        raise HTTPException(status_code=400, detail="No topic linked to this review")
    
    # Get all papers from the topic
    topic_papers = db.query(TopicPaper).filter(TopicPaper.topic_id == review.topic_id).all()
    
    # Get papers already in screening
    existing_paper_ids = set(
        p.paper_id for p in db.query(PaperScreening.paper_id).filter(
            PaperScreening.living_review_id == review_id
        ).all()
    )
    
    # Add new papers to screening queue
    added = 0
    for tp in topic_papers:
        if tp.paper_id not in existing_paper_ids:
            screening = PaperScreening(
                living_review_id=review_id,
                paper_id=tp.paper_id,
            )
            db.add(screening)
            added += 1
    
    db.commit()
    
    # Update review stats
    review.total_screened = db.query(PaperScreening).filter(
        PaperScreening.living_review_id == review_id
    ).count()
    db.commit()
    
    return {"message": f"Added {added} papers to screening queue", "added": added}

@router.get("/{review_id}/screening", response_model=ScreeningQueueResponse)
def get_screening_queue(
    review_id: UUID,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get papers to screen for a living review."""
    review = check_review_access(review_id, current_user, db)
    
    query = db.query(PaperScreening).filter(
        PaperScreening.living_review_id == review_id
    )
    
    if status_filter == "pending":
        query = query.filter(PaperScreening.final_decision == None)
    elif status_filter == "conflicts":
        query = query.filter(
            PaperScreening.reviewer1_decision != None,
            PaperScreening.reviewer2_decision != None,
            PaperScreening.reviewer1_decision != PaperScreening.reviewer2_decision,
            PaperScreening.final_decision == None
        )
    
    total = query.count()
    pending = query.filter(PaperScreening.final_decision == None).count()
    conflicts = db.query(PaperScreening).filter(
        PaperScreening.living_review_id == review_id,
        PaperScreening.reviewer1_decision != None,
        PaperScreening.reviewer2_decision != None,
        PaperScreening.reviewer1_decision != PaperScreening.reviewer2_decision,
        PaperScreening.final_decision == None
    ).count()
    
    screenings = query.offset(offset).limit(limit).all()
    
    # Enrich with paper details
    items = []
    for screening in screenings:
        paper = db.query(Paper).filter(Paper.id == screening.paper_id).first()
        
        # Check if PDF is fetchable (arXiv always, or has OA URL)
        # Only show PDF button for papers we're confident have PDFs
        pdf_available = False
        if paper:
            if paper.source == 'arxiv' and paper.external_id:
                # arXiv always has PDFs
                pdf_available = True
            elif paper.pdf_url:
                # We already have a PDF URL stored
                pdf_available = True
            elif paper.is_oa and paper.oa_url:
                # Known open access with OA URL
                pdf_available = True
            # Note: Not checking DOI/Unpaywall by default as it requires API call
            # and may not always have PDFs
        
        items.append({
            "id": str(screening.id),
            "paper_id": str(screening.paper_id),
            "paper_title": paper.title if paper else None,
            "paper_abstract": paper.abstract if paper else None,
            "paper_doi": paper.doi if paper else None,
            "paper_authors": paper.authors if paper else None,
            "paper_publication_date": paper.publication_date if paper else None,
            "paper_source": paper.source if paper else None,
            "paper_external_id": paper.external_id if paper else None,
            "paper_pdf_url": paper.pdf_url if paper else None,
            "paper_oa_url": paper.oa_url if paper else None,
            "paper_is_oa": paper.is_oa if paper else False,
            "paper_pdf_available": pdf_available,
            "ai_decision": screening.ai_decision.value if screening.ai_decision else None,
            "ai_confidence": screening.ai_confidence,
            "ai_rationale": screening.ai_rationale,
            "reviewer1_decision": screening.reviewer1_decision.value if screening.reviewer1_decision else None,
            "reviewer2_decision": screening.reviewer2_decision.value if screening.reviewer2_decision else None,
            "final_decision": screening.final_decision.value if screening.final_decision else None,
            "exclusion_reason": screening.exclusion_reason,
            "created_at": screening.created_at
        })
    
    return {
        "total": total,
        "pending": pending,
        "conflicts": conflicts,
        "items": items
    }


@router.post("/{review_id}/screening", status_code=status.HTTP_200_OK)
def submit_screening_decisions(
    review_id: UUID,
    batch: ScreeningBatchSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit screening decisions for papers."""
    review = check_review_access(review_id, current_user, db,
                                  require_role=[ReviewTeamRole.OWNER, ReviewTeamRole.ADMIN, ReviewTeamRole.SCREENER])
    
    from datetime import datetime
    from app.models import ScreeningMode
    
    # Get the review's screening mode (default to single if not set)
    screening_mode = review.screening_mode if review.screening_mode else ScreeningMode.SINGLE
    
    updated = 0
    for decision in batch.decisions:
        screening = db.query(PaperScreening).filter(
            PaperScreening.living_review_id == review_id,
            PaperScreening.paper_id == decision.paper_id
        ).first()
        
        if not screening:
            continue
        
        decision_enum = ScreeningDecision(decision.decision.value)
        
        # Single reviewer mode - first reviewer's decision is final
        if screening_mode == ScreeningMode.SINGLE:
            if not screening.reviewer1_id or screening.reviewer1_id == current_user.id:
                screening.reviewer1_id = current_user.id
                screening.reviewer1_decision = decision_enum
                screening.reviewer1_reason = decision.reason
                screening.reviewer1_at = datetime.utcnow()
                screening.final_decision = decision_enum
        
        # Dual reviewer modes
        else:
            if not screening.reviewer1_id:
                # First reviewer
                screening.reviewer1_id = current_user.id
                screening.reviewer1_decision = decision_enum
                screening.reviewer1_reason = decision.reason
                screening.reviewer1_at = datetime.utcnow()
            elif screening.reviewer1_id != current_user.id and not screening.reviewer2_id:
                # Second reviewer (different person)
                screening.reviewer2_id = current_user.id
                screening.reviewer2_decision = decision_enum
                screening.reviewer2_reason = decision.reason
                screening.reviewer2_at = datetime.utcnow()
                
                # Auto-resolve if both agree
                if screening.reviewer1_decision == screening.reviewer2_decision:
                    screening.final_decision = decision_enum
                elif screening_mode == ScreeningMode.DUAL:
                    # In dual mode, disagreement still resolves to reviewer2's decision
                    # (or set to conflict for admin resolution - here we just accept it)
                    screening.final_decision = decision_enum
                # In dual_consensus mode, leave final_decision as None until resolved
            else:
                # User already reviewed, update their decision
                if screening.reviewer1_id == current_user.id:
                    screening.reviewer1_decision = decision_enum
                    screening.reviewer1_reason = decision.reason
                    screening.reviewer1_at = datetime.utcnow()
                    # Re-check consensus if updating
                    if screening.reviewer2_id and screening.reviewer2_decision == decision_enum:
                        screening.final_decision = decision_enum
                elif screening.reviewer2_id == current_user.id:
                    screening.reviewer2_decision = decision_enum
                    screening.reviewer2_reason = decision.reason
                    screening.reviewer2_at = datetime.utcnow()
                    # Re-check consensus if updating
                    if screening.reviewer1_decision == decision_enum:
                        screening.final_decision = decision_enum
        
        if decision.exclusion_reason:
            screening.exclusion_reason = decision.exclusion_reason
        
        updated += 1
    
    db.commit()
    
    return {"updated": updated}


@router.post("/{review_id}/resolve", status_code=status.HTTP_200_OK)
def resolve_conflicts(
    review_id: UUID,
    batch: ScreeningBatchSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resolve screening conflicts (admin/owner only)."""
    review = check_review_access(review_id, current_user, db,
                                  require_role=[ReviewTeamRole.OWNER, ReviewTeamRole.ADMIN])
    
    from datetime import datetime
    
    resolved = 0
    for decision in batch.decisions:
        screening = db.query(PaperScreening).filter(
            PaperScreening.living_review_id == review_id,
            PaperScreening.paper_id == decision.paper_id
        ).first()
        
        if not screening:
            continue
        
        screening.resolver_id = current_user.id
        screening.final_decision = ScreeningDecision(decision.decision.value)
        screening.resolution_notes = decision.reason
        screening.resolved_at = datetime.utcnow()
        
        if decision.exclusion_reason:
            screening.exclusion_reason = decision.exclusion_reason
        
        resolved += 1
    
    db.commit()
    
    return {"resolved": resolved}


# ============== Public Page ==============

@router.get("/public/{slug}", response_model=LivingReviewPublic)
def get_public_review(
    slug: str,
    db: Session = Depends(get_db)
):
    """Get public landing page for a living review (no auth required)."""
    review = db.query(LivingReview).filter(
        LivingReview.slug == slug,
        LivingReview.is_public == True
    ).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found or not public")
    
    return review


@router.get("/public/{slug}/updates", response_model=List[ReviewUpdateResponse])
def get_public_updates(
    slug: str,
    db: Session = Depends(get_db)
):
    """Get update history for a public living review."""
    review = db.query(LivingReview).filter(
        LivingReview.slug == slug,
        LivingReview.is_public == True
    ).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found or not public")
    
    return db.query(ReviewUpdate).filter(
        ReviewUpdate.living_review_id == review.id,
        ReviewUpdate.is_published == True
    ).order_by(ReviewUpdate.version.desc()).all()


# ============== Export ==============

@router.get("/{review_id}/export/{format}")
def export_review(
    review_id: UUID,
    format: ExportFormat,
    included_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export papers from a living review in various formats."""
    review = check_review_access(review_id, current_user, db)
    
    # Get papers
    query = db.query(PaperScreening).filter(
        PaperScreening.living_review_id == review_id
    )
    
    if included_only:
        query = query.filter(PaperScreening.final_decision == ScreeningDecision.INCLUDE)
    
    screenings = query.all()
    
    papers = []
    for screening in screenings:
        paper = db.query(Paper).filter(Paper.id == screening.paper_id).first()
        if paper:
            papers.append(paper)
    
    # Generate export based on format
    if format == ExportFormat.ris:
        content = _generate_ris(papers)
        media_type = "application/x-research-info-systems"
        filename = f"{review.slug}_export.ris"
    elif format == ExportFormat.bibtex:
        content = _generate_bibtex(papers)
        media_type = "application/x-bibtex"
        filename = f"{review.slug}_export.bib"
    elif format == ExportFormat.csv:
        content = _generate_csv(papers)
        media_type = "text/csv"
        filename = f"{review.slug}_export.csv"
    else:  # JSON
        import json
        content = json.dumps([{
            "doi": p.doi,
            "title": p.title,
            "abstract": p.abstract,
            "authors": p.authors,
            "publication_date": str(p.publication_date) if p.publication_date else None,
            "source": p.source
        } for p in papers], indent=2)
        media_type = "application/json"
        filename = f"{review.slug}_export.json"
    
    from fastapi.responses import Response
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def _generate_ris(papers: list) -> str:
    """Generate RIS format export."""
    lines = []
    for paper in papers:
        lines.append("TY  - JOUR")
        if paper.title:
            lines.append(f"TI  - {paper.title}")
        if paper.doi:
            lines.append(f"DO  - {paper.doi}")
        if paper.abstract:
            lines.append(f"AB  - {paper.abstract}")
        if paper.authors:
            for author in paper.authors:
                lines.append(f"AU  - {author}")
        if paper.publication_date:
            lines.append(f"PY  - {paper.publication_date.year}")
        if paper.oa_url:
            lines.append(f"UR  - {paper.oa_url}")
        lines.append("ER  - ")
        lines.append("")
    return "\n".join(lines)


def _generate_bibtex(papers: list) -> str:
    """Generate BibTeX format export."""
    entries = []
    for i, paper in enumerate(papers):
        key = paper.doi.replace("/", "_").replace(".", "_") if paper.doi else f"paper_{i}"
        entry = f"@article{{{key},\n"
        if paper.title:
            entry += f"  title = {{{paper.title}}},\n"
        if paper.authors:
            entry += f"  author = {{{' and '.join(paper.authors)}}},\n"
        if paper.publication_date:
            entry += f"  year = {{{paper.publication_date.year}}},\n"
        if paper.doi:
            entry += f"  doi = {{{paper.doi}}},\n"
        if paper.abstract:
            abstract = paper.abstract[:500] + "..." if len(paper.abstract) > 500 else paper.abstract
            entry += f"  abstract = {{{abstract}}},\n"
        entry += "}"
        entries.append(entry)
    return "\n\n".join(entries)


def _generate_csv(papers: list) -> str:
    """Generate CSV format export."""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["DOI", "Title", "Authors", "Year", "Abstract", "URL", "Source"])
    
    for paper in papers:
        writer.writerow([
            paper.doi or "",
            paper.title or "",
            "; ".join(paper.authors) if paper.authors else "",
            paper.publication_date.year if paper.publication_date else "",
            paper.abstract or "",
            paper.oa_url or "",
            paper.source or ""
        ])
    
    return output.getvalue()
