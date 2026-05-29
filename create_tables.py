"""Create Living Review tables in SQLite database."""
import sqlite3

conn = sqlite3.connect('dev.db')
c = conn.cursor()

# Create review_updates table
c.execute('''CREATE TABLE IF NOT EXISTS review_updates (
    id VARCHAR PRIMARY KEY, 
    living_review_id VARCHAR, 
    version INTEGER, 
    papers_screened INTEGER, 
    papers_included INTEGER, 
    papers_excluded INTEGER, 
    search_start_date TIMESTAMP, 
    search_end_date TIMESTAMP, 
    prisma_flow_url TEXT, 
    change_summary TEXT, 
    notes TEXT, 
    is_published BOOLEAN, 
    published_at TIMESTAMP, 
    created_at TIMESTAMP
)''')
print('Created review_updates')

# Create review_team_members table
c.execute('''CREATE TABLE IF NOT EXISTS review_team_members (
    id VARCHAR PRIMARY KEY, 
    living_review_id VARCHAR, 
    user_id VARCHAR, 
    role VARCHAR, 
    invited_by VARCHAR, 
    invited_at TIMESTAMP, 
    accepted_at TIMESTAMP
)''')
print('Created review_team_members')

# Create paper_screenings table
c.execute('''CREATE TABLE IF NOT EXISTS paper_screenings (
    id VARCHAR PRIMARY KEY, 
    living_review_id VARCHAR, 
    paper_id VARCHAR, 
    ai_decision VARCHAR, 
    ai_confidence FLOAT, 
    ai_rationale TEXT, 
    reviewer1_id VARCHAR, 
    reviewer1_decision VARCHAR, 
    reviewer1_reason TEXT, 
    reviewer1_at TIMESTAMP, 
    reviewer2_id VARCHAR, 
    reviewer2_decision VARCHAR, 
    reviewer2_reason TEXT, 
    reviewer2_at TIMESTAMP, 
    resolver_id VARCHAR, 
    final_decision VARCHAR, 
    resolution_notes TEXT, 
    resolved_at TIMESTAMP, 
    exclusion_reason VARCHAR, 
    added_in_version INTEGER, 
    created_at TIMESTAMP, 
    updated_at TIMESTAMP
)''')
print('Created paper_screenings')

conn.commit()

# Verify
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('All tables:', [row[0] for row in c.fetchall()])
conn.close()
