"""
Papers API Router

Endpoints for paper management and PDF access.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from typing import Optional
import logging
import io

from app.database import get_db
from app.models import Paper, User
from app.auth import get_current_user
from app.services import storage
from app.services.pdf_fetcher import (
    get_pdf_url_for_paper,
    download_pdf,
    is_pdf_fetchable
)

router = APIRouter(prefix="/papers", tags=["papers"])
logger = logging.getLogger(__name__)


@router.get("/{paper_id}")
def get_paper(
    paper_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get paper details."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    return {
        "id": str(paper.id),
        "title": paper.title,
        "abstract": paper.abstract,
        "authors": paper.authors,
        "doi": paper.doi,
        "external_id": paper.external_id,
        "source": paper.source,
        "publication_date": paper.publication_date.isoformat() if paper.publication_date else None,
        "is_oa": paper.is_oa,
        "oa_url": paper.oa_url,
        "pdf_url": paper.pdf_url,
        "pdf_available": paper.pdf_url is not None or is_pdf_fetchable(paper.source, paper.external_id, paper.doi),
        "created_at": paper.created_at.isoformat() if paper.created_at else None
    }


@router.get("/{paper_id}/pdf")
async def get_paper_pdf(
    paper_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get PDF for a paper.
    
    If PDF is already stored, returns a redirect to the stored URL.
    If PDF needs to be fetched, fetches it and stores for future use.
    """
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # If PDF is already stored, generate presigned URL
    if paper.pdf_s3_key and storage.pdf_exists(paper.pdf_s3_key):
        presigned_url = storage.generate_presigned_url(paper.pdf_s3_key, expires_in=3600)
        if presigned_url:
            return {"pdf_url": presigned_url, "source": "cached"}
    
    # Try to fetch PDF
    pdf_source_url = await get_pdf_url_for_paper(
        source=paper.source,
        external_id=paper.external_id,
        doi=paper.doi,
        oa_url=paper.oa_url
    )
    
    if not pdf_source_url:
        raise HTTPException(status_code=404, detail="PDF not available for this paper")
    
    # Download the PDF
    pdf_content, error = await download_pdf(pdf_source_url)
    
    if not pdf_content:
        raise HTTPException(status_code=502, detail=f"Failed to fetch PDF: {error}")
    
    # Store PDF in background
    background_tasks.add_task(
        store_pdf_async,
        paper_id=str(paper.id),
        pdf_content=pdf_content,
        source=paper.source,
        external_id=paper.external_id,
        db=db
    )
    
    # Return PDF content directly
    return StreamingResponse(
        io.BytesIO(pdf_content),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{paper_id}.pdf"',
            "Cache-Control": "public, max-age=86400"  # 1 day cache
        }
    )


@router.get("/{paper_id}/pdf/url")
async def get_paper_pdf_url(
    paper_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the PDF URL for a paper (without downloading).
    
    Returns either:
    - stored_url: URL to our cached PDF
    - source_url: Original source URL (arXiv, publisher, etc.)
    """
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # If PDF is already stored
    if paper.pdf_s3_key and storage.pdf_exists(paper.pdf_s3_key):
        presigned_url = storage.generate_presigned_url(paper.pdf_s3_key, expires_in=3600)
        if presigned_url:
            return {
                "pdf_url": presigned_url,
                "source": "cached",
                "size_bytes": paper.pdf_size_bytes
            }
    
    # Get source URL
    pdf_source_url = await get_pdf_url_for_paper(
        source=paper.source,
        external_id=paper.external_id,
        doi=paper.doi,
        oa_url=paper.oa_url
    )
    
    if pdf_source_url:
        return {
            "pdf_url": pdf_source_url,
            "source": paper.source or "external",
            "size_bytes": None
        }
    
    raise HTTPException(status_code=404, detail="PDF not available for this paper")


@router.post("/{paper_id}/pdf/fetch")
async def fetch_and_store_pdf(
    paper_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Explicitly fetch and store a PDF for a paper.
    
    Useful for pre-caching PDFs for screening.
    """
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Check if already stored
    if paper.pdf_s3_key and storage.pdf_exists(paper.pdf_s3_key):
        presigned_url = storage.generate_presigned_url(paper.pdf_s3_key, expires_in=3600)
        return {
            "status": "already_cached",
            "pdf_url": presigned_url,
            "size_bytes": paper.pdf_size_bytes
        }
    
    # Get source URL
    pdf_source_url = await get_pdf_url_for_paper(
        source=paper.source,
        external_id=paper.external_id,
        doi=paper.doi,
        oa_url=paper.oa_url
    )
    
    if not pdf_source_url:
        raise HTTPException(status_code=404, detail="PDF not available for this paper")
    
    # Download
    pdf_content, error = await download_pdf(pdf_source_url)
    
    if not pdf_content:
        raise HTTPException(status_code=502, detail=f"Failed to fetch PDF: {error}")
    
    # Store
    result = storage.upload_pdf(
        pdf_content=pdf_content,
        paper_id=str(paper.id),
        source=paper.source,
        external_id=paper.external_id
    )
    
    if not result:
        raise HTTPException(status_code=500, detail="Failed to store PDF")
    
    # Update paper record
    paper.pdf_url = result["url"]
    paper.pdf_s3_key = result["key"]
    paper.pdf_size_bytes = result["size_bytes"]
    paper.pdf_fetched_at = datetime.utcnow()
    db.commit()
    
    return {
        "status": "fetched",
        "pdf_url": result["url"],
        "size_bytes": result["size_bytes"]
    }


def store_pdf_async(
    paper_id: str,
    pdf_content: bytes,
    source: str,
    external_id: Optional[str],
    db: Session
):
    """Background task to store PDF after serving it."""
    try:
        result = storage.upload_pdf(
            pdf_content=pdf_content,
            paper_id=paper_id,
            source=source,
            external_id=external_id
        )
        
        if result:
            # Update paper record
            paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if paper:
                paper.pdf_url = result["url"]
                paper.pdf_s3_key = result["key"]
                paper.pdf_size_bytes = result["size_bytes"]
                paper.pdf_fetched_at = datetime.utcnow()
                db.commit()
                logger.info(f"PDF stored for paper {paper_id}")
    except Exception as e:
        logger.exception(f"Failed to store PDF async for paper {paper_id}: {e}")
