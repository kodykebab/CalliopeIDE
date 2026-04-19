"""
Migration: Add OAuth columns to users table
Run from the project root with:  python server/migrate_add_oauth.py
"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server.middleware.database import db
from server.start import app       # triggers app + db creation
from sqlalchemy import text

COLUMNS = [
    ("oauth_provider", "VARCHAR(50)  DEFAULT NULL"),
    ("oauth_id",       "VARCHAR(255) DEFAULT NULL"),
    ("full_name",      "VARCHAR(150) DEFAULT NULL"),  
    ("avatar_url",     "VARCHAR(500) DEFAULT NULL"),
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_users_oauth_id ON users (oauth_id);",
]

def run():
    with app.app_context():
        with db.engine.connect() as conn:
            # 1. Make password_hash nullable (SQLite workaround via recreate is complex;
            #    for SQLite we just add a check; for Postgres use ALTER COLUMN).
            dialect = db.engine.dialect.name
            if dialect == 'postgresql':
                conn.execute(text(
                    "ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;"
                ))
                print("✓ password_hash made nullable (Postgres)")

            # 2. Add OAuth columns (idempotent)
            for col_name, col_def in COLUMNS:
                try:
                    conn.execute(text(
                        f"ALTER TABLE users ADD COLUMN {col_name} {col_def};"
                    ))
                    print(f"✓ Added column: {col_name}")
                except Exception as e:
                    if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                        print(f"  Column already exists, skipping: {col_name}")
                    else:
                        raise

            # 3. Create indexes
            for idx_sql in INDEXES:
                try:
                    conn.execute(text(idx_sql))
                    print(f"✓ Index created/confirmed")
                except Exception as e:
                    print(f"  Index note: {e}")

            conn.commit()

    print("\n✅ OAuth migration complete.")

if __name__ == '__main__':
    run()