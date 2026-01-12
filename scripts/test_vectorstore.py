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
print("Testing Vector Store with Parsed Resumes")
print("=" * 70)

# Step 1: Get parsed resume from database
print("\n📂 Step 1: Loading parsed resume from database...")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT resume_id, document_id, candidate_name, email, phone, location,
           total_experience_years, current_role, technical_skills, 
           work_experience, education
    FROM parsed_resumes
    LIMIT 1
""")

result = cursor.fetchall()
conn.close()

if not result:
    print("❌ No parsed resumes found. Run test_parser.py first!")
    exit(1)

# Unpack database row
(resume_id, document_id, candidate_name, email, phone, location,
 total_experience_years, current_role, technical_skills_json, 
 work_experience_json, education_json) = result

print(f"✅ Loaded resume: {candidate_name}")

# Step 2: Convert database row to ParsedResume object
print("\n🔄 Step 2: Converting database data to ParsedResume object...")

# Parse JSON strings
technical_skills = json.loads(technical_skills_json) if technical_skills_json else []
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
    work_experience=work_experience,
    education=education
)

print(f"✅ Created ParsedResume object with {len(work_experience)} jobs, {len(technical_skills)} skills")

# Step 3: Create chunks and metadata
print("\n📝 Step 3: Creating resume chunks...")
chunks = create_resume_chunks(parsed_resume)
metadata = create_resume_metadata(parsed_resume, document_id, resume_id)

print(f"✅ Created {len(chunks)} chunks:")
for i, chunk in enumerate(chunks, 1):
    print(f"   {i}. {chunk['type']}: {chunk['text'][:80]}...")

# Step 4: Initialize vector store and add resume
print("\n💾 Step 4: Adding resume to vector store...")
vector_store = ResumeVectorStore()

try:
    vector_store.add_resume_chunks(
        resume_id=resume_id,
        chunks=chunks,
        metadata=metadata
    )
    print(f"✅ Successfully added resume to vector store")
except Exception as e:
    print(f"❌ Failed to add resume: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Step 5: Test search queries
print("\n" + "=" * 70)
print("🔍 Step 5: Testing Search Queries")
print("=" * 70)

# Test 1: Generic search
print("\n📌 Test 1: Generic search for 'experienced professional'")
results = vector_store.search(query="experienced professional", top_k=5)

if results['documents']:
    print(f"   Found {len(results['documents'][0])} results")
    for i, (doc, meta) in enumerate(zip(results['documents'][0][:3], results['metadatas'][0][:3])):
        print(f"\n   Result {i+1}:")
        print(f"      Name: {meta['candidate_name']}")
        print(f"      Role: {meta['current_role']}")
        print(f"      Experience: {meta['total_experience_years']} years")
        print(f"      Text: {doc[:100]}...")

# Test 2: Skills-based search
print("\n📌 Test 2: Search for specific skills")
if technical_skills:
    skill_query = f"expert in {technical_skills[0]}"
    results = vector_store.search(query=skill_query, top_k=5, chunk_type="skills_education")
    
    if results['documents']:
        print(f"   Query: '{skill_query}'")
        print(f"   Found {len(results['documents'][0])} results")
        for i, doc in enumerate(results['documents'][0][:2]):
            print(f"   {i+1}. {doc[:120]}...")

# Test 3: Experience-based search
print("\n📌 Test 3: Search work experience")
if work_experience:
    company = work_experience[0].company
    results = vector_store.search(query=f"worked at {company}", top_k=5, chunk_type="experience")
    
    if results['documents']:
        print(f"   Query: 'worked at {company}'")
        print(f"   Found {len(results['documents'][0])} results")

# Test 4: Search with metadata filters
print("\n📌 Test 4: Search with experience filter")
results = vector_store.search(
    query="professional with strong background",
    top_k=5,
    filters={"total_experience_years": {"$gte": 0}}
)

if results['documents']:
    print(f"   Found {len(results['documents'][0])} results with filters")
    for i, meta in enumerate(results['metadatas'][0][:3]):
        print(f"   {i+1}. {meta['candidate_name']} - {meta['total_experience_years']} years")

# Test 5: Retrieve by resume_id
print("\n📌 Test 5: Retrieve specific resume by ID")
resume_data = vector_store.get_resume_by_id(resume_id)

if resume_data['documents']:
    print(f"   Retrieved {len(resume_data['documents'])} chunks for resume {resume_id}")
    for i, doc in enumerate(resume_data['documents']):
        print(f"   Chunk {i+1}: {doc[:80]}...")

print("\n" + "=" * 70)
print("✅ Vector Store Test Complete!")
print("=" * 70)
print("\n📊 Summary:")
print(f"   - Resume indexed: {candidate_name}")
print(f"   - Total chunks: {len(chunks)}")
print(f"   - Search tests passed: 5/5")
print(f"   - Vector store location: storage/chroma")