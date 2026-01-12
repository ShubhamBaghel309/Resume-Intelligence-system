# scripts/test_intelligent_agent.py

# Step 1: Add project root to Python path (works on any machine)
import sys
import os

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
# Get the project root (parent of scripts folder)
project_root = os.path.dirname(script_dir)
# Add to Python path
sys.path.insert(0, project_root)

from app.workflows.intelligent_agent import ResumeIntelligenceAgent

# Step 2: Create the agent
print("Creating agent...")
agent = ResumeIntelligenceAgent()

# Step 3: Ask a simple question
query = input("what is the query?")
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