"""Add missing columns to living_reviews table."""
import sqlite3

conn = sqlite3.connect('dev.db')
c = conn.cursor()

# Add missing columns (ignore error if already exists)
try:
    c.execute('ALTER TABLE living_reviews ADD COLUMN inclusion_criteria TEXT')
    print('Added inclusion_criteria')
except sqlite3.OperationalError as e:
    print(f'inclusion_criteria: {e}')

try:
    c.execute('ALTER TABLE living_reviews ADD COLUMN exclusion_criteria TEXT')
    print('Added exclusion_criteria')
except sqlite3.OperationalError as e:
    print(f'exclusion_criteria: {e}')

try:
    c.execute('ALTER TABLE living_reviews ADD COLUMN databases_searched TEXT')
    print('Added databases_searched')
except sqlite3.OperationalError as e:
    print(f'databases_searched: {e}')

conn.commit()
print('Done')
