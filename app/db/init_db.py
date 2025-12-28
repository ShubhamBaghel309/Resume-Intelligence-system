import sqlite3

DB_PATH = "resumes.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS upload_batches (
        batch_id TEXT PRIMARY KEY,
        recruiter_id TEXT,
        upload_type TEXT,
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
        
        -- Skills (JSON array as string: ["Python", "AWS", "GenAI"])
        technical_skills TEXT,
        
        -- Work Experience (JSON array of job objects)
        work_experience TEXT,
        
        -- Education
        education TEXT,
        
        -- Metadata
        parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (document_id) REFERENCES documents(document_id)
    )
""")


    conn.commit()
    conn.close()

    print("Database initialized successfully")

if __name__ == "__main__":
    init_db()
