import feedparser
import datetime
from typing import List, Dict, Any
from dateutil import parser as date_parser

def fetch_rss_feeds(feed_urls: List[str], since_date: str = None) -> List[Dict[str, Any]]:
    """
    Fetches items from a list of RSS feed URLs.
    """
    results = []
    
    for url in feed_urls:
        print(f"Fetching RSS feed: {url}")
        try:
            feed = feedparser.parse(url)
            
            for entry in feed.entries:
                # Parse date
                published_date = None
                if hasattr(entry, 'published'):
                    try:
                        dt = date_parser.parse(entry.published)
                        published_date = dt.strftime("%Y-%m-%d")
                    except:
                        pass
                
                # Filter by date if needed
                if since_date and published_date:
                    if published_date < since_date:
                        continue
                
                # Basic keyword filtering to reduce noise before LLM
                # We want to catch "DeepScholar" or "Research Assistant" type tools
                # even if they don't say "evidence synthesis" explicitly.
                text_content = (entry.title + " " + entry.get('summary', '')).lower()
                keywords = [
                    "evidence", "synthesis", "literature", "review", "research", 
                    "academic", "scholar", "science", "paper", "study", "analysis"
                ]
                
                # If it's a general AI newsletter, we need at least ONE research-related keyword
                if not any(k in text_content for k in keywords):
                    continue

                results.append({
                    "source": "rss_newsletter",
                    "id": entry.link, # Use URL as ID
                    "doi": None,
                    "title": entry.title,
                    "abstract": entry.get('summary', '')[:2000], # Truncate if too long
                    "publication_date": published_date,
                    "oa_status": {"url": entry.link, "is_oa": True},
                    "raw_data": {"feed_title": feed.feed.get('title', 'Unknown Feed')}
                })
                
        except Exception as e:
            print(f"Error fetching RSS {url}: {e}")
            
    return results
