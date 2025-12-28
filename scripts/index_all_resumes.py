import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import json
from app.vectorstore.chroma_store import ResumeVectorStore
from app.vectorstore.embeddings import create_resume_chunks, create_resume_metadata
from app.models.resume import ParsedResume, WorkExperience, Education

DB_PATH = "resumes.db"

print("=" * 70)
print("Indexing All Parsed Resumes to Vector Store")
print("=" * 70)

# Step 1: Get ALL parsed resumes from database
print("\n📂 Loading all parsed resumes from database...")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT 
        pr.resume_id, pr.document_id, pr.candidate_name, pr.email, pr.phone, pr.location,
        pr.total_experience_years, pr.current_role, pr.technical_skills,
        pr.programming_languages, pr.frameworks, pr.tools,
        pr.work_experience, pr.education,
        d.raw_text
    FROM parsed_resumes pr
    JOIN documents d ON pr.document_id = d.document_id
""")

results = cursor.fetchall()
conn.close()

if not results:
    print("❌ No parsed resumes found. Parse some resumes first!")
    exit(1)

print(f"✅ Found {len(results)} parsed resumes in database\n")

# Step 2: Initialize vector store
print("💾 Initializing vector store...")
vector_store = ResumeVectorStore()

# Step 3: Index all resumes
print("\n🔄 Indexing resumes...")
indexed_count = 0

for row in results:
    (resume_id, document_id, candidate_name, email, phone, location,
     total_experience_years, current_role, technical_skills_json, 
     programming_languages_json, frameworks_json, tools_json,
     work_experience_json, education_json, raw_text) = row
    
    try:
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
        chunks = create_resume_chunks(parsed_resume,raw_text=raw_text)
        metadata = create_resume_metadata(parsed_resume, document_id, resume_id)
        
        # Add to vector store
        vector_store.add_resume_chunks(
            resume_id=resume_id,
            chunks=chunks,
            metadata=metadata
        )
        
        indexed_count += 1
        print(f"   ✅ {indexed_count}. {candidate_name}")
        
    except Exception as e:
        print(f"   ❌ Failed to index {candidate_name}: {e}")

print(f"\n✅ Successfully indexed {indexed_count}/{len(results)} resumes")

# Step 4: Search for GenAI experts
print("\n" + "=" * 70)
print("🔍 Searching for GenAI Experts")
print("=" * 70)

queries = [
    "generative AI expert with stable diffusion image generation experience",
    "machine learning engineer with GenAI projects",
    "AI researcher with experience in large language models",
    "deep learning specialist with generative models",
]

for query in queries:
    print(f"\n📌 Query: '{query}'")
    results = vector_store.search(query=query, top_k=5)
    
    if results['documents'] and len(results['documents'][0]) > 0:
        print(f"   Found {len(results['documents'][0])} candidates:\n")
        
        for i, (doc, meta) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
            print(f"   {i+1}. {meta['candidate_name']}")
            print(f"      Role: {meta['current_role']}")
            print(f"      Skills: {meta.get('num_skills', 0)} technical skills")
            print(f"      Relevant text: {doc[:150]}...")
            print()
    else:
        print("   ❌ No candidates found for this query\n")

print("=" * 70)
print("✅ Search Complete!")
print("=" * 70)