import os
from typing import Dict, List, Optional

import chromadb
from sentence_transformers import SentenceTransformer


class JDVectorStore:
    """Dedicated vector store for job descriptions."""

    def __init__(self, persist_directory: str = "storage/chroma_jd"):
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(persist_directory)), "model_cache")
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["HF_HOME"] = cache_dir
        os.environ["TRANSFORMERS_CACHE"] = cache_dir
        os.environ["SENTENCE_TRANSFORMERS_HOME"] = cache_dir

        abs_persist_dir = os.path.abspath(persist_directory)
        os.makedirs(abs_persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(path=abs_persist_dir)
        self.embedder = SentenceTransformer("all-mpnet-base-v2", cache_folder=cache_dir)

        self.collection = self.client.get_or_create_collection(
            name="job_descriptions",
            metadata={"hnsw:space": "cosine"},
        )

    def add_jd_chunks(self, jd_id: str, chunks: List[Dict[str, object]], metadata: Dict[str, object]) -> None:
        """Add chunks for a JD after removing any stale chunks for the same jd_id."""
        self.delete_jd_chunks(jd_id)

        ids: List[str] = []
        texts: List[str] = []
        metadatas: List[Dict[str, object]] = []

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{jd_id}__{chunk['type']}__{idx}"
            ids.append(chunk_id)
            texts.append(str(chunk["text"]))

            chunk_metadata = {
                **metadata,
                **chunk.get("metadata", {}),
                "jd_id": jd_id,
                "chunk_type": chunk.get("type", "unknown"),
            }
            metadatas.append(chunk_metadata)

        embeddings = self.embedder.encode(texts).tolist()

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts,
        )

    def delete_jd_chunks(self, jd_id: str) -> None:
        """Delete all chunks associated with a jd_id."""
        try:
            existing = self.collection.get(where={"jd_id": jd_id})
            if existing and existing.get("ids"):
                self.collection.delete(ids=existing["ids"])
        except Exception:
            pass

    def search(self, query: str, top_k: int = 5, filters: Optional[Dict] = None, chunk_type: Optional[str] = None):
        """Semantic search over JD chunks."""
        where_clause = filters
        if chunk_type and filters:
            where_clause = {"$and": [filters, {"chunk_type": chunk_type}]}
        elif chunk_type:
            where_clause = {"chunk_type": chunk_type}

        query_embedding = self.embedder.encode([query]).tolist()
        return self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            where=where_clause,
        )

    def get_jd_by_id(self, jd_id: str):
        return self.collection.get(where={"jd_id": jd_id})
