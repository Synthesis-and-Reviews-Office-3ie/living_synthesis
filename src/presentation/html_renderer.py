import os
from jinja2 import Environment, FileSystemLoader
import datetime

def render_newsletter_html(records, output_path, target_date=None):
    """
    Renders the newsletter records into an HTML file using Jinja2.
    
    Args:
        records: List of record dictionaries
        output_path: Path to save the HTML file
        target_date: Optional date object for the newsletter (defaults to today)
    """
    # 1. Prepare Data Structure for Template
    categories = {
        "New Tool/App": [],
        "Methodology": [],
        "Review/Benchmark": [],
        "Opinion/Discussion": []
    }
    
    # Sort by relevance (internal use only, not displayed)
    records.sort(key=lambda x: x.get('newsletter_content', {}).get('relevance_score', 0), reverse=True)

    for r in records:
        cat = r.get('newsletter_content', {}).get('category', 'Methodology')
        content = r.get('newsletter_content', {})
        
        # Build Links
        links = []
        if r.get('doi'):
            doi_val = r.get('doi').replace('https://doi.org/', '').replace('http://doi.org/', '')
            links.append({"label": "DOI", "url": f"https://doi.org/{doi_val}"})
        
        oa_url = r.get('oa_status', {}).get('url')
        if oa_url:
            label = "Link"
            if r.get('source') == 'github': label = "Repo"
            elif r.get('source') == 'twitter': label = "Tweet"
            elif oa_url.endswith('.pdf'): label = "PDF"
            links.append({"label": label, "url": oa_url})
            
        if not links:
            source = r.get('source')
            val = r.get('id')
            if source == 'arxiv':
                links.append({"label": "arXiv", "url": f"https://arxiv.org/abs/{val}"})
            elif source == 'pubmed':
                links.append({"label": "PubMed", "url": f"https://pubmed.ncbi.nlm.nih.gov/{val}/"})
            elif source == 'openalex':
                links.append({"label": "OpenAlex", "url": val})

        item_data = {
            "headline": content.get('headline'),
            "models": content.get('models', []),
            "summary": content.get('summary'),
            "links": links
        }
        
        if cat in categories:
            categories[cat].append(item_data)
        else:
            categories['Methodology'].append(item_data)

    # 2. Render Template
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('newsletter.html')
    
    if target_date is None:
        target_date = datetime.date.today()
    date_str = target_date.strftime("%B %d, %Y")
    title = f"LLMs in Evidence Synthesis - {date_str}"
    
    html_output = template.render(title=title, categories=categories)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_output)
    
    print(f"HTML Newsletter saved to {output_path}")
