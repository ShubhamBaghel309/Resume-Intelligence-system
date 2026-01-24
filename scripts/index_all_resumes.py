import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import json
from datetime import datetime
from app.vectorstore.chroma_store import ResumeVectorStore
from app.vectorstore.embeddings import create_resume_chunks, create_resume_metadata
from app.models.resume import ParsedResume, WorkExperience, Education, Project

DB_PATH = "resumes.db"

print("=" * 70)
print("Indexing All Unindexed Parsed Resumes to Vector Store (Incremental)")
print("=" * 70)

# Step 1: Get ONLY unparsed resumes from database (where indexed_at IS NULL)
print("\n📂 Loading unparsed resumes from database...")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT 
        pr.resume_id, pr.document_id, pr.candidate_name, pr.email, pr.phone, pr.location,
        pr.total_experience_years, pr.current_role, pr.skills,
        pr.work_experience, pr.education, pr.projects, pr.additional_information,
        d.raw_text
    FROM parsed_resumes pr
    JOIN documents d ON pr.document_id = d.document_id
    WHERE pr.indexed_at IS NULL
    ORDER BY pr.parsed_at
""")

results = cursor.fetchall()
conn.close()

if not results:
    print("❌ No unindexed parsed resumes found.")
    print("   All resumes may already be indexed or no resumes have been parsed yet.")
    exit(0)

print(f"✅ Found {len(results)} unindexed resumes to index\n")

# Step 2: Initialize vector store
print("💾 Initializing vector store...")
vector_store = ResumeVectorStore()

# Step 3: Index all unindexed resumes
print("\n🔄 Indexing resumes...")
indexed_count = 0

for row in results:
    (resume_id, document_id, candidate_name, email, phone, location,
     total_experience_years, current_role, skills_json,
     work_experience_json, education_json, projects_json, additional_info, raw_text) = row
    
    try:
        # Parse JSON strings - single skills column
        skills = json.loads(skills_json) if skills_json else []
        work_experience_data = json.loads(work_experience_json) if work_experience_json else []
        education_data = json.loads(education_json) if education_json else []
        projects_data = json.loads(projects_json) if projects_json else []
        
        # Reconstruct Pydantic objects
        work_experience = [WorkExperience(**job) for job in work_experience_data]
        education = [Education(**edu) for edu in education_data]
        projects = [Project(**proj) for proj in projects_data]
        
        # Create ParsedResume object (with additional_information)
        parsed_resume = ParsedResume(
            candidate_name=candidate_name,
            email=email,
            phone=phone,
            location=location,
            total_experience_years=total_experience_years,
            current_role=current_role,
            technical_skills=skills,  # All skills merged here
            programming_languages=[],
            frameworks=[],
            tools=[],
            work_experience=work_experience,
            education=education,
            projects=projects,
            additional_information=additional_info  # NEW
        )
        
        # Create chunks and metadata
        chunks = create_resume_chunks(parsed_resume,raw_text=raw_text)
        metadata = create_resume_metadata(parsed_resume, document_id, resume_id)
        
        # Add to vector store
        vector_store.add_resume_chunks(
            resume_id=resume_id,
            chunks=chunks,
            metadata=metadata
        )
        
        # ✅ UPDATE indexed_at timestamp after successful indexing
        update_conn = sqlite3.connect(DB_PATH)
        update_cursor = update_conn.cursor()
        update_cursor.execute(
            "UPDATE parsed_resumes SET indexed_at = ? WHERE resume_id = ?",
            (datetime.now().isoformat(), resume_id)
        )
        update_conn.commit()
        update_conn.close()
        
        indexed_count += 1
        print(f"   ✅ {indexed_count}. {candidate_name}")
        
    except Exception as e:
        print(f"   ❌ Failed to index {candidate_name}: {e}")

print(f"\n✅ Successfully indexed {indexed_count}/{len(results)} resumes")

# Step 4: Verify indexing status
print("\n" + "=" * 70)
print("📊 Indexing Status Summary")
print("=" * 70)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT 
        COUNT(*) as total_parsed,
        COUNT(CASE WHEN indexed_at IS NOT NULL THEN 1 END) as indexed,
        COUNT(CASE WHEN indexed_at IS NULL THEN 1 END) as not_indexed
    FROM parsed_resumes
""")

total_parsed, indexed, not_indexed = cursor.fetchone()
conn.close()

print(f"   Total Parsed Resumes: {total_parsed}")
print(f"   ✅ Indexed: {indexed}")
print(f"   ⏳ Pending: {not_indexed}")
print("=" * 70)

print("\n📌 To process more resumes:")
print("   1. Run 'python scripts/text_extraction.py' to extract unextracted PDFs")
print("   2. Run 'python scripts/test_parser.py' to parse extracted resumes")
print("   3. Run 'python scripts/index_all_resumes.py' to index parsed resumes")
print("=" * 70)