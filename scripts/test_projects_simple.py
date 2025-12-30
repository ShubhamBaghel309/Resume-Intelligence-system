import sys
sys.path.append("d:/GEN AI internship work/Resume Intelligence System")

from app.workflows.intelligent_agent import ResumeIntelligenceAgent

# Create the agent
agent = ResumeIntelligenceAgent()

# Test query
query = "Show me all the projects of Shubham Baghel"

print(f"\nQuery: {query}\n")
answer = agent.query(query)

print(f"\n\n{'='*70}")
print("FINAL ANSWER:")
print('='*70)
print(answer)
print('='*70)
