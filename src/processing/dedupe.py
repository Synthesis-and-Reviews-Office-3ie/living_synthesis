from typing import List, Dict, Any
import re

def normalize_title(title: str) -> str:
    """Normalize a title for comparison by removing punctuation, extra spaces, and lowercasing."""
    if not title:
        return ""
    # Remove punctuation and extra whitespace, lowercase
    title = re.sub(r'[^\w\s]', '', title.lower())
    title = re.sub(r'\s+', ' ', title).strip()
    return title

def title_similarity(title1: str, title2: str) -> float:
    """Calculate simple word-based Jaccard similarity between two titles."""
    if not title1 or not title2:
        return 0.0
    words1 = set(title1.split())
    words2 = set(title2.split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union)

def deduplicate_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicates records based on DOI, normalized Title, or fuzzy title matching.
    Handles cases like different DOI versions of the same paper (e.g., Zenodo versions).
    """
    seen_dois = set()
    seen_titles = []  # List of normalized titles for fuzzy matching
    unique_records = []
    
    # Sort by source priority (prefer openalex > pubmed > crossref > arxiv > others)
    source_priority = {'openalex': 0, 'pubmed': 1, 'crossref': 2, 'arxiv': 3}
    records_sorted = sorted(records, key=lambda r: source_priority.get(r.get('source', ''), 99))
    
    for record in records_sorted:
        doi = record.get('doi')
        title = record.get('title')
        normalized_title = normalize_title(title) if title else None
        
        # 1. Check exact DOI match
        if doi:
            doi_normalized = doi.lower().strip()
            if doi_normalized in seen_dois:
                continue
        
        # 2. Check exact title match
        if normalized_title and normalized_title in seen_titles:
            continue
        
        # 3. Check fuzzy title match (>85% similar)
        is_fuzzy_duplicate = False
        if normalized_title and len(normalized_title) > 20:  # Only for substantial titles
            for seen_title in seen_titles:
                if title_similarity(normalized_title, seen_title) > 0.85:
                    is_fuzzy_duplicate = True
                    break
        
        if is_fuzzy_duplicate:
            continue
            
        # Record is unique - add it
        if doi:
            seen_dois.add(doi.lower().strip())
        if normalized_title:
            seen_titles.append(normalized_title)
        unique_records.append(record)
            
    return unique_records


def prefilter_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Quick keyword-based pre-filtering to remove obviously irrelevant records
    BEFORE sending to the expensive LLM for analysis.
    
    This saves API costs by filtering out papers that are clearly not about
    LLMs in evidence synthesis methodology.
    """
    # Keywords that indicate the paper is about LLM methodology (not just a review topic)
    method_keywords = [
        'llm', 'large language model', 'gpt', 'chatgpt', 'claude', 'llama', 'gemini',
        'transformer', 'bert', 'natural language processing', 'nlp', 'ai-assisted',
        'automated screening', 'machine learning', 'deep learning', 'neural network',
        'text mining', 'automation', 'artificial intelligence screening',
        'language model', 'generative ai', 'rag', 'retrieval augmented'
    ]
    
    # Keywords that suggest it's a clinical/topic review (not methodology)
    exclude_keywords = [
        'cancer treatment outcomes', 'drug efficacy', 'patient outcomes',
        'clinical trial results', 'mortality rate', 'survival rate',
        'therapy effectiveness', 'diagnostic accuracy'
    ]
    
    filtered = []
    for record in records:
        title = (record.get('title') or '').lower()
        abstract = (record.get('abstract') or '').lower()
        combined_text = title + ' ' + abstract
        
        # Must have at least one method keyword
        has_method_keyword = any(kw in combined_text for kw in method_keywords)
        
        # Skip if it looks like a pure clinical review
        has_exclude_keyword = any(kw in combined_text for kw in exclude_keywords)
        
        if has_method_keyword and not has_exclude_keyword:
            filtered.append(record)
    
    return filtered
