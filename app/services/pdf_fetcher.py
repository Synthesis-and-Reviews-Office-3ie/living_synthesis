"""
PDF Fetcher Service

Fetches PDFs from various sources:
- arXiv: Direct PDF URLs (always available)
- Unpaywall: OA PDF URLs for DOI-based papers
- Publisher OA: Direct from oa_url field
"""

import httpx
import logging
import re
from typing import Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Unpaywall requires an email for API access
UNPAYWALL_EMAIL = getattr(settings, 'unpaywall_email', 'contact@example.com')

# HTTP client config
HTTP_TIMEOUT = 30.0
MAX_PDF_SIZE = 50 * 1024 * 1024  # 50 MB max


def get_arxiv_pdf_url(arxiv_id: str) -> str:
    """
    Convert arXiv ID to direct PDF URL.
    
    Handles various arXiv ID formats:
    - 2312.12345
    - arXiv:2312.12345
    - hep-th/0601001
    - http://arxiv.org/abs/2312.12345
    """
    # Clean up the ID
    arxiv_id = arxiv_id.strip()
    
    # Remove arXiv: prefix
    if arxiv_id.lower().startswith('arxiv:'):
        arxiv_id = arxiv_id[6:]
    
    # Extract ID from URL
    if 'arxiv.org' in arxiv_id:
        # Match /abs/ID or /pdf/ID
        match = re.search(r'arxiv\.org/(?:abs|pdf)/([^\s/]+)', arxiv_id)
        if match:
            arxiv_id = match.group(1)
    
    # Remove .pdf extension if present
    arxiv_id = re.sub(r'\.pdf$', '', arxiv_id)
    
    # Remove version number for consistent storage, but keep for URL
    # e.g., 2312.12345v2 -> we fetch the latest version
    
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


async def fetch_unpaywall_oa_url(doi: str) -> Optional[str]:
    """
    Query Unpaywall API to find OA PDF URL for a DOI.
    
    Returns the best available OA PDF URL, or None if not available.
    """
    if not doi:
        return None
    
    # Clean DOI
    doi = doi.strip()
    if doi.lower().startswith('https://doi.org/'):
        doi = doi[16:]
    elif doi.lower().startswith('doi:'):
        doi = doi[4:]
    
    url = f"https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}"
    
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(url)
            
            if response.status_code == 404:
                logger.debug(f"DOI not found in Unpaywall: {doi}")
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Check if open access
            if not data.get('is_oa'):
                return None
            
            # Try to get best OA location
            best_location = data.get('best_oa_location', {})
            if best_location:
                # Prefer PDF URL over landing page
                pdf_url = best_location.get('url_for_pdf')
                if pdf_url:
                    return pdf_url
                
                # Fall back to landing page (might redirect to PDF)
                url_landing = best_location.get('url')
                if url_landing:
                    return url_landing
            
            # Check other OA locations
            for location in data.get('oa_locations', []):
                pdf_url = location.get('url_for_pdf')
                if pdf_url:
                    return pdf_url
            
            return None
            
    except httpx.TimeoutException:
        logger.warning(f"Timeout querying Unpaywall for DOI: {doi}")
        return None
    except Exception as e:
        logger.warning(f"Error querying Unpaywall for DOI {doi}: {e}")
        return None


async def download_pdf(url: str) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Download PDF from URL.
    
    Returns:
        Tuple of (pdf_bytes, content_type) or (None, error_message)
    """
    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; LivingEvidenceHub/1.0; research-tool)',
                'Accept': 'application/pdf,*/*'
            }
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower()
            
            # Check if it's actually a PDF
            content = response.content
            if not content.startswith(b'%PDF'):
                # Sometimes PDFs are served with wrong content-type
                # Check first bytes for PDF magic number
                if b'%PDF' not in content[:1024]:
                    logger.warning(f"URL did not return a PDF: {url}")
                    return None, "Not a PDF file"
            
            # Check size
            if len(content) > MAX_PDF_SIZE:
                logger.warning(f"PDF too large ({len(content)} bytes): {url}")
                return None, f"PDF too large (>{MAX_PDF_SIZE // 1024 // 1024}MB)"
            
            return content, None
            
    except httpx.TimeoutException:
        return None, "Download timeout"
    except httpx.HTTPStatusError as e:
        return None, f"HTTP {e.response.status_code}"
    except Exception as e:
        logger.warning(f"Error downloading PDF from {url}: {e}")
        return None, str(e)


async def get_pdf_url_for_paper(
    source: str,
    external_id: Optional[str] = None,
    doi: Optional[str] = None,
    oa_url: Optional[str] = None
) -> Optional[str]:
    """
    Get the best PDF URL for a paper based on its source and identifiers.
    
    Priority:
    1. arXiv papers: Always use arXiv PDF URL
    2. Existing oa_url: Use if it's a PDF
    3. Unpaywall: Query for OA PDF if we have DOI
    """
    # arXiv papers always have PDFs
    if source == 'arxiv' and external_id:
        return get_arxiv_pdf_url(external_id)
    
    # Check if oa_url is already a PDF URL
    if oa_url:
        parsed = urlparse(oa_url)
        if parsed.path.lower().endswith('.pdf'):
            return oa_url
        # arXiv URLs that aren't /pdf/ can be converted
        if 'arxiv.org' in oa_url:
            if '/abs/' in oa_url:
                return oa_url.replace('/abs/', '/pdf/') + '.pdf'
    
    # Try Unpaywall for DOI-based papers
    if doi:
        unpaywall_url = await fetch_unpaywall_oa_url(doi)
        if unpaywall_url:
            return unpaywall_url
    
    # If we have an oa_url that's not obviously a PDF, try it anyway
    if oa_url:
        return oa_url
    
    return None


def is_pdf_fetchable(source: str, external_id: Optional[str] = None, doi: Optional[str] = None) -> bool:
    """
    Check if a paper is likely to have a fetchable PDF.
    
    Returns True for:
    - arXiv papers (always)
    - Papers with DOI (might have OA version)
    """
    if source == 'arxiv' and external_id:
        return True
    
    if doi:
        return True
    
    return False
