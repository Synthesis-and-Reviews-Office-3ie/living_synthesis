import yaml
import os
import datetime
import time
from src.ingestion.fetchers import fetch_openalex, fetch_pubmed, fetch_crossref, fetch_arxiv
from src.ingestion.web_fetchers import fetch_google_search, fetch_github
from src.ingestion.rss_fetcher import fetch_rss_feeds
from src.storage.db import Database
from src.processing.dedupe import deduplicate_records, prefilter_records
from src.processing.enrichment import enrich_with_oa
from src.analysis.newsletter_analyzer import NewsletterAnalyzer, analyze_records
from src.presentation.html_renderer import render_newsletter_html

def load_config(path: str):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def generate_newsletter(records):
    # Sort by relevance score
    records.sort(key=lambda x: x.get('newsletter_content', {}).get('relevance_score', 0), reverse=True)
    
    # Group by category
    categories = {
        "New Tool/App": [],
        "Methodology": [],
        "Review/Benchmark": [],
        "Opinion/Discussion": []
    }
    
    for r in records:
        cat = r.get('newsletter_content', {}).get('category', 'Methodology')
        if cat in categories:
            categories[cat].append(r)
        else:
            categories['Methodology'].append(r) # Fallback

    # Generate Markdown
    date_str = datetime.date.today().strftime("%B %d, %Y")
    md = f"# LLMs in Evidence Synthesis - {date_str}\n\n"
    md += "Welcome to your weekly update on Large Language Models in Evidence Synthesis. Here's what's happening.\n\n"
    
    for cat, items in categories.items():
        if not items:
            continue
        
        md += f"## {cat}\n\n"
        for item in items[:5]: # Top 5 per category
            content = item.get('newsletter_content', {})
            md += f"### {content.get('headline')}\n"
            
            models = content.get('models', [])
            if models:
                md += f"**Models:** {', '.join(models)}\n\n"
            
            md += f"{content.get('summary')}\n\n"
            
            links = []
            # 1. DOI
            if item.get('doi'):
                doi_val = item.get('doi').replace('https://doi.org/', '').replace('http://doi.org/', '')
                links.append(f"[DOI](https://doi.org/{doi_val})")
            
            # 2. Direct URL / PDF
            oa_url = item.get('oa_status', {}).get('url')
            if oa_url:
                label = "Link"
                if item.get('source') == 'github': label = "Repo"
                elif item.get('source') == 'twitter': label = "Tweet"
                elif oa_url.endswith('.pdf'): label = "PDF"
                links.append(f"[{label}]({oa_url})")

            # 3. Fallback Source Link (if no DOI/Link or specific source needs it)
            # Ensure we always have at least one link
            if not links:
                source = item.get('source')
                val = item.get('id')
                if source == 'arxiv':
                    links.append(f"[arXiv](https://arxiv.org/abs/{val})")
                elif source == 'pubmed':
                    links.append(f"[PubMed](https://pubmed.ncbi.nlm.nih.gov/{val}/)")
                elif source == 'openalex':
                    links.append(f"[OpenAlex]({val})")
            
            if links:
                md += f"🔗 {' | '.join(links)}\n\n"
            md += "---\n\n"
            
    return md

def main():
    # 1. Load Configuration
    config_path = os.path.join("config", "settings.yaml")
    if not os.path.exists(config_path):
        print("Config file not found. Please create config/settings.yaml")
        return
    
    print(f"DEBUG: Loading config from {os.path.abspath(config_path)}")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # 2. Initialize Components
    db = Database(config['database']['connection_string'])
    db.connect()
    
    # Get existing DOIs to avoid duplicates
    existing_dois = db.get_existing_dois()
    print(f"Found {len(existing_dois)} existing papers in database.")
    
    analyzer = NewsletterAnalyzer(
        config['api_keys']['openai'], 
        config['llm']['model'],
        config['llm'].get('base_url')
    )
    
    # 3. Discover (Ingestion)
    # Calculate date range (e.g., last 7 days)
    days_back = 7
    since_date = (datetime.date.today() - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
    print(f"Starting discovery for papers published since {since_date}...")
    
    all_records = []
    
    # OpenAlex
    # Expanded query to catch broader "scientific synthesis" tools
    openalex_query = '("evidence synthesis" OR "systematic review" OR "literature review" OR "meta-analysis" OR "scientific assistant") AND ("LLM" OR "large language model" OR "generative AI" OR "RAG")'
    print(f"Fetching from OpenAlex: {openalex_query}")
    # Use the email from unpaywall config for the polite pool
    user_email = config['api_keys'].get('unpaywall')
    openalex_records = fetch_openalex(openalex_query, since_date=since_date, email=user_email, max_results=100)
    print(f"  -> Found {len(openalex_records)} records from OpenAlex")
    all_records.extend(openalex_records)
    
    # PubMed
    # Add date range to query: ("YYYY/MM/DD"[dp] : "3000"[dp])
    date_query = f' AND ("{since_date.replace("-", "/")}"[dp] : "3000"[dp])'
    pubmed_query = '(("systematic review"[tiab] OR "evidence synthesis"[tiab] OR "literature review"[tiab]) AND ("large language model"[tiab] OR LLM[tiab] OR "artificial intelligence"[tiab]))' + date_query
    print(f"Fetching from PubMed: {pubmed_query}")
    
    pubmed_api_key = config['api_keys'].get('pubmed')
    if pubmed_api_key == "YOUR_PUBMED_API_KEY":
        pubmed_api_key = None
        
    pubmed_records = fetch_pubmed(pubmed_query, pubmed_api_key, max_results=200)
    print(f"  -> Found {len(pubmed_records)} records from PubMed")
    all_records.extend(pubmed_records)
    
    # Crossref
    crossref_query = "large language model systematic review literature synthesis"
    print(f"Fetching from Crossref: {crossref_query}")
    crossref_records = fetch_crossref(crossref_query, from_date=since_date, rows=500)
    print(f"  -> Found {len(crossref_records)} records from Crossref")
    all_records.extend(crossref_records)
    
    # arXiv
    # Broader query for arXiv to catch "DeepScholar" type tools
    arxiv_query = 'all:("evidence synthesis" OR "literature review" OR "scientific assistant" OR "academic writing") AND all:("LLM" OR "agent")'
    print(f"Fetching from arXiv: {arxiv_query}")
    # Note: fetch_arxiv now filters by date client-side, so we can ask for more
    arxiv_records = fetch_arxiv(arxiv_query, max_results=500, since_date=since_date)
    print(f"  -> Found {len(arxiv_records)} records from arXiv")
    all_records.extend(arxiv_records)

    # Google Search (Web/Blogs & Twitter)
    google_key = config['api_keys'].get('google_search_api')
    google_cx = config['api_keys'].get('google_search_cx')
    if google_key and google_cx and google_key != "YOUR_GOOGLE_SEARCH_API_KEY" and google_cx != "YOUR_GOOGLE_SEARCH_CX":
        # 1. General Blog Search - Expanded
        google_query = '"LLM" "evidence synthesis" OR "literature review" OR "scientific assistant" blog'
        print(f"Fetching from Google: {google_query}")
        
        # Split query by day to bypass 100-result limit
        google_records = []
        print(f"  -> Splitting Google Search into {days_back} daily queries to maximize results...")
        
        for i in range(days_back):
            target_date = datetime.date.today() - datetime.timedelta(days=i)
            date_str = target_date.strftime("%Y%m%d")
            sort_param = f"date:r:{date_str}:{date_str}"
            
            print(f"    -> Fetching for {target_date}...")
            daily_records = fetch_google_search(
                google_query, 
                google_key, 
                google_cx, 
                max_results=100, # Max per query
                sort=sort_param
            )
            google_records.extend(daily_records)
            time.sleep(1) # Polite delay between days
            
        print(f"  -> Found {len(google_records)} total records from Google Search")
        all_records.extend(google_records)

        # 2. Twitter/X Search (via Google to avoid API costs)
        twitter_query = 'site:x.com OR site:twitter.com "evidence synthesis" OR "systematic review" "LLM"'
        print(f"Fetching from Twitter (via Google): {twitter_query}")
        
        # Also split Twitter search by day
        twitter_records = []
        for i in range(days_back):
            target_date = datetime.date.today() - datetime.timedelta(days=i)
            date_str = target_date.strftime("%Y%m%d")
            sort_param = f"date:r:{date_str}:{date_str}"
            
            daily_twitter = fetch_google_search(
                twitter_query, 
                google_key, 
                google_cx, 
                max_results=100,
                sort=sort_param
            )
            twitter_records.extend(daily_twitter)
            time.sleep(1) # Polite delay between days
        
        # Override source for clarity and filter out profile links
        filtered_twitter_records = []
        for r in twitter_records:
            r['source'] = 'twitter'
            # Filter out profile links (must contain /status/)
            link = r.get('oa_status', {}).get('url', '')
            if '/status/' in link:
                filtered_twitter_records.append(r)
                
        print(f"  -> Found {len(filtered_twitter_records)} records from Twitter (filtered from {len(twitter_records)})")
        all_records.extend(filtered_twitter_records)
    else:
        print("Skipping Google Search (missing or placeholder keys)")

    # GitHub
    github_token = config['api_keys'].get('github_token')
    if github_token == "YOUR_GITHUB_TOKEN":
        github_token = None
    
    github_query = "LLM evidence synthesis literature review"
    print(f"Fetching from GitHub: {github_query}")
    github_records = fetch_github(github_query, github_token, max_results=20)
    print(f"  -> Found {len(github_records)} records from GitHub")
    all_records.extend(github_records)
    
    # RSS Feeds (AI Newsletters)
    rss_urls = config.get('rss_feeds', [])
    if rss_urls:
        print(f"Fetching from {len(rss_urls)} RSS feeds...")
        rss_records = fetch_rss_feeds(rss_urls, since_date=since_date)
        print(f"  -> Found {len(rss_records)} records from RSS Feeds")
        all_records.extend(rss_records)
    
    print(f"Total raw records: {len(all_records)}")
    
    # 4. Deduplicate & Filter Existing
    unique_records = deduplicate_records(all_records)
    
    # Identify records that are NEW to the database (for saving later)
    records_to_save = []
    for r in unique_records:
        is_in_db = False
        if r.get('doi') and r.get('doi') in existing_dois:
            is_in_db = True
        elif r.get('id') and r.get('id') in existing_dois:
            is_in_db = True
            
        if not is_in_db:
            records_to_save.append(r)
    
    # For the NEWSLETTER GENERATION, we want to include ALL relevant records found in this window,
    # even if they were already saved in a previous run today.
    # This allows re-running the script to regenerate the HTML without losing items.
    records_to_analyze = unique_records
    
    print(f"Unique records found in window: {len(unique_records)}")
    print(f"New records to save to DB: {len(records_to_save)}")
    
    if not records_to_analyze:
        print("No records found in this window. Exiting.")
        db.close()
        return

    # 5. Pre-filter to reduce LLM costs
    print("Pre-filtering records by keywords...")
    prefiltered_records = prefilter_records(records_to_analyze)
    print(f"  -> {len(prefiltered_records)} records passed pre-filter (removed {len(records_to_analyze) - len(prefiltered_records)} irrelevant)")
    
    if not prefiltered_records:
        print("No relevant records after pre-filtering. Exiting.")
        db.close()
        return

    # 6. Enrich (OA Status)
    print("Enriching with OA status...")
    enriched_records = enrich_with_oa(prefiltered_records, config['api_keys']['unpaywall'])
    
    # 7. Analyze for Newsletter
    print("Analyzing records for newsletter...")
    # Note: This re-runs analysis on items even if they are in DB. 
    # Ideally, we would fetch the analysis from DB, but for now we re-run to ensure fresh prompt/format.
    analyzed_records = analyze_records(enriched_records, analyzer)
    
    # --- HUMAN IN THE LOOP STEP ---
    draft_file = "draft_review.yaml"
    print(f"\n[HITL] Saving {len(analyzed_records)} analyzed records to {draft_file} for review.")
    
    # Prepare simplified data for YAML to make it readable
    draft_data = []
    for r in analyzed_records:
        # Create a simplified structure for the reviewer
        # We exclude 'raw_data' and 'abstract' to keep the file manageable
        item = {
            'id': r.get('id'),
            'title': r.get('title'),
            'source': r.get('source'),
            'doi': r.get('doi'),
            'oa_status': r.get('oa_status'),
            'include': True,
            'newsletter_content': r.get('newsletter_content', {})
        }
        draft_data.append(item)
        
    with open(draft_file, 'w', encoding='utf-8') as f:
        yaml.dump(draft_data, f, sort_keys=False)
        
    print(f"PLEASE REVIEW '{draft_file}' NOW.")
    print("Set 'include: false' for any items you want to exclude.")
    print("You can also edit the 'headline' or 'summary' directly in the YAML file.")
    input("Press Enter to continue after you have saved your changes to draft_review.yaml...")
    
    # Reload the reviewed data
    print(f"Reloading {draft_file}...")
    with open(draft_file, 'r', encoding='utf-8') as f:
        reviewed_data = yaml.safe_load(f)
        
    # Reconstruct final records merging user edits with full data (preserved in memory)
    final_records = []
    original_map = {str(r.get('id')): r for r in analyzed_records}
    
    excluded_count = 0
    for item in reviewed_data:
        if item.get('include', True):
            item_id = str(item.get('id'))
            if item_id in original_map:
                original = original_map[item_id]
                # Update content with user edits
                original['newsletter_content'] = item.get('newsletter_content')
                final_records.append(original)
            else:
                print(f"Warning: Could not find original record for ID {item_id}")
        else:
            excluded_count += 1
            
    print(f"Proceeding with {len(final_records)} records (excluded {excluded_count}).")
    
    # 7. Generate & Save Newsletter
    print("Generating newsletter draft...")
    newsletter_md = generate_newsletter(final_records)
    
    output_file = f"newsletter_{datetime.date.today().strftime('%Y_%m_%d')}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(newsletter_md)
        
    print(f"Newsletter draft saved to {output_file}")
    
    # 8. Generate HTML
    html_output_file = f"newsletter_{datetime.date.today().strftime('%Y_%m_%d')}.html"
    render_newsletter_html(final_records, html_output_file)

    print("\n--- Preview ---\n")
    print(newsletter_md[:500] + "...\n(See file for full content)")

    # 9. Save to DB
    print("Saving new records to database...")
    # We only save the ones that were marked as new AND included in the final newsletter
    # We need to find the analyzed versions of the 'records_to_save'
    final_records_to_save = []
    save_ids = set(r.get('id') for r in records_to_save)
    
    for r in final_records:
        if r.get('id') in save_ids:
            final_records_to_save.append(r)
            
    db.save_records(final_records_to_save)
    db.close()

if __name__ == "__main__":
    main()
