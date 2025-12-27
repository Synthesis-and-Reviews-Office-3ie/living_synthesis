import requests
import datetime
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

def fetch_arxiv(query: str, max_results: int = 20, since_date: str = None) -> List[Dict[str, Any]]:
    """
    Fetches preprints from arXiv.
    """
    base_url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }
    
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        results = []
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        for entry in root.findall('atom:entry', ns):
            pub_date = entry.find('atom:published', ns).text
            
            # Client-side date filtering
            if since_date:
                # arXiv date format: 2023-10-25T14:30:00Z
                # since_date format: 2023-10-25
                pub_dt = pub_date.split('T')[0]
                if pub_dt < since_date:
                    continue

            # Extract DOI if available (often in arxiv:doi link)
            doi = None
            for link in entry.findall('atom:link', ns):
                if link.get('title') == 'doi':
                    doi = link.get('href').replace('http://dx.doi.org/', '')
            
            # Extract ID (remove version number for cleaner ID)
            arxiv_id = entry.find('atom:id', ns).text.split('/')[-1]
            
            results.append({
                "source": "arxiv",
                "id": arxiv_id,
                "doi": doi, # Might be None
                "title": entry.find('atom:title', ns).text.strip().replace('\n', ' '),
                "abstract": entry.find('atom:summary', ns).text.strip(),
                "publication_date": pub_date,
                "raw_data": {} # Keep light
            })
        return results
    else:
        print(f"Error fetching from arXiv: {response.status_code}")
        return []

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

def fetch_openalex(query: str, since_date: str = None, email: str = None, max_results: int = 100) -> List[Dict[str, Any]]:
    """
    Fetches works from OpenAlex based on a search query.
    """
    base_url = "https://api.openalex.org/works"
    params = {
        "search": query,
        "per-page": max_results,
        "sort": "publication_date:desc"
    }
    if since_date:
        params["filter"] = f"from_publication_date:{since_date}"
    
    if email:
        params["mailto"] = email

    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        data = response.json()
        results = []
        for item in data.get('results', []):
            # Reconstruct abstract from inverted index
            abstract_raw = item.get('abstract_inverted_index')
            abstract = reconstruct_abstract(abstract_raw) if abstract_raw else None
            
            results.append({
                "source": "openalex",
                "id": item.get('id'),
                "doi": item.get('doi'),
                "title": item.get('title'),
                "abstract": abstract,
                "publication_date": item.get('publication_date'),
                "raw_data": item
            })
        return results
    else:
        print(f"Error fetching from OpenAlex: {response.status_code}")
        return []

def fetch_pubmed(query: str, api_key: str = None, max_results: int = 100) -> List[Dict[str, Any]]:
    """
    Fetches works from PubMed using E-utilities.
    """
    # 1. ESearch
    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results
    }
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
                    
                    results.append({
                        "source": "pubmed",
                        "id": pmid,
                        "doi": doi,
                        "title": title,
                        "abstract": abstract,
                        "publication_date": pub_date,
                        "raw_data": {}
                    })
            else:
                print(f"Error fetching PubMed batch {i}: {fetch_response.status_code}")
        except Exception as e:
            print(f"Exception fetching PubMed batch {i}: {e}")

    return results

def fetch_crossref(query: str, rows: int = 20, from_date: str = None) -> List[Dict[str, Any]]:
    """
    Fetches works from Crossref.
    """
    base_url = "https://api.crossref.org/works"
    params = {
        "query": query,
        "rows": rows,
        "sort": "published",
        "order": "desc"
    }
    if from_date:
        params["filter"] = f"from-pub-date:{from_date}"
    
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        data = response.json()
        results = []
        for item in data.get('message', {}).get('items', []):
            # Client-side date filtering to be safe
            # Use 'created' date as it's usually the most reliable timestamp for "newness" in the system
            pub_date_iso = item.get('created', {}).get('date-time')
            
            if from_date and pub_date_iso:
                # pub_date_iso is like "2023-12-02T14:30:00Z"
                pub_date_str = pub_date_iso.split('T')[0]
                if pub_date_str < from_date:
                    continue

            results.append({
                "source": "crossref",
                "id": item.get('DOI'),
                "doi": item.get('DOI'),
                "title": item.get('title', [''])[0] if item.get('title') else None,
                "abstract": None, # Crossref often doesn't have abstracts
                "publication_date": pub_date_iso,
                "raw_data": item
            })
        return results
    else:
        print(f"Error fetching from Crossref: {response.status_code}")
        return []
