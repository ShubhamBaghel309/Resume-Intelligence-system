# scripts/rigorous_agent_test.py
"""
Rigorous Testing Framework for Conversational Resume Intelligence Agent
Tests: SQL filtering, context handling, follow-up questions, edge cases
"""

import sys
import os
import sqlite3
import json
from datetime import datetime

# Add project root to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from app.workflows.intelligent_agent import ResumeIntelligenceAgent

# ============= Test Configuration =============
DB_PATH = os.path.join(project_root, "resumes.db")
RESULTS_FILE = "test_results_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"


# ============= Database Inspection Utilities =============
def get_database_stats():
    """Get comprehensive database statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    stats = {}
    
    # Total resumes
    cursor.execute("SELECT COUNT(*) FROM parsed_resumes")
    stats['total_resumes'] = cursor.fetchone()[0]
    
    # Total candidates
    cursor.execute("SELECT COUNT(DISTINCT candidate_name) FROM parsed_resumes")
    stats['total_candidates'] = cursor.fetchone()[0]
    
    # Skills distribution
    cursor.execute("""
        SELECT 
            COUNT(*) as count,
            COUNT(CASE WHEN skills != '[]' AND skills IS NOT NULL THEN 1 END) as with_skills
        FROM parsed_resumes
    """)
    row = cursor.fetchone()
    stats['skills'] = {
        'total': row[0],
        'with_skills': row[1]
    }
    
    # Experience distribution
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN total_experience_years = 0 THEN 1 END) as freshers,
            COUNT(CASE WHEN total_experience_years BETWEEN 1 AND 2 THEN 1 END) as junior,
            COUNT(CASE WHEN total_experience_years BETWEEN 3 AND 5 THEN 1 END) as mid,
            COUNT(CASE WHEN total_experience_years > 5 THEN 1 END) as senior
        FROM parsed_resumes
    """)
    row = cursor.fetchone()
    stats['experience'] = {
        'freshers': row[0],
        'junior_1-2yrs': row[1],
        'mid_3-5yrs': row[2],
        'senior_5+yrs': row[3]
    }
    
    # Sample skills (top 5)
    cursor.execute("""
        SELECT DISTINCT skills FROM parsed_resumes 
        WHERE skills != '[]' AND skills IS NOT NULL
        LIMIT 5
    """)
    stats['sample_skills'] = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return stats


def check_sql_query_results(query, expected_min=0):
    """Execute SQL query and return count"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(query)
        results = cursor.fetchall()
        count = len(results)
        conn.close()
        return count, count >= expected_min
    except Exception as e:
        conn.close()
        return 0, False, str(e)


# ============= Test Cases =============
class TestCase:
    def __init__(self, name, query, expected_behavior, validation_criteria=None):
        self.name = name
        self.query = query
        self.expected_behavior = expected_behavior
        self.validation_criteria = validation_criteria or {}
        self.result = None
        self.passed = None
        self.issues = []


# Define comprehensive test scenarios
TEST_SCENARIOS = [
    # ========== CATEGORY 1: Basic Skill-based Filtering ==========
    TestCase(
        name="Simple Skill Search - Python",
        query="Find candidates with Python experience",
        expected_behavior="Should use SQL filtering to find Python developers",
        validation_criteria={
            "should_mention_sql": True,
            "min_candidates": 1,
            "should_list_names": True
        }
    ),
    
    TestCase(
        name="Multiple Skills - AND logic",
        query="Find candidates who know Python AND Machine Learning",
        expected_behavior="Should filter using SQL with both skills",
        validation_criteria={
            "min_candidates": 1,
            "should_list_names": True
        }
    ),
    
    # ========== CATEGORY 2: Experience-based Filtering ==========
    TestCase(
        name="Experience Range",
        query="Show me candidates with 3-5 years of experience",
        expected_behavior="Should use SQL WHERE total_experience_years BETWEEN 3 AND 5",
        validation_criteria={
            "should_use_sql": True,
            "min_candidates": 1
        }
    ),
    
    TestCase(
        name="Senior Candidates",
        query="Find senior developers with more than 5 years experience",
        expected_behavior="Should filter by experience > 5 years",
        validation_criteria={
            "min_candidates": 1
        }
    ),
    
    # ========== CATEGORY 3: Complex Multi-criteria ==========
    TestCase(
        name="Skills + Experience Combined",
        query="Find Python developers with 2+ years experience",
        expected_behavior="Should combine skill and experience filters in SQL",
        validation_criteria={
            "should_use_sql": True,
            "min_candidates": 1
        }
    ),
    
    # ========== CATEGORY 4: Context & Follow-up Questions ==========
    TestCase(
        name="Initial Search",
        query="Find candidates with Java experience",
        expected_behavior="Should return Java developers",
        validation_criteria={
            "min_candidates": 1,
            "should_list_names": True
        }
    ),
]

# Follow-up questions (these test context understanding)
FOLLOW_UP_SCENARIOS = [
    TestCase(
        name="Follow-up: Filter Previous Results",
        query="From these, who has more than 3 years experience?",
        expected_behavior="Should filter the previous Java candidates by experience",
        validation_criteria={
            "should_reference_previous": True
        }
    ),
    
    TestCase(
        name="Follow-up: Ask about Specific Candidate",
        query="Tell me more about the first candidate",
        expected_behavior="Should provide detailed info about first candidate from previous results",
        validation_criteria={
            "should_reference_previous": True,
            "should_be_detailed": True
        }
    ),
    
    TestCase(
        name="Follow-up: Compare Candidates",
        query="Compare their projects",
        expected_behavior="Should compare projects of previously mentioned candidates",
        validation_criteria={
            "should_reference_previous": True
        }
    ),
]


# ============= Test Execution Engine =============
class TestRunner:
    def __init__(self):
        self.agent = None
        self.session_id = None
        self.results = []
        self.log_file = open(RESULTS_FILE, "w", encoding="utf-8")
        
    def log(self, message):
        """Write to both console and file"""
        print(message)
        self.log_file.write(message + "\n")
        self.log_file.flush()
        
    def initialize_agent(self):
        """Create fresh agent instance"""
        self.log("\n" + "="*80)
        self.log("INITIALIZING AGENT")
        self.log("="*80)
        self.agent = ResumeIntelligenceAgent()
        self.session_id = None  # Session will be created on first query
        self.log(f"✅ Agent initialized (session will be created on first query)\n")
        
    def run_test(self, test_case, is_followup=False):
        """Execute a single test case"""
        self.log("\n" + "-"*80)
        self.log(f"TEST: {test_case.name}")
        self.log("-"*80)
        self.log(f"Query: {test_case.query}")
        self.log(f"Expected: {test_case.expected_behavior}")
        
        if is_followup:
            self.log("⚠️  This is a FOLLOW-UP question (tests context handling)")
        
        self.log("\n🤖 Agent Response:")
        self.log("-" * 40)
        
        try:
            # Execute query
            result = self.agent.query(test_case.query, self.session_id, verbose=False)
            
            # Update session_id for follow-up queries
            self.session_id = result['session_id']
            
            # Extract answer and results
            test_case.result = result['answer']
            candidate_ids = result.get('candidate_ids', [])
            
            self.log(test_case.result)
            
            # Log candidate info
            if candidate_ids:
                self.log(f"\n📊 Returned {len(candidate_ids)} candidates")
            
            # Validate results
            self.validate_test(test_case, is_followup)
            
        except Exception as e:
            self.log(f"\n❌ EXCEPTION: {str(e)}")
            test_case.passed = False
            test_case.issues.append(f"Exception: {str(e)}")
        
        self.results.append(test_case)
        
    def validate_test(self, test_case, is_followup):
        """Validate test results against criteria"""
        self.log("\n📊 VALIDATION:")
        self.log("-" * 40)
        
        answer = test_case.result.lower()
        criteria = test_case.validation_criteria
        issues = []
        
        # Check if answer is empty or too short
        if len(answer) < 20:
            issues.append("Answer too short (possible failure)")
            
        # Check if answer says "no candidates found" when we expect results
        if criteria.get("min_candidates", 0) > 0:
            if "no candidates" in answer or "couldn't find" in answer or "no results" in answer:
                issues.append("No candidates found when expected results")
                
        # Check if candidate names are mentioned
        if criteria.get("should_list_names"):
            # Simple heuristic: check if there are capitalized names
            if not any(word[0].isupper() for word in answer.split() if len(word) > 2):
                issues.append("No candidate names mentioned")
                
        # Check for context reference in follow-ups
        if is_followup and criteria.get("should_reference_previous"):
            # Check if answer references previous results or uses pronouns
            context_keywords = ["previous", "these", "those", "them", "mentioned", "above", "earlier"]
            if not any(kw in answer for kw in context_keywords):
                issues.append("Follow-up question didn't reference previous context")
        
        # Report validation results
        if issues:
            test_case.passed = False
            test_case.issues = issues
            self.log("❌ FAILED - Issues found:")
            for issue in issues:
                self.log(f"   • {issue}")
        else:
            test_case.passed = True
            self.log("✅ PASSED - All validations successful")
            
    def print_summary(self):
        """Print comprehensive test summary"""
        self.log("\n\n" + "="*80)
        self.log("TEST SUMMARY")
        self.log("="*80)
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)
        
        self.log(f"\nTotal Tests: {total}")
        self.log(f"✅ Passed: {passed}")
        self.log(f"❌ Failed: {failed}")
        self.log(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if failed > 0:
            self.log("\n" + "="*80)
            self.log("FAILED TESTS - DETAILED ANALYSIS")
            self.log("="*80)
            
            for test in self.results:
                if not test.passed:
                    self.log(f"\n❌ {test.name}")
                    self.log(f"   Query: {test.query}")
                    self.log(f"   Issues:")
                    for issue in test.issues:
                        self.log(f"      • {issue}")
                        
        self.log("\n" + "="*80)
        self.log(f"Full results saved to: {RESULTS_FILE}")
        self.log("="*80)


# ============= Main Execution =============
def main():
    print("="*80)
    print("RIGOROUS AGENT TESTING FRAMEWORK")
    print("="*80)
    
    # Step 1: Get database stats
    print("\n📊 DATABASE STATISTICS")
    print("-"*80)
    stats = get_database_stats()
    print(f"Total Resumes: {stats['total_resumes']}")
    print(f"Total Candidates: {stats['total_candidates']}")
    print(f"Experience Distribution:")
    print(f"  • Freshers (0 yrs): {stats['experience']['freshers']}")
    print(f"  • Junior (1-2 yrs): {stats['experience']['junior_1-2yrs']}")
    print(f"  • Mid (3-5 yrs): {stats['experience']['mid_3-5yrs']}")
    print(f"  • Senior (5+ yrs): {stats['experience']['senior_5+yrs']}")
    print(f"Skills Coverage:")
    print(f"  • With Skills: {stats['skills']['with_skills']}")
    
    # Step 2: Run tests
    runner = TestRunner()
    runner.initialize_agent()
    
    # Run basic tests
    print("\n" + "="*80)
    print("RUNNING BASIC TESTS")
    print("="*80)
    
    for i, test in enumerate(TEST_SCENARIOS, 1):
        runner.log(f"\n\n{'='*80}")
        runner.log(f"TEST {i}/{len(TEST_SCENARIOS)}")
        runner.run_test(test)
    
    # Run follow-up tests (context-dependent)
    print("\n" + "="*80)
    print("RUNNING CONTEXT/FOLLOW-UP TESTS")
    print("="*80)
    
    # Start fresh conversation for follow-up tests
    runner.initialize_agent()
    
    for i, test in enumerate(FOLLOW_UP_SCENARIOS, 1):
        runner.log(f"\n\n{'='*80}")
        runner.log(f"FOLLOW-UP TEST {i}/{len(FOLLOW_UP_SCENARIOS)}")
        runner.run_test(test, is_followup=True)
    
    # Print summary
    runner.print_summary()
    runner.log_file.close()


if __name__ == "__main__":
    main()
