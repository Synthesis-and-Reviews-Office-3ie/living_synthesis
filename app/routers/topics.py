"""
Topic management routes: CRUD for user topics.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timedelta

from app.database import get_db
from app.models import User, Topic, UserTier, Paper, TopicPaper
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
    
    # Living Review fields (Pro+ only)
    if topic_data.living_review_enabled is not None:
        if topic_data.living_review_enabled and current_user.tier == UserTier.FREE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Living Review feature is only available for Pro and Team tiers."
            )
        topic.living_review_enabled = topic_data.living_review_enabled
    if topic_data.living_review_type is not None:
        topic.living_review_type = topic_data.living_review_type
    if topic_data.living_review_source is not None:
        topic.living_review_source = topic_data.living_review_source
    
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


@router.post("/{topic_id}/run", status_code=status.HTTP_202_ACCEPTED)
def run_topic_search(
    topic_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Run paper search for a topic.
    Fetches papers from configured sources and adds them to the review queue.
    """
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Copy queries before passing to background task (session might close)
    queries_copy = dict(topic.queries) if topic.queries else {}
    
    # Run the search in the background
    background_tasks.add_task(
        _run_paper_search,
        str(topic_id),
        queries_copy,
        historical=False
    )
    
    return {"message": "Paper search started", "topic_id": str(topic_id)}


@router.post("/{topic_id}/run-historical", status_code=status.HTTP_202_ACCEPTED)
def run_historical_search(
    topic_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Run a one-time historical paper search without date limits.
    This allows users to gather all past papers for initial topic setup.
    Can only be run once per topic.
    """
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Check if historical search has already been done
    if topic.historical_search_done:
        raise HTTPException(
            status_code=400, 
            detail="Historical search has already been performed for this topic. This is a one-time feature."
        )
    
    # Copy queries before passing to background task
    queries_copy = dict(topic.queries) if topic.queries else {}
    
    # Run the historical search in the background
    background_tasks.add_task(
        _run_paper_search,
        str(topic_id),
        queries_copy,
        historical=True
    )
    
    return {"message": "Historical paper search started (no date limit)", "topic_id": str(topic_id)}


def _run_paper_search(topic_id: str, queries: dict, historical: bool = False):
    """Background task to search for papers across configured sources.
    
    Args:
        topic_id: UUID of the topic
        queries: Dict of source -> query string
        historical: If True, skip date filtering (one-time historical search)
    """
    import sys
    import traceback
    sys.path.insert(0, '.')
    
    print(f"[Background Task] Starting paper search for topic {topic_id}")
    print(f"[Background Task] Queries: {queries}")
    print(f"[Background Task] Historical mode: {historical}")
    
    from src.ingestion.fetchers import fetch_openalex, fetch_pubmed, fetch_arxiv, fetch_crossref
    from src.ingestion.web_fetchers import fetch_github, fetch_google_search
    from uuid import UUID as UUIDType
    from app.database import SessionLocal
    import os
    
    # Create a new database session for the background task
    db = SessionLocal()
    
    try:
        topic_uuid = UUIDType(topic_id)
        
        # Get the topic and user tier settings
        topic = db.query(Topic).filter(Topic.id == topic_uuid).first()
        if not topic:
            print(f"[Background Task] Topic {topic_id} not found")
            return
            
        user = db.query(User).filter(User.id == topic.user_id).first()
        user_tier = user.tier.value if user and user.tier else "free"
        
        search_days = topic.search_days if topic.search_days else 30
        # No artificial limits - fetch all available papers
        max_results = 100000
        
        # All tiers get pagination for complete results
        use_pagination = True
        
        # Historical search: no date limit
        if historical:
            since_date = None
            print(f"[Background Task] HISTORICAL SEARCH - no date limit")
        # Smart date range for regular searches:
        # - First run: use search_days as initial lookback
        # - Subsequent runs: use last_run_at + 2 day buffer (to catch late-indexed papers)
        elif topic.last_run_at:
            # Add 2-day overlap buffer for papers that might be indexed with delay
            buffer_days = 2
            since_date = (topic.last_run_at - timedelta(days=buffer_days)).strftime("%Y-%m-%d")
            print(f"[Background Task] Incremental search since last run: {topic.last_run_at} (with {buffer_days}d buffer)")
        else:
            # First run - use full search_days lookback
            since_date = (datetime.now() - timedelta(days=search_days)).strftime("%Y-%m-%d")
            print(f"[Background Task] Initial search with {search_days} days lookback")
        
        print(f"[Background Task] Tier={user_tier}, since_date={since_date}, max_results={max_results}, paginate={use_pagination}")
        
        all_papers = []
        
        # Fetch from each configured source
        for source, query in queries.items():
            if not query:
                continue
                
            try:
                print(f"Fetching from {source} with query: {query[:50]}...")
                if source.lower() == "openalex":
                    papers = fetch_openalex(query, since_date=since_date, max_results=max_results, paginate=use_pagination)
                elif source.lower() == "pubmed":
                    papers = fetch_pubmed(query, max_results=max_results, since_date=since_date)
                elif source.lower() == "arxiv":
                    papers = fetch_arxiv(query, max_results=max_results, since_date=since_date)
                elif source.lower() == "google_scholar":
                    from src.ingestion.fetchers import fetch_google_scholar
                    papers = fetch_google_scholar(query, max_results=max_results, since_date=since_date)
                elif source.lower() == "crossref":
                    papers = fetch_crossref(query, rows=max_results, from_date=since_date)
                elif source.lower() == "github":
                    github_token = os.getenv("GITHUB_TOKEN")
                    papers = fetch_github(query, token=github_token, max_results=max_results)
                elif source.lower() == "google":
                    google_api_key = os.getenv("GOOGLE_API_KEY")
                    google_cx = os.getenv("GOOGLE_CX")
                    if google_api_key and google_cx:
                        papers = fetch_google_search(query, api_key=google_api_key, cx=google_cx, max_results=max_results)
                    else:
                        print(f"Skipping {source}: Missing Google API credentials")
                        continue
                else:
                    print(f"Skipping {source}: Unknown source")
                    continue
                    
                print(f"Found {len(papers)} papers from {source}")
                all_papers.extend(papers)
            except Exception as e:
                print(f"Error fetching from {source}: {e}")
        
        # Deduplicate by DOI or title
        seen_dois = set()
        seen_titles = set()
        unique_papers = []
        
        for paper in all_papers:
            doi = paper.get("doi")
            title = paper.get("title", "").lower().strip()
            
            if doi and doi in seen_dois:
                continue
            if title and title in seen_titles:
                continue
                
            if doi:
                seen_dois.add(doi)
            if title:
                seen_titles.add(title)
            unique_papers.append(paper)
        
        # Add papers to database
        added_count = 0
        for paper_data in unique_papers:
            # Check if paper already exists
            existing = None
            if paper_data.get("doi"):
                existing = db.query(Paper).filter(Paper.doi == paper_data["doi"]).first()
            if not existing and paper_data.get("id"):
                existing = db.query(Paper).filter(
                    Paper.external_id == paper_data["id"],
                    Paper.source == paper_data["source"]
                ).first()
            
            if existing:
                paper = existing
            else:
                # Parse publication_date if it's a string
                pub_date = paper_data.get("publication_date")
                if pub_date and isinstance(pub_date, str):
                    try:
                        from dateutil.parser import parse as parse_date
                        pub_date = parse_date(pub_date)
                    except:
                        pub_date = None
                
                paper = Paper(
                    doi=paper_data.get("doi"),
                    external_id=paper_data.get("id"),
                    source=paper_data.get("source", "unknown"),
                    title=paper_data.get("title", "Untitled"),
                    abstract=paper_data.get("abstract"),
                    publication_date=pub_date,
                    authors=paper_data.get("authors", []),
                    oa_url=paper_data.get("oa_url"),
                    is_oa=paper_data.get("is_oa", False)
                )
                db.add(paper)
                db.flush()
            
            # Check if already linked to this topic
            existing_link = db.query(TopicPaper).filter(
                TopicPaper.topic_id == topic_uuid,
                TopicPaper.paper_id == paper.id
            ).first()
            
            if not existing_link:
                topic_paper = TopicPaper(
                    topic_id=topic_uuid,
                    paper_id=paper.id,
                    include=False  # Default to not included, needs review
                )
                db.add(topic_paper)
                added_count += 1
    
        # Update topic's last_run_at and historical_search_done flag
        topic = db.query(Topic).filter(Topic.id == topic_uuid).first()
        if topic:
            topic.last_run_at = datetime.utcnow()
            if historical:
                topic.historical_search_done = True
        
        db.commit()
        print(f"[Background Task] Paper search complete for topic {topic_id}: found {len(unique_papers)} unique papers, added {added_count} new")
    except Exception as e:
        print(f"[Background Task] Error in paper search: {e}")
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


@router.get("/{topic_id}/review")
def get_review_queue(
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all papers for a topic's review queue (excludes trashed papers)."""
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Get all papers linked to this topic (exclude trashed/deleted papers)
    topic_papers = db.query(TopicPaper, Paper).join(
        Paper, TopicPaper.paper_id == Paper.id
    ).filter(
        TopicPaper.topic_id == topic_id,
        TopicPaper.deleted_at == None  # Exclude trashed papers
    ).all()
    
    result = []
    for tp, paper in topic_papers:
        result.append({
            "id": str(tp.id),
            "paper_id": str(paper.id),
            "title": paper.title,
            "abstract": paper.abstract,
            "authors": paper.authors if hasattr(paper, 'authors') and paper.authors else [],
            "source": paper.source,
            "url": paper.oa_url or (f"https://doi.org/{paper.doi}" if paper.doi else None),
            "doi": paper.doi,
            "published_date": paper.publication_date,
            "is_oa": paper.is_oa or False,
            # AI Analysis fields
            "summary": tp.summary,
            "headline": tp.headline,
            "category": tp.category,
            "relevance_score": tp.relevance_score,
            "ai_relevance_reason": tp.ai_relevance_reason,
            # Review status
            "included": tp.include,
            "reviewed_at": tp.reviewed_at,
            "reviewer_notes": tp.reviewer_notes if hasattr(tp, 'reviewer_notes') else None
        })
    
    return result


@router.post("/{topic_id}/papers/{paper_id}/review")
def review_paper(
    topic_id: UUID,
    paper_id: UUID,
    review_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Review a single paper (include or exclude it)."""
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Find the topic-paper link (paper_id here is actually TopicPaper.id)
    topic_paper = db.query(TopicPaper).filter(
        TopicPaper.id == paper_id,
        TopicPaper.topic_id == topic_id
    ).first()
    
    if not topic_paper:
        raise HTTPException(status_code=404, detail="Paper not found in this topic")
    
    # Update review
    included = review_data.get("included", False)
    topic_paper.include = included
    topic_paper.reviewed_at = datetime.utcnow()
    
    # If excluded, move to trash (soft delete)
    if not included:
        topic_paper.deleted_at = datetime.utcnow()
    else:
        # If including, remove from trash
        topic_paper.deleted_at = None
    
    db.commit()
    
    return {"message": "Paper reviewed successfully", "included": included, "trashed": not included}


@router.get("/{topic_id}/stats")
def get_topic_stats(
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get analytics stats for a topic's papers."""
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Get all papers linked to this topic (exclude trashed)
    topic_papers = db.query(TopicPaper, Paper).join(
        Paper, TopicPaper.paper_id == Paper.id
    ).filter(
        TopicPaper.topic_id == topic_id,
        TopicPaper.deleted_at == None  # Exclude trashed papers from stats
    ).all()
    
    # Calculate stats
    total_papers = len(topic_papers)
    reviewed = sum(1 for tp, _ in topic_papers if tp.reviewed_at)
    included = sum(1 for tp, _ in topic_papers if tp.include and tp.reviewed_at)
    pending = total_papers - reviewed
    with_summaries = sum(1 for tp, _ in topic_papers if tp.summary)
    
    # New this week (papers added in last 7 days)
    from datetime import datetime, timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_this_week = sum(1 for tp, _ in topic_papers if tp.created_at and tp.created_at >= week_ago)
    
    # Source breakdown
    sources = {}
    for tp, paper in topic_papers:
        source = paper.source or "unknown"
        sources[source] = sources.get(source, 0) + 1
    
    # Top source
    top_source = max(sources.items(), key=lambda x: x[1])[0] if sources else None
    top_source_count = sources.get(top_source, 0) if top_source else 0
    
    # Category breakdown (from AI analysis)
    categories = {}
    for tp, paper in topic_papers:
        cat = tp.category or "uncategorized"
        categories[cat] = categories.get(cat, 0) + 1
    
    # Open access breakdown
    oa_count = sum(1 for _, paper in topic_papers if paper.is_oa)
    
    # Publication date trend (papers by month)
    monthly_trend = {}
    for tp, paper in topic_papers:
        if paper.publication_date:
            month_key = paper.publication_date.strftime("%Y-%m")
            monthly_trend[month_key] = monthly_trend.get(month_key, 0) + 1
    
    # Average relevance score
    scores = [tp.relevance_score for tp, _ in topic_papers if tp.relevance_score]
    avg_relevance = sum(scores) / len(scores) if scores else None
    
    return {
        "total_papers": total_papers,
        "reviewed": reviewed,
        "included": included,
        "pending": pending,
        "with_summaries": with_summaries,
        "new_this_week": new_this_week,
        "top_source": top_source,
        "top_source_count": top_source_count,
        "open_access": oa_count,
        "avg_relevance_score": avg_relevance,
        "sources": sources,
        "categories": categories,
        "monthly_trend": dict(sorted(monthly_trend.items()))
    }


@router.post("/{topic_id}/papers/{paper_id}/summarize")
async def generate_paper_summary(
    topic_id: UUID,
    paper_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate an AI summary for a specific paper."""
    from app.services.llm import get_llm_service
    
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Get the topic-paper link and paper
    topic_paper = db.query(TopicPaper).filter(
        TopicPaper.id == paper_id,
        TopicPaper.topic_id == topic_id
    ).first()
    
    if not topic_paper:
        raise HTTPException(status_code=404, detail="Paper not found in this topic")
    
    paper = db.query(Paper).filter(Paper.id == topic_paper.paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Generate summary using LLM
    llm = get_llm_service()
    
    try:
        # Get user's preferred model or default
        model_id = current_user.preferred_llm_model or "openai/gpt-4o-mini"
        
        analysis = await llm.analyze_paper(
            title=paper.title,
            abstract=paper.abstract or "",
            model_id=model_id
        )
        
        # Parse response - it should be JSON with summary, methodology, etc.
        content = analysis.get("content", "")
        
        # Try to extract structured data
        import json
        import re
        try:
            # Clean up markdown code blocks if present
            cleaned_content = content.strip()
            # Remove ```json ... ``` wrapper
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned_content)
            if json_match:
                cleaned_content = json_match.group(1).strip()
            
            # Try parsing as JSON
            parsed = json.loads(cleaned_content)
            summary = parsed.get("summary", content[:500])
            methodology = parsed.get("methodology", "")
            relevance = parsed.get("relevance_score", 5)
            tags = parsed.get("tags", [])
            
            # Ensure relevance is numeric and in valid range
            if isinstance(relevance, (int, float)):
                relevance = max(1, min(10, float(relevance)))
            else:
                relevance = 5.0
        except json.JSONDecodeError:
            # If not valid JSON, use content as summary
            summary = content[:500] if len(content) > 500 else content
            methodology = ""
            relevance = 5.0
            tags = []
        
        # Update TopicPaper with the analysis
        topic_paper.summary = summary
        topic_paper.headline = summary[:150] + "..." if len(summary) > 150 else summary
        topic_paper.relevance_score = relevance
        
        db.commit()
        
        return {
            "paper_id": str(paper_id),
            "summary": summary,
            "headline": topic_paper.headline,
            "methodology": methodology,
            "relevance_score": relevance,
            "tags": tags
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")


@router.post("/{topic_id}/summarize-all")
async def summarize_all_papers(
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 10  # Process max 10 at a time to avoid timeout
):
    """Generate AI summaries for all papers without summaries."""
    from app.services.llm import get_llm_service
    
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Tier-based limits for AI summaries per topic
    tier = str(current_user.tier) if current_user.tier else "free"
    SUMMARY_LIMITS = {
        "free": 10,      # Free tier: 10 summaries per topic
        "pro": 100,      # Pro tier: 100 summaries per topic
        "team": 10000,   # Team tier: essentially unlimited
    }
    max_summaries = SUMMARY_LIMITS.get(tier, 10)
    
    # Count existing summaries for this topic
    existing_summaries = db.query(TopicPaper).filter(
        TopicPaper.topic_id == topic_id,
        TopicPaper.summary.isnot(None)
    ).count()
    
    remaining_quota = max_summaries - existing_summaries
    if remaining_quota <= 0:
        return {
            "message": f"AI summary limit reached for {tier} tier ({max_summaries} per topic). Upgrade to generate more.",
            "summarized": 0,
            "limit_reached": True,
            "tier": tier,
            "max_summaries": max_summaries
        }
    
    # Get papers without summaries, respecting the remaining quota
    effective_limit = min(limit, remaining_quota)
    
    topic_papers = db.query(TopicPaper, Paper).join(
        Paper, TopicPaper.paper_id == Paper.id
    ).filter(
        TopicPaper.topic_id == topic_id,
        TopicPaper.summary.is_(None)
    ).limit(effective_limit).all()
    
    if not topic_papers:
        return {"message": "All papers already have summaries", "summarized": 0}
    
    llm = get_llm_service()
    model_id = current_user.preferred_llm_model or "openai/gpt-4o-mini"
    processed = 0
    errors = 0
    
    import json
    import re
    
    for tp, paper in topic_papers:
        try:
            analysis = await llm.analyze_paper(
                title=paper.title,
                abstract=paper.abstract or "",
                model_id=model_id
            )
            
            content = analysis.get("content", "")
            
            try:
                # Clean up markdown code blocks if present
                cleaned_content = content.strip()
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned_content)
                if json_match:
                    cleaned_content = json_match.group(1).strip()
                
                parsed = json.loads(cleaned_content)
                summary = parsed.get("summary", content[:500])
                relevance = parsed.get("relevance_score", 5)
                
                # Ensure relevance is numeric and in valid range
                if isinstance(relevance, (int, float)):
                    relevance = max(1, min(10, float(relevance)))
                else:
                    relevance = 5.0
            except json.JSONDecodeError:
                summary = content[:500] if len(content) > 500 else content
                relevance = 5.0
            
            tp.summary = summary
            tp.headline = summary[:150] + "..." if len(summary) > 150 else summary
            tp.relevance_score = relevance
            processed += 1
            
        except Exception as e:
            errors += 1
            continue
    
    db.commit()
    
    # Count remaining (without summaries)
    remaining_without_summary = db.query(TopicPaper).filter(
        TopicPaper.topic_id == topic_id,
        TopicPaper.summary.is_(None)
    ).count()
    
    # Updated quota
    new_existing = existing_summaries + processed
    new_remaining_quota = max_summaries - new_existing
    
    return {
        "summarized": processed,
        "errors": errors,
        "remaining_papers": remaining_without_summary,
        "tier": tier,
        "quota_used": new_existing,
        "quota_remaining": max(0, new_remaining_quota),
        "max_summaries": max_summaries
    }


# ============================================================================
# LLM RELEVANCE SCORING
# ============================================================================

@router.post("/{topic_id}/score-relevance")
async def score_paper_relevance(
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Score all unscored papers in a topic for relevance using LLM.
    
    Papers are scored 0-10 based on how relevant they are to the topic.
    Low-scoring papers (< 4) are flagged for potential hiding.
    """
    from app.services.llm import get_llm_service
    
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Get papers without relevance scores
    unscored_papers = db.query(TopicPaper, Paper).join(
        Paper, TopicPaper.paper_id == Paper.id
    ).filter(
        TopicPaper.topic_id == topic_id,
        TopicPaper.relevance_score == None
    ).all()
    
    if not unscored_papers:
        return {
            "scored": 0,
            "high_relevance": 0,
            "low_relevance": 0,
            "message": "All papers already scored"
        }
    
    llm = get_llm_service()
    model_id = current_user.preferred_llm_model or "gpt-4o-mini"
    
    # Prepare papers for batch scoring
    papers_to_score = []
    paper_map = {}  # Map paper ID to TopicPaper for updating
    
    for tp, paper in unscored_papers:
        papers_to_score.append({
            "id": str(tp.id),
            "title": paper.title,
            "abstract": paper.abstract or ""
        })
        paper_map[str(tp.id)] = tp
    
    # Score in batches of 20
    all_scores = []
    batch_size = 20
    
    for i in range(0, len(papers_to_score), batch_size):
        batch = papers_to_score[i:i + batch_size]
        try:
            scores = await llm.batch_score_relevance(
                papers=batch,
                topic_name=topic.name,
                topic_description=topic.description or topic.name,
                model_id=model_id
            )
            all_scores.extend(scores)
        except Exception as e:
            print(f"Error scoring batch {i}: {e}")
            # On error, mark batch as moderately relevant
            for p in batch:
                all_scores.append({
                    "id": p["id"],
                    "score": 5,
                    "reason": f"Scoring error: {str(e)[:50]}",
                    "keep": True
                })
    
    # Update database with scores
    high_relevance = 0
    low_relevance = 0
    
    for score_data in all_scores:
        paper_id = score_data.get("id")
        if paper_id in paper_map:
            tp = paper_map[paper_id]
            tp.relevance_score = score_data.get("score", 5)
            tp.ai_relevance_reason = score_data.get("reason", "")
            
            if score_data.get("score", 5) >= 6:
                high_relevance += 1
            elif score_data.get("score", 5) < 4:
                low_relevance += 1
    
    db.commit()
    
    return {
        "scored": len(all_scores),
        "high_relevance": high_relevance,
        "low_relevance": low_relevance,
        "message": f"Scored {len(all_scores)} papers. {high_relevance} highly relevant, {low_relevance} low relevance."
    }


@router.get("/{topic_id}/review-filtered")
def get_filtered_review_queue(
    topic_id: UUID,
    min_relevance: float = 0,
    hide_low_relevance: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get papers for review with optional relevance filtering.
    
    Args:
        min_relevance: Minimum relevance score (0-10) to include
        hide_low_relevance: If true, hide papers with score < 4
    """
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Build query with optional filtering (exclude trashed papers)
    query = db.query(TopicPaper, Paper).join(
        Paper, TopicPaper.paper_id == Paper.id
    ).filter(
        TopicPaper.topic_id == topic_id,
        TopicPaper.deleted_at == None  # Exclude trashed papers
    )
    
    if hide_low_relevance:
        # Hide papers with score < 4 (but keep unscored papers)
        query = query.filter(
            (TopicPaper.relevance_score >= 4) | (TopicPaper.relevance_score == None)
        )
    elif min_relevance > 0:
        query = query.filter(
            (TopicPaper.relevance_score >= min_relevance) | (TopicPaper.relevance_score == None)
        )
    
    # Order by relevance score descending (nulls last)
    topic_papers = query.order_by(
        TopicPaper.relevance_score.desc().nullslast(),
        Paper.publication_date.desc().nullslast()
    ).all()
    
    return [{
        "id": str(tp.id),
        "paper_id": str(paper.id),
        "title": paper.title,
        "abstract": paper.abstract,
        "authors": paper.authors,
        "source": paper.source,
        "url": paper.oa_url or f"https://doi.org/{paper.doi}" if paper.doi else None,
        "doi": paper.doi,
        "published_date": paper.publication_date.isoformat() if paper.publication_date else None,
        "is_oa": paper.is_oa,
        "summary": tp.summary,
        "headline": tp.headline,
        "category": tp.category,
        "relevance_score": tp.relevance_score,
        "ai_relevance_reason": tp.ai_relevance_reason,
        "included": tp.include,
        "reviewed_at": tp.reviewed_at.isoformat() if tp.reviewed_at else None
    } for tp, paper in topic_papers]


@router.post("/{topic_id}/generate-digest")
async def generate_weekly_digest(
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a weekly AI digest summarizing papers for this topic.
    
    Creates a narrative summary of recent papers, highlighting key findings,
    trends, and research gaps. Uses the user's preferred LLM model.
    """
    from app.services.llm import get_llm_service
    
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Get papers for this topic (recent ones, sorted by relevance)
    topic_papers = db.query(TopicPaper, Paper).join(
        Paper, TopicPaper.paper_id == Paper.id
    ).filter(
        TopicPaper.topic_id == topic_id
    ).order_by(
        TopicPaper.relevance_score.desc().nullslast(),
        Paper.publication_date.desc().nullslast()
    ).limit(30).all()  # Limit to 30 most relevant papers
    
    if not topic_papers:
        return {
            "digest": f"No papers found for **{topic.name}**. Run a paper search first.",
            "highlights": [],
            "stats": {"total": 0}
        }
    
    # Prepare papers data for LLM
    papers_data = [{
        "id": str(tp.id),
        "title": paper.title,
        "abstract": paper.abstract,
        "source": paper.source,
        "relevance_score": tp.relevance_score,
        "summary": tp.summary,
        "published_date": paper.publication_date.isoformat() if paper.publication_date else None
    } for tp, paper in topic_papers]
    
    # Generate digest using LLM
    llm = get_llm_service()
    model_id = current_user.preferred_llm_model or "openai/gpt-4o-mini"
    
    try:
        result = await llm.generate_weekly_digest(
            papers=papers_data,
            topic_name=topic.name,
            topic_description=topic.description or topic.name,
            model_id=model_id
        )
        
        return {
            "digest": result.get("digest", ""),
            "highlights": result.get("highlights", []),
            "stats": result.get("stats", {}),
            "model_used": result.get("model_used", model_id),
            "papers_analyzed": len(papers_data)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate digest: {str(e)}"
        )


@router.get("/{topic_id}/trash")
def get_trashed_papers(
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all trashed (excluded) papers for a topic."""
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Get trashed papers
    topic_papers = db.query(TopicPaper, Paper).join(
        Paper, TopicPaper.paper_id == Paper.id
    ).filter(
        TopicPaper.topic_id == topic_id,
        TopicPaper.deleted_at != None
    ).order_by(
        TopicPaper.deleted_at.desc()
    ).all()
    
    return [{
        "id": str(tp.id),
        "paper_id": str(paper.id),
        "title": paper.title,
        "source": paper.source,
        "deleted_at": tp.deleted_at.isoformat() if tp.deleted_at else None,
        "days_until_permanent_delete": max(0, 30 - (datetime.utcnow() - tp.deleted_at).days) if tp.deleted_at else 30
    } for tp, paper in topic_papers]


@router.post("/{topic_id}/papers/{paper_id}/restore")
def restore_paper(
    topic_id: UUID,
    paper_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Restore a paper from trash."""
    topic = db.query(Topic).filter(
        Topic.id == topic_id,
        Topic.user_id == current_user.id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    topic_paper = db.query(TopicPaper).filter(
        TopicPaper.id == paper_id,
        TopicPaper.topic_id == topic_id
    ).first()
    
    if not topic_paper:
        raise HTTPException(status_code=404, detail="Paper not found in this topic")
    
    # Restore from trash
    topic_paper.deleted_at = None
    topic_paper.include = False  # Keep as excluded but visible
    topic_paper.reviewed_at = None  # Reset review status
    
    db.commit()
    
    return {"message": "Paper restored successfully"}
