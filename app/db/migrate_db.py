# scripts/migrate_add_chat_tables.py
import sqlite3

DB_PATH = "resumes.db"

print("=" * 70)
print("📊 Database Migration: Add Chat Tables")
print("=" * 70)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Table 1: chat_sessions
print("\n✅ Creating chat_sessions table...")
cursor.execute("""
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id TEXT PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Table 2: chat_messages
print("✅ Creating chat_messages table...")
cursor.execute("""
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT,
    role TEXT,
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Agent-specific fields (NULL for user messages)
    search_type TEXT,
    query_analysis TEXT,
    
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
)
""")

# Table 3: message_results
print("✅ Creating message_results table...")
cursor.execute("""
CREATE TABLE IF NOT EXISTS message_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT,
    resume_id TEXT,
    rank INTEGER,
    
    FOREIGN KEY (message_id) REFERENCES chat_messages(message_id),
    FOREIGN KEY (resume_id) REFERENCES parsed_resumes(resume_id)
)
""")

conn.commit()
conn.close()

print("\n" + "=" * 70)
print("✅ Migration Complete! Chat tables added successfully.")
print("=" * 70)