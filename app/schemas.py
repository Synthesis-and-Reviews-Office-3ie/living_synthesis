"""
Pydantic schemas for API request/response validation.
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
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
    created_at: datetime


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


class TopicUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    queries: Optional[Dict[str, str]] = None
    frequency: Optional[TopicFrequencyEnum] = None
    is_active: Optional[bool] = None


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    description: Optional[str]
    queries: Dict[str, str]
    frequency: str
    is_active: bool
    created_at: datetime
    last_run_at: Optional[datetime]


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
