"""
Pydantic schemas for API request/response validation.
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ============== Auth Schemas ==============

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    email: str
    name: Optional[str]
    tier: str
    is_verified: bool
    preferred_llm_model: Optional[str] = "openai/gpt-4o"
    created_at: datetime


class UserSettingsUpdate(BaseModel):
    """Schema for updating user settings like name and LLM preference."""
    name: Optional[str] = None
    preferred_llm_model: Optional[str] = None


# ============== Topic Schemas ==============

class TopicFrequencyEnum(str, Enum):
    daily = "daily"
    weekly = "weekly"


class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    queries: Dict[str, str] = Field(
        ...,
        description="Search queries per source",
        json_schema_extra={
            "example": {
                "openalex": '("evidence synthesis") AND ("LLM")',
                "pubmed": '("systematic review") AND ("large language model")',
                "google": '"LLM" "evidence synthesis" blog'
            }
        }
    )
    frequency: TopicFrequencyEnum = TopicFrequencyEnum.weekly
    search_days: int = Field(default=30, ge=7, le=365, description="Search lookback period in days (Pro/Team: 7-365)")
    max_papers_per_source: int = Field(default=1000, ge=10, le=10000, description="Max papers per source (no tier limits)")


class TopicUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    queries: Optional[Dict[str, str]] = None
    frequency: Optional[TopicFrequencyEnum] = None
    is_active: Optional[bool] = None
    search_days: Optional[int] = Field(default=None, ge=7, le=365, description="Search lookback period in days (Pro/Team only)")
    max_papers_per_source: Optional[int] = Field(default=None, ge=10, le=10000, description="Max papers per source")
    # Living Review fields (Pro+)
    living_review_enabled: Optional[bool] = None
    living_review_type: Optional[str] = None
    living_review_source: Optional[str] = None


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    description: Optional[str]
    queries: Dict[str, str]
    frequency: str
    is_active: bool
    search_days: int = 30  # Search lookback period in days
    max_papers_per_source: int = 1000  # Max papers per source
    created_at: datetime
    last_run_at: Optional[datetime]
    # Historical search (one-time, no date limit)
    historical_search_done: Optional[bool] = False
    # Living Review fields
    living_review_enabled: Optional[bool] = False
    living_review_type: Optional[str] = None
    living_review_source: Optional[str] = None
    living_review_last_sync: Optional[datetime] = None


# ============== Paper Schemas ==============

class PaperResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    doi: Optional[str]
    external_id: Optional[str]
    source: str
    title: str
    abstract: Optional[str]
    publication_date: Optional[datetime]
    oa_url: Optional[str]
    is_oa: bool


class TopicPaperResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    paper: PaperResponse
    headline: Optional[str]
    summary: Optional[str]
    category: Optional[str]
    models_mentioned: Optional[List[str]]
    relevance_score: Optional[int]
    include: bool
    reviewed_at: Optional[datetime]


class ReviewDecision(BaseModel):
    paper_id: UUID
    include: bool
    reviewer_notes: Optional[str] = None


class BulkReviewRequest(BaseModel):
    decisions: List[ReviewDecision]


# ============== Newsletter Schemas ==============

class NewsletterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    topic_id: UUID
    html_url: Optional[str]
    pdf_url: Optional[str]
    paper_count: int
    sent_at: Optional[datetime]
    opens: int
    clicks: int
    created_at: datetime
    period_start: Optional[datetime]
    period_end: Optional[datetime]


# ============== Email Subscription Schemas ==============

class EmailSubscribe(BaseModel):
    email: EmailStr
    topic_id: UUID


class EmailUnsubscribe(BaseModel):
    token: str


# ============== Password Reset Schemas ==============

class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


# ============== Billing Schemas ==============

class CheckoutRequest(BaseModel):
    tier: str = Field(..., pattern="^(pro|team)$")


class CheckoutResponse(BaseModel):
    checkout_url: str


# ============== Stats/Dashboard Schemas ==============

class DashboardStats(BaseModel):
    total_topics: int
    total_papers: int
    total_newsletters: int
    papers_this_week: int
    pending_review: int


# ============== Living Review Schemas ==============

class LivingReviewStatusEnum(str, Enum):
    active = "active"
    paused = "paused"
    completed = "completed"
    archived = "archived"


class ReviewTypeEnum(str, Enum):
    systematic_review = "systematic_review"
    evidence_gap_map = "evidence_gap_map"
    meta_analysis = "meta_analysis"
    scoping_review = "scoping_review"


class TeamRoleEnum(str, Enum):
    owner = "owner"
    admin = "admin"
    screener = "screener"
    viewer = "viewer"


class ScreeningDecisionEnum(str, Enum):
    pending = "pending"
    include = "include"
    exclude = "exclude"
    maybe = "maybe"
    conflict = "conflict"


class ScreeningModeEnum(str, Enum):
    single = "single"              # One reviewer, decision is final
    dual = "dual"                  # Two reviewers, auto-resolve if agree
    dual_consensus = "dual_consensus"  # Two reviewers must agree, third resolves


class EligibilityCriterion(BaseModel):
    criterion: str
    required: bool = True
    description: Optional[str] = None


class PICOCriteria(BaseModel):
    population: Optional[str] = None
    intervention: Optional[str] = None
    comparator: Optional[str] = None
    outcome: Optional[str] = None
    study_design: Optional[str] = None


class LivingReviewCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    review_type: ReviewTypeEnum = ReviewTypeEnum.systematic_review
    topic_id: Optional[UUID] = None  # Optional - can create standalone reviews
    
    # PICO criteria (for standalone reviews without topic)
    population: Optional[str] = None
    intervention: Optional[str] = None
    comparator: Optional[str] = None
    outcomes: Optional[str] = None
    
    # Optional at creation
    protocol_url: Optional[str] = None
    publication_doi: Optional[str] = None
    prospero_id: Optional[str] = None
    osf_id: Optional[str] = None
    is_public: bool = False
    
    # Screening settings
    screening_mode: ScreeningModeEnum = ScreeningModeEnum.single
    require_full_text: bool = False


class LivingReviewUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    status: Optional[LivingReviewStatusEnum] = None
    is_public: Optional[bool] = None
    topic_id: Optional[UUID] = None  # Allow linking a topic to an existing review
    
    # Protocol & Publication
    protocol_url: Optional[str] = None
    publication_doi: Optional[str] = None
    publication_citation: Optional[str] = None
    publication_url: Optional[str] = None
    
    # Registry IDs
    prospero_id: Optional[str] = None
    cochrane_id: Optional[str] = None
    campbell_id: Optional[str] = None
    osf_id: Optional[str] = None
    
    # PICO
    pico_population: Optional[str] = None
    pico_intervention: Optional[str] = None
    pico_comparator: Optional[str] = None
    pico_outcome: Optional[str] = None
    pico_study_design: Optional[str] = None
    
    # Criteria
    inclusion_criteria: Optional[List[EligibilityCriterion]] = None
    exclusion_criteria: Optional[List[EligibilityCriterion]] = None
    
    # Screening settings
    screening_mode: Optional[ScreeningModeEnum] = None
    require_full_text: Optional[bool] = None


class LivingReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    topic_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    title: str
    slug: Optional[str]
    description: Optional[str]
    review_type: str
    status: str
    is_public: bool
    
    # Protocol & Publication
    protocol_url: Optional[str]
    protocol_file_url: Optional[str]
    publication_doi: Optional[str]
    publication_citation: Optional[str]
    publication_url: Optional[str]
    
    # Registry IDs
    prospero_id: Optional[str]
    cochrane_id: Optional[str]
    campbell_id: Optional[str]
    osf_id: Optional[str]
    
    # PICO - expose as simpler names for frontend
    population: Optional[str] = None
    intervention: Optional[str] = None
    comparator: Optional[str] = None
    outcomes: Optional[str] = None
    
    # Also keep original names for compatibility
    pico_population: Optional[str] = None
    pico_intervention: Optional[str] = None
    pico_comparator: Optional[str] = None
    pico_outcome: Optional[str] = None
    pico_study_design: Optional[str] = None
    
    # Criteria
    inclusion_criteria: Optional[List[Dict[str, Any]]] = None
    exclusion_criteria: Optional[List[Dict[str, Any]]] = None
    
    # Screening settings
    screening_mode: str = "single"
    require_full_text: bool = False
    
    # Stats
    total_screened: int = 0
    total_included: int = 0
    total_excluded: int = 0
    current_version: int = 0
    
    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    @model_validator(mode='after')
    def map_pico_fields(self):
        """Map pico_* fields to simpler names for frontend."""
        if self.pico_population and not self.population:
            self.population = self.pico_population
        if self.pico_intervention and not self.intervention:
            self.intervention = self.pico_intervention
        if self.pico_comparator and not self.comparator:
            self.comparator = self.pico_comparator
        if self.pico_outcome and not self.outcomes:
            self.outcomes = self.pico_outcome
        return self


class LivingReviewPublic(BaseModel):
    """Public-facing view of a living review (no auth required)."""
    model_config = ConfigDict(from_attributes=True)
    
    title: str
    slug: str
    description: Optional[str]
    review_type: str
    status: str
    
    # Publication info
    publication_doi: Optional[str]
    publication_citation: Optional[str]
    prospero_id: Optional[str]
    
    # Stats
    total_screened: int
    total_included: int
    current_version: int
    
    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime]


# ============== Review Update Schemas ==============

class ReviewUpdateCreate(BaseModel):
    change_summary: Optional[str] = None
    notes: Optional[str] = None


class ReviewUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    living_review_id: UUID
    version: int
    papers_screened: int
    papers_included: int
    papers_excluded: int
    search_start_date: Optional[datetime]
    search_end_date: Optional[datetime]
    prisma_flow_url: Optional[str]
    change_summary: Optional[str]
    is_published: bool
    published_at: Optional[datetime]
    created_at: datetime


# ============== Team Member Schemas ==============

class TeamMemberInvite(BaseModel):
    email: EmailStr
    role: TeamRoleEnum = TeamRoleEnum.screener


class TeamMemberUpdate(BaseModel):
    role: TeamRoleEnum


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    role: str
    invited_at: datetime
    accepted_at: Optional[datetime]


# ============== Screening Schemas ==============

class ScreeningDecisionSubmit(BaseModel):
    paper_id: UUID
    decision: ScreeningDecisionEnum
    reason: Optional[str] = None
    exclusion_reason: Optional[str] = None  # If decision is 'exclude'


class ScreeningBatchSubmit(BaseModel):
    decisions: List[ScreeningDecisionSubmit]


class PaperScreeningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    paper_id: UUID
    
    # Paper details (joined)
    paper_title: Optional[str] = None
    paper_abstract: Optional[str] = None
    paper_doi: Optional[str] = None
    paper_authors: Optional[List[str]] = None
    paper_publication_date: Optional[datetime] = None
    paper_source: Optional[str] = None
    paper_external_id: Optional[str] = None
    
    # PDF access
    paper_pdf_url: Optional[str] = None  # Stored PDF URL
    paper_oa_url: Optional[str] = None   # Original OA URL
    paper_is_oa: bool = False
    paper_pdf_available: bool = False    # Is PDF fetchable?
    
    # AI Pre-screening
    ai_decision: Optional[str]
    ai_confidence: Optional[float]
    ai_rationale: Optional[str]
    
    # Review status
    reviewer1_decision: Optional[str]
    reviewer2_decision: Optional[str]
    final_decision: Optional[str]
    exclusion_reason: Optional[str]
    
    # Timestamps
    created_at: datetime


class ScreeningQueueResponse(BaseModel):
    total: int
    pending: int
    conflicts: int
    items: List[PaperScreeningResponse]


# ============== Export Schemas ==============

class ExportFormat(str, Enum):
    ris = "ris"
    bibtex = "bibtex"
    csv = "csv"
    json = "json"


class ExportRequest(BaseModel):
    format: ExportFormat = ExportFormat.ris
    include_only: bool = True  # Export only included papers?


# ============== Assignment Schemas ==============

class AssignmentStatusEnum(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    skipped = "skipped"


class AssignmentStrategyEnum(str, Enum):
    balanced = "balanced"  # Evenly distribute
    random = "random"  # Random assignment
    manual = "manual"  # Manual assignment
    round_robin = "round_robin"  # Sequential distribution


class AssignmentCreate(BaseModel):
    paper_ids: List[UUID] = Field(..., description="List of paper IDs to assign")
    user_ids: Optional[List[UUID]] = Field(None, description="Specific users for manual assignment")
    strategy: AssignmentStrategyEnum = AssignmentStrategyEnum.balanced
    is_blinded: bool = False
    due_date: Optional[datetime] = None
    reviewers_per_paper: int = Field(default=1, ge=1, le=5)


class AssignmentUpdate(BaseModel):
    status: Optional[AssignmentStatusEnum] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    living_review_id: UUID
    paper_id: UUID
    user_id: UUID
    assignment_order: int
    is_blinded: bool
    status: str
    assigned_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    
    # Enriched fields
    paper_title: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None


class AssignmentStats(BaseModel):
    total_assignments: int
    pending: int
    in_progress: int
    completed: int
    overdue: int
    completion_rate: float
    avg_time_to_complete_hours: Optional[float] = None


class AssignmentListResponse(BaseModel):
    assignments: List[AssignmentResponse]
    total: int
    stats: Optional[AssignmentStats] = None


# ============== Conflict Schemas ==============

class ConflictTypeEnum(str, Enum):
    human_disagreement = "human_disagreement"
    human_llm_disagreement = "human_llm_disagreement"
    uncertain_decision = "uncertain_decision"


class ConflictResolutionStatusEnum(str, Enum):
    unresolved = "unresolved"
    resolved = "resolved"
    escalated = "escalated"


class ConflictResolve(BaseModel):
    final_decision: ScreeningDecisionEnum = Field(..., description="Must be 'include' or 'exclude'")
    resolution_notes: Optional[str] = None


class ConflictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    living_review_id: UUID
    paper_id: UUID
    screening_id: UUID
    conflict_type: str
    decision_1: str
    decision_2: str
    resolution_status: str
    final_decision: Optional[str]
    resolution_notes: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime
    
    # Enriched fields
    paper_title: Optional[str] = None
    reviewer_1_name: Optional[str] = None
    reviewer_2_name: Optional[str] = None
    resolved_by_name: Optional[str] = None


class ConflictStats(BaseModel):
    total_conflicts: int
    unresolved_conflicts: int
    resolved_conflicts: int
    conflicts_by_type: Dict[str, int] = {}
    average_resolution_time_hours: Optional[float] = None
    cohens_kappa: Optional[float] = None
    agreement_rate: Optional[float] = None


class ConflictListResponse(BaseModel):
    conflicts: List[ConflictResponse]
    total: int
    stats: Optional[ConflictStats] = None


# ============== Workflow Metrics Schemas ==============

class WorkflowMetricsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    living_review_id: UUID
    
    # Inter-rater reliability
    cohens_kappa: Optional[float] = None
    agreement_rate: Optional[float] = None
    disagreement_count: int = 0
    total_comparisons: int = 0
    
    # Kappa interpretation
    kappa_interpretation: Optional[str] = None  # "Excellent", "Good", "Moderate", etc.
    
    # AI performance
    ai_accuracy: Optional[float] = None
    ai_precision: Optional[float] = None
    ai_recall: Optional[float] = None
    ai_f1_score: Optional[float] = None
    
    # Confusion matrix
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    
    # Efficiency
    avg_time_per_paper_seconds: Optional[float] = None
    total_papers_screened: int = 0
    
    # Workload
    reviewer_count: int = 0
    papers_per_reviewer_avg: Optional[float] = None
    
    # Metadata
    calculated_at: datetime
