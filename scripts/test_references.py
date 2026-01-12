# Test: Can the agent answer questions about references, languages, etc.?
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.workflows.intelligent_agent import ResumeIntelligenceAgent

def test_references():
    """Test if agent can find references in resumes"""
    
    print("\n" + "="*80)
    print("🧪 TESTING: References, Languages, Driving License")
    print("="*80)
    
    agent = ResumeIntelligenceAgent()
    
    # Test 1: References
    print("\n\n📋 Test 1: Show me the references of BINEESHA E")
    print("-" * 80)
    result = agent.query("Show me the references of BINEESHA E")
    print(result["answer"])
    
    # Test 2: Languages
    print("\n\n📋 Test 2: What languages does Rosy Yuniar speak?")
    print("-" * 80)
    result = agent.query("What languages does Rosy Yuniar speak?")
    print(result["answer"])
    
    # Test 3: Driving License
    print("\n\n📋 Test 3: Does Rosy have a driving license?")
    print("-" * 80)
    result = agent.query("Does Rosy Yuniar have a driving license?")
    print(result["answer"])
    
    print("\n\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    test_references()
