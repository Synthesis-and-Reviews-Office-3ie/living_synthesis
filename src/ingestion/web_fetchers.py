import requests
import time
from typing import List, Dict, Any

def fetch_github(query: str, token: str = None, max_results: int = 20) -> List[Dict[str, Any]]:
    """
    Fetches repositories from GitHub.
    """
    base_url = "https://api.github.com/search/repositories"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
        
    params = {
        "q": query,
        "sort": "updated",
        "order": "desc",
        "per_page": max_results
    }
    
    response = requests.get(base_url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        results = []
        for item in data.get('items', []):
            results.append({
                "source": "github",
                "id": str(item.get('id')),
                "doi": None,
                "title": f"Repo: {item.get('full_name')}",
                "abstract": f"{item.get('description')} (Stars: {item.get('stargazers_count')}, Language: {item.get('language')})",
                "publication_date": item.get('created_at'),
                "oa_status": {"url": item.get('html_url'), "is_oa": True}, # Code is "OA"
                "raw_data": item
            })
        return results
    else:
        print(f"Error fetching from GitHub: {response.status_code}")
        return []

def fetch_google_search(query: str, api_key: str, cx: str, max_results: int = 20, date_restrict: str = None, sort: str = None) -> List[Dict[str, Any]]:
    """
    Fetches results from Google Custom Search JSON API.
    Useful for blogs, news, and tools.
    Handles pagination to fetch up to max_results.
    """
    if not api_key or not cx:
        print("Google Search skipped: Missing API Key or CX.")
        return []

    base_url = "https://www.googleapis.com/customsearch/v1"
    results = []
    start_index = 1
    
    # Google Custom Search API has a hard limit of 100 results (start index <= 91)
    # We cap max_results at 100 to avoid 400 errors.
    effective_max_results = min(max_results, 100)
    
    while len(results) < effective_max_results:
        # Calculate how many to fetch in this batch (max 10)
        num_to_fetch = min(effective_max_results - len(results), 10)
        if num_to_fetch <= 0:
            break
            
        params = {
            "q": query,
            "key": api_key,
            "cx": cx,
            "num": num_to_fetch,
            "start": start_index
        }
        
        if date_restrict:
            params["dateRestrict"] = date_restrict
        if sort:
            params["sort"] = sort
        
        try:
            # Sleep to avoid hitting QPS limits
            time.sleep(1)
            
            response = requests.get(base_url, params=params)
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                if not items:
                    break # No more results
                    
                for item in items:
                    results.append({
                        "source": "google_web",
                        "id": item.get('link'),
                        "doi": None,
                        "title": item.get('title'),
                        "abstract": item.get('snippet'),
                        "publication_date": None,
                        "oa_status": {"url": item.get('link'), "is_oa": True},
                        "raw_data": item
                    })
                
                start_index += len(items)
            elif response.status_code == 429:
                print("Error fetching from Google: 429 (Rate Limit Exceeded). You may have hit your daily quota.")
                break
            else:
                print(f"Error fetching from Google: {response.status_code}")
                break
        except Exception as e:
            print(f"Exception during Google Search: {e}")
            break
            
    return results
