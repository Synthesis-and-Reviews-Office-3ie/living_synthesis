"""
Migration script to add workflow tables:
- reviewer_assignments: Track paper assignments to reviewers
- screening_conflicts: Track disagreements for resolution  
- workflow_metrics: Store Cohen's Kappa and other metrics
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'dev.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create reviewer_assignments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviewer_assignments (
            id VARCHAR(36) PRIMARY KEY,
            living_review_id VARCHAR(36) NOT NULL,
            paper_id VARCHAR(36) NOT NULL,
            user_id VARCHAR(36) NOT NULL,
            assigned_by VARCHAR(36),
            assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            due_date DATETIME,
            assignment_order INTEGER DEFAULT 1,
            is_blinded BOOLEAN DEFAULT 0,
            status VARCHAR(20) DEFAULT 'pending',
            started_at DATETIME,
            completed_at DATETIME,
            notes TEXT,
            FOREIGN KEY (living_review_id) REFERENCES living_reviews(id),
            FOREIGN KEY (paper_id) REFERENCES papers(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (assigned_by) REFERENCES users(id)
        )
    """)
    print("Created reviewer_assignments table")
    
    # Create screening_conflicts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screening_conflicts (
            id VARCHAR(36) PRIMARY KEY,
            living_review_id VARCHAR(36) NOT NULL,
            paper_id VARCHAR(36) NOT NULL,
            screening_id VARCHAR(36) NOT NULL,
            conflict_type VARCHAR(50) NOT NULL,
            decision_1 VARCHAR(50),
            reviewer_1_id VARCHAR(36),
            decision_2 VARCHAR(50),
            reviewer_2_id VARCHAR(36),
            resolution_status VARCHAR(20) DEFAULT 'unresolved',
            resolved_by VARCHAR(36),
            final_decision VARCHAR(50),
            resolution_notes TEXT,
            resolved_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (living_review_id) REFERENCES living_reviews(id),
            FOREIGN KEY (paper_id) REFERENCES papers(id),
            FOREIGN KEY (screening_id) REFERENCES paper_screenings(id),
            FOREIGN KEY (reviewer_1_id) REFERENCES users(id),
            FOREIGN KEY (reviewer_2_id) REFERENCES users(id),
            FOREIGN KEY (resolved_by) REFERENCES users(id)
        )
    """)
    print("Created screening_conflicts table")
    
    # Create workflow_metrics table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_metrics (
            id VARCHAR(36) PRIMARY KEY,
            living_review_id VARCHAR(36) NOT NULL,
            cohens_kappa REAL,
            agreement_rate REAL,
            disagreement_count INTEGER DEFAULT 0,
            total_comparisons INTEGER DEFAULT 0,
            ai_accuracy REAL,
            ai_precision REAL,
            ai_recall REAL,
            ai_f1_score REAL,
            true_positives INTEGER DEFAULT 0,
            false_positives INTEGER DEFAULT 0,
            true_negatives INTEGER DEFAULT 0,
            false_negatives INTEGER DEFAULT 0,
            avg_time_per_paper_seconds REAL,
            total_papers_screened INTEGER DEFAULT 0,
            reviewer_count INTEGER DEFAULT 0,
            papers_per_reviewer_avg REAL,
            papers_per_reviewer_min INTEGER,
            papers_per_reviewer_max INTEGER,
            calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            calculated_by VARCHAR(36),
            FOREIGN KEY (living_review_id) REFERENCES living_reviews(id),
            FOREIGN KEY (calculated_by) REFERENCES users(id)
        )
    """)
    print("Created workflow_metrics table")
    
    # Create indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_review ON reviewer_assignments(living_review_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_user ON reviewer_assignments(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_status ON reviewer_assignments(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_review ON screening_conflicts(living_review_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_status ON screening_conflicts(resolution_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_review ON workflow_metrics(living_review_id)")
    print("Created indexes")
    
    conn.commit()
    conn.close()
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    migrate()
