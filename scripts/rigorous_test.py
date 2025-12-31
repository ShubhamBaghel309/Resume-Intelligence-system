import sys
sys.path.append("d:/GEN AI internship work/Resume Intelligence System")

from app.workflows.intelligent_agent import ResumeIntelligenceAgent
import time

# Create the agent
agent = ResumeIntelligenceAgent()

# 5 Rigorous Test Queries (covering different complexity levels)
test_queries = [
    {
        "id": 1,
        "query": "Find candidates with more than 10 years of experience who have worked on generative AI or LLM projects",
        "difficulty": "Hard - Multi-criteria (experience + semantic project search)",
        "expected": "Should use hybrid strategy: SQL for experience filter, vector for GenAI/LLM projects"
    },
    {
        "id": 2,
        "query": "Compare the projects of Shubham Baghel and RATISH NAIR. Who has more experience with transformers?",
        "difficulty": "Very Hard - Multi-name comparison with semantic skill analysis",
        "expected": "Should extract both names, compare their projects, analyze transformer experience"
    },
    {
        "id": 3,
        "query": "Which candidate has the most diverse skill set combining machine learning, computer vision, and NLP?",
        "difficulty": "Hard - Semantic skill analysis across multiple domains",
        "expected": "Should use vector search to find candidates with all three skill areas"
    },
    {
        "id": 4,
        "query": "Show me candidates from India who have built RAG systems or chatbots using LangChain",
        "difficulty": "Hard - Location filter + specific technology + project type",
        "expected": "Should use hybrid: SQL for location, vector for RAG/LangChain projects"
    },
    {
        "id": 5,
        "query": "What is the educational background of the candidate who worked as a DATA SCIENTIST at WHITEHAT JR?",
        "difficulty": "Medium - Specific job role and company, asking for education",
        "expected": "Should find RATISH NAIR via vector search on job experience, return education"
    }
]

print("=" * 80)
print("🧪 RIGOROUS AGENT TESTING - 5 CHALLENGING QUERIES")
print("=" * 80)

results = []

for test in test_queries:
    print(f"\n\n{'='*80}")
    print(f"TEST {test['id']}/5")
    print(f"{'='*80}")
    print(f"📋 Difficulty: {test['difficulty']}")
    print(f"🎯 Expected: {test['expected']}")
    print(f"\n❓ Query: {test['query']}")
    print(f"\n{'-'*80}\n")
    
    start_time = time.time()
    
    try:
        answer = agent.query(test['query'], verbose=True)
        elapsed = time.time() - start_time
        
        results.append({
            "test_id": test['id'],
            "query": test['query'],
            "status": "✅ SUCCESS",
            "time": f"{elapsed:.2f}s",
            "answer_length": len(answer)
        })
        
        print(f"\n⏱️  Time taken: {elapsed:.2f} seconds")
        print(f"📊 Answer length: {len(answer)} characters")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ ERROR: {str(e)}")
        results.append({
            "test_id": test['id'],
            "query": test['query'],
            "status": f"❌ FAILED: {str(e)[:100]}",
            "time": f"{elapsed:.2f}s",
            "answer_length": 0
        })
    
    # Small delay between tests
    time.sleep(2)

# Summary
print("\n\n" + "=" * 80)
print("📊 TEST SUMMARY")
print("=" * 80)

for result in results:
    print(f"\nTest {result['test_id']}: {result['status']}")
    print(f"   Time: {result['time']}")
    print(f"   Answer: {result['answer_length']} chars")
    print(f"   Query: {result['query'][:60]}...")

success_count = sum(1 for r in results if "SUCCESS" in r['status'])
print(f"\n{'='*80}")
print(f"✅ Passed: {success_count}/5")
print(f"❌ Failed: {5 - success_count}/5")
print(f"{'='*80}")
