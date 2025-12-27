"""
Celery tasks for background job processing.

This module contains async tasks for:
- Running evidence searches
- LLM analysis of papers
- Newsletter generation
- Email delivery
"""

from celery import Celery
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from app.config import get_settings
from app.database import SessionLocal
from app.models import Topic, Paper, TopicPaper, Newsletter, UserTier

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    "evidence_synthesis",
    broker=settings.redis_url,
    backend=settings.redis_url
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,  # Prevent workers grabbing too many tasks
)


@celery_app.task(bind=True, max_retries=3)
def run_evidence_search(self, topic_id: str):
    """
    Run evidence search for a topic.
    
    This task:
    1. Fetches papers from configured sources (PubMed, OpenAlex, Google Scholar)
    2. Deduplicates against existing papers
    3. Pre-filters for relevance
    4. Runs LLM analysis
    5. Creates TopicPaper records for review
    """
    db = SessionLocal()
    try:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            logger.error(f"Topic {topic_id} not found")
            return {"error": "Topic not found"}
        
        logger.info(f"Starting evidence search for topic: {topic.name}")
        
        # Import pipeline components
        from src.ingestion.fetchers import fetch_pubmed, fetch_openalex, fetch_google_scholar
        from src.processing.dedupe import dedupe_records, prefilter_records
        from src.processing.llm_analysis import analyze_records
        
        all_records = []
        
        # Fetch from each configured source
        queries = topic.queries or {}
        date_from = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
        
        if queries.get("pubmed"):
            logger.info("Fetching from PubMed...")
            records = fetch_pubmed(queries["pubmed"], date_from, date_to)
            all_records.extend(records)
        
        if queries.get("openalex"):
            logger.info("Fetching from OpenAlex...")
            records = fetch_openalex(queries["openalex"], date_from, date_to)
            all_records.extend(records)
        
        if queries.get("google_scholar"):
            logger.info("Fetching from Google Scholar...")
            records = fetch_google_scholar(queries["google_scholar"], date_from, date_to)
            all_records.extend(records)
        
        logger.info(f"Fetched {len(all_records)} total records")
        
        # Deduplicate
        unique_records = dedupe_records(all_records)
        logger.info(f"After deduplication: {len(unique_records)} records")
        
        # Pre-filter (keyword-based)
        keywords = topic.description.split() if topic.description else []
        filtered_records = prefilter_records(unique_records, keywords)
        logger.info(f"After pre-filtering: {len(filtered_records)} records")
        
        # LLM analysis
        if filtered_records:
            analyzed = analyze_records(filtered_records, topic.description or topic.name)
            logger.info(f"Analyzed {len(analyzed)} records")
            
            # Save to database
            for record in analyzed:
                # Check if paper exists
                paper = db.query(Paper).filter(Paper.doi == record.get("doi")).first()
                if not paper:
                    paper = Paper(
                        doi=record.get("doi"),
                        title=record.get("title"),
                        authors=record.get("authors"),
                        abstract=record.get("abstract"),
                        publication_date=record.get("publication_date"),
                        source=record.get("source"),
                        url=record.get("url"),
                        raw_data=record
                    )
                    db.add(paper)
                    db.flush()
                
                # Create TopicPaper link
                existing = db.query(TopicPaper).filter(
                    TopicPaper.topic_id == topic.id,
                    TopicPaper.paper_id == paper.id
                ).first()
                
                if not existing:
                    topic_paper = TopicPaper(
                        topic_id=topic.id,
                        paper_id=paper.id,
                        relevance_score=record.get("relevance_score"),
                        llm_analysis=record.get("analysis")
                    )
                    db.add(topic_paper)
            
            db.commit()
        
        # Update topic's last_run timestamp
        topic.last_run = datetime.utcnow()
        db.commit()
        
        return {
            "status": "success",
            "topic_id": topic_id,
            "records_found": len(all_records),
            "records_unique": len(unique_records),
            "records_analyzed": len(filtered_records)
        }
        
    except Exception as e:
        logger.exception(f"Error in evidence search for topic {topic_id}")
        self.retry(exc=e, countdown=60)  # Retry after 1 minute
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def generate_newsletter_task(self, topic_id: str):
    """
    Generate newsletter for a topic.
    
    This task:
    1. Gets approved papers
    2. Renders HTML using Jinja2
    3. Uploads to S3 (optional)
    4. Creates Newsletter record
    """
    db = SessionLocal()
    try:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            return {"error": "Topic not found"}
        
        # Get approved papers
        approved = db.query(TopicPaper).filter(
            TopicPaper.topic_id == topic.id,
            TopicPaper.include == True,
            TopicPaper.reviewed_at != None
        ).all()
        
        if not approved:
            return {"error": "No approved papers"}
        
        # Prepare paper data for template
        papers_data = []
        for tp in approved:
            paper = tp.paper
            papers_data.append({
                "title": paper.title,
                "authors": paper.authors,
                "abstract": paper.abstract,
                "url": paper.url,
                "doi": paper.doi,
                "relevance_score": tp.relevance_score,
                "analysis": tp.llm_analysis
            })
        
        # Render newsletter
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template("newsletter.html")
        
        html_content = template.render(
            topic_name=topic.name,
            papers=papers_data,
            generation_date=datetime.utcnow().strftime("%Y-%m-%d")
        )
        
        # Create newsletter record
        newsletter = Newsletter(
            topic_id=topic.id,
            title=f"{topic.name} - {datetime.utcnow().strftime('%B %d, %Y')}",
            html_content=html_content,
            paper_count=len(papers_data),
            period_start=datetime.utcnow() - timedelta(days=7),
            period_end=datetime.utcnow()
        )
        db.add(newsletter)
        db.commit()
        
        logger.info(f"Newsletter generated for topic {topic.name}")
        
        return {
            "status": "success",
            "newsletter_id": str(newsletter.id),
            "paper_count": len(papers_data)
        }
        
    except Exception as e:
        logger.exception(f"Error generating newsletter for topic {topic_id}")
        self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task
def send_newsletter_email(newsletter_id: str):
    """Send newsletter via email to subscribers."""
    db = SessionLocal()
    try:
        newsletter = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
        if not newsletter:
            return {"error": "Newsletter not found"}
        
        # Get topic subscribers
        from app.models import EmailSubscriber
        subscribers = db.query(EmailSubscriber).filter(
            EmailSubscriber.topic_id == newsletter.topic_id,
            EmailSubscriber.is_active == True,
            EmailSubscriber.confirmed == True
        ).all()
        
        # Send emails (using Resend or similar)
        # This is a placeholder - implement with your email provider
        sent_count = 0
        for sub in subscribers:
            try:
                # send_email(sub.email, newsletter.title, newsletter.html_content)
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {sub.email}: {e}")
        
        newsletter.sent_at = datetime.utcnow()
        db.commit()
        
        return {"status": "success", "sent_count": sent_count}
        
    finally:
        db.close()


# Periodic task scheduling
celery_app.conf.beat_schedule = {
    "run-daily-topics": {
        "task": "app.tasks.run_scheduled_searches",
        "schedule": 86400.0,  # Every 24 hours
    },
    "run-weekly-topics": {
        "task": "app.tasks.run_scheduled_searches",
        "schedule": 604800.0,  # Every 7 days
        "kwargs": {"frequency": "weekly"}
    }
}


@celery_app.task
def run_scheduled_searches(frequency: str = "daily"):
    """Run evidence searches for all active topics with matching frequency."""
    db = SessionLocal()
    try:
        topics = db.query(Topic).filter(
            Topic.is_active == True,
            Topic.frequency == frequency
        ).all()
        
        for topic in topics:
            run_evidence_search.delay(str(topic.id))
        
        return {"scheduled": len(topics)}
    finally:
        db.close()
