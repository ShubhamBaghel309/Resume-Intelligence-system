# scripts/test_hybrid_search.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.querying.hybrid_search import HybridResumeSearch
import sqlite3

print("=" * 70)
print("Testing Hybrid Search")
print("=" * 70)

# Initialize hybrid search
searcher = HybridResumeSearch()

def display_results(results):
    """Display search results with resume details"""
    if not results or not results['documents'][0]:
        print("   ❌ No results found")
        return
    
    conn = sqlite3.connect("resumes.db")
    cursor = conn.cursor()
    
    # Get unique resume IDs from metadata
    resume_ids = []
    for metadata in results['metadatas'][0]:
        rid = metadata.get('resume_id')
        if rid and rid not in resume_ids:
            resume_ids.append(rid)
    
    print(f"   Found {len(resume_ids)} candidates:\n")
    
    # Fetch full details from database
    for i, resume_id in enumerate(resume_ids[:5], 1):  # Show top 5
        cursor.execute("""
            SELECT candidate_name, email, phone, location, 
                   total_experience_years, current_role, technical_skills
            FROM parsed_resumes 
            WHERE resume_id = ?
        """, (resume_id,))
        
        row = cursor.fetchone()
        if row:
            name, email, phone, location, exp, role, skills = row
            print(f"   {i}. {name or 'N/A'}")
            print(f"      Role: {role or 'Not specified'}")
            print(f"      Experience: {exp or 'N/A'} years")
            print(f"      Location: {location or 'N/A'}")
            print(f"      Email: {email or 'N/A'}")
            print(f"      Skills: {skills[:80]}..." if skills and len(skills) > 80 else f"      Skills: {skills or 'N/A'}")
            print()
    
    conn.close()

# Test 1: Simple semantic search (no filters)
print("\n🔍 Test 1: Simple search - 'Python developer'")
results = searcher.search(query="Python developer", top_k=5)
display_results(results)

# Test 2: Search with skill filter
print("\n🔍 Test 2: SQL Filter - Only candidates with 'LLM' skill")
results = searcher.search(
    query="machine learning expert",
    filters={"skills": ["LLM"]},
    top_k=5
)
display_results(results)

# Test 3: Search with experience filter
print("\n🔍 Test 3: SQL Filter - Candidates with 5+ years experience")
results = searcher.search(
    query="senior developer",
    filters={"min_experience": 5},
    top_k=10
)
display_results(results)

print("\n" + "=" * 70)
print("✅ Hybrid Search Test Complete!")
print("=" * 70)