import sys
sys.path.insert(0, '.')

from app.vectorstore.chroma_store import ResumeVectorStore

vs = ResumeVectorStore()

# Get all chunks for Vishnu Vikas
results = vs.collection.get(
    where={"candidate_name": "Bondalakunta Vishnu Vikas"}
)

if results and results['ids']:
    print(f"Found {len(results['ids'])} chunks for Bondalakunta Vishnu Vikas\n")
    
    for i, (chunk_id, metadata, document) in enumerate(zip(
        results['ids'],
        results['metadatas'],
        results['documents']
    ), 1):
        print("="*70)
        print(f"Chunk #{i} - Type: {metadata.get('chunk_type', 'Unknown')}")
        print("="*70)
        print(f"Chunk ID: {chunk_id}")
        print(f"\nContent:")
        print(document)
        print()
else:
    print("No chunks found")
