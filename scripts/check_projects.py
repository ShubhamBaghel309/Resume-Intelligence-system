import sqlite3
import json
import sys
sys.path.insert(0, "d:/GEN AI internship work/Resume Intelligence System")

from app.vectorstore.chroma_store import ResumeVectorStore

# Check database for Shubham's projects
print("=" * 70)
print("CHECKING DATABASE FOR SHUBHAM'S PROJECTS")
print("=" * 70)

conn = sqlite3.connect('resumes.db')
cursor = conn.cursor()

cursor.execute('SELECT resume_id, candidate_name, projects FROM parsed_resumes WHERE candidate_name LIKE "%Shubham%"')
result = cursor.fetchone()

if result:
    resume_id, name, projects_json = result
    print(f"\n✅ Found candidate: {name}")
    print(f"   Resume ID: {resume_id}")
    
    projects = json.loads(projects_json) if projects_json else []
    print(f"\n📋 Projects in Database ({len(projects)} total):")
    for i, proj in enumerate(projects, 1):
        print(f"\n   {i}. {proj.get('name', 'Unnamed')}")
        print(f"      Description: {proj.get('description', 'N/A')[:100]}...")
        print(f"      Technologies: {', '.join(proj.get('technologies', []))}")
else:
    print("❌ No candidate found with name containing 'Shubham'")
    sys.exit(1)

conn.close()

# Check vector store for project chunks
print("\n" + "=" * 70)
print("CHECKING VECTOR STORE FOR PROJECT CHUNKS")
print("=" * 70)

vector_store = ResumeVectorStore()

# Get all chunks for Shubham's resume
chunks = vector_store.get_resume_by_id(resume_id)

print(f"\n✅ Found {len(chunks['ids'])} chunks in vector store")

# Count chunk types
chunk_types = {}
for metadata in chunks['metadatas']:
    chunk_type = metadata.get('chunk_type', 'unknown')
    chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

print(f"\n📊 Chunk Type Breakdown:")
for chunk_type, count in chunk_types.items():
    print(f"   - {chunk_type}: {count}")

# Show project chunks specifically
print(f"\n📋 Project Chunks:")
project_count = 0
for i, (chunk_id, doc, metadata) in enumerate(zip(chunks['ids'], chunks['documents'], chunks['metadatas'])):
    if metadata.get('chunk_type') == 'project':
        project_count += 1
        print(f"\n   Project {project_count}:")
        print(f"   - Chunk ID: {chunk_id}")
        print(f"   - Project Name: {metadata.get('project_name', 'N/A')}")
        print(f"   - Text Preview: {doc[:150]}...")

if project_count == 0:
    print("   ❌ NO PROJECT CHUNKS FOUND IN VECTOR STORE!")
    print("\n🔍 This is the issue - projects are in the database but not indexed as chunks")

print("\n" + "=" * 70)
