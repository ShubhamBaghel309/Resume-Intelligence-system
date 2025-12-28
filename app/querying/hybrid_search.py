# app/querying/hybrid_search.py
import sqlite3
from typing import List, Dict
from app.vectorstore.chroma_store import ResumeVectorStore

class HybridResumeSearch:
    """Combines SQL filtering + Vector search for accurate results"""
    
    def __init__(self, db_path: str = "resumes.db"):
        self.db_path = db_path
        self.vector_store = ResumeVectorStore(persist_directory="storage/chroma")
    
    def search(self, query: str, filters: Dict = None, top_k: int = 5):
        """
        Hybrid search: SQL filter first, then vector search
        
        Args:
            query: Natural language query
            filters: Optional SQL filters like {"min_experience": 5, "skills": ["Python"]}
            top_k: Number of results to return
        """
        # Step 1: SQL filtering (if filters provided)
        candidate_ids = self._sql_filter(filters) if filters else None
        
        # Step 2: Vector search (within filtered candidates or all)
        vector_filters = {"resume_id": {"$in": candidate_ids}} if candidate_ids else None
        results = self.vector_store.search(
            query=query,
            top_k=top_k,
            filters=vector_filters
        )
        
        return results
    
    def _sql_filter(self, filters: Dict) -> List[str]:
        """Filter resumes using SQL based on structured criteria"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        where_clauses = []
        params = []
        
        # Filter by experience
        if "min_experience" in filters:
            where_clauses.append("total_experience_years >= ?")
            params.append(filters["min_experience"])
        
        # Filter by skills
        if "skills" in filters:
            for skill in filters["skills"]:
                where_clauses.append("technical_skills LIKE ?")
                params.append(f"%{skill}%")
        
        # Filter by location
        if "location" in filters:
            where_clauses.append("location LIKE ?")
            params.append(f"%{filters['location']}%")
        
        # Build query
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        query = f"SELECT resume_id FROM parsed_resumes WHERE {where_sql}"
        
        cursor.execute(query, params)
        resume_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return resume_ids