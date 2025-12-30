import sys
sys.path.insert(0, "d:/GEN AI internship work/Resume Intelligence System")

from app.vectorstore.chroma_store import ResumeVectorStore

# Quick check for Shubham's project chunks
vector_store = ResumeVectorStore()

# Search for Shubham's projects
results = vector_store.search(query="Shubham Baghel projects", top_k=10)

print("=" * 70)
print("VECTOR SEARCH RESULTS FOR 'Shubham Baghel projects'")
print("=" * 70)

if results['documents'] and len(results['documents'][0]) > 0:
    print(f"\n✅ Found {len(results['documents'][0])} chunks\n")
    
    for i, (doc, meta) in enumerate(zip(results['documents'][0], results['metadatas'][0]), 1):
        chunk_type = meta.get('chunk_type', 'unknown')
        candidate = meta.get('candidate_name', 'Unknown')
        
        print(f"{i}. [{chunk_type.upper()}] {candidate}")
        
        if chunk_type == 'project':
            print(f"   Project: {meta.get('project_name', 'N/A')}")
            print(f"   Technologies: {meta.get('technologies', 'N/A')}")
        elif chunk_type == 'experience':
            print(f"   Role: {meta.get('role', 'N/A')}")
            print(f"   Company: {meta.get('company', 'N/A')}")
        
        print(f"   Text: {doc[:100]}...")
        print()
else:
    print("\n❌ NO RESULTS FOUND!")

print("=" * 70)
