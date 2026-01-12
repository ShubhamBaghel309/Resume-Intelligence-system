"""
ChromaDB Vector Store Query Utility

Test and query the ChromaDB vector store directly.
"""

import sys
sys.path.insert(0, '.')

from app.vectorstore.chroma_store import ResumeVectorStore

def query_vectorstore(query: str, top_k: int = 5, filters: dict = None, show_full: bool = False):
    """
    Query the vector store and display results
    
    Args:
        query: Search query text
        top_k: Number of results to return
        filters: Optional ChromaDB filters (e.g., {"resume_id": {"$in": [...]}})
        show_full: Show full content instead of preview
    """
    
    print("="*70)
    print(f"🔍 QUERYING VECTOR STORE")
    print("="*70)
    print(f"Query: '{query}'")
    print(f"Top K: {top_k}")
    if filters:
        print(f"Filters: {filters}")
    if show_full:
        print(f"Show Full Content: True")
    print()
    
    # Initialize vector store
    vs = ResumeVectorStore()
    
    # Get collection info
    total_chunks = vs.collection.count()
    print(f"📊 Total chunks in ChromaDB: {total_chunks}\n")
    
    # Execute search
    results = vs.search(
        query=query,
        top_k=top_k,
        filters=filters
    )
    
    # Display results
    if not results or not results['ids'][0]:
        print("❌ No results found")
        return
    
    print(f"✅ Found {len(results['ids'][0])} results:\n")
    
    for i, (chunk_id, metadata, document, distance) in enumerate(zip(
        results['ids'][0],
        results['metadatas'][0],
        results['documents'][0],
        results['distances'][0]
    ), 1):
        print(f"{'='*70}")
        print(f"Result #{i}")
        print(f"{'='*70}")
        print(f"Chunk ID: {chunk_id}")
        print(f"Distance: {distance:.4f}")
        print(f"Candidate: {metadata.get('candidate_name', 'Unknown')}")
        print(f"Chunk Type: {metadata.get('chunk_type', 'Unknown')}")
        print(f"Resume ID: {metadata.get('resume_id', 'Unknown')[:8]}...")
        
        if show_full:
            print(f"\nFull Content:")
            print(document)
        else:
            print(f"\nContent Preview (first 500 chars):")
            print(f"{document[:]}...")
        print()


def inspect_candidate(candidate_name: str):
    """
    Inspect all chunks for a specific candidate
    
    Args:
        candidate_name: Name of the candidate to inspect
    """
    
    print("="*70)
    print(f"🔎 INSPECTING CANDIDATE: {candidate_name}")
    print("="*70)
    
    vs = ResumeVectorStore()
    
    # Get all chunks for this candidate
    results = vs.collection.get(
        where={"candidate_name": candidate_name}
    )
    
    if not results or not results['ids']:
        print(f"❌ No chunks found for '{candidate_name}'")
        return
    
    print(f"✅ Found {len(results['ids'])} chunks for {candidate_name}\n")
    
    for i, (chunk_id, metadata, document) in enumerate(zip(
        results['ids'],
        results['metadatas'],
        results['documents']
    ), 1):
        print(f"{'='*70}")
        print(f"Chunk #{i} - {metadata.get('chunk_type', 'Unknown')}")
        print(f"{'='*70}")
        print(f"Chunk ID: {chunk_id}")
        print(f"Resume ID: {metadata.get('resume_id', 'Unknown')[:8]}...")
        print(f"\nContent:")
        print(document)
        print()


def list_all_candidates():
    """List all unique candidates in the vector store"""
    
    print("="*70)
    print(f"👥 ALL CANDIDATES IN VECTOR STORE")
    print("="*70)
    
    vs = ResumeVectorStore()
    
    # Get all chunks
    results = vs.collection.get()
    
    if not results or not results['metadatas']:
        print("❌ No data in vector store")
        return
    
    # Extract unique candidates
    candidates = set()
    for metadata in results['metadatas']:
        name = metadata.get('candidate_name', 'Unknown')
        candidates.add(name)
    
    print(f"Total unique candidates: {len(candidates)}\n")
    
    for i, name in enumerate(sorted(candidates), 1):
        # Count chunks per candidate
        count = sum(1 for m in results['metadatas'] if m.get('candidate_name') == name)
        print(f"{i}. {name} ({count} chunks)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Query ChromaDB Vector Store")
    parser.add_argument("--query", "-q", type=str, help="Search query")
    parser.add_argument("--top-k", "-k", type=int, default=5, help="Number of results")
    parser.add_argument("--full", "-f", action="store_true", help="Show full content instead of preview")
    parser.add_argument("--inspect", "-i", type=str, help="Inspect specific candidate")
    parser.add_argument("--list", "-l", action="store_true", help="List all candidates")
    
    args = parser.parse_args()
    
    if args.list:
        list_all_candidates()
    elif args.inspect:
        inspect_candidate(args.inspect)
    elif args.query:
        query_vectorstore(args.query, args.top_k, show_full=args.full)
    else:
        # Interactive mode
        print("\n" + "="*70)
        print("ChromaDB Query Utility - Interactive Mode")
        print("="*70)
        print("\nCommands:")
        print("  query <text>        - Search the vector store")
        print("  inspect <name>      - View all chunks for a candidate")
        print("  list                - List all candidates")
        print("  exit                - Quit")
        print()
        
        while True:
            try:
                cmd = input("\n> ").strip()
                
                if not cmd:
                    continue
                
                if cmd.lower() == "exit":
                    break
                
                parts = cmd.split(maxsplit=1)
                command = parts[0].lower()
                
                if command == "query" and len(parts) > 1:
                    query_vectorstore(parts[1])
                elif command == "inspect" and len(parts) > 1:
                    inspect_candidate(parts[1])
                elif command == "list":
                    list_all_candidates()
                else:
                    print("Invalid command. Use: query <text>, inspect <name>, list, or exit")
                    
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
