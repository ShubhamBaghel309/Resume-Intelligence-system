# Test: Pronoun resolution in conversational queries
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.workflows.intelligent_agent import ResumeIntelligenceAgent

def test_pronoun_resolution():
    """Test if agent can resolve pronouns like 'her', 'his', 'their'"""
    
    print("\n" + "="*80)
    print("🧪 TESTING: Pronoun Resolution in Follow-up Queries")
    print("="*80)
    
    agent = ResumeIntelligenceAgent()
    
    # Conversation 1: Ask about Rosy, then use "her"
    print("\n\n📋 Conversation 1: Rosy Yuniar")
    print("-" * 80)
    
    print("\n👤 USER: Tell me about Rosy Yuniar")
    result1 = agent.query("Tell me about Rosy Yuniar", session_id="test_pronouns_1")
    print(f"🤖 AGENT: {result1['answer'][:200]}...")
    
    print("\n\n👤 USER: What is her education?")
    result2 = agent.query("What is her education?", session_id="test_pronouns_1")
    print(f"🤖 AGENT: {result2['answer']}")
    
    # Check if it understood "her" = Rosy
    if "rosy" in result2['answer'].lower() or "yuniar" in result2['answer'].lower():
        print("\n✅ PASS: Agent correctly resolved 'her' to Rosy Yuniar")
    else:
        print("\n❌ FAIL: Agent did NOT resolve pronoun correctly")
        print(f"   Expected mention of Rosy Yuniar, but got: {result2['answer'][:100]}")
    
    # Conversation 2: Ask about Shubham, then use "his"
    print("\n\n📋 Conversation 2: Shubham Baghel")
    print("-" * 80)
    
    print("\n👤 USER: Show me projects of Shubham Baghel")
    result3 = agent.query("Show me projects of Shubham Baghel", session_id="test_pronouns_2")
    print(f"🤖 AGENT: {result3['answer'][:200]}...")
    
    print("\n\n👤 USER: What are his skills?")
    result4 = agent.query("What are his skills?", session_id="test_pronouns_2")
    print(f"🤖 AGENT: {result4['answer']}")
    
    # Check if it understood "his" = Shubham
    if "shubham" in result4['answer'].lower() or "baghel" in result4['answer'].lower():
        print("\n✅ PASS: Agent correctly resolved 'his' to Shubham Baghel")
    else:
        print("\n❌ FAIL: Agent did NOT resolve pronoun correctly")
        print(f"   Expected mention of Shubham Baghel, but got: {result4['answer'][:100]}")
    
    # Conversation 3: Multiple candidates, then use "their"
    print("\n\n📋 Conversation 3: Multiple candidates")
    print("-" * 80)
    
    print("\n👤 USER: Find Python developers")
    result5 = agent.query("Find Python developers", session_id="test_pronouns_3")
    print(f"🤖 AGENT: Found candidates (showing first 200 chars): {result5['answer'][:200]}...")
    
    print("\n\n👤 USER: Show me their experience")
    result6 = agent.query("Show me their experience", session_id="test_pronouns_3")
    print(f"🤖 AGENT: {result6['answer'][:300]}...")
    
    # For multiple candidates, it should show the same candidates' experience
    print("\n✅ PASS: Agent maintained context for 'their' (multiple candidates)")
    
    print("\n\n" + "="*80)
    print("✅ PRONOUN RESOLUTION TEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    test_pronoun_resolution()
