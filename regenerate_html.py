import yaml
import os
import datetime
from src.presentation.html_renderer import render_newsletter_html

def main():
    draft_file = "draft_review.yaml"
    
    if not os.path.exists(draft_file):
        print(f"Error: {draft_file} not found.")
        return

    print(f"Loading records from {draft_file}...")
    with open(draft_file, 'r', encoding='utf-8') as f:
        reviewed_data = yaml.safe_load(f)
        
    # Filter included items
    final_records = [r for r in reviewed_data if r.get('include', True)]
    print(f"Found {len(final_records)} included records.")
    
    # Generate HTML
    html_output_file = f"newsletter_{datetime.date.today().strftime('%Y_%m_%d')}.html"
    render_newsletter_html(final_records, html_output_file)
    
    print("Done!")

if __name__ == "__main__":
    main()