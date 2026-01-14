# scripts/interactive_agent_test.py
"""
Interactive Testing Tool for Resume Intelligence Agent
Shows detailed internal workings: SQL queries, vector searches, filtering logic
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

# ============= Configuration =============
DB_PATH = os.path.join(project_root, "resumes.db")
LOG_FILE = f"interactive_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


class DetailedTestLogger:
    """Captures and displays detailed agent execution info"""
    
    def __init__(self):
        self.log_file = open(LOG_FILE, "w", encoding="utf-8")
        
    def log(self, message, level="INFO"):
        """Log to both console and file"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {level}: {message}"
        print(formatted)
        self.log_file.write(formatted + "\n")
        self.log_file.flush()
        
    def log_section(self, title):
        """Log a section header"""
        separator = "=" * 80
        self.log(f"\n{separator}")
        self.log(f"{title}")
        self.log(separator)
        
    def close(self):
        self.log_file.close()


def get_conversation_history(session_id):
    """Retrieve conversation history from database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT role, content, candidate_ids, candidate_names, timestamp
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY timestamp ASC
    """, (session_id,))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            'role': row['role'],
            'content': row['content'],
            'candidate_ids': json.loads(row['candidate_ids']) if row['candidate_ids'] else [],
            'candidate_names': json.loads(row['candidate_names']) if row['candidate_names'] else [],
            'timestamp': row['timestamp']
        })
    
    conn.close()
    return messages


def verify_sql_results(sql_query):
    """Execute and verify SQL query results"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql_query)
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        conn.close()
        return None, str(e)


def show_database_sample():
    """Show sample of what's in the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("DATABASE SAMPLE (First 5 candidates)")
    print("="*80)
    
    cursor.execute("""
        SELECT 
            candidate_name, 
            total_experience_years, 
            skills,
            current_role
        FROM parsed_resumes 
        LIMIT 5
    """)
    
    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"\n{i}. {row['candidate_name']}")
        print(f"   Experience: {row['total_experience_years']} years")
        print(f"   Role: {row['current_role'] or 'Not specified'}")
        print(f"   Skills: {row['skills'][:100]}...")
        
    # Show some statistics
    cursor.execute("SELECT COUNT(*) FROM parsed_resumes")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM parsed_resumes WHERE skills LIKE '%Python%'")
    python_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM parsed_resumes WHERE total_experience_years >= 3")
    exp_count = cursor.fetchone()[0]
    
    print("\n" + "-"*80)
    print(f"Total Resumes: {total}")
    print(f"Python Developers: {python_count}")
    print(f"3+ Years Experience: {exp_count}")
    print("="*80 + "\n")
    
    conn.close()


def main():
    logger = DetailedTestLogger()
    
    logger.log_section("INTERACTIVE RESUME INTELLIGENCE AGENT TESTER")
    
    # Show database sample
    show_database_sample()
    
    # Initialize agent
    logger.log("Initializing agent...", "SETUP")
    agent = ResumeIntelligenceAgent()
    
    # Session will be created automatically on first query
    session_id = None
    logger.log("Agent initialized (session will be created on first query)", "SETUP")
    
    print("\n" + "="*80)
    print("READY TO TEST!")
    print("="*80)
    print("Tips:")
    print("  • Type your questions naturally")
    print("  • Try follow-up questions to test context handling")
    print("  • Type 'history' to see conversation history")
    print("  • Type 'stats' to see database statistics")
    print("  • Type 'exit' to quit")
    print("="*80 + "\n")
    
    query_count = 0
    
    while True:
        try:
            # Get user input
            query = input("\n🔍 Your Query: ").strip()
            
            if not query:
                continue
                
            if query.lower() == 'exit':
                logger.log("Exiting...", "EXIT")
                break
                
            if query.lower() == 'history':
                print("\n" + "="*80)
                print("CONVERSATION HISTORY")
                print("="*80)
                history = get_conversation_history(session_id)
                for i, msg in enumerate(history, 1):
                    print(f"\n{i}. [{msg['role'].upper()}]")
                    print(f"   {msg['content'][:200]}...")
                    if msg['candidate_names']:
                        print(f"   Candidates: {', '.join(msg['candidate_names'][:5])}")
                continue
                
            if query.lower() == 'stats':
                show_database_sample()
                continue
            
            # Execute query
            query_count += 1
            logger.log_section(f"QUERY #{query_count}: {query}")
            
            # Show what we're doing
            logger.log("Sending to agent...", "EXEC")
            
            # Get answer - returns a dict with answer, session_id, candidate_ids
            result = agent.query(query, session_id, verbose=True)
            
            # Update session_id for next query
            session_id = result['session_id']
            answer = result['answer']
            
            # Display answer
            print("\n" + "="*80)
            print("🤖 AGENT RESPONSE:")
            print("="*80)
            print(answer)
            print("="*80)
            
            # Log to file
            logger.log(f"Query: {query}", "QUERY")
            logger.log(f"Answer: {answer}", "RESPONSE")
            logger.log(f"Session ID: {session_id}", "INFO")
            logger.log(f"Candidates returned: {len(result.get('candidate_ids', []))}", "STATS")
            
            # Prompt for feedback
            print("\n💭 Was this response satisfactory? (y/n/comment): ", end="")
            feedback = input().strip()
            if feedback and feedback.lower() != 'y':
                logger.log(f"User feedback: {feedback}", "FEEDBACK")
                
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            logger.log(f"ERROR: {str(e)}", "ERROR")
            print(f"\n❌ Error: {str(e)}")
    
    # Summary
    logger.log_section("SESSION SUMMARY")
    logger.log(f"Total queries: {query_count}", "SUMMARY")
    logger.log(f"Session ID: {session_id}", "SUMMARY")
    logger.log(f"Log saved to: {LOG_FILE}", "SUMMARY")
    
    logger.close()
    print(f"\n✅ Session log saved to: {LOG_FILE}")


if __name__ == "__main__":
    main()
