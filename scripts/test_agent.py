# scripts/test_intelligent_agent.py

# Step 1: Import the agent
import sys
sys.path.append("d:/GEN AI internship work/Resume Intelligence System")

from app.workflows.intelligent_agent import ResumeIntelligenceAgent

# Step 2: Create the agent
print("Creating agent...")
agent = ResumeIntelligenceAgent()

# Step 3: Ask a simple question
query = "summarize each candidate's details and present it to me in short only main points"

print(f"\nAsking: {query}\n")

# Step 4: Get the answer
answer = agent.query(query)

with open("agents_results.txt" , "a",encoding="utf-8") as f:
    f.write(f"Query: {query}\n\n")
    f.write(f"Answer:\n{answer}\n")
    f.write("\n" + "="*70 + "\n")

# Step 5: Print the answer
print(f"\n\nFinal Answer:\n{answer}")


# Revaldy Rahmanda
# CUSTOMERHAPPINESSASSOCIATE
# PROFESSIONALPLACEMENT
# CUSTOMERHAPPINESSANALYST
# ADMINISTRATIVE STAFF
# by.U Indonesia July2021-Now
# Identify and assess customers needsto achieve satisfactionHandle customer complaints, provideappropriate solutions and alternativeswithin the time limitsProvide accurate, valid and completeinformation by using the right methods