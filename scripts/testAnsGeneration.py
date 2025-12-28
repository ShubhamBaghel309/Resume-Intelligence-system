# scripts/testAnsGeneration.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.querying.hybrid_search import HybridResumeSearch
from app.generation.answer_generation import generate_answer, generate_summary
import sqlite3
import json

print("="*70)
print("Testing Answer Generation with Real Search Results")
print("="*70)

# Initialize search
searcher = HybridResumeSearch()

# Test queries
test_queries = [
    "Find me a candidates with experience of more than 5 years",
    "which candidate has projects including Retreival Augmentated Generation (RAG) and Large Language Models finetuning?",
    "Show me candidates from who is proficient in Data structures and Algorithms and have experience with competitive programming.",
]

for query in test_queries:
    print(f"\n{'='*70}")
    print(f"Query: {query}")
    print("="*70)
    
    # Step 1: Search
    print("\n🔍 Searching...")
    vector_results = searcher.search(query=query, top_k=10)
    print(f"\n🔍 Vector search returned these candidates:")
    for i, meta in enumerate(vector_results['metadatas'][0][:3]):
        print(f"  {i+1}. {meta['candidate_name']}")
        print(f"     Matched text: {vector_results['documents'][0][i][:200]}...")
    
    # Step 2: Get full resume data from database
    conn = sqlite3.connect("resumes.db")
    cursor = conn.cursor()
    
    resume_ids = [meta['resume_id'] for meta in vector_results['metadatas'][0]]
    
    full_results = []
    for resume_id in resume_ids:
        cursor.execute("""
            SELECT pr.candidate_name, pr.email, pr.phone, pr.location, 
                   pr.total_experience_years, pr.current_role, pr.technical_skills,
                   pr.work_experience, pr.education,
                   d.raw_text
            FROM parsed_resumes pr
            JOIN documents d ON pr.document_id = d.document_id
            WHERE pr.resume_id = ?
        """, (resume_id,))
        
        row = cursor.fetchone()
        if row:
            full_results.append({
                "candidate_name": row[0],
                "email": row[1],
                "phone": row[2],
                "location": row[3],
                "experience_years": row[4],
                "current_role": row[5],
                "technical_skills": row[6],
                "work_experience": row[7],
                "education": row[8],
                "raw_text": row[9]
            })
    
    conn.close()
    
    # Step 3: Generate answer
    print(f"\n💬 Generating answer...")
    answer = generate_answer(query, full_results)
    
    print(f"\n📝 Answer:\n{answer}")
    
    # Step 4: Quick summary
    print(f"\n📊 Summary: {generate_summary(full_results)}")

print("\n" + "="*70)
print("✅ Test Complete!")