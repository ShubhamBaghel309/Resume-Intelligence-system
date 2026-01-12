"""
Test if matched_chunks are being added to final_results
"""

import sys
sys.path.insert(0, '.')

from app.workflows.intelligent_agent import ResumeIntelligenceAgent

# Create agent
agent = ResumeIntelligenceAgent()

# Run query but capture state before LLM call
query = "What are the achievements of Suryansh Rathore?"

print(f"Testing query: {query}\n")

# Invoke the graph
final_state = agent.graph.invoke({
    "query": query,
    "query_analysis": {},
    "search_strategy": "",
    "sql_filters": {},
    "vector_query": "",
    "candidate_ids": [],
    "search_results": [],
    "final_results": [],
    "answer": "",
    "should_retry": False,
    "retry_count": 0,
    "use_llm_sql": False,
    "llm_generated_sql": ""
})

# Check final_results
if final_results := final_state.get("final_results"):
    print(f"✅ Found {len(final_results)} results\n")
    
    for i, resume in enumerate(final_results, 1):
        name = resume.get("candidate_name")
        matched_chunks = resume.get("matched_chunks", [])
        
        print(f"Result #{i}: {name}")
        print(f"  - Has matched_chunks: {'YES' if matched_chunks else 'NO'}")
        
        if matched_chunks:
            print(f"  - Number of chunks: {len(matched_chunks)}")
            for chunk in matched_chunks:
                chunk_type = chunk.get("chunk_type")
                chunk_len = len(chunk.get("chunk_text", ""))
                print(f"    * {chunk_type}: {chunk_len} chars")
        print()
else:
    print("❌ No final_results found")
