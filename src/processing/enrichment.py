import requests
from typing import Dict, Any, List
from tqdm import tqdm

def get_oa_status(doi: str, email: str) -> Dict[str, Any]:
    """
    Queries Unpaywall for Open Access status.
    """
    if not doi:
        return {}
        
    url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
    try:
        # Add timeout to prevent hanging
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "is_oa": data.get('is_oa', False),
                "oa_status": data.get('oa_status'),
                "url": data.get('best_oa_location', {}).get('url') if data.get('best_oa_location') else None,
                "license": data.get('best_oa_location', {}).get('license') if data.get('best_oa_location') else None
            }
    except Exception as e:
        # Catch all exceptions to prevent pipeline crash
        # print(f"Error fetching Unpaywall data for {doi}: {e}") # Optional: reduce noise
        pass
    
    return {}

def enrich_with_oa(records: List[Dict[str, Any]], email: str) -> List[Dict[str, Any]]:
    print(f"Enriching {len(records)} records via Unpaywall...")
    for record in tqdm(records):
        if record.get('doi'):
            oa_data = get_oa_status(record['doi'], email)
            record['oa_status'] = oa_data
    return records
