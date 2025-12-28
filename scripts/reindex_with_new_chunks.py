# scripts/reindex_with_new_chunks.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import json
import shutil
from app.vectorstore.chroma_store import ResumeVectorStore
from app.vectorstore.embeddings import create_resume_chunks, create_resume_metadata
from app.models.resume import ParsedResume, WorkExperience, Education

DB_PATH = "resumes.db"

print("="*70)
print("Re-indexing with New 4-Chunk Embeddings")
print("="*70)

# Step 1: Clear old vector store
print("\n🗑️  Clearing old vector store...")
chroma_path = Path("storage/chroma")
if chroma_path.exists():
    shutil.rmtree(chroma_path)
    print("  ✓ Old vector store deleted")

# Step 2: Initialize new vector store
print("\n💾 Initializing new vector store...")
vector_store = ResumeVectorStore()

# Step 3: Get all parsed resumes
print("\n📂 Loading parsed resumes from database...")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT 
        resume_id, document_id, candidate_name, email, phone, location,
        total_experience_years, current_role, technical_skills,
        programming_languages, frameworks, tools,
        work_experience, education
    FROM parsed_resumes
""")

results = cursor.fetchall()
conn.close()

total = len(results)
print(f"  ✓ Found {total} resumes\n")

# Step 4: Index all resumes
print("🔄 Indexing resumes with new 4-chunk strategy...\n")
indexed_count = 0

for row in results:
    try:
        (resume_id, document_id, candidate_name, email, phone, location,
         total_experience_years, current_role, technical_skills_json,
         programming_languages_json, frameworks_json, tools_json,
         work_experience_json, education_json) = row
        
        # Parse JSON strings
        technical_skills = json.loads(technical_skills_json) if technical_skills_json else []
        programming_languages = json.loads(programming_languages_json) if programming_languages_json else []
        frameworks = json.loads(frameworks_json) if frameworks_json else []
        tools = json.loads(tools_json) if tools_json else []
        work_experience_data = json.loads(work_experience_json) if work_experience_json else []
        education_data = json.loads(education_json) if education_json else []
        
        # Reconstruct Pydantic objects
        work_experience = [WorkExperience(**job) for job in work_experience_data]
        education = [Education(**edu) for edu in education_data]
        
        # Create ParsedResume object
        parsed_resume = ParsedResume(
            candidate_name=candidate_name,
            email=email,
            phone=phone,
            location=location,
            total_experience_years=total_experience_years,
            current_role=current_role,
            technical_skills=technical_skills,
            programming_languages=programming_languages,
            frameworks=frameworks,
            tools=tools,
            work_experience=work_experience,
            education=education
        )
        
        # Create chunks and metadata
        chunks = create_resume_chunks(parsed_resume)
        metadata = create_resume_metadata(parsed_resume, document_id, resume_id)
        
        # Add to vector store
        vector_store.add_resume_chunks(
            resume_id=resume_id,
            chunks=chunks,
            metadata=metadata
        )
        
        indexed_count += 1
        print(f"  ✅ {indexed_count}. {candidate_name} (4 chunks)")
        
    except Exception as e:
        print(f"  ❌ Failed to index {candidate_name}: {e}")

print(f"\n{'='*70}")
print(f"✅ Re-indexing Complete!")
print(f"{'='*70}")
print(f"Indexed: {indexed_count}/{total} resumes")
print(f"Total chunks: {indexed_count * 4} (4 per resume)")
print(f"\n🎯 Next: Run test_hybrid_search.py to see improved results!")