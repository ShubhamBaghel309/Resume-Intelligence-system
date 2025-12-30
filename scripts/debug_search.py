import sqlite3
import sys
sys.path.insert(0, '.')

# Check what SQL returns
conn = sqlite3.connect('resumes.db')
cursor = conn.cursor()
cursor.execute('SELECT resume_id, candidate_name, total_experience_years FROM parsed_resumes WHERE total_experience_years >= 10')
sql_results = cursor.fetchall()
print('=== SQL RESULTS (10+ years) ===')
for rid, name, exp in sql_results:
    print(f'  {rid[:8]}... | {name} | {exp} years')

resume_ids = [r[0] for r in sql_results]
conn.close()

# Check what's in ChromaDB for those IDs
from app.vectorstore.chroma_store import ResumeVectorStore
vs = ResumeVectorStore()

print(f'\n=== CHROMADB CHECK ===')
print(f'SQL found {len(resume_ids)} resume_ids')

# Try to find these in ChromaDB
for rid in resume_ids[:3]:  # Check first 3
    result = vs.collection.get(where={'resume_id': rid})
    count = len(result['ids']) if result['ids'] else 0
    print(f'  {rid[:8]}... has {count} chunks in ChromaDB')

# Now test vector search with filter
print('\n=== VECTOR SEARCH WITH FILTER ===')
search_result = vs.search(
    query="work experience",
    filters={"resume_id": {"$in": resume_ids}},
    top_k=5
)
print(f'Vector search returned {len(search_result["ids"][0])} results')
for meta in search_result['metadatas'][0][:5]:
    print(f'  {meta.get("candidate_name")} | {meta.get("resume_id", "")[:8]}...')
