"""
Retrospective Newsletter Generator

This script runs the newsletter pipeline for past weeks that were missed.
It will generate separate newsletters for each week.
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import datetime
import time
from src.ingestion.fetchers import fetch_openalex, fetch_pubmed, fetch_crossref, fetch_arxiv
from src.ingestion.web_fetchers import fetch_google_search, fetch_github
from src.ingestion.rss_fetcher import fetch_rss_feeds
from src.storage.db import Database
from src.processing.dedupe import deduplicate_records
from src.processing.enrichment import enrich_with_oa
from src.analysis.newsletter_analyzer import NewsletterAnalyzer, analyze_records
from src.presentation.html_renderer import render_newsletter_html


def generate_newsletter_md(records, target_date):
    """Generate Markdown newsletter for a specific date."""
    records.sort(key=lambda x: x.get('newsletter_content', {}).get('relevance_score', 0), reverse=True)
    
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
            categories['Methodology'].append(r)

    date_str = target_date.strftime("%B %d, %Y")
    md = f"# LLMs in Evidence Synthesis - {date_str}\n\n"
    md += "Welcome to your weekly update on Large Language Models in Evidence Synthesis. Here's what's happening.\n\n"
    
    for cat, items in categories.items():
        if not items:
            continue
        
        md += f"## {cat}\n\n"
        for item in items[:5]:
            content = item.get('newsletter_content', {})
            md += f"### {content.get('headline')}\n"
            
            models = content.get('models', [])
            if models:
                md += f"**Models:** {', '.join(models)}\n\n"
            
            md += f"{content.get('summary')}\n\n"
            
            links = []
            if item.get('doi'):
                doi_val = item.get('doi').replace('https://doi.org/', '').replace('http://doi.org/', '')
                links.append(f"[DOI](https://doi.org/{doi_val})")
            
            oa_url = item.get('oa_status', {}).get('url')
            if oa_url:
                label = "Link"
                if item.get('source') == 'github': label = "Repo"
                elif item.get('source') == 'twitter': label = "Tweet"
                elif oa_url.endswith('.pdf'): label = "PDF"
                links.append(f"[{label}]({oa_url})")

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


def run_for_week(target_date, config, db, analyzer, skip_hitl=False):
    """
    Run the newsletter pipeline for a specific week ending on target_date.
    
    NOTE: For retrospective runs, we can't truly search "past" data since APIs
    return current results. Instead, we do a broad search and let the user
    manually curate what's relevant for each week.
    """
    print(f"\n{'='*60}")
    print(f"GENERATING NEWSLETTER FOR WEEK ENDING: {target_date}")
    print(f"{'='*60}\n")
    
    # For retrospective, we search the last 30 days to cast a wide net
    # The user will manually select what's appropriate for each week
    days_back = 30
    since_date = (datetime.date.today() - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
    print(f"Searching broadly for papers from the last {days_back} days...")
    print(f"(You will manually select which items belong to week ending {target_date})")
    
    all_records = []
    
    # OpenAlex - broader search without strict date filtering
    openalex_query = '("evidence synthesis" OR "systematic review" OR "literature review" OR "meta-analysis" OR "scientific assistant") AND ("LLM" OR "large language model" OR "generative AI" OR "RAG")'
    print(f"Fetching from OpenAlex...")
    user_email = config['api_keys'].get('unpaywall')
    openalex_records = fetch_openalex(openalex_query, since_date=since_date, email=user_email, max_results=100)
    print(f"  -> Found {len(openalex_records)} records from OpenAlex")
    all_records.extend(openalex_records)
    
    # PubMed - broader date range
    date_query = f' AND ("{since_date.replace("-", "/")}"[dp] : "3000"[dp])'
    pubmed_query = '(("systematic review"[tiab] OR "evidence synthesis"[tiab] OR "literature review"[tiab]) AND ("large language model"[tiab] OR LLM[tiab] OR "artificial intelligence"[tiab]))' + date_query
    print(f"Fetching from PubMed...")
    
    pubmed_api_key = config['api_keys'].get('pubmed')
    if pubmed_api_key == "YOUR_PUBMED_API_KEY":
        pubmed_api_key = None
        
    pubmed_records = fetch_pubmed(pubmed_query, pubmed_api_key, max_results=200)
    print(f"  -> Found {len(pubmed_records)} records from PubMed")
    all_records.extend(pubmed_records)
    
    # Crossref
    crossref_query = "large language model systematic review literature synthesis"
    print(f"Fetching from Crossref...")
    crossref_records = fetch_crossref(crossref_query, from_date=since_date, rows=500)
    print(f"  -> Found {len(crossref_records)} records from Crossref")
    all_records.extend(crossref_records)
    
    # arXiv
    arxiv_query = 'all:("evidence synthesis" OR "literature review" OR "scientific assistant" OR "academic writing") AND all:("LLM" OR "agent")'
    print(f"Fetching from arXiv...")
    arxiv_records = fetch_arxiv(arxiv_query, max_results=500, since_date=since_date)
    print(f"  -> Found {len(arxiv_records)} records from arXiv")
    all_records.extend(arxiv_records)

    # GitHub (no date filtering available, always gets recent)
    github_token = config['api_keys'].get('github_token')
    if github_token == "YOUR_GITHUB_TOKEN":
        github_token = None
    
    github_query = "LLM evidence synthesis literature review"
    print(f"Fetching from GitHub...")
    github_records = fetch_github(github_query, github_token, max_results=20)
    print(f"  -> Found {len(github_records)} records from GitHub")
    all_records.extend(github_records)
    
    # RSS Feeds
    rss_urls = config.get('rss_feeds', [])
    if rss_urls:
        print(f"Fetching from {len(rss_urls)} RSS feeds...")
        rss_records = fetch_rss_feeds(rss_urls, since_date=since_date)
        print(f"  -> Found {len(rss_records)} records from RSS Feeds")
        all_records.extend(rss_records)
    
    print(f"Total raw records: {len(all_records)}")
    
    # Deduplicate
    unique_records = deduplicate_records(all_records)
    print(f"Unique records: {len(unique_records)}")
    
    if not unique_records:
        print("No records found for this week. Skipping.")
        return

    # Enrich
    print("Enriching with OA status...")
    enriched_records = enrich_with_oa(unique_records, config['api_keys']['unpaywall'])
    
    # Analyze
    print("Analyzing records for newsletter...")
    analyzed_records = analyze_records(enriched_records, analyzer)
    
    # HITL Step
    if not skip_hitl:
        draft_file = f"draft_review_{target_date.strftime('%Y_%m_%d')}.yaml"
        print(f"\n[HITL] Saving {len(analyzed_records)} analyzed records to {draft_file} for review.")
        
        draft_data = []
        for r in analyzed_records:
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
        input(f"Press Enter to continue after you have saved your changes to {draft_file}...")
        
        # Reload
        with open(draft_file, 'r', encoding='utf-8') as f:
            reviewed_data = yaml.safe_load(f)
            
        final_records = []
        original_map = {str(r.get('id')): r for r in analyzed_records}
        
        for item in reviewed_data:
            if item.get('include', True):
                item_id = str(item.get('id'))
                if item_id in original_map:
                    original = original_map[item_id]
                    original['newsletter_content'] = item.get('newsletter_content')
                    final_records.append(original)
    else:
        final_records = analyzed_records
    
    if not final_records:
        print("No records to include. Skipping newsletter generation.")
        return
        
    # Generate outputs
    print("Generating newsletter...")
    newsletter_md = generate_newsletter_md(final_records, target_date)
    
    output_file = f"newsletter_{target_date.strftime('%Y_%m_%d')}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(newsletter_md)
    print(f"Markdown saved to {output_file}")
    
    html_output_file = f"newsletter_{target_date.strftime('%Y_%m_%d')}.html"
    render_newsletter_html(final_records, html_output_file, target_date)
    
    print(f"Done with week ending {target_date}!")


def main():
    # Load config
    config_path = os.path.join("config", "settings.yaml")
    if not os.path.exists(config_path):
        print("Config file not found.")
        return
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize
    db = Database(config['database']['connection_string'])
    db.connect()
    
    analyzer = NewsletterAnalyzer(
        config['api_keys']['openai'], 
        config['llm']['model'],
        config['llm'].get('base_url')
    )
    
    # Define the weeks to catch up on
    # Last run was Dec 2, so we need Dec 9, Dec 16, and Dec 23
    weeks_to_run = [
        datetime.date(2025, 12, 9),
        datetime.date(2025, 12, 16),
        datetime.date(2025, 12, 23),
    ]
    
    print(f"Running retrospective newsletter generation for {len(weeks_to_run)} weeks...")
    print("Weeks: " + ", ".join(d.strftime("%Y-%m-%d") for d in weeks_to_run))
    print()
    
    for target_date in weeks_to_run:
        run_for_week(target_date, config, db, analyzer, skip_hitl=False)
        print()
    
    db.close()
    print("\nAll done!")


if __name__ == "__main__":
    main()
