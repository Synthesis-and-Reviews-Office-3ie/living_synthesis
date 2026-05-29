"""
Assignments & Conflicts API for Living Reviews

Handles:
- Paper assignments to reviewers (with distribution strategies)
- Conflict detection and resolution
- Cohen's Kappa calculation for inter-rater reliability
- Workflow metrics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import Optional, List
from datetime import datetime
from uuid import UUID, uuid4
import random

from app.database import get_db
from app.auth import get_current_user
from app.models import (
    User, LivingReview, Paper, PaperScreening, ReviewTeamMember,
    ReviewerAssignment, ScreeningConflict, WorkflowMetrics,
    ScreeningMode, ScreeningDecision as ScreeningDecisionEnum,
    AssignmentStatus, ConflictType, ConflictResolutionStatus, ReviewTeamRole
)
from app.schemas import (
    AssignmentCreate, AssignmentUpdate, AssignmentResponse, AssignmentStats, AssignmentListResponse,
    ConflictResolve, ConflictResponse, ConflictStats, ConflictListResponse,
    WorkflowMetricsResponse, ScreeningDecisionEnum as SchemaDecisionEnum
)

router = APIRouter(prefix="/reviews/{review_id}", tags=["workflow"])


# ============================================================================
# Helper Functions
# ============================================================================

def check_review_access(db: Session, review_id: UUID, user: User, require_admin: bool = False):
    """Check if user has access to the review."""
    review = db.query(LivingReview).filter(LivingReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Living review not found")
    
    # Check team membership
    member = db.query(ReviewTeamMember).filter(
        ReviewTeamMember.living_review_id == review_id,
        ReviewTeamMember.user_id == user.id
    ).first()
    
    # Owner always has access
    if review.owner_id == user.id:
        return review, None
    
    if not member:
        raise HTTPException(status_code=403, detail="You are not a member of this review")
    
    if require_admin and member.role not in [ReviewTeamRole.OWNER, ReviewTeamRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return review, member


def calculate_cohens_kappa(agreements: int, total: int, categories: int = 2) -> float:
    """
    Calculate Cohen's Kappa coefficient for inter-rater reliability.
    
    Formula: κ = (P_o - P_e) / (1 - P_e)
    where P_o = observed agreement, P_e = expected agreement by chance
    
    Returns kappa score (-1 to 1, where 1 = perfect agreement)
    """
    if total == 0:
        return 0.0
    
    # Observed agreement
    p_o = agreements / total
    
    # Expected agreement (assuming equal distribution)
    p_e = 1 / categories
    
    # Cohen's Kappa
    if p_e == 1:
        return 1.0
    
    kappa = (p_o - p_e) / (1 - p_e)
    return round(kappa, 3)


def interpret_kappa(kappa: float) -> str:
    """Interpret Cohen's Kappa value."""
    if kappa >= 0.81:
        return "Excellent"
    elif kappa >= 0.61:
        return "Good"
    elif kappa >= 0.41:
        return "Moderate"
    elif kappa >= 0.21:
        return "Fair"
    elif kappa > 0:
        return "Slight"
    else:
        return "Poor"


def distribute_balanced(paper_ids: List[UUID], user_ids: List[UUID], reviewers_per_paper: int) -> List[tuple]:
    """Evenly distribute papers across reviewers."""
    assignments = []
    user_count = len(user_ids)
    
    for idx, paper_id in enumerate(paper_ids):
        for reviewer_num in range(reviewers_per_paper):
            user_idx = (idx * reviewers_per_paper + reviewer_num) % user_count
            user_id = user_ids[user_idx]
            assignments.append((paper_id, user_id, reviewer_num + 1))
    
    return assignments


def distribute_random(paper_ids: List[UUID], user_ids: List[UUID], reviewers_per_paper: int) -> List[tuple]:
    """Randomly distribute papers across reviewers."""
    assignments = []
    
    for paper_id in paper_ids:
        selected_users = random.sample(user_ids, min(reviewers_per_paper, len(user_ids)))
        for order, user_id in enumerate(selected_users, start=1):
            assignments.append((paper_id, user_id, order))
    
    return assignments


def detect_conflict(db: Session, screening: PaperScreening, review: LivingReview) -> Optional[ScreeningConflict]:
    """Detect if a conflict exists for this screening."""
    # Only detect conflicts in dual/dual_consensus mode
    if review.screening_mode == ScreeningMode.SINGLE:
        return None
    
    # Need both reviewers to have decided
    if not screening.reviewer1_decision or not screening.reviewer2_decision:
        return None
    
    # Check if decisions differ
    r1 = screening.reviewer1_decision.value if screening.reviewer1_decision else None
    r2 = screening.reviewer2_decision.value if screening.reviewer2_decision else None
    
    if r1 == r2:
        return None  # No conflict
    
    # Check if conflict already exists
    existing = db.query(ScreeningConflict).filter(
        ScreeningConflict.screening_id == screening.id,
        ScreeningConflict.resolution_status == ConflictResolutionStatus.UNRESOLVED
    ).first()
    
    if existing:
        return existing
    
    # Create new conflict
    conflict = ScreeningConflict(
        id=uuid4(),
        living_review_id=review.id,
        paper_id=screening.paper_id,
        screening_id=screening.id,
        conflict_type=ConflictType.HUMAN_DISAGREEMENT,
        decision_1=r1,
        reviewer_1_id=screening.reviewer1_id,
        decision_2=r2,
        reviewer_2_id=screening.reviewer2_id,
        resolution_status=ConflictResolutionStatus.UNRESOLVED,
        created_at=datetime.utcnow()
    )
    
    db.add(conflict)
    db.commit()
    db.refresh(conflict)
    
    return conflict


# ============================================================================
# Assignment Endpoints
# ============================================================================

@router.post("/assignments", response_model=dict)
def create_assignments(
    review_id: UUID,
    request: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create paper assignments for reviewers.
    
    Strategies:
    - balanced: Evenly distribute across reviewers
    - random: Randomly assign reviewers
    - manual: Assign to specific users (requires user_ids)
    - round_robin: Sequential distribution
    """
    review, _ = check_review_access(db, review_id, current_user, require_admin=True)
    
    # Get eligible reviewers if not specified
    if request.strategy.value == "manual":
        if not request.user_ids:
            raise HTTPException(status_code=400, detail="user_ids required for manual strategy")
        user_ids = request.user_ids
    else:
        # Get all team members who can screen
        members = db.query(ReviewTeamMember).filter(
            ReviewTeamMember.living_review_id == review_id,
            ReviewTeamMember.role.in_([ReviewTeamRole.OWNER, ReviewTeamRole.ADMIN, ReviewTeamRole.SCREENER])
        ).all()
        
        if not members:
            raise HTTPException(status_code=400, detail="No eligible reviewers found")
        
        user_ids = [m.user_id for m in members]
    
    # Verify we have enough reviewers
    if request.reviewers_per_paper > len(user_ids):
        raise HTTPException(
            status_code=400, 
            detail=f"Need {request.reviewers_per_paper} reviewers but only {len(user_ids)} available"
        )
    
    # Distribute assignments
    if request.strategy.value in ["balanced", "round_robin"]:
        distribution = distribute_balanced(request.paper_ids, user_ids, request.reviewers_per_paper)
    elif request.strategy.value == "random":
        distribution = distribute_random(request.paper_ids, user_ids, request.reviewers_per_paper)
    else:  # manual
        distribution = [
            (paper_id, user_id, idx + 1)
            for paper_id in request.paper_ids
            for idx, user_id in enumerate(user_ids[:request.reviewers_per_paper])
        ]
    
    # Create assignments
    created_count = 0
    for paper_id, user_id, order in distribution:
        # Skip if already exists
        existing = db.query(ReviewerAssignment).filter(
            ReviewerAssignment.living_review_id == review_id,
            ReviewerAssignment.paper_id == paper_id,
            ReviewerAssignment.user_id == user_id
        ).first()
        
        if existing:
            continue
        
        assignment = ReviewerAssignment(
            id=uuid4(),
            living_review_id=review_id,
            paper_id=paper_id,
            user_id=user_id,
            assigned_by=current_user.id,
            assignment_order=order,
            is_blinded=request.is_blinded,
            status=AssignmentStatus.PENDING,
            due_date=request.due_date
        )
        db.add(assignment)
        created_count += 1
    
    db.commit()
    
    return {"message": f"Created {created_count} assignments for {len(request.paper_ids)} papers"}


@router.get("/assignments", response_model=AssignmentListResponse)
def list_assignments(
    review_id: UUID,
    status: Optional[str] = Query(None),
    user_id: Optional[UUID] = Query(None),
    include_stats: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List assignments for a review with filtering and stats."""
    review, _ = check_review_access(db, review_id, current_user)
    
    query = db.query(ReviewerAssignment).filter(ReviewerAssignment.living_review_id == review_id)
    
    if status:
        query = query.filter(ReviewerAssignment.status == status)
    if user_id:
        query = query.filter(ReviewerAssignment.user_id == user_id)
    
    total = query.count()
    assignments = query.offset(skip).limit(limit).all()
    
    # Enrich with paper/user data
    enriched = []
    for a in assignments:
        paper = db.query(Paper).filter(Paper.id == a.paper_id).first()
        user = db.query(User).filter(User.id == a.user_id).first()
        
        enriched.append(AssignmentResponse(
            id=a.id,
            living_review_id=a.living_review_id,
            paper_id=a.paper_id,
            user_id=a.user_id,
            assignment_order=a.assignment_order,
            is_blinded=a.is_blinded,
            status=a.status.value if a.status else "pending",
            assigned_at=a.assigned_at,
            due_date=a.due_date,
            started_at=a.started_at,
            completed_at=a.completed_at,
            notes=a.notes,
            paper_title=paper.title if paper else None,
            user_name=user.name if user else None,
            user_email=user.email if user else None
        ))
    
    # Calculate stats
    stats = None
    if include_stats:
        all_assignments = db.query(ReviewerAssignment).filter(
            ReviewerAssignment.living_review_id == review_id
        ).all()
        
        now = datetime.utcnow()
        pending = sum(1 for a in all_assignments if a.status == AssignmentStatus.PENDING)
        in_progress = sum(1 for a in all_assignments if a.status == AssignmentStatus.IN_PROGRESS)
        completed = sum(1 for a in all_assignments if a.status == AssignmentStatus.COMPLETED)
        overdue = sum(
            1 for a in all_assignments 
            if a.status in [AssignmentStatus.PENDING, AssignmentStatus.IN_PROGRESS]
            and a.due_date and a.due_date < now
        )
        
        # Calculate avg completion time
        completed_with_times = [
            a for a in all_assignments
            if a.status == AssignmentStatus.COMPLETED and a.started_at and a.completed_at
        ]
        avg_time = None
        if completed_with_times:
            total_hours = sum(
                (a.completed_at - a.started_at).total_seconds() / 3600
                for a in completed_with_times
            )
            avg_time = round(total_hours / len(completed_with_times), 2)
        
        stats = AssignmentStats(
            total_assignments=len(all_assignments),
            pending=pending,
            in_progress=in_progress,
            completed=completed,
            overdue=overdue,
            completion_rate=round((completed / len(all_assignments) * 100) if all_assignments else 0, 1),
            avg_time_to_complete_hours=avg_time
        )
    
    return AssignmentListResponse(assignments=enriched, total=total, stats=stats)


@router.get("/assignments/my", response_model=AssignmentListResponse)
def get_my_assignments(
    review_id: UUID,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current user's assignments for this review."""
    review, _ = check_review_access(db, review_id, current_user)
    
    query = db.query(ReviewerAssignment).filter(
        ReviewerAssignment.living_review_id == review_id,
        ReviewerAssignment.user_id == current_user.id
    )
    
    if status:
        query = query.filter(ReviewerAssignment.status == status)
    
    assignments = query.all()
    
    enriched = []
    for a in assignments:
        paper = db.query(Paper).filter(Paper.id == a.paper_id).first()
        
        enriched.append(AssignmentResponse(
            id=a.id,
            living_review_id=a.living_review_id,
            paper_id=a.paper_id,
            user_id=a.user_id,
            assignment_order=a.assignment_order,
            is_blinded=a.is_blinded,
            status=a.status.value if a.status else "pending",
            assigned_at=a.assigned_at,
            due_date=a.due_date,
            started_at=a.started_at,
            completed_at=a.completed_at,
            notes=a.notes,
            paper_title=paper.title if paper else None,
            user_name=current_user.name,
            user_email=current_user.email
        ))
    
    return AssignmentListResponse(assignments=enriched, total=len(enriched), stats=None)


@router.put("/assignments/{assignment_id}", response_model=AssignmentResponse)
def update_assignment(
    review_id: UUID,
    assignment_id: UUID,
    request: AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an assignment status."""
    review, member = check_review_access(db, review_id, current_user)
    
    assignment = db.query(ReviewerAssignment).filter(
        ReviewerAssignment.id == assignment_id,
        ReviewerAssignment.living_review_id == review_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Users can only update their own assignments (unless admin)
    is_own = assignment.user_id == current_user.id
    is_admin = review.owner_id == current_user.id or (member and member.role in [ReviewTeamRole.OWNER, ReviewTeamRole.ADMIN])
    
    if not (is_own or is_admin):
        raise HTTPException(status_code=403, detail="You can only update your own assignments")
    
    # Update fields
    if request.status:
        new_status = AssignmentStatus(request.status.value)
        if new_status == AssignmentStatus.IN_PROGRESS and assignment.status == AssignmentStatus.PENDING:
            assignment.started_at = datetime.utcnow()
        elif new_status == AssignmentStatus.COMPLETED and assignment.status == AssignmentStatus.IN_PROGRESS:
            assignment.completed_at = datetime.utcnow()
        assignment.status = new_status
    
    if request.started_at:
        assignment.started_at = request.started_at
    if request.completed_at:
        assignment.completed_at = request.completed_at
    if request.notes is not None:
        assignment.notes = request.notes
    
    db.commit()
    db.refresh(assignment)
    
    paper = db.query(Paper).filter(Paper.id == assignment.paper_id).first()
    user = db.query(User).filter(User.id == assignment.user_id).first()
    
    return AssignmentResponse(
        id=assignment.id,
        living_review_id=assignment.living_review_id,
        paper_id=assignment.paper_id,
        user_id=assignment.user_id,
        assignment_order=assignment.assignment_order,
        is_blinded=assignment.is_blinded,
        status=assignment.status.value if assignment.status else "pending",
        assigned_at=assignment.assigned_at,
        due_date=assignment.due_date,
        started_at=assignment.started_at,
        completed_at=assignment.completed_at,
        notes=assignment.notes,
        paper_title=paper.title if paper else None,
        user_name=user.name if user else None,
        user_email=user.email if user else None
    )


# ============================================================================
# Conflict Endpoints
# ============================================================================

@router.get("/conflicts", response_model=ConflictListResponse)
def list_conflicts(
    review_id: UUID,
    status: Optional[str] = Query(None),
    include_stats: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List conflicts for a review with filtering and stats."""
    review, _ = check_review_access(db, review_id, current_user)
    
    query = db.query(ScreeningConflict).filter(ScreeningConflict.living_review_id == review_id)
    
    if status:
        query = query.filter(ScreeningConflict.resolution_status == status)
    
    total = query.count()
    conflicts = query.order_by(ScreeningConflict.created_at.desc()).offset(skip).limit(limit).all()
    
    # Enrich with paper/user data
    enriched = []
    for c in conflicts:
        paper = db.query(Paper).filter(Paper.id == c.paper_id).first()
        r1 = db.query(User).filter(User.id == c.reviewer_1_id).first() if c.reviewer_1_id else None
        r2 = db.query(User).filter(User.id == c.reviewer_2_id).first() if c.reviewer_2_id else None
        resolver = db.query(User).filter(User.id == c.resolved_by).first() if c.resolved_by else None
        
        enriched.append(ConflictResponse(
            id=c.id,
            living_review_id=c.living_review_id,
            paper_id=c.paper_id,
            screening_id=c.screening_id,
            conflict_type=c.conflict_type.value if c.conflict_type else "human_disagreement",
            decision_1=c.decision_1,
            decision_2=c.decision_2,
            resolution_status=c.resolution_status.value if c.resolution_status else "unresolved",
            final_decision=c.final_decision,
            resolution_notes=c.resolution_notes,
            resolved_at=c.resolved_at,
            created_at=c.created_at,
            paper_title=paper.title if paper else None,
            reviewer_1_name=r1.name or r1.email if r1 else None,
            reviewer_2_name=r2.name or r2.email if r2 else None,
            resolved_by_name=resolver.name or resolver.email if resolver else None
        ))
    
    # Calculate stats
    stats = None
    if include_stats:
        all_conflicts = db.query(ScreeningConflict).filter(
            ScreeningConflict.living_review_id == review_id
        ).all()
        
        unresolved = sum(1 for c in all_conflicts if c.resolution_status == ConflictResolutionStatus.UNRESOLVED)
        resolved = sum(1 for c in all_conflicts if c.resolution_status == ConflictResolutionStatus.RESOLVED)
        
        # Conflicts by type
        by_type = {}
        for c in all_conflicts:
            t = c.conflict_type.value if c.conflict_type else "unknown"
            by_type[t] = by_type.get(t, 0) + 1
        
        # Calculate inter-rater metrics
        screenings = db.query(PaperScreening).filter(
            PaperScreening.living_review_id == review_id
        ).all()
        
        # Count agreements where both reviewers made decisions
        agreements = 0
        total_pairs = 0
        for s in screenings:
            if s.reviewer1_decision and s.reviewer2_decision:
                total_pairs += 1
                if s.reviewer1_decision == s.reviewer2_decision:
                    agreements += 1
        
        kappa = calculate_cohens_kappa(agreements, total_pairs) if total_pairs > 0 else None
        agreement_rate = round((agreements / total_pairs * 100) if total_pairs > 0 else 0, 1)
        
        # Average resolution time
        resolved_with_times = [
            c for c in all_conflicts
            if c.resolution_status == ConflictResolutionStatus.RESOLVED and c.resolved_at
        ]
        avg_time = None
        if resolved_with_times:
            total_hours = sum(
                (c.resolved_at - c.created_at).total_seconds() / 3600
                for c in resolved_with_times
            )
            avg_time = round(total_hours / len(resolved_with_times), 2)
        
        stats = ConflictStats(
            total_conflicts=len(all_conflicts),
            unresolved_conflicts=unresolved,
            resolved_conflicts=resolved,
            conflicts_by_type=by_type,
            average_resolution_time_hours=avg_time,
            cohens_kappa=kappa,
            agreement_rate=agreement_rate
        )
    
    return ConflictListResponse(conflicts=enriched, total=total, stats=stats)


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictResponse)
def resolve_conflict(
    review_id: UUID,
    conflict_id: UUID,
    request: ConflictResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resolve a conflict with a final decision."""
    review, _ = check_review_access(db, review_id, current_user, require_admin=True)
    
    conflict = db.query(ScreeningConflict).filter(
        ScreeningConflict.id == conflict_id,
        ScreeningConflict.living_review_id == review_id
    ).first()
    
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    
    if conflict.resolution_status != ConflictResolutionStatus.UNRESOLVED:
        raise HTTPException(status_code=400, detail=f"Conflict already {conflict.resolution_status.value}")
    
    # Validate decision
    if request.final_decision not in [SchemaDecisionEnum.include, SchemaDecisionEnum.exclude]:
        raise HTTPException(status_code=400, detail="Final decision must be 'include' or 'exclude'")
    
    # Update conflict
    conflict.resolution_status = ConflictResolutionStatus.RESOLVED
    conflict.resolved_by = current_user.id
    conflict.resolved_at = datetime.utcnow()
    conflict.final_decision = request.final_decision.value
    conflict.resolution_notes = request.resolution_notes
    
    # Update the screening record
    screening = db.query(PaperScreening).filter(PaperScreening.id == conflict.screening_id).first()
    if screening:
        screening.resolver_id = current_user.id
        screening.final_decision = ScreeningDecisionEnum(request.final_decision.value)
        screening.resolution_notes = request.resolution_notes
        screening.resolved_at = datetime.utcnow()
    
    db.commit()
    db.refresh(conflict)
    
    paper = db.query(Paper).filter(Paper.id == conflict.paper_id).first()
    
    return ConflictResponse(
        id=conflict.id,
        living_review_id=conflict.living_review_id,
        paper_id=conflict.paper_id,
        screening_id=conflict.screening_id,
        conflict_type=conflict.conflict_type.value,
        decision_1=conflict.decision_1,
        decision_2=conflict.decision_2,
        resolution_status=conflict.resolution_status.value,
        final_decision=conflict.final_decision,
        resolution_notes=conflict.resolution_notes,
        resolved_at=conflict.resolved_at,
        created_at=conflict.created_at,
        paper_title=paper.title if paper else None,
        reviewer_1_name=None,
        reviewer_2_name=None,
        resolved_by_name=current_user.name or current_user.email
    )


@router.post("/conflicts/detect", response_model=dict)
def detect_conflicts(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually trigger conflict detection for all screenings."""
    review, _ = check_review_access(db, review_id, current_user, require_admin=True)
    
    screenings = db.query(PaperScreening).filter(
        PaperScreening.living_review_id == review_id,
        PaperScreening.reviewer1_decision.isnot(None),
        PaperScreening.reviewer2_decision.isnot(None)
    ).all()
    
    conflicts_created = 0
    for screening in screenings:
        conflict = detect_conflict(db, screening, review)
        if conflict:
            conflicts_created += 1
    
    return {"message": f"Detected {conflicts_created} new conflicts"}


# ============================================================================
# Metrics Endpoints
# ============================================================================

@router.get("/metrics", response_model=WorkflowMetricsResponse)
def get_workflow_metrics(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get workflow metrics including Cohen's Kappa."""
    review, _ = check_review_access(db, review_id, current_user)
    
    # Get or calculate metrics
    metrics = db.query(WorkflowMetrics).filter(
        WorkflowMetrics.living_review_id == review_id
    ).order_by(WorkflowMetrics.calculated_at.desc()).first()
    
    # If no recent metrics, calculate now
    if not metrics:
        metrics = calculate_and_save_metrics(db, review_id, current_user.id)
    
    return WorkflowMetricsResponse(
        id=metrics.id,
        living_review_id=metrics.living_review_id,
        cohens_kappa=metrics.cohens_kappa,
        agreement_rate=metrics.agreement_rate,
        disagreement_count=metrics.disagreement_count,
        total_comparisons=metrics.total_comparisons,
        kappa_interpretation=interpret_kappa(metrics.cohens_kappa) if metrics.cohens_kappa else None,
        ai_accuracy=metrics.ai_accuracy,
        ai_precision=metrics.ai_precision,
        ai_recall=metrics.ai_recall,
        ai_f1_score=metrics.ai_f1_score,
        true_positives=metrics.true_positives,
        false_positives=metrics.false_positives,
        true_negatives=metrics.true_negatives,
        false_negatives=metrics.false_negatives,
        avg_time_per_paper_seconds=metrics.avg_time_per_paper_seconds,
        total_papers_screened=metrics.total_papers_screened,
        reviewer_count=metrics.reviewer_count,
        papers_per_reviewer_avg=metrics.papers_per_reviewer_avg,
        calculated_at=metrics.calculated_at
    )


@router.post("/metrics/calculate", response_model=WorkflowMetricsResponse)
def recalculate_metrics(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Recalculate workflow metrics."""
    review, _ = check_review_access(db, review_id, current_user)
    
    metrics = calculate_and_save_metrics(db, review_id, current_user.id)
    
    return WorkflowMetricsResponse(
        id=metrics.id,
        living_review_id=metrics.living_review_id,
        cohens_kappa=metrics.cohens_kappa,
        agreement_rate=metrics.agreement_rate,
        disagreement_count=metrics.disagreement_count,
        total_comparisons=metrics.total_comparisons,
        kappa_interpretation=interpret_kappa(metrics.cohens_kappa) if metrics.cohens_kappa else None,
        ai_accuracy=metrics.ai_accuracy,
        ai_precision=metrics.ai_precision,
        ai_recall=metrics.ai_recall,
        ai_f1_score=metrics.ai_f1_score,
        true_positives=metrics.true_positives,
        false_positives=metrics.false_positives,
        true_negatives=metrics.true_negatives,
        false_negatives=metrics.false_negatives,
        avg_time_per_paper_seconds=metrics.avg_time_per_paper_seconds,
        total_papers_screened=metrics.total_papers_screened,
        reviewer_count=metrics.reviewer_count,
        papers_per_reviewer_avg=metrics.papers_per_reviewer_avg,
        calculated_at=metrics.calculated_at
    )


def calculate_and_save_metrics(db: Session, review_id: UUID, user_id: UUID) -> WorkflowMetrics:
    """Calculate and save workflow metrics."""
    screenings = db.query(PaperScreening).filter(
        PaperScreening.living_review_id == review_id
    ).all()
    
    # Inter-rater reliability
    agreements = 0
    disagreements = 0
    total_pairs = 0
    
    for s in screenings:
        if s.reviewer1_decision and s.reviewer2_decision:
            total_pairs += 1
            if s.reviewer1_decision == s.reviewer2_decision:
                agreements += 1
            else:
                disagreements += 1
    
    kappa = calculate_cohens_kappa(agreements, total_pairs) if total_pairs > 0 else None
    agreement_rate = (agreements / total_pairs) if total_pairs > 0 else None
    
    # AI performance (compare AI decision to final decision)
    tp = fp = tn = fn = 0
    for s in screenings:
        if s.ai_decision and s.final_decision:
            ai_include = s.ai_decision == ScreeningDecisionEnum.INCLUDE
            final_include = s.final_decision == ScreeningDecisionEnum.INCLUDE
            
            if ai_include and final_include:
                tp += 1
            elif ai_include and not final_include:
                fp += 1
            elif not ai_include and not final_include:
                tn += 1
            else:
                fn += 1
    
    ai_total = tp + fp + tn + fn
    ai_accuracy = (tp + tn) / ai_total if ai_total > 0 else None
    ai_precision = tp / (tp + fp) if (tp + fp) > 0 else None
    ai_recall = tp / (tp + fn) if (tp + fn) > 0 else None
    ai_f1 = 2 * ai_precision * ai_recall / (ai_precision + ai_recall) if ai_precision and ai_recall else None
    
    # Workload distribution
    reviewer_counts = {}
    for s in screenings:
        if s.reviewer1_id:
            reviewer_counts[s.reviewer1_id] = reviewer_counts.get(s.reviewer1_id, 0) + 1
        if s.reviewer2_id:
            reviewer_counts[s.reviewer2_id] = reviewer_counts.get(s.reviewer2_id, 0) + 1
    
    reviewer_count = len(reviewer_counts)
    papers_per_reviewer = list(reviewer_counts.values()) if reviewer_counts else [0]
    
    # Create metrics record
    metrics = WorkflowMetrics(
        id=uuid4(),
        living_review_id=review_id,
        cohens_kappa=kappa,
        agreement_rate=agreement_rate,
        disagreement_count=disagreements,
        total_comparisons=total_pairs,
        ai_accuracy=ai_accuracy,
        ai_precision=ai_precision,
        ai_recall=ai_recall,
        ai_f1_score=ai_f1,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        total_papers_screened=len(screenings),
        reviewer_count=reviewer_count,
        papers_per_reviewer_avg=sum(papers_per_reviewer) / len(papers_per_reviewer) if papers_per_reviewer else None,
        papers_per_reviewer_min=min(papers_per_reviewer) if papers_per_reviewer else None,
        papers_per_reviewer_max=max(papers_per_reviewer) if papers_per_reviewer else None,
        calculated_at=datetime.utcnow(),
        calculated_by=user_id
    )
    
    db.add(metrics)
    db.commit()
    db.refresh(metrics)
    
    return metrics
