"""
AI-powered routes: Query generation, analysis, etc.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
import json

from app.database import get_db
from app.models import User
from app.auth import get_current_user
from app.services.llm import LLMService

router = APIRouter(prefix="/ai", tags=["AI"])


class QueryGenerationRequest(BaseModel):
    """Request to generate search queries from a description."""
    description: str
    sources: Optional[List[str]] = None  # If None, generate for all sources


class QueryGenerationResponse(BaseModel):
    """Generated queries for each data source."""
    queries: Dict[str, str]
    explanation: str


QUERY_GENERATION_PROMPT = """You are an expert in academic literature search and systematic review methodology.

Given a research topic description, generate optimized search queries for each of the following academic databases:
- OpenAlex: Uses a simple search syntax. Use AND/OR operators and quotes for exact phrases. Example: "machine learning" AND "climate change" AND "health"
- PubMed: Uses MeSH terms and field tags like [Title/Abstract], [MeSH Terms]. Use AND/OR/NOT operators.
- arXiv: Use the SAME Boolean syntax as OpenAlex. Use AND/OR operators and quotes for exact phrases. The arXiv API supports this. Example: "machine learning" AND "climate change" AND "health"
- Google Scholar: Use the SAME Boolean syntax as OpenAlex. Use AND/OR operators and quotes for exact phrases. Example: "machine learning" AND "climate change" AND "health"

IMPORTANT: arXiv and Google Scholar queries should be IDENTICAL or very similar to the OpenAlex query. They all support Boolean AND/OR and quoted phrases.

Guidelines:
1. Use appropriate field tags and syntax for each database
2. Include relevant synonyms and related terms
3. Balance sensitivity (finding all relevant papers) with specificity (avoiding irrelevant ones)
4. Be INCLUSIVE - do NOT add exclusion terms like -review or -NOT unless the user explicitly asks to exclude something
5. Generate queries that match what the user described - don't add filters they didn't request
6. arXiv and Google Scholar should have the SAME query structure as OpenAlex

User's research topic description:
{description}

Respond in this exact JSON format:
{{
  "queries": {{
    "openalex": "your OpenAlex query here",
    "pubmed": "your PubMed query here", 
    "arxiv": "SAME as OpenAlex - use Boolean AND/OR and quotes",
    "google_scholar": "SAME as OpenAlex - use Boolean AND/OR and quotes"
  }},
  "explanation": "Brief explanation of the search strategy and key terms used"
}}

Only output the JSON, nothing else."""


@router.post("/generate-queries", response_model=QueryGenerationResponse)
async def generate_queries(
    request: QueryGenerationRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate optimized search queries from a plain language description.
    Uses LLM to create database-specific queries for OpenAlex, PubMed, and arXiv.
    """
    if not request.description or len(request.description.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Please provide a more detailed description (at least 10 characters)"
        )
    
    llm_service = LLMService()
    
    prompt = QUERY_GENERATION_PROMPT.format(description=request.description)
    
    try:
        result = await llm_service.generate(
            prompt=prompt,
            model_id="gpt-4o-mini",  # Use fast model for query generation
            temperature=0.3,  # Lower temperature for more consistent output
            max_tokens=1024,
        )
        
        # Parse the JSON response
        content = result["content"].strip()
        
        # Handle potential markdown code blocks
        if content.startswith("```"):
            # Extract JSON from code block
            lines = content.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```") and not in_json:
                    in_json = True
                    continue
                elif line.startswith("```") and in_json:
                    break
                elif in_json:
                    json_lines.append(line)
            content = "\n".join(json_lines)
        
        parsed = json.loads(content)
        
        return QueryGenerationResponse(
            queries=parsed.get("queries", {}),
            explanation=parsed.get("explanation", "Queries generated successfully.")
        )
        
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse LLM response: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate queries: {str(e)}"
        )


class QueryTestRequest(BaseModel):
    """Request to test a query against a data source."""
    query: str
    source: str  # openalex, pubmed, arxiv
    limit: int = 5


class QueryTestResult(BaseModel):
    """Result of testing a query."""
    source: str
    query: str
    result_count: int
    sample_papers: List[dict]
    error: Optional[str] = None


@router.post("/test-query", response_model=QueryTestResult)
async def test_query(
    request: QueryTestRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Test a search query against a specific data source.
    Returns a sample of results to help users validate their query.
    """
    import sys
    sys.path.insert(0, '.')
    
    from src.ingestion.fetchers import fetch_openalex, fetch_pubmed, fetch_arxiv, fetch_google_scholar
    
    source = request.source.lower()
    query = request.query
    
    try:
        papers = []
        
        if source == "openalex":
            papers = fetch_openalex(query, max_results=request.limit)
        elif source == "pubmed":
            papers = fetch_pubmed(query, max_results=request.limit)
        elif source == "arxiv":
            papers = fetch_arxiv(query, max_results=request.limit)
        elif source == "google_scholar":
            papers = fetch_google_scholar(query, max_results=request.limit)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown source: {source}")
        
        # Simplify paper data for response
        sample_papers = [
            {
                "title": p.get("title", "Untitled"),
                "authors": p.get("authors", [])[:3],  # First 3 authors
                "source": p.get("source"),
                "published_date": p.get("publication_date"),
                "doi": p.get("doi"),
            }
            for p in papers[:request.limit]
        ]
        
        return QueryTestResult(
            source=source,
            query=query,
            result_count=len(papers),
            sample_papers=sample_papers,
        )
        
    except Exception as e:
        return QueryTestResult(
            source=source,
            query=query,
            result_count=0,
            sample_papers=[],
            error=str(e),
        )
