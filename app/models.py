"""
SQLAlchemy database models for multi-tenant evidence synthesis newsletter.
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Float, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

from app.database import Base


class UserTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"


class TopicFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255))
    
    # OAuth fields
    oauth_provider = Column(String(50))  # google, microsoft-entra-id, github
    oauth_provider_id = Column(String(255))  # provider's user ID
    
    # Subscription
    tier = Column(SQLEnum(UserTier), default=UserTier.FREE)
    stripe_customer_id = Column(String(255))
    stripe_subscription_id = Column(String(255))
    
    # LLM Preferences
    preferred_llm_model = Column(String(100), default="openai/gpt-4o")
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    topics = relationship("Topic", back_populates="user", cascade="all, delete-orphan")


class Topic(Base):
    """A topic represents a user's subscription to a specific research area."""
    __tablename__ = "topics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    name = Column(String(255), nullable=False)  # e.g., "LLMs in Evidence Synthesis"
    description = Column(Text)
    
    # Search queries for each source (JSON object)
    # {"openalex": "query...", "pubmed": "query...", "google": "query...", ...}
    queries = Column(JSON, nullable=False)
    
    # Settings
    frequency = Column(SQLEnum(TopicFrequency), default=TopicFrequency.WEEKLY)
    is_active = Column(Boolean, default=True)
    
    # Search date range in days (Free: 30 fixed, Pro/Team: 7-365 configurable)
    search_days = Column(Integer, default=30)
    
    # Max papers per source (Free: 50, Pro: 200, Team: 500 with pagination)
    max_papers_per_source = Column(Integer, default=50)
    
    # Auto-approve low-relevance threshold (papers below this are auto-excluded)
    auto_exclude_threshold = Column(Integer, default=5)
    
    # Living Review Feature (Pro+)
    # Links this topic to an existing systematic review or evidence gap map
    living_review_enabled = Column(Boolean, default=False)
    living_review_type = Column(String(50))  # "systematic_review", "evidence_gap_map", "meta_analysis"
    living_review_source = Column(Text)  # URL or reference to the original review
    living_review_last_sync = Column(DateTime)  # Last time new papers were synced
    
    # Historical search flag - allows one-time search without date limits
    historical_search_done = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_run_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="topics")
    papers = relationship("TopicPaper", back_populates="topic", cascade="all, delete-orphan")
    newsletters = relationship("Newsletter", back_populates="topic", cascade="all, delete-orphan")


class Paper(Base):
    """A paper/article stored globally (deduplicated across all users)."""
    __tablename__ = "papers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identifiers
    doi = Column(String(255), unique=True, index=True)
    external_id = Column(String(255), index=True)  # arXiv ID, PubMed ID, URL, etc.
    source = Column(String(50))  # openalex, pubmed, arxiv, crossref, google_web, github, rss
    
    # Content
    title = Column(Text, nullable=False)
    abstract = Column(Text)
    
    # Metadata
    publication_date = Column(DateTime)
    authors = Column(JSON)  # List of author names
    
    # Open Access
    oa_url = Column(Text)  # Original OA PDF URL (e.g., arXiv, publisher OA)
    is_oa = Column(Boolean, default=False)
    
    # PDF Storage
    pdf_url = Column(Text)  # Stored PDF URL in our S3/R2
    pdf_s3_key = Column(String(500))  # S3 key for the stored PDF
    pdf_fetched_at = Column(DateTime)  # When we fetched/stored the PDF
    pdf_size_bytes = Column(Integer)  # PDF file size
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    topic_papers = relationship("TopicPaper", back_populates="paper")


class TopicPaper(Base):
    """
    Association table between Topics and Papers.
    Contains per-topic analysis (since relevance varies by topic).
    """
    __tablename__ = "topic_papers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), nullable=False)
    
    # LLM Analysis (specific to this topic)
    headline = Column(String(255))
    summary = Column(Text)
    category = Column(String(50))  # New Tool/App, Methodology, Review/Benchmark, Opinion
    models_mentioned = Column(JSON)  # List of LLM names mentioned
    relevance_score = Column(Integer)  # 1-10
    ai_relevance_reason = Column(String(255))  # Brief explanation of relevance score
    
    # Review status (HITL)
    include = Column(Boolean, default=True)
    reviewed_at = Column(DateTime)
    reviewer_notes = Column(Text)
    
    # Trash (soft delete for excluded papers)
    deleted_at = Column(DateTime, nullable=True)  # When excluded, set this for auto-cleanup
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    topic = relationship("Topic", back_populates="papers")
    paper = relationship("Paper", back_populates="topic_papers")


class Newsletter(Base):
    """A generated newsletter for a topic."""
    __tablename__ = "newsletters"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False)
    
    # Content URLs (stored in S3/R2)
    html_url = Column(Text)
    pdf_url = Column(Text)
    
    # Paper count
    paper_count = Column(Integer, default=0)
    
    # Sending status
    sent_at = Column(DateTime)
    
    # Analytics
    opens = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Period covered
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    
    # Relationships
    topic = relationship("Topic", back_populates="newsletters")


class EmailSubscriber(Base):
    """
    Email-only subscribers (for public newsletter lists).
    These are people who sign up without creating a full account.
    """
    __tablename__ = "email_subscribers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    
    # Which public topics they're subscribed to
    subscribed_topics = Column(JSON, default=[])  # List of topic IDs
    
    # Unsubscribe token
    unsubscribe_token = Column(String(255), unique=True, default=lambda: str(uuid.uuid4()))
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime)


# ============== Living Review Models ==============

class LivingReviewStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ScreeningMode(str, enum.Enum):
    SINGLE = "single"          # One reviewer, decision is final
    DUAL = "dual"              # Two reviewers, auto-resolve if agree, conflict if disagree
    DUAL_CONSENSUS = "dual_consensus"  # Two reviewers must agree, third resolves conflicts


class ReviewTeamRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    SCREENER = "screener"
    VIEWER = "viewer"


class ScreeningDecision(str, enum.Enum):
    PENDING = "pending"
    INCLUDE = "include"
    EXCLUDE = "exclude"
    MAYBE = "maybe"
    CONFLICT = "conflict"


class LivingReview(Base):
    """
    A Living Systematic Review or Evidence Gap Map.
    This is the "home" for an SR/EGM that is continuously updated.
    """
    __tablename__ = "living_reviews"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True)  # Optional - can be standalone
    
    # Owner (for standalone reviews without a topic)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Basic Info
    title = Column(String(500), nullable=False)  # "Effects of X on Y: A Living Systematic Review"
    slug = Column(String(255), unique=True, index=True)  # URL-friendly: effects-of-x-on-y
    description = Column(Text)
    review_type = Column(String(50), default="systematic_review")  # systematic_review, evidence_gap_map, meta_analysis
    
    # Protocol & Publication
    protocol_url = Column(Text)  # Link to PROSPERO, OSF
    protocol_file_url = Column(Text)  # Uploaded PDF stored in S3/R2
    publication_doi = Column(String(255))  # DOI of original published paper
    publication_citation = Column(Text)  # Full citation text
    publication_url = Column(Text)  # Link to full text
    
    # Registry IDs
    prospero_id = Column(String(50))  # CRD42024xxxxxx
    cochrane_id = Column(String(50))
    campbell_id = Column(String(50))
    osf_id = Column(String(50))
    
    # Status
    status = Column(SQLEnum(LivingReviewStatus), default=LivingReviewStatus.ACTIVE)
    is_public = Column(Boolean, default=False)  # Show on public landing page?
    
    # PICO Criteria (for AI-assisted screening)
    pico_population = Column(Text)
    pico_intervention = Column(Text)
    pico_comparator = Column(Text)
    pico_outcome = Column(Text)
    pico_study_design = Column(Text)  # e.g., "RCTs and quasi-experimental"
    
    # Eligibility Criteria (structured for AI)
    inclusion_criteria = Column(JSON)  # [{"criterion": "RCTs only", "required": true}, ...]
    exclusion_criteria = Column(JSON)  # [{"criterion": "Conference abstracts", "reason": "Insufficient detail"}]
    
    # Screening Settings
    screening_mode = Column(SQLEnum(ScreeningMode), default=ScreeningMode.SINGLE)  # single, dual, dual_consensus
    require_full_text = Column(Boolean, default=False)  # If true, full-text screening is required after TAS
    
    # Search Strategy
    original_search_date = Column(DateTime)  # When was the original SR search done?
    databases_searched = Column(JSON)  # ["PubMed", "CENTRAL", "EMBASE", ...]
    
    # Current Stats (cached for performance)
    total_screened = Column(Integer, default=0)
    total_included = Column(Integer, default=0)
    total_excluded = Column(Integer, default=0)
    current_version = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    topic = relationship("Topic")
    updates = relationship("ReviewUpdate", back_populates="living_review", cascade="all, delete-orphan")
    team_members = relationship("ReviewTeamMember", back_populates="living_review", cascade="all, delete-orphan")
    screenings = relationship("PaperScreening", back_populates="living_review", cascade="all, delete-orphan")


class ReviewUpdate(Base):
    """
    Tracks each update cycle of a living review.
    Like a "version" or "release" of the review.
    """
    __tablename__ = "review_updates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    living_review_id = Column(UUID(as_uuid=True), ForeignKey("living_reviews.id"), nullable=False)
    
    version = Column(Integer, nullable=False)  # 1, 2, 3...
    
    # What changed in this update
    papers_screened = Column(Integer, default=0)
    papers_included = Column(Integer, default=0)
    papers_excluded = Column(Integer, default=0)
    
    # Search details
    search_start_date = Column(DateTime)  # Date range searched
    search_end_date = Column(DateTime)
    
    # Generated artifacts
    prisma_flow_url = Column(Text)  # Generated PRISMA diagram
    change_summary = Column(Text)  # "Added 3 RCTs from 2024, excluded 12 non-RCTs"
    notes = Column(Text)  # Internal notes
    
    # Status
    is_published = Column(Boolean, default=False)
    published_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    living_review = relationship("LivingReview", back_populates="updates")


class ReviewTeamMember(Base):
    """
    Team members who can collaborate on a living review.
    """
    __tablename__ = "review_team_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    living_review_id = Column(UUID(as_uuid=True), ForeignKey("living_reviews.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    role = Column(SQLEnum(ReviewTeamRole), default=ReviewTeamRole.SCREENER)
    
    # Invitation tracking
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    invited_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime)
    
    # Relationships
    living_review = relationship("LivingReview", back_populates="team_members")
    user = relationship("User", foreign_keys=[user_id])
    inviter = relationship("User", foreign_keys=[invited_by])


class PaperScreening(Base):
    """
    Screening decisions for papers in a living review.
    Supports dual screening and conflict resolution.
    """
    __tablename__ = "paper_screenings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    living_review_id = Column(UUID(as_uuid=True), ForeignKey("living_reviews.id"), nullable=False)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), nullable=False)
    
    # AI Pre-screening
    ai_decision = Column(SQLEnum(ScreeningDecision), default=ScreeningDecision.PENDING)
    ai_confidence = Column(Float)  # 0.0 - 1.0
    ai_rationale = Column(Text)  # Why AI thinks include/exclude
    
    # First Reviewer
    reviewer1_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewer1_decision = Column(SQLEnum(ScreeningDecision))
    reviewer1_reason = Column(Text)
    reviewer1_at = Column(DateTime)
    
    # Second Reviewer (for dual screening)
    reviewer2_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewer2_decision = Column(SQLEnum(ScreeningDecision))
    reviewer2_reason = Column(Text)
    reviewer2_at = Column(DateTime)
    
    # Conflict Resolution
    resolver_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    final_decision = Column(SQLEnum(ScreeningDecision))
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime)
    
    # Exclusion reason (if excluded)
    exclusion_reason = Column(String(255))  # "Wrong population", "Wrong intervention", etc.
    
    # Which update version this was added in
    added_in_version = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    living_review = relationship("LivingReview", back_populates="screenings")
    paper = relationship("Paper")
    reviewer1 = relationship("User", foreign_keys=[reviewer1_id])
    reviewer2 = relationship("User", foreign_keys=[reviewer2_id])
    resolver = relationship("User", foreign_keys=[resolver_id])


class AssignmentStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class ConflictType(str, enum.Enum):
    HUMAN_DISAGREEMENT = "human_disagreement"  # Two reviewers disagree
    HUMAN_LLM_DISAGREEMENT = "human_llm_disagreement"  # Human overrides LLM
    UNCERTAIN_DECISION = "uncertain_decision"  # Multiple "Maybe" decisions


class ConflictResolutionStatus(str, enum.Enum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class ReviewerAssignment(Base):
    """
    Tracks which papers are assigned to which reviewers.
    Supports double-blind, workload balancing, and progress tracking.
    """
    __tablename__ = "reviewer_assignments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    living_review_id = Column(UUID(as_uuid=True), ForeignKey("living_reviews.id"), nullable=False)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Assignment metadata
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    assigned_at = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime)
    
    # For double-blind (1st reviewer, 2nd reviewer, etc.)
    assignment_order = Column(Integer, default=1)
    is_blinded = Column(Boolean, default=False)
    
    # Status tracking
    status = Column(SQLEnum(AssignmentStatus), default=AssignmentStatus.PENDING)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Notes
    notes = Column(Text)
    
    # Relationships
    living_review = relationship("LivingReview")
    paper = relationship("Paper")
    user = relationship("User", foreign_keys=[user_id])
    assigner = relationship("User", foreign_keys=[assigned_by])


class ScreeningConflict(Base):
    """
    Tracks disagreements between reviewers for conflict resolution.
    """
    __tablename__ = "screening_conflicts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    living_review_id = Column(UUID(as_uuid=True), ForeignKey("living_reviews.id"), nullable=False)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), nullable=False)
    screening_id = Column(UUID(as_uuid=True), ForeignKey("paper_screenings.id"), nullable=False)
    
    # Conflict details
    conflict_type = Column(SQLEnum(ConflictType), nullable=False)
    
    # The conflicting decisions
    decision_1 = Column(String(50))  # e.g., "include"
    reviewer_1_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    decision_2 = Column(String(50))  # e.g., "exclude"
    reviewer_2_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Resolution
    resolution_status = Column(SQLEnum(ConflictResolutionStatus), default=ConflictResolutionStatus.UNRESOLVED)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    final_decision = Column(String(50))  # "include" or "exclude"
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    living_review = relationship("LivingReview")
    paper = relationship("Paper")
    screening = relationship("PaperScreening")
    reviewer1 = relationship("User", foreign_keys=[reviewer_1_id])
    reviewer2 = relationship("User", foreign_keys=[reviewer_2_id])
    resolver = relationship("User", foreign_keys=[resolved_by])


class WorkflowMetrics(Base):
    """
    Tracks inter-rater reliability metrics (Cohen's Kappa) and workflow efficiency.
    Calculated periodically or on-demand.
    """
    __tablename__ = "workflow_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    living_review_id = Column(UUID(as_uuid=True), ForeignKey("living_reviews.id"), nullable=False)
    
    # Inter-rater reliability (human-human)
    cohens_kappa = Column(Float)  # -1 to 1 (>0.8 = excellent)
    agreement_rate = Column(Float)  # 0.0 to 1.0
    disagreement_count = Column(Integer, default=0)
    total_comparisons = Column(Integer, default=0)
    
    # AI performance (vs human ground truth)
    ai_accuracy = Column(Float)
    ai_precision = Column(Float)
    ai_recall = Column(Float)
    ai_f1_score = Column(Float)
    
    # Confusion matrix (for AI)
    true_positives = Column(Integer, default=0)
    false_positives = Column(Integer, default=0)
    true_negatives = Column(Integer, default=0)
    false_negatives = Column(Integer, default=0)
    
    # Efficiency metrics
    avg_time_per_paper_seconds = Column(Float)
    total_papers_screened = Column(Integer, default=0)
    
    # Workload distribution
    reviewer_count = Column(Integer, default=0)
    papers_per_reviewer_avg = Column(Float)
    papers_per_reviewer_min = Column(Integer)
    papers_per_reviewer_max = Column(Integer)
    
    # Metadata
    calculated_at = Column(DateTime, default=datetime.utcnow)
    calculated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    living_review = relationship("LivingReview")
    calculator = relationship("User", foreign_keys=[calculated_by])
