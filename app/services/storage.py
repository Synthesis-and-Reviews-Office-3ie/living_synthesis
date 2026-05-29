"""
S3/R2 storage service for newsletter files.

Supports:
- AWS S3
- Cloudflare R2 (S3-compatible)
- MinIO (local development)
"""

import boto3
from botocore.config import Config
import logging
from typing import Optional
from datetime import datetime
import uuid

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize S3 client
_s3_client = None


def get_s3_client():
    """Get or create S3 client."""
    global _s3_client
    
    if _s3_client is None:
        if not settings.s3_access_key or not settings.s3_secret_key:
            logger.warning("S3 credentials not configured")
            return None
        
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,  # For R2/MinIO
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "adaptive"}
            )
        )
    
    return _s3_client


def upload_newsletter_html(
    html_content: str,
    topic_id: str,
    newsletter_id: str,
    topic_name: Optional[str] = None
) -> Optional[str]:
    """
    Upload newsletter HTML to S3/R2.
    
    Args:
        html_content: The HTML content to upload
        topic_id: UUID of the topic
        newsletter_id: UUID of the newsletter
        topic_name: Optional topic name for the path
    
    Returns:
        Public URL of the uploaded file, or None if upload failed
    """
    client = get_s3_client()
    if not client:
        logger.warning("S3 client not available. Newsletter not uploaded.")
        return None
    
    try:
        # Generate key path
        date_prefix = datetime.utcnow().strftime("%Y/%m")
        safe_name = (topic_name or "topic").replace(" ", "-").lower()[:50]
        key = f"newsletters/{date_prefix}/{safe_name}/{newsletter_id}.html"
        
        # Upload
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=html_content.encode("utf-8"),
            ContentType="text/html",
            CacheControl="public, max-age=31536000",  # 1 year cache (immutable)
            Metadata={
                "topic_id": str(topic_id),
                "newsletter_id": str(newsletter_id)
            }
        )
        
        # Generate public URL
        if settings.s3_endpoint:
            # R2/MinIO custom endpoint
            url = f"{settings.s3_endpoint}/{settings.s3_bucket}/{key}"
        else:
            # Standard S3
            url = f"https://{settings.s3_bucket}.s3.amazonaws.com/{key}"
        
        logger.info(f"Newsletter uploaded to {url}")
        return url
        
    except Exception as e:
        logger.exception(f"Failed to upload newsletter: {e}")
        return None


def upload_file(
    content: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
    folder: str = "uploads"
) -> Optional[str]:
    """
    Upload a generic file to S3/R2.
    
    Args:
        content: File content as bytes
        filename: Original filename
        content_type: MIME type
        folder: Folder prefix in bucket
    
    Returns:
        Public URL of the uploaded file
    """
    client = get_s3_client()
    if not client:
        return None
    
    try:
        # Generate unique key
        ext = filename.split(".")[-1] if "." in filename else ""
        unique_id = str(uuid.uuid4())[:8]
        key = f"{folder}/{unique_id}-{filename}"
        
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=content,
            ContentType=content_type
        )
        
        if settings.s3_endpoint:
            url = f"{settings.s3_endpoint}/{settings.s3_bucket}/{key}"
        else:
            url = f"https://{settings.s3_bucket}.s3.amazonaws.com/{key}"
        
        return url
        
    except Exception as e:
        logger.exception(f"Failed to upload file: {e}")
        return None


def delete_file(key: str) -> bool:
    """Delete a file from S3/R2."""
    client = get_s3_client()
    if not client:
        return False
    
    try:
        client.delete_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except Exception as e:
        logger.exception(f"Failed to delete file: {e}")
        return False


def generate_presigned_url(key: str, expires_in: int = 3600) -> Optional[str]:
    """
    Generate a presigned URL for temporary access.
    
    Args:
        key: S3 object key
        expires_in: URL expiration in seconds (default 1 hour)
    
    Returns:
        Presigned URL
    """
    client = get_s3_client()
    if not client:
        return None
    
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires_in
        )
        return url
    except Exception as e:
        logger.exception(f"Failed to generate presigned URL: {e}")
        return None


def upload_pdf(
    pdf_content: bytes,
    paper_id: str,
    source: str,
    external_id: Optional[str] = None
) -> Optional[dict]:
    """
    Upload a paper PDF to S3/R2.
    
    Args:
        pdf_content: PDF file content as bytes
        paper_id: UUID of the paper
        source: Paper source (arxiv, pubmed, etc.)
        external_id: External ID (arXiv ID, DOI, etc.)
    
    Returns:
        Dict with {url, key, size_bytes} or None if upload failed
    """
    client = get_s3_client()
    if not client:
        logger.warning("S3 client not available. PDF not uploaded.")
        return None
    
    try:
        # Generate key path: pdfs/{source}/{paper_id}.pdf
        # Using paper_id ensures uniqueness
        safe_source = (source or "unknown").lower()[:20]
        key = f"pdfs/{safe_source}/{paper_id}.pdf"
        
        # Upload with appropriate metadata
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=pdf_content,
            ContentType="application/pdf",
            CacheControl="public, max-age=31536000",  # 1 year cache (immutable)
            Metadata={
                "paper_id": str(paper_id),
                "source": source or "",
                "external_id": external_id or ""
            }
        )
        
        # Generate URL
        if settings.s3_public_url:
            # Custom public URL (e.g., CDN)
            url = f"{settings.s3_public_url}/{key}"
        elif settings.s3_endpoint:
            # R2/MinIO custom endpoint
            url = f"{settings.s3_endpoint}/{settings.s3_bucket}/{key}"
        else:
            # Standard S3
            url = f"https://{settings.s3_bucket}.s3.amazonaws.com/{key}"
        
        logger.info(f"PDF uploaded to {key} ({len(pdf_content)} bytes)")
        
        return {
            "url": url,
            "key": key,
            "size_bytes": len(pdf_content)
        }
        
    except Exception as e:
        logger.exception(f"Failed to upload PDF: {e}")
        return None


def get_pdf(key: str) -> Optional[bytes]:
    """
    Download a PDF from S3/R2.
    
    Args:
        key: S3 object key
    
    Returns:
        PDF content as bytes, or None if not found
    """
    client = get_s3_client()
    if not client:
        return None
    
    try:
        response = client.get_object(Bucket=settings.s3_bucket, Key=key)
        return response['Body'].read()
    except client.exceptions.NoSuchKey:
        logger.warning(f"PDF not found: {key}")
        return None
    except Exception as e:
        logger.exception(f"Failed to get PDF: {e}")
        return None


def pdf_exists(key: str) -> bool:
    """Check if a PDF exists in S3/R2."""
    client = get_s3_client()
    if not client:
        return False
    
    try:
        client.head_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except:
        return False

