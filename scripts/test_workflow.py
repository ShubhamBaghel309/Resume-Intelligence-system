import sys
sys.path.append("d:/GEN AI internship work/Resume Intelligence System")

from app.workflows.intelligent_agent import ResumeIntelligenceAgent

print("""
================================================================================
🔍 AGENT INTERNAL WORKFLOW DEMONSTRATION
================================================================================

This test will show you EVERY step the agent takes:

1. 🧠 QUERY ANALYSIS
   - What type of query is it? (name-based, skill-based, etc.)
   - What entities are extracted? (names, skills, experience)
   - What strategy is chosen? (sql_first, vector_first, hybrid, sql_only)
   - Why was this strategy chosen? (reasoning)

2. 📊 SQL FILTERING (if applicable)
   - What SQL query is generated?
   - What parameters are used?
   - How many candidates match?

3. 🔍 VECTOR SEARCH (if applicable)
   - Is it filtering to SQL candidates or searching all?
   - How many vector matches found?

4. 💎 RESULT ENRICHMENT
   - How many chunks were deduplicated?
   - How many unique resumes?
   - Full data fetched from database

5. 🤖 ANSWER GENERATION
   - LLM generates natural language answer
   - Uses enriched resume data as context

6. 🔄 RETRY LOGIC (if needed)
   - If no results, retry with different strategy

================================================================================
""")

# Create the agent
agent = ResumeIntelligenceAgent()

# Test with a complex query
query = "Find candidates with more than 10 years of experience who have worked on generative AI or LLM projects"

print(f"\n📝 QUERY: {query}\n")
print("=" * 80)
print("STARTING AGENT WORKFLOW...")
print("=" * 80)

# Run with verbose=True to see all internal steps
answer = agent.query(query, verbose=True)

print("\n\n" + "=" * 80)
print("🎯 WORKFLOW ANALYSIS")
print("=" * 80)
print("""
What happened:
1. The agent analyzed the query and detected it's a multi-criteria query
2. It chose a strategy (likely 'hybrid' - SQL for experience + vector for GenAI)
3. SQL filtered candidates by experience >= 10 years
4. Vector search found candidates with GenAI/LLM project mentions
5. Results were deduplicated and enriched with full resume data
6. LLM generated a natural language answer from the enriched data

This is the power of the intelligent agent - it automatically chooses the
best strategy based on the query type!
""")
