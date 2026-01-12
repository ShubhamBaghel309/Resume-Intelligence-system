# Migration: Add candidate_names column to chat_messages table
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resumes.db")

def migrate():
    """Add candidate_names column to chat_messages table"""
    
    print("🔧 Running migration: Add candidate_names to chat_messages")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if column already exists
    cursor.execute("PRAGMA table_info(chat_messages)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'candidate_names' in columns:
        print("✅ Column 'candidate_names' already exists. Skipping migration.")
        conn.close()
        return
    
    # Add the column
    try:
        cursor.execute("""
            ALTER TABLE chat_messages 
            ADD COLUMN candidate_names TEXT
        """)
        conn.commit()
        print("✅ Added 'candidate_names' column to chat_messages table")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
