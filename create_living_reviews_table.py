"""Create living_reviews table in SQLite database."""
import sqlite3

conn = sqlite3.connect('dev.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS living_reviews (
    id VARCHAR PRIMARY KEY, 
    topic_id VARCHAR,
    owner_id VARCHAR,
    title VARCHAR(500) NOT NULL, 
    slug VARCHAR(255) UNIQUE, 
    description TEXT, 
    review_type VARCHAR(50), 
    protocol_url TEXT,
    protocol_file_url TEXT,
    publication_doi VARCHAR(255),
    publication_citation TEXT,
    publication_url TEXT,
    prospero_id VARCHAR(50),
    cochrane_id VARCHAR(50),
    campbell_id VARCHAR(50),
    osf_id VARCHAR(50),
    status VARCHAR(20) DEFAULT 'ACTIVE',
    is_public BOOLEAN DEFAULT 0,
    pico_population TEXT,
    pico_intervention TEXT,
    pico_comparator TEXT,
    pico_outcome TEXT,
    pico_study_design TEXT,
    original_search_date TIMESTAMP,
    total_screened INTEGER DEFAULT 0,
    total_included INTEGER DEFAULT 0,
    total_excluded INTEGER DEFAULT 0,
    current_version INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)''')
conn.commit()
print('Created living_reviews table')

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([row[0] for row in c.fetchall()])
