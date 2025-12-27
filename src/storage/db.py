import sqlite3
import json
import os
from typing import List, Dict, Any

class Database:
    def __init__(self, connection_string: str):
        # Use SQLite file instead of Postgres connection string
        self.db_path = "data/evidence_synthesis.db"
        self.conn = None
        self.memory_store = []

    def connect(self):
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.conn = sqlite3.connect(self.db_path)
            self.create_tables()
        except Exception as e:
            print(f"Database connection failed: {e}")
            print("Proceeding with in-memory storage for demonstration.")
            self.conn = None

    def create_tables(self):
        if not self.conn:
            return
        
        queries = [
            """
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                external_id TEXT,
                doi TEXT UNIQUE,
                title TEXT,
                abstract TEXT,
                publication_date TEXT,
                oa_status TEXT,
                classification TEXT,
                extraction TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        ]
        
        cursor = self.conn.cursor()
        for q in queries:
            cursor.execute(q)
        self.conn.commit()

    def get_existing_dois(self) -> set:
        if not self.conn:
            return set(r.get('doi') for r in self.memory_store if r.get('doi'))
            
        # Get DOIs
        query_doi = "SELECT doi FROM papers WHERE doi IS NOT NULL;"
        cursor = self.conn.cursor()
        cursor.execute(query_doi)
        existing = set(row[0] for row in cursor.fetchall())
        
        # Get External IDs (for non-DOI items like GitHub/arXiv)
        query_id = "SELECT external_id FROM papers WHERE external_id IS NOT NULL;"
        cursor.execute(query_id)
        existing.update(row[0] for row in cursor.fetchall())
        
        return existing

    def save_records(self, records: List[Dict[str, Any]]):
        if not self.conn:
            self.memory_store.extend(records)
            print(f"Saved {len(records)} records to memory.")
            return

        query = """
        INSERT OR IGNORE INTO papers (source, external_id, doi, title, abstract, publication_date, oa_status, classification, extraction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        cursor = self.conn.cursor()
        for r in records:
            # Ensure abstract is a string, not a dict (OpenAlex sometimes returns inverted index)
            abstract = r.get('abstract')
            if isinstance(abstract, dict):
                abstract = json.dumps(abstract)
            
            cursor.execute(query, (
                r.get('source'),
                r.get('id'),
                r.get('doi'),
                r.get('title'),
                abstract,
                r.get('publication_date'),
                json.dumps(r.get('oa_status', {})),
                json.dumps(r.get('classification', [])),
                json.dumps(r.get('extraction', {}))
            ))
        self.conn.commit()
        print(f"Saved {len(records)} records to database.")

    def close(self):
        if self.conn:
            self.conn.close()
