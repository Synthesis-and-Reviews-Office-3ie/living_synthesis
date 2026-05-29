"""
LLM Service - Multi-provider support for newsletter generation.

Supports:
- OpenRouter (unified access to GPT-4, Claude, Gemini, etc.)
- OpenAI Direct
- Anthropic Claude
- Google Gemini  
- Perplexity (Pro feature - research-focused with citations)

Users can select their preferred model per topic.
"""

from typing import Optional, Literal
from enum import Enum
import httpx
from pydantic import BaseModel
from app.config import get_settings

settings = get_settings()


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    PERPLEXITY = "perplexity"


class LLMModel(BaseModel):
    """Available LLM models with metadata."""
    id: str
    name: str
    provider: LLMProvider
    description: str
    tier_required: Literal["free", "pro", "team"]
    context_window: int
    supports_citations: bool = False
    
    
# Available models - users can choose from these
AVAILABLE_MODELS = [
    # Free tier models
    LLMModel(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        provider=LLMProvider.OPENROUTER,
        description="Fast and affordable, great for most tasks",
        tier_required="free",
        context_window=128000,
    ),
    LLMModel(
        id="claude-3-haiku",
        name="Claude 3 Haiku",
        provider=LLMProvider.OPENROUTER,
        description="Fast, affordable Claude model",
        tier_required="free",
        context_window=200000,
    ),
    LLMModel(
        id="gemini-1.5-flash",
        name="Gemini 1.5 Flash",
        provider=LLMProvider.OPENROUTER,
        description="Google's fast model with large context",
        tier_required="free",
        context_window=1000000,
    ),
    
    # Pro tier models
    LLMModel(
        id="gpt-4o",
        name="GPT-4o",
        provider=LLMProvider.OPENROUTER,
        description="OpenAI's flagship model, excellent reasoning",
        tier_required="pro",
        context_window=128000,
    ),
    LLMModel(
        id="claude-3-5-sonnet",
        name="Claude 3.5 Sonnet",
        provider=LLMProvider.OPENROUTER,
        description="Best for nuanced analysis and writing",
        tier_required="pro",
        context_window=200000,
    ),
    LLMModel(
        id="gemini-1.5-pro",
        name="Gemini 1.5 Pro",
        provider=LLMProvider.OPENROUTER,
        description="Google's pro model with huge context",
        tier_required="pro",
        context_window=2000000,
    ),
    LLMModel(
        id="perplexity-sonar-pro",
        name="Perplexity Sonar Pro",
        provider=LLMProvider.PERPLEXITY,
        description="Research-focused with real-time citations",
        tier_required="pro",
        context_window=128000,
        supports_citations=True,
    ),
    
    # Team tier models
    LLMModel(
        id="claude-3-opus",
        name="Claude 3 Opus",
        provider=LLMProvider.OPENROUTER,
        description="Most capable Claude, best for complex tasks",
        tier_required="team",
        context_window=200000,
    ),
    LLMModel(
        id="gpt-4-turbo",
        name="GPT-4 Turbo",
        provider=LLMProvider.OPENROUTER,
        description="Latest GPT-4 with vision capabilities",
        tier_required="team",
        context_window=128000,
    ),
]


def get_available_models(user_tier: str = "free") -> list[LLMModel]:
    """Get models available for a user's tier."""
    tier_order = {"free": 0, "pro": 1, "team": 2}
    user_level = tier_order.get(user_tier, 0)
    
    return [
        model for model in AVAILABLE_MODELS
        if tier_order.get(model.tier_required, 0) <= user_level
    ]


def get_available_models_for_user(user_tier: str = "free") -> list[dict]:
    """Get models available for a user's tier in API-friendly format."""
    models = get_available_models(user_tier)
    return [
        {
            "id": model.id,
            "name": model.name,
            "description": model.description,
            "tier": model.tier_required,
            "provider": model.provider.value,
            "supports_citations": model.supports_citations,
        }
        for model in models
    ]


def get_model_by_id(model_id: str) -> Optional[LLMModel]:
    """Get a model by its ID."""
    for model in AVAILABLE_MODELS:
        if model.id == model_id:
            return model
    return None


class LLMService:
    """Multi-provider LLM service."""
    
    def __init__(self):
        self.openrouter_key = settings.openrouter_api_key or settings.openai_api_key
        self.perplexity_key = settings.perplexity_api_key
        self.anthropic_key = settings.anthropic_api_key
        self.google_key = settings.google_ai_api_key
    
    async def generate(
        self,
        prompt: str,
        model_id: str = "gpt-4o-mini",
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> dict:
        """
        Generate text using the specified model.
        
        Returns:
            dict with 'content', 'model', 'usage', and optionally 'citations'
        """
        model = get_model_by_id(model_id)
        if not model:
            model = AVAILABLE_MODELS[0]  # Default to first model
        
        if model.provider == LLMProvider.PERPLEXITY:
            return await self._generate_perplexity(prompt, model_id, system_prompt, max_tokens, temperature)
        else:
            return await self._generate_openrouter(prompt, model_id, system_prompt, max_tokens, temperature)
    
    async def _generate_openrouter(
        self,
        prompt: str,
        model_id: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> dict:
        """Generate using OpenRouter (supports most models)."""
        if not self.openrouter_key:
            raise ValueError("OpenRouter API key not configured")
        
        # Map model IDs to OpenRouter format
        model_mapping = {
            "gpt-4o": "openai/gpt-4o",
            "gpt-4o-mini": "openai/gpt-4o-mini",
            "gpt-4-turbo": "openai/gpt-4-turbo",
            "claude-3-5-sonnet": "anthropic/claude-3.5-sonnet",
            "claude-3-haiku": "anthropic/claude-3-haiku",
            "claude-3-opus": "anthropic/claude-3-opus",
            "gemini-1.5-pro": "google/gemini-pro-1.5",
            "gemini-1.5-flash": "google/gemini-flash-1.5",
        }
        
        openrouter_model = model_mapping.get(model_id, f"openai/{model_id}")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": settings.frontend_url,
                    "X-Title": "Living Synthesis",
                },
                json={
                    "model": openrouter_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
        
        return {
            "content": data["choices"][0]["message"]["content"],
            "model": model_id,
            "usage": data.get("usage", {}),
        }
    
    async def _generate_perplexity(
        self,
        prompt: str,
        model_id: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> dict:
        """
        Generate using Perplexity API.
        Returns content with citations for research-focused queries.
        """
        if not self.perplexity_key:
            raise ValueError("Perplexity API key not configured")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.perplexity_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar-pro",  # Best for research
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "return_citations": True,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
        
        result = {
            "content": data["choices"][0]["message"]["content"],
            "model": "perplexity-sonar-pro",
            "usage": data.get("usage", {}),
        }
        
        # Include citations if available
        if "citations" in data:
            result["citations"] = data["citations"]
        
        return result
    
    async def analyze_paper(
        self,
        title: str,
        abstract: str,
        model_id: str = "gpt-4o-mini",
    ) -> dict:
        """
        Analyze a research paper for relevance and generate a summary.
        """
        system_prompt = """You are an expert research analyst specializing in evidence synthesis.
Analyze the provided paper and return a JSON response with:
- relevance_score: 1-10 rating of relevance to evidence synthesis/systematic reviews
- summary: 2-3 sentence summary of key findings
- methodology: Brief description of the method used
- implications: Key implications for practitioners
- tags: List of relevant tags/keywords"""

        prompt = f"""Analyze this research paper:

Title: {title}

Abstract: {abstract}

Provide your analysis as JSON."""

        result = await self.generate(
            prompt=prompt,
            model_id=model_id,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temperature for analysis
        )
        
        return result
    
    async def generate_newsletter_section(
        self,
        papers: list[dict],
        topic_name: str,
        model_id: str = "gpt-4o-mini",
    ) -> str:
        """
        Generate a newsletter section summarizing multiple papers.
        """
        system_prompt = f"""You are a scientific newsletter writer for "{topic_name}".
Write engaging, informative summaries of research papers for busy professionals.
Use clear language, highlight practical implications, and maintain scientific accuracy.
Format with markdown: use headers, bullet points, and bold for emphasis."""

        papers_text = "\n\n".join([
            f"**{p.get('title', 'Untitled')}**\n{p.get('abstract', 'No abstract')}"
            for p in papers[:10]  # Limit to 10 papers per section
        ])

        prompt = f"""Create a newsletter section summarizing these papers:

{papers_text}

Write an engaging summary that:
1. Groups papers by theme if appropriate
2. Highlights key findings and implications
3. Notes any methodological innovations
4. Suggests practical applications"""

        result = await self.generate(
            prompt=prompt,
            model_id=model_id,
            system_prompt=system_prompt,
            temperature=0.7,
        )
        
        return result["content"]

    async def score_relevance(
        self,
        paper_title: str,
        paper_abstract: str,
        topic_name: str,
        topic_description: str,
        model_id: str = "gpt-4o-mini",
    ) -> dict:
        """
        Score a paper's relevance to a specific topic.
        
        Returns:
            dict with 'score' (0-10), 'reason' (one-line explanation), 'keep' (bool)
        """
        system_prompt = """You are an expert research screener for systematic reviews.
Your job is to quickly assess if a paper is relevant to a specific research topic.

IMPORTANT: Be strict. Only high-relevance papers should score above 5.
Papers that match keywords but are about different subjects should score low.

Respond with ONLY valid JSON, no markdown:
{"score": <0-10>, "reason": "<one-line explanation>", "keep": <true/false>}

Score guide:
- 0-2: Completely irrelevant (wrong field, wrong population, wrong concept)
- 3-4: Tangentially related (shares keywords but different focus)
- 5-6: Moderately relevant (related topic but not core focus)
- 7-8: Highly relevant (directly addresses the topic)
- 9-10: Perfect match (exactly what the researcher is looking for)

Set "keep": true only for scores >= 4."""

        prompt = f"""Research Topic: {topic_name}
Topic Description: {topic_description}

Paper to evaluate:
Title: {paper_title}
Abstract: {paper_abstract[:1500] if paper_abstract else "No abstract available"}

Is this paper relevant to the research topic? Score 0-10 and explain briefly."""

        try:
            result = await self.generate(
                prompt=prompt,
                model_id=model_id,
                system_prompt=system_prompt,
                temperature=0.1,  # Very low temperature for consistent scoring
                max_tokens=200,
            )
            
            import json
            import re
            content = result.get("content", "").strip()
            
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', content)
            if json_match:
                parsed = json.loads(json_match.group())
                score = float(parsed.get("score", 5))
                score = max(0, min(10, score))  # Clamp to 0-10
                return {
                    "score": score,
                    "reason": parsed.get("reason", ""),
                    "keep": parsed.get("keep", score >= 4)
                }
            else:
                # Fallback: assume moderately relevant
                return {"score": 5, "reason": "Could not parse LLM response", "keep": True}
                
        except Exception as e:
            print(f"Error scoring relevance: {e}")
            # On error, keep the paper but mark as unscored
            return {"score": 5, "reason": f"Scoring error: {str(e)[:50]}", "keep": True}

    async def batch_score_relevance(
        self,
        papers: list[dict],
        topic_name: str,
        topic_description: str,
        model_id: str = "gpt-4o-mini",
    ) -> list[dict]:
        """
        Score multiple papers for relevance in a single prompt (more efficient).
        
        Args:
            papers: List of dicts with 'id', 'title', 'abstract'
            topic_name: Name of the research topic
            topic_description: Description of what the researcher is looking for
            
        Returns:
            List of dicts with 'id', 'score', 'reason', 'keep'
        """
        if not papers:
            return []
        
        # Limit batch size to avoid context overflow
        batch = papers[:20]
        
        system_prompt = """You are an expert research screener for systematic reviews.
Score each paper's relevance to the research topic on a 0-10 scale.

IMPORTANT: Be strict. Papers matching keywords but about different subjects score LOW.

Respond with ONLY a JSON array, no markdown:
[{"id": "paper_id", "score": 0-10, "reason": "brief explanation", "keep": true/false}, ...]

Score guide:
- 0-2: Wrong field/population/concept
- 3-4: Shares keywords but different focus  
- 5-6: Related but not core focus
- 7-8: Directly addresses topic
- 9-10: Perfect match

Set "keep": true only for scores >= 4."""

        papers_text = "\n\n".join([
            f"[{p.get('id', i)}] {p.get('title', 'Untitled')}\n{(p.get('abstract') or 'No abstract')[:500]}"
            for i, p in enumerate(batch)
        ])

        prompt = f"""Research Topic: {topic_name}
Description: {topic_description}

Papers to evaluate:
{papers_text}

Score each paper's relevance (0-10) to the research topic."""

        try:
            result = await self.generate(
                prompt=prompt,
                model_id=model_id,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=2000,
            )
            
            import json
            import re
            content = result.get("content", "").strip()
            
            # Try to extract JSON array from response
            # Remove markdown code blocks if present
            content = re.sub(r'```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```', '', content)
            
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                parsed = json.loads(json_match.group())
                # Normalize scores and ensure all fields present
                results = []
                for item in parsed:
                    score = float(item.get("score", 5))
                    score = max(0, min(10, score))
                    results.append({
                        "id": str(item.get("id", "")),
                        "score": score,
                        "reason": item.get("reason", ""),
                        "keep": item.get("keep", score >= 4)
                    })
                return results
            else:
                # Fallback: keep all with moderate score
                return [{"id": str(p.get("id", i)), "score": 5, "reason": "Parse error", "keep": True} 
                        for i, p in enumerate(batch)]
                
        except Exception as e:
            print(f"Error in batch relevance scoring: {e}")
            return [{"id": str(p.get("id", i)), "score": 5, "reason": "Scoring error", "keep": True} 
                    for i, p in enumerate(batch)]

    async def generate_weekly_digest(
        self,
        papers: list[dict],
        topic_name: str,
        topic_description: str,
        model_id: str = "gpt-4o-mini",
    ) -> dict:
        """
        Generate a weekly digest narrative summarizing new papers for a topic.
        
        Args:
            papers: List of paper dicts with title, abstract, source, relevance_score, summary
            topic_name: Name of the research topic
            topic_description: Description of what the topic covers
            model_id: LLM model to use
            
        Returns:
            dict with 'digest' (markdown narrative), 'highlights' (list), 'stats' (dict)
        """
        if not papers:
            return {
                "digest": f"No new papers found for **{topic_name}** this period.",
                "highlights": [],
                "stats": {"total": 0, "high_relevance": 0, "sources": {}}
            }
        
        # Compute stats
        high_relevance = [p for p in papers if (p.get("relevance_score") or 0) >= 7]
        sources = {}
        for p in papers:
            src = p.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1
        
        # Prepare papers text for LLM
        papers_text = "\n\n".join([
            f"[{i+1}] **{p.get('title', 'Untitled')}** (Score: {p.get('relevance_score', 'N/A')}/10, Source: {p.get('source', 'unknown')})\n"
            f"Abstract: {(p.get('abstract') or 'No abstract')[:500]}...\n"
            f"AI Summary: {p.get('summary', 'Not summarized yet')}"
            for i, p in enumerate(papers[:20])  # Limit to 20 papers
        ])
        
        system_prompt = f"""You are a research digest writer for "{topic_name}".
Write an engaging, informative weekly digest for researchers and practitioners.

Topic Description: {topic_description}

Your digest should:
1. Start with an executive summary (2-3 sentences)
2. Highlight the most important/relevant papers (those with scores >= 7)
3. Group papers by theme or methodology when appropriate
4. Note trends or patterns across the papers
5. End with "What to Watch" - emerging themes or gaps
6. Use markdown formatting with headers (##), bullet points, and bold

Keep it concise but insightful. Target 400-600 words."""

        prompt = f"""Create a weekly research digest for this topic based on {len(papers)} new papers:

{papers_text}

Statistics:
- Total papers: {len(papers)}
- High relevance (7+): {len(high_relevance)}
- Sources: {', '.join(f'{k}: {v}' for k, v in sources.items())}

Write the digest now:"""

        try:
            result = await self.generate(
                prompt=prompt,
                model_id=model_id,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=2000,
            )
            
            digest_content = result.get("content", "")
            
            # Extract highlights (papers mentioned prominently)
            highlights = [
                {"title": p.get("title"), "score": p.get("relevance_score")}
                for p in high_relevance[:5]
            ]
            
            return {
                "digest": digest_content,
                "highlights": highlights,
                "stats": {
                    "total": len(papers),
                    "high_relevance": len(high_relevance),
                    "sources": sources
                },
                "model_used": model_id
            }
            
        except Exception as e:
            print(f"Error generating weekly digest: {e}")
            return {
                "digest": f"Error generating digest: {str(e)}",
                "highlights": [],
                "stats": {"total": len(papers), "error": str(e)}
            }


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get the LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
