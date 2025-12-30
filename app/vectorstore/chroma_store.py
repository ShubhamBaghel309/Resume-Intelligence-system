import chromadb
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from chromadb.config import Settings

class ResumeVectorStore:
    """Production-grade vector store for resume embeddings"""
    
    def __init__(self, persist_directory: str = "storage/chroma"):
        # Persistent client (survives restarts)
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Best balance of speed and quality
        self.embedder = SentenceTransformer('all-mpnet-base-v2')
        
        # Create collection with metadata indexing
        self.collection = self.client.get_or_create_collection(
            name="resumes",
            metadata={"hnsw:space": "cosine"}  # Better for semantic similarity
        )
    
    def add_resume_chunks(
        self, 
        resume_id: str, 
        chunks: List[Dict[str, str]], 
        metadata: Dict
    ):
        """
        Add multiple chunks for one resume (idempotent - safe to call multiple times)
        
        Args:
            resume_id: Unique resume identifier
            chunks: [{"type": "summary", "text": "..."}, ...]
            metadata: Common metadata for all chunks
        """
        # CRITICAL FIX: Delete existing chunks for this resume before adding new ones
        # This prevents duplicate/stale chunks when re-indexing
        try:
            existing = self.collection.get(where={"resume_id": resume_id})
            if existing and existing['ids']:
                self.collection.delete(ids=existing['ids'])
                print(f"   🗑️  Deleted {len(existing['ids'])} old chunks for resume {resume_id[:8]}...")
        except Exception:
            pass  # Collection may be empty or no existing chunks
        
        ids = []
        texts = []
        metadatas = []
        
        for i, chunk in enumerate(chunks):
            # Generate unique ID: resume_id + chunk type + index (for multiple experience chunks)
            chunk_id = f"{resume_id}__{chunk['type']}__{i}"
            ids.append(chunk_id)
            texts.append(chunk['text'])
            
            # Each chunk now has its own metadata
            if 'metadata' in chunk:
                # Use chunk-specific metadata
                chunk_metadata = {
                    **chunk['metadata'],
                    "resume_id": resume_id,
                    "document_id": metadata.get("document_id", "")
                }
            else:
                # Fallback to common metadata
                chunk_metadata = {
                    **metadata,
                    "chunk_type": chunk['type'],
                    "resume_id": resume_id
                }
            metadatas.append(chunk_metadata)
        
        # Generate embeddings (batch for efficiency)
        embeddings = self.embedder.encode(texts).tolist()
        
        # Add to Chroma (now safe since we deleted old chunks first)
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts
        )
    
    def search(
        self, 
        query: str, 
        top_k: int = 10, 
        filters: Dict = None,
        chunk_type: str = None
    ):
        """
        Semantic search with optional filters
        
        Args:
            query: Search query
            top_k: Number of results
            filters: Metadata filters (Chroma where clause)
            chunk_type: Limit to specific chunk type
        """
        # Add chunk_type to filters if specified
        if chunk_type and filters:
            filters = {"$and": [filters, {"chunk_type": chunk_type}]}
        elif chunk_type:
            filters = {"chunk_type": chunk_type}
        
        # Generate query embedding
        query_embedding = self.embedder.encode([query]).tolist()
        
        # Search
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            where=filters
        )
        
        return results
    
    def get_resume_by_id(self, resume_id: str):
        """Retrieve all chunks for a specific resume"""
        results = self.collection.get(
            where={"resume_id": resume_id}
        )
        return results