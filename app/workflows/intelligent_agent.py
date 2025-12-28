# app/workflows/intelligent_agent.py
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import os

# Import existing components
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from querying.hybrid_search import HybridResumeSearch
from generation.answer_generation import generate_answer
import sqlite3


# ============= State Definition =============
class AgentState(TypedDict):
    """State that flows through the agent graph"""
    query: str                           # User's original question
    query_analysis: dict                 # LLM's analysis of the query
    search_strategy: str                 # Chosen strategy: "sql", "vector", "hybrid"
    sql_filters: dict                    # Extracted SQL filters
    vector_query: str                    # Reformulated query for vector search
    candidate_ids: list                  # Resume IDs from SQL filtering
    search_results: list                 # Raw search results
    final_results: list                  # Deduplicated and enriched results
    answer: str                          # Generated natural language answer
    should_retry: bool                   # Whether to retry with different strategy
    retry_count: int                     # Number of retries attempted


# ============= Query Analysis Models =============
class QueryAnalysis(BaseModel):
    """Structured output from query analyzer"""
    query_type: Literal["name_based", "skill_based", "experience_based", "project_based", "education_based", "location_based", "complex_multi_criteria"] = Field(
        description="Primary type of the query"
    )
    
    intent: str = Field(
        description="What the user wants to know (e.g., 'find candidates', 'get education details', 'compare candidates')"
    )
    
    entities: dict = Field(
        description="Extracted entities: names, skills, companies, locations, degrees, etc."
    )
    
    filters: dict = Field(
        description="Structured filters: min_experience, max_experience, location, required_skills, etc."
    )
    
    search_strategy: Literal["sql_first", "vector_first", "hybrid", "sql_only"] = Field(
        description="Recommended search strategy based on query analysis"
    )
    
    confidence: float = Field(
        description="Confidence in the analysis (0.0 to 1.0)",
        ge=0.0,
        le=1.0
    )
    
    reasoning: str = Field(
        description="Brief explanation of why this strategy was chosen"
    )


# ============= Initialize LLM =============
from dotenv import load_dotenv
load_dotenv()
# API key loaded from .env file

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.1,  # Low temperature for structured analysis
    max_tokens=1024
)

answer_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.3,
    max_tokens=2048
)


# ============= Agent Nodes =============

def analyze_query_node(state: AgentState) -> AgentState:
    """
    Node 1: Analyze user query to understand intent and plan strategy
    
    This is the BRAIN of the agent - decides what to do based on the question
    """
    
    analysis_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a query analyzer for a resume search system. Analyze user queries and plan the best search strategy.

Your task:
1. Identify query type (name-based, skill-based, experience-based, etc.)
2. Extract structured entities (names, skills, locations, experience years, etc.)
3. Recommend search strategy:
   - "sql_first": Use SQL to find exact matches (names, locations), then vector search if needed
   - "vector_first": Use semantic search for skills, projects, complex criteria
   - "hybrid": Combine SQL filtering + vector ranking for multi-criteria queries
   - "sql_only": Pure SQL for simple structured queries

Examples:

Query: "Find Anshika Chaudhary's education"
→ Type: name_based, Strategy: sql_first (exact name match in SQL)

Query: "Python developers with 5+ years experience"  
→ Type: skill_based + experience_based, Strategy: hybrid (SQL filters experience, vector finds Python expertise)

Query: "Who worked on RAG projects?"
→ Type: project_based, Strategy: vector_first (projects described in full text, need semantic search)

Query: "Compare Machine Learning engineers in Bangalore"
→ Type: complex_multi_criteria, Strategy: hybrid (SQL filters location, vector ranks ML expertise)

Be intelligent - choose the strategy that will give BEST results, not just fastest."""),
        
        ("user", "Query: {query}\n\nAnalyze this query and recommend the best search strategy.")
    ])
    
    chain = analysis_prompt | llm.with_structured_output(QueryAnalysis)
    
    try:
        analysis = chain.invoke({"query": state["query"]})
        
        state["query_analysis"] = analysis.model_dump()  # Convert Pydantic to dict
        state["search_strategy"] = analysis.search_strategy
        state["sql_filters"] = analysis.filters
        
        print(f"\n🧠 QUERY ANALYSIS:")
        print(f"   Type: {analysis.query_type}")  # ✅ Direct attribute access
        print(f"   Strategy: {analysis.search_strategy}")
        print(f"   Reasoning: {analysis.reasoning}")
        print(f"   Confidence: {analysis.confidence:.2f}")
        
    except Exception as e:
        print(f"⚠️  Analysis failed: {e}. Defaulting to hybrid search.")
        state["query_analysis"] = {"error": str(e)}
        state["search_strategy"] = "hybrid"
        state["sql_filters"] = {}
    
    return state


def sql_filter_node(state: AgentState) -> AgentState:
    """
    Node 2: Execute SQL filtering based on extracted entities
    
    Only runs if strategy requires SQL (sql_first, sql_only, hybrid)
    """
    
    if state["search_strategy"] == "vector_first":
        print("\n📊 SKIPPING SQL (vector-first strategy)")
        state["candidate_ids"] = []
        return state
    
    print("\n📊 EXECUTING SQL FILTERS...")
    
    filters = state["sql_filters"]
    analysis = state["query_analysis"]
    
    # Build SQL query dynamically
    import os
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "resumes.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    where_clauses = []
    params = []
    
    # Extract name from entities
    entities = analysis.get("entities", {})
    if entities.get("names"):
        name = entities["names"][0]  # First name mentioned
        where_clauses.append("candidate_name LIKE ?")
        params.append(f"%{name}%")
    
    # Experience filters
    if filters.get("min_experience"):
        where_clauses.append("total_experience_years >= ?")
        params.append(filters["min_experience"])
    
    if filters.get("max_experience"):
        where_clauses.append("total_experience_years <= ?")
        params.append(filters["max_experience"])
    
    # Location filter
    if filters.get("location"):
        where_clauses.append("location LIKE ?")
        params.append(f"%{filters['location']}%")
    
    # Skills filter (check in all skill columns)
    if filters.get("required_skills"):
        skill_conditions = []
        for skill in filters["required_skills"]:
            skill_conditions.append(
                "(programming_languages LIKE ? OR frameworks LIKE ? OR tools LIKE ? OR technical_skills LIKE ?)"
            )
            params.extend([f"%{skill}%"] * 4)
        where_clauses.append(f"({' OR '.join(skill_conditions)})")
    
    # Build final query
    sql = "SELECT resume_id FROM parsed_resumes"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    
    print(f"   SQL: {sql}")
    print(f"   Params: {params}")
    
    cursor.execute(sql, params)
    results = cursor.fetchall()
    conn.close()
    
    candidate_ids = [row[0] for row in results]
    state["candidate_ids"] = candidate_ids
    
    print(f"   ✅ Found {len(candidate_ids)} candidates via SQL")
    
    return state


def vector_search_node(state: AgentState) -> AgentState:
    """
    Node 3: Execute vector search with optional metadata filtering
    
    Uses candidate_ids from SQL as metadata filter if available
    """
    
    print("\n🔍 EXECUTING VECTOR SEARCH...")
    
    searcher = HybridResumeSearch()
    
    # Prepare metadata filter if we have candidate IDs from SQL
    vector_filters = {}
    if state["candidate_ids"]:
        vector_filters = {"resume_id": {"$in": state["candidate_ids"]}}
        print(f"   Filtering to {len(state['candidate_ids'])} candidates from SQL")
    
    # Execute search
    results = searcher.search(
        query=state["vector_query"],
        filters=vector_filters if vector_filters else None,
        top_k=10
    )
    
    state["search_results"] = results
    
    print(f"   ✅ Found {len(results.get('ids', [[]])[0])} vector matches")
    
    return state


def enrich_results_node(state: AgentState) -> AgentState:
    """
    Node 4: Fetch full resume data from SQLite and deduplicate
    
    Handles same resume appearing multiple times (different chunks)
    """
    
    print("\n💎 ENRICHING RESULTS...")
    
    if not state["search_results"] or not state["search_results"].get("metadatas"):
        state["final_results"] = []
        state["should_retry"] = True
        return state
    
    # Deduplicate by resume_id (keep highest scoring chunk per resume)
    seen_resumes = {}
    metadatas = state["search_results"]["metadatas"][0]
    documents = state["search_results"]["documents"][0]
    distances = state["search_results"]["distances"][0]
    
    for meta, doc, dist in zip(metadatas, documents, distances):
        resume_id = meta.get("resume_id")
        if resume_id not in seen_resumes or dist < seen_resumes[resume_id]["distance"]:
            seen_resumes[resume_id] = {
                "resume_id": resume_id,
                "distance": dist,
                "chunk_type": meta.get("chunk_type"),
                "snippet": doc[:200]
            }
    
    unique_ids = list(seen_resumes.keys())
    print(f"   Deduplicated: {len(metadatas)} chunks → {len(unique_ids)} unique resumes")
    
    # Fetch full data from SQLite
    import os
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "resumes.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    placeholders = ",".join("?" * len(unique_ids))
    query = f"""
        SELECT 
            pr.*,
            d.raw_text
        FROM parsed_resumes pr
        LEFT JOIN documents d ON pr.document_id = d.document_id
        WHERE pr.resume_id IN ({placeholders})
    """
    
    cursor.execute(query, unique_ids)
    rows = cursor.fetchall()
    conn.close()
    
    final_results = [dict(row) for row in rows]
    state["final_results"] = final_results
    
    print(f"   ✅ Enriched {len(final_results)} resumes with full data")
    
    # Decide if we should retry
    state["should_retry"] = len(final_results) == 0
    
    return state


def generate_answer_node(state: AgentState) -> AgentState:
    """
    Node 5: Generate natural language answer using LLM
    
    Uses existing answer generation function
    """
    
    print("\n🤖 GENERATING ANSWER...")
    
    if not state["final_results"]:
        state["answer"] = "I couldn't find any candidates matching your criteria. Try:\n- Broadening your search terms\n- Removing some filters\n- Checking for typos in names or skills"
        return state
    
    answer = generate_answer(
        query=state["query"],
        search_results=state["final_results"]
    )
    
    state["answer"] = answer
    
    print(f"   ✅ Answer generated ({len(answer)} chars)")
    
    return state


def should_retry_node(state: AgentState) -> Literal["retry", "end"]:
    """
    Router: Decide whether to retry with different strategy
    
    Only retry once, and only if we got zero results
    """
    
    if state["should_retry"] and state.get("retry_count", 0) < 1:
        print("\n🔄 NO RESULTS - RETRYING WITH FALLBACK STRATEGY...")
        state["retry_count"] = state.get("retry_count", 0) + 1
        
        # Switch strategy
        if state["search_strategy"] == "sql_first":
            state["search_strategy"] = "vector_first"
        else:
            state["search_strategy"] = "hybrid"
        
        return "retry"
    
    return "end"


# ============= Build Graph =============

def create_intelligent_agent() -> StateGraph:
    """
    Build the LangGraph workflow for intelligent resume search
    
    Flow:
    1. Analyze query → 2. SQL filter (conditional) → 3. Vector search → 
    4. Enrich results → 5. Generate answer → Retry if needed
    """
    
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("analyze_query", analyze_query_node)
    workflow.add_node("sql_filter", sql_filter_node)
    workflow.add_node("vector_search", vector_search_node)
    workflow.add_node("enrich_results", enrich_results_node)
    workflow.add_node("generate_answer", generate_answer_node)
    
    # Define edges
    workflow.set_entry_point("analyze_query")
    workflow.add_edge("analyze_query", "sql_filter")
    workflow.add_edge("sql_filter", "vector_search")
    workflow.add_edge("vector_search", "enrich_results")
    workflow.add_edge("enrich_results", "generate_answer")
    
    # Conditional retry logic
    workflow.add_conditional_edges(
        "generate_answer",
        should_retry_node,
        {
            "retry": "sql_filter",  # Go back and try different strategy
            "end": END
        }
    )
    
    return workflow.compile()


# ============= Easy-to-Use Interface =============

class ResumeIntelligenceAgent:
    """
    Main agent interface - handles everything automatically
    
    Usage:
        agent = ResumeIntelligenceAgent()
        answer = agent.query("Find Python developers with 5+ years")
    """
    
    def __init__(self):
        self.graph = create_intelligent_agent()
    
    def query(self, user_query: str, verbose: bool = True) -> str:
        """
        Process a query and return natural language answer
        
        The agent will automatically:
        - Analyze the query to understand intent
        - Choose the best search strategy (SQL, vector, or hybrid)
        - Execute the search with appropriate filters
        - Deduplicate results
        - Generate a helpful answer
        - Retry with different strategy if needed
        """
        
        if verbose:
            print("="*70)
            print(f"📝 USER QUERY: {user_query}")
            print("="*70)
        
        # Initialize state
        initial_state = {
            "query": user_query,
            "query_analysis": {},
            "search_strategy": "hybrid",
            "sql_filters": {},
            "vector_query": user_query,
            "candidate_ids": [],
            "search_results": [],
            "final_results": [],
            "answer": "",
            "should_retry": False,
            "retry_count": 0
        }
        
        # Run the graph
        final_state = self.graph.invoke(initial_state)
        
        if verbose:
            print("\n" + "="*70)
            print("✅ FINAL ANSWER:")
            print("="*70)
            print(final_state["answer"])
            print("="*70)
        
        return final_state["answer"]


# ============= Testing =============

if __name__ == "__main__":
    agent = ResumeIntelligenceAgent()
    
    # Test different query types
    test_queries = [
        "Find Anshika Chaudhary's education",
        "Python developers with more than 5 years experience",
        "Who has worked on RAG or LLM projects?",
        "Machine Learning engineers in Bangalore or Delhi",
        "Compare candidates who know PyTorch and TensorFlow"
    ]
    
    for query in test_queries:
        print("\n\n")
        answer = agent.query(query)
        print("\n" + "─"*70 + "\n")