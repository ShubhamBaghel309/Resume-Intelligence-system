import sqlite3

DB_PATH = "resumes.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Chat Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        session_id TEXT PRIMARY KEY,
        title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Chat Messages Table (with candidate_names column)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        message_id TEXT PRIMARY KEY,
        session_id TEXT,
        role TEXT,
        content TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        candidate_names TEXT,
        search_type TEXT,
        query_analysis TEXT,
        FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
    )
    """)

    # Message Results Table
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

    # Upload Batches Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS upload_batches (
        batch_id TEXT PRIMARY KEY,
        recruiter_id TEXT,
        upload_type pdf,
        total_files INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        document_id TEXT PRIMARY KEY,
        batch_id TEXT,
        raw_text TEXT,
        original_filename TEXT,
        file_path TEXT,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (batch_id) REFERENCES upload_batches(batch_id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS parsed_resumes(
        resume_id TEXT PRIMARY KEY,
        document_id TEXT,
        
        -- Basic Info
        candidate_name TEXT,
        email TEXT,
        phone TEXT,
        location TEXT,
        
        -- Professional Summary
        total_experience_years REAL,
        current_role TEXT,
        
        -- Skills (single JSON array with ALL skills merged)
        skills TEXT,
        
        -- Work Experience (JSON array of job objects)
        work_experience TEXT,
        
        -- Education
        education TEXT,
        
        -- Projects (JSON array of project objects)
        projects TEXT,
        
        -- Additional Information (achievements, awards, references, etc.)
        additional_information TEXT,
        
        -- Metadata
        parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        indexed_at TIMESTAMP,
        
        FOREIGN KEY (document_id) REFERENCES documents(document_id)
    )
""")


    conn.commit()
    conn.close()

    print("Database initialized successfully")

if __name__ == "__main__":
    init_db()
