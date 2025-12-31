import sys
sys.path.append("d:/GEN AI internship work/Resume Intelligence System")

from app.workflows.intelligent_agent import ResumeIntelligenceAgent

# Create the agent
agent = ResumeIntelligenceAgent()

# Test the same query that previously returned all 17 candidates
query = "What is the educational background of the candidate who worked as a DATA SCIENTIST at WHITEHAT JR?"

print(f"\n🧪 TESTING IMPROVED SQL FILTERING")
print(f"{'='*80}")
print(f"Query: {query}")
print(f"\n📊 Expected Improvement:")
print(f"   BEFORE: SQL returned all 17 candidates (no filtering)")
print(f"   AFTER:  SQL should filter to ~1-2 candidates with job_title + company")
print(f"{'='*80}\n")

answer = agent.query(query, verbose=True)

print(f"\n\n{'='*80}")
print("✅ TEST COMPLETE")
print(f"{'='*80}")
print("\nCheck the SQL output above:")
print("- Did it have WHERE clause with job_title and company?")
print("- Did it filter to fewer candidates (ideally 1-2 instead of 17)?")
print("\nThis is critical for scalability with 17,000+ candidates!")
