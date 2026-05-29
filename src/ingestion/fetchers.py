import requests
import datetime
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import time
import urllib.parse
import re

def fetch_arxiv(query: str, max_results: int = 100, since_date: str = None) -> List[Dict[str, Any]]:
    """
    Fetches preprints from arXiv with pagination support.
    arXiv API supports Boolean operators and field prefixes.
    """
    base_url = "http://export.arxiv.org/api/query"
    results = []
    start = 0
    batch_size = min(max_results, 100)  # arXiv recommends max 100 per request
    
    # Convert Boolean query to arXiv format
    # arXiv uses: all: (default), ti: (title), au: (author), abs: (abstract)
    # Example: "mortality" AND "climate change" -> all:"mortality" AND all:"climate change"
    
    # First, extract quoted phrases and standalone terms
    arxiv_query = query
    
    # Replace "term" with all:"term" for arXiv
    # Handle quoted phrases
    arxiv_query = re.sub(r'"([^"]+)"', r'all:"\1"', arxiv_query)
    
    # Handle standalone words that aren't AND/OR operators
    words = arxiv_query.split()
    processed = []
    for word in words:
        if word.upper() in ('AND', 'OR', 'NOT', 'ANDNOT'):
            processed.append(word.upper())
        elif word.startswith('all:'):
            processed.append(word)
        elif not word.startswith('"') and not word.endswith('"'):
            # Standalone word - add all: prefix if not already prefixed
            processed.append(f'all:{word}' if ':' not in word else word)
        else:
            processed.append(word)
    
    arxiv_query = ' '.join(processed)
    
    while len(results) < max_results:
        params = {
            "search_query": arxiv_query,
            "start": start,
            "max_results": batch_size,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=30)
            if response.status_code != 200:
                print(f"Error fetching from arXiv: {response.status_code}")
                # Try with simpler query on first failure - just use first quoted phrase
                if start == 0:
                    print(f"Retrying arXiv with simpler query...")
                    # Extract first quoted phrase or first word
                    match = re.search(r'"([^"]+)"', query)
                    simple_term = match.group(1) if match else query.split()[0]
                    params["search_query"] = f'all:"{simple_term}"'
                    response = requests.get(base_url, params=params, timeout=30)
                    if response.status_code != 200:
                        break
                else:
                    break
        except requests.exceptions.RequestException as e:
            print(f"arXiv request error: {e}")
            break
            
        root = ET.fromstring(response.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        entries = root.findall('atom:entry', ns)
        if not entries:
            break
            
        for entry in entries:
            if len(results) >= max_results:
                break
                
            pub_date = entry.find('atom:published', ns).text
            
            # Client-side date filtering
            if since_date:
                pub_dt = pub_date.split('T')[0]
                if pub_dt < since_date:
                    continue

            # Extract DOI if available
            doi = None
            for link in entry.findall('atom:link', ns):
                if link.get('title') == 'doi':
                    doi = link.get('href').replace('http://dx.doi.org/', '')
            
            arxiv_id = entry.find('atom:id', ns).text.split('/')[-1]
            
            authors = []
            for author in entry.findall('atom:author', ns):
                name = author.find('atom:name', ns)
                if name is not None and name.text:
                    authors.append(name.text)
            
            results.append({
                "source": "arxiv",
                "id": arxiv_id,
                "doi": doi,
                "title": entry.find('atom:title', ns).text.strip().replace('\n', ' '),
                "abstract": entry.find('atom:summary', ns).text.strip(),
                "publication_date": pub_date,
                "authors": authors,
                "raw_data": {}
            })
        
        # Check if we got fewer results than requested (end of results)
        if len(entries) < batch_size:
            break
            
        start += batch_size
        time.sleep(0.5)  # Rate limit - arXiv asks for 3 second delay, but 0.5 is usually ok
    
    return results

def reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index or not isinstance(inverted_index, dict):
        return None
    
    # The inverted index maps words to positions: {"word": [0, 5, 10], ...}
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    
    # Sort by position and join
    word_positions.sort(key=lambda x: x[0])
    return ' '.join(word for _, word in word_positions)

def _parse_openalex_item(item: dict) -> dict:
    """Parse a single OpenAlex work item into our standard format."""
    # Reconstruct abstract from inverted index
    abstract_raw = item.get('abstract_inverted_index')
    abstract = reconstruct_abstract(abstract_raw) if abstract_raw else None
    
    # Extract authors
    authors = []
    for authorship in item.get('authorships', []):
        author_info = authorship.get('author', {})
        name = author_info.get('display_name')
        if name:
            authors.append(name)
    
    # Get open access URL
    oa_url = None
    primary_location = item.get('primary_location', {})
    if primary_location:
        oa_url = primary_location.get('pdf_url') or primary_location.get('landing_page_url')
    
    return {
        "source": "openalex",
        "id": item.get('id'),
        "doi": item.get('doi'),
        "title": item.get('title'),
        "abstract": abstract,
        "publication_date": item.get('publication_date'),
        "authors": authors,
        "oa_url": oa_url,
        "is_oa": item.get('open_access', {}).get('is_oa', False),
        "raw_data": item
    }

def fetch_openalex(query: str, since_date: str = None, email: str = None, max_results: int = 100, paginate: bool = False) -> List[Dict[str, Any]]:
    """
    Fetches works from OpenAlex based on a search query.
    If paginate=True, fetches multiple pages up to max_results (for Team tier).
    """
    import time
    base_url = "https://api.openalex.org/works"
    results = []
    per_page = min(max_results, 200)  # OpenAlex max per page is 200
    cursor = "*"
    
    while len(results) < max_results:
        params = {
            "search": query,
            "per-page": per_page,
            "sort": "publication_date:desc",
            "cursor": cursor
        }
        if since_date:
            params["filter"] = f"from_publication_date:{since_date}"
        if email:
            params["mailto"] = email

        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            print(f"Error fetching from OpenAlex: {response.status_code}")
            break
            
        data = response.json()
        items = data.get('results', [])
        
        if not items:
            break
            
        for item in items:
            results.append(_parse_openalex_item(item))
            if len(results) >= max_results:
                break
        
        # Check for next page
        meta = data.get('meta', {})
        cursor = meta.get('next_cursor')
        
        if not cursor or not paginate:
            break  # Stop after first page if not paginating
            
        time.sleep(0.1)  # Rate limit
    
    return results

def fetch_pubmed(query: str, api_key: str = None, max_results: int = 100, since_date: str = None) -> List[Dict[str, Any]]:
    """
    Fetches works from PubMed using E-utilities.
    
    Args:
        query: Search query string
        api_key: Optional NCBI API key for higher rate limits
        max_results: Maximum number of results to return
        since_date: Optional date string (YYYY-MM-DD) to filter papers published after this date
    """
    # 1. ESearch
    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results
    }
    
    # Add date range filter if since_date is provided
    if since_date:
        # PubMed uses mindate/maxdate with format YYYY/MM/DD
        # datetype=pdat means publication date
        min_date = since_date.replace("-", "/")
        params["datetype"] = "pdat"
        params["mindate"] = min_date
        params["maxdate"] = "3000/01/01"  # Far future to include all recent
        print(f"[PubMed] Filtering from publication date: {min_date}")
    
    if api_key:
        params["api_key"] = api_key

    response = requests.get(esearch_url, params=params)
    if response.status_code != 200:
        print(f"Error searching PubMed: {response.status_code}")
        print(f"Response: {response.text}")
        return []
    
    id_list = response.json().get('esearchresult', {}).get('idlist', [])
    if not id_list:
        return []

    # 2. EFetch - Get actual article data
    efetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    
    results = []
    chunk_size = 50
    
    for i in range(0, len(id_list), chunk_size):
        chunk_ids = id_list[i:i + chunk_size]
        
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(chunk_ids),
            "retmode": "xml"
        }
        if api_key:
            fetch_params["api_key"] = api_key
            
        try:
            fetch_response = requests.get(efetch_url, params=fetch_params)
            if fetch_response.status_code == 200:
                # Parse XML properly
                root = ET.fromstring(fetch_response.content)
                
                for article in root.findall('.//PubmedArticle'):
                    pmid = article.find('.//PMID')
                    pmid = pmid.text if pmid is not None else None
                    
                    # Get title
                    title_elem = article.find('.//ArticleTitle')
                    title = title_elem.text if title_elem is not None else "No title"
                    
                    # Get abstract (may have multiple AbstractText elements)
                    abstract_parts = []
                    for abs_text in article.findall('.//AbstractText'):
                        label = abs_text.get('Label', '')
                        text = abs_text.text or ''
                        if label:
                            abstract_parts.append(f"{label}: {text}")
                        else:
                            abstract_parts.append(text)
                    abstract = ' '.join(abstract_parts) if abstract_parts else None
                    
                    # Get DOI
                    doi = None
                    for art_id in article.findall('.//ArticleId'):
                        if art_id.get('IdType') == 'doi':
                            doi = art_id.text
                            break
                    
                    # Get publication date
                    pub_date = None
                    pub_date_elem = article.find('.//PubDate')
                    if pub_date_elem is not None:
                        year = pub_date_elem.find('Year')
                        month = pub_date_elem.find('Month')
                        day = pub_date_elem.find('Day')
                        if year is not None:
                            pub_date = year.text
                            if month is not None:
                                # Convert month name to number if needed
                                month_text = month.text
                                month_map = {'Jan':'01','Feb':'02','Mar':'03','Apr':'04','May':'05','Jun':'06',
                                           'Jul':'07','Aug':'08','Sep':'09','Oct':'10','Nov':'11','Dec':'12'}
                                month_num = month_map.get(month_text, month_text)
                                pub_date = f"{year.text}-{month_num}"
                                if day is not None:
                                    pub_date = f"{year.text}-{month_num}-{day.text.zfill(2)}"
                    
                    # Get authors
                    authors = []
                    for author in article.findall('.//Author'):
                        last_name = author.find('LastName')
                        fore_name = author.find('ForeName')
                        if last_name is not None and last_name.text:
                            name = last_name.text
                            if fore_name is not None and fore_name.text:
                                name = f"{fore_name.text} {last_name.text}"
                            authors.append(name)
                    
                    results.append({
                        "source": "pubmed",
                        "id": pmid,
                        "doi": doi,
                        "title": title,
                        "abstract": abstract,
                        "publication_date": pub_date,
                        "authors": authors,
                        "raw_data": {}
                    })
            else:
                print(f"Error fetching PubMed batch {i}: {fetch_response.status_code}")
        except Exception as e:
            print(f"Exception fetching PubMed batch {i}: {e}")

    return results

def fetch_crossref(query: str, rows: int = 100, from_date: str = None) -> List[Dict[str, Any]]:
    """
    Fetches works from Crossref with pagination support.
    """
    base_url = "https://api.crossref.org/works"
    results = []
    offset = 0
    batch_size = min(rows, 100)  # Crossref max per request is 1000, but 100 is safer
    
    while len(results) < rows:
        params = {
            "query": query,
            "rows": batch_size,
            "offset": offset,
            "sort": "published",
            "order": "desc"
        }
        if from_date:
            params["filter"] = f"from-pub-date:{from_date}"
        
        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            print(f"Error fetching from Crossref: {response.status_code}")
            break
            
        data = response.json()
        items = data.get('message', {}).get('items', [])
        
        if not items:
            break
            
        for item in items:
            if len(results) >= rows:
                break
                
            pub_date_iso = item.get('created', {}).get('date-time')
            
            if from_date and pub_date_iso:
                pub_date_str = pub_date_iso.split('T')[0]
                if pub_date_str < from_date:
                    continue

            # Extract authors
            authors = []
            for author in item.get('author', []):
                name_parts = []
                if author.get('given'):
                    name_parts.append(author['given'])
                if author.get('family'):
                    name_parts.append(author['family'])
                if name_parts:
                    authors.append(' '.join(name_parts))

            results.append({
                "source": "crossref",
                "id": item.get('DOI'),
                "doi": item.get('DOI'),
                "title": item.get('title', [''])[0] if item.get('title') else None,
                "abstract": item.get('abstract'),  # Some Crossref entries have abstracts
                "publication_date": pub_date_iso,
                "authors": authors,
                "url": item.get('URL'),
                "raw_data": item
            })
        
        if len(items) < batch_size:
            break
            
        offset += batch_size
        time.sleep(0.2)  # Rate limit
    
    return results


def _google_scholar_worker(query: str, max_results: int, since_date: str, results_list: list, error_container: list):
    """Worker function for Google Scholar search in a separate thread."""
    try:
        from scholarly import scholarly
        
        search_query = scholarly.search_pubs(query)
        start_time = time.time()
        timeout_seconds = 20  # Internal timeout per result
        
        for i, paper in enumerate(search_query):
            # Check timeout
            if time.time() - start_time > timeout_seconds:
                print(f"Google Scholar internal timeout after {i} results")
                break
                
            if i >= max_results:
                break
            
            # Extract paper info
            bib = paper.get('bib', {})
            
            # Try to get the year and convert to date - handle 'NA' or invalid values
            year = bib.get('pub_year')
            pub_date = None
            if year and year != 'NA':
                try:
                    year_int = int(year)
                    pub_date = f"{year_int}-01-01"
                except (ValueError, TypeError):
                    pass
            
            # Date filtering (basic - just by year)
            if since_date and pub_date and year:
                try:
                    since_year = int(since_date.split('-')[0])
                    if int(year) < since_year:
                        continue
                except (ValueError, TypeError):
                    pass
            
            # Extract authors
            authors = bib.get('author', '')
            if isinstance(authors, str):
                authors = [a.strip() for a in authors.split(' and ')]
            
            # Handle citations that might be 'NA' or non-numeric
            citations = paper.get('num_citations', 0)
            if citations == 'NA' or citations is None:
                citations = 0
            try:
                citations = int(citations)
            except (ValueError, TypeError):
                citations = 0
            
            results_list.append({
                "source": "google_scholar",
                "id": paper.get('author_id', [None])[0] if paper.get('author_id') else None,
                "title": bib.get('title'),
                "abstract": bib.get('abstract'),
                "publication_date": pub_date,
                "authors": authors,
                "url": paper.get('pub_url') or paper.get('eprint_url'),
                "venue": bib.get('venue'),
                "citations": citations,
                "raw_data": dict(paper)
            })
    except Exception as e:
        error_container.append(str(e))


def fetch_google_scholar(query: str, max_results: int = 20, since_date: str = None, until_date: str = None) -> List[Dict[str, Any]]:
    """
    Fetches papers from Google Scholar using the scholarly package.
    
    Note: Google Scholar doesn't have an official API, so this uses web scraping
    which may be rate-limited or blocked. Use sparingly.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (capped at 20 for performance)
        since_date: Optional start date (YYYY-MM-DD) - not fully supported by Scholar
        until_date: Optional end date (YYYY-MM-DD) - not fully supported by Scholar
    
    Returns:
        List of paper dictionaries
    """
    import threading
    
    # Cap max_results to 20 for Google Scholar - it's very slow due to web scraping
    max_results = min(max_results, 20)
    
    try:
        from scholarly import scholarly
    except ImportError:
        print("scholarly package not installed. Run: pip install scholarly")
        return []
    
    results = []
    errors = []
    
    # Run in a thread with a hard timeout
    thread = threading.Thread(
        target=_google_scholar_worker,
        args=(query, max_results, since_date, results, errors)
    )
    thread.daemon = True  # Allow the thread to be killed
    thread.start()
    
    # Wait max 30 seconds for the thread to complete
    thread.join(timeout=30)
    
    if thread.is_alive():
        print(f"Google Scholar hard timeout - returning {len(results)} results collected so far")
        # Thread is still running but we continue - it will be garbage collected eventually
    
    if errors:
        print(f"Error fetching from Google Scholar: {errors[0]}")
    
    return results
