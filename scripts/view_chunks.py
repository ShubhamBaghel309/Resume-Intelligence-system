"""
View all chunks for a candidate - FULL content, no truncation
"""

import sys
sys.path.insert(0, '.')

from app.vectorstore.chroma_store import ResumeVectorStore

def view_candidate_chunks(candidate_name: str):
    """
    Display ALL chunks for a candidate with FULL content
    
    Args:
        candidate_name: Name of the candidate
    """
    
    print("="*80)
    print(f"📋 ALL CHUNKS FOR: {candidate_name}")
    print("="*80)
    print()
    
    vs = ResumeVectorStore()
    
    # Get all chunks for this candidate
    results = vs.collection.get(
        where={"candidate_name": candidate_name}
    )
    
    if not results or not results['ids']:
        print(f"❌ No chunks found for '{candidate_name}'")
        print("\nTip: Check spelling or use --list to see all candidates")
        return
    
    print(f"✅ Found {len(results['ids'])} chunks\n")
    
    # Display each chunk
    for i, (chunk_id, metadata, document) in enumerate(zip(
        results['ids'],
        results['metadatas'],
        results['documents']
    ), 1):
        chunk_type = metadata.get('chunk_type', 'Unknown')
        resume_id = metadata.get('resume_id', 'Unknown')
        
        print("="*80)
        print(f"CHUNK #{i}: {chunk_type.upper()}")
        print("="*80)
        print(f"Chunk ID: {chunk_id}")
        print(f"Resume ID: {resume_id}")
        print(f"Length: {len(document)} characters")
        print()
        print("--- FULL CONTENT ---")
        print(document)
        print()
        print("="*80)
        print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="View all chunks for a candidate")
    parser.add_argument("name", type=str, help="Candidate name (e.g., 'Suryansh Rathore')")
    parser.add_argument("--save", "-s", type=str, help="Save to file instead of printing")
    
    args = parser.parse_args()
    
    if args.save:
        # Redirect output to file
        import sys
        original_stdout = sys.stdout
        with open(args.save, 'w', encoding='utf-8') as f:
            sys.stdout = f
            view_candidate_chunks(args.name)
        sys.stdout = original_stdout
        print(f"✅ Saved to {args.save}")
    else:
        view_candidate_chunks(args.name)
