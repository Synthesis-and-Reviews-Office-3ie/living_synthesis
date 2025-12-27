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
    
    # Subscription
    tier = Column(SQLEnum(UserTier), default=UserTier.FREE)
    stripe_customer_id = Column(String(255))
    stripe_subscription_id = Column(String(255))
    
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
    
    # Auto-approve low-relevance threshold (papers below this are auto-excluded)
    auto_exclude_threshold = Column(Integer, default=5)
    
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
    oa_url = Column(Text)
    is_oa = Column(Boolean, default=False)
    
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
    
    # Review status (HITL)
    include = Column(Boolean, default=True)
    reviewed_at = Column(DateTime)
    reviewer_notes = Column(Text)
    
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
