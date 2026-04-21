# scripts/interactive_agent_test.py
"""
Interactive Testing Tool for Resume Intelligence Agent
Shows detailed internal workings: SQL queries, vector searches, filtering logic
WITH MCP EMAIL SENDING CAPABILITY
"""

import sys
import os
import sqlite3
import json
import asyncio
from datetime import datetime

# Fix Windows encoding for emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from app.workflows.intelligent_agent import ResumeIntelligenceAgent
from app.mcp_infra.registry import MCPRegistry

# MCP imports
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("⚠️  MCP library not installed. Email sending disabled. Run: uv pip install mcp")

# ============= Configuration =============
DB_PATH = os.path.join(project_root, "resumes.db")
LOG_FILE = "results01.txt"


class DetailedTestLogger:
    """Captures and displays detailed agent execution info"""
    
    def __init__(self):
        self.log_file = open(LOG_FILE, "a", encoding="utf-8")
        
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


def show_job_descriptions():
    """Show available job descriptions in the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("\n" + "="*80)
    print("AVAILABLE JOB DESCRIPTIONS")
    print("="*80)

    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='job_descriptions'")
    if not cursor.fetchone():
        print("\n  No job_descriptions table found!")
        print("  Use scripts/JDindexing.py to add a JD first.")
        print("="*80 + "\n")
        conn.close()
        return

    cursor.execute("""
        SELECT jd_id, job_title, status, required_skills, nice_to_have_skills
        FROM job_descriptions
        ORDER BY COALESCE(indexed_at, posting_date) DESC
    """)

    rows = cursor.fetchall()
    if not rows:
        print("\n  No JDs found in database!")
        print("  Use scripts/JDindexing.py to add a JD first.")
    else:
        for i, row in enumerate(rows, 1):
            status_icon = "🟢" if row['status'] in ('open', 'active', None) else "⚪"
            print(f"\n{i}. {status_icon} {row['jd_id']}: {row['job_title']}")
            print(f"   Status: {row['status'] or 'active'}")

            # Parse and display skills
            try:
                required = json.loads(row['required_skills']) if row['required_skills'] else []
                nice_to_have = json.loads(row['nice_to_have_skills']) if row['nice_to_have_skills'] else []
            except:
                required = [row['required_skills']] if row['required_skills'] else []
                nice_to_have = []

            if required:
                print(f"   Required Skills: {', '.join(required[:5])}" + ("..." if len(required) > 5 else ""))
            if nice_to_have:
                print(f"   Nice-to-have: {', '.join(nice_to_have[:3])}" + ("..." if len(nice_to_have) > 3 else ""))

    print("\n" + "-"*80)
    print(f"Total JDs: {len(rows)}")
    print("="*80 + "\n")

    conn.close()


async def send_interview_invite_mcp(resume_id, job_role, company_name, interview_datetime, 
                                    interview_location, interviewer_name, tone="professional"):
    """Send interview invite using MCP server"""
    
    if not MCP_AVAILABLE:
        return {"error": "MCP library not installed"}
    
    # Find fastmcp executable - try PATH first, then venv
    import shutil
    fastmcp_cmd = shutil.which("fastmcp")
    if not fastmcp_cmd:
        venv_fastmcp = os.path.join(project_root, "myenv311", "Scripts", "fastmcp.exe")
        if os.path.exists(venv_fastmcp):
            fastmcp_cmd = venv_fastmcp
        else:
            return {"error": "fastmcp not found. Run: pip install fastmcp"}
    
    server_params = StdioServerParameters(
        command=fastmcp_cmd,
        args=["run", os.path.join(project_root, "MCP", "interview_invite_sender.py")],
        env=None
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool(
                    "send_interview_invite",
                    arguments={
                        "resume_id": resume_id,
                        "job_role": job_role,
                        "company_name": company_name,
                        "interview_datetime": interview_datetime,
                        "interview_location": interview_location,
                        "interviewer_name": interviewer_name,
                        "tone": tone
                    }
                )
                
                # Parse MCP result
                if result.content:
                    return json.loads(result.content[0].text)
                return {"error": "No result from MCP server"}
                
    except Exception as e:
        return {"error": str(e)}


async def main_async():
    logger = DetailedTestLogger()
    
    logger.log_section("INTERACTIVE RESUME INTELLIGENCE AGENT TESTER")
    
    # Show database sample
    show_database_sample()
    
    # Initialize agent
    logger.log("Initializing agent...", "SETUP")
    agent = ResumeIntelligenceAgent()
    
    # Session will be created automatically on first query
    session_id = None
    conversation_context = {}  # ✅ Persist across turns for email field collection
    logger.log("Agent initialized (session will be created on first query)", "SETUP")
    
    print("\n" + "="*80)
    print("READY TO TEST!")
    print("="*80)
    print("Tips:")
    print("  • Type your questions naturally")
    print("  • Try follow-up questions to test context handling")
    print("  • Type 'history' to see conversation history")
    print("  • Type 'stats' to see database statistics")
    print("  • Type 'jd' to see available Job Descriptions")
    print("  • Type 'jd-context' to inspect the active JD context")
    print("  • Try: 'what is the JD summarize it' → then follow up naturally")
    print("  • Try: 'Find best resumes for the JD' to test JD matching")
    if MCP_AVAILABLE:
        print("  • Type 'email' to send interview invite")
    print("  • Type 'exit' to quit")
    print("="*80 + "\n")
    
    query_count = 0
    next_query = None  # ✅ For email field continuation
    
    while True:
        try:
            # Use pending query from email field flow, or prompt fresh input
            if next_query:
                query = next_query
                next_query = None
            else:
                # Show active JD in prompt when context is set
                _active_jd = conversation_context.get('active_jd', {}) if conversation_context else {}
                _jd_title  = _active_jd.get('job_title', '') if _active_jd else ''
                _prompt    = f"\n🔍 Your Query [JD: {_jd_title}]: " if _jd_title else "\n🔍 Your Query: "
                query = input(_prompt).strip()
            
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

            if query.lower() == 'jd':
                show_job_descriptions()
                continue

            if query.lower() in ('jd-context', 'jdc'):
                active_jd = conversation_context.get('active_jd', {})
                print("\n" + "="*80)
                print("ACTIVE JD CONTEXT")
                print("="*80)
                if active_jd:
                    print(f"  JD ID    : {active_jd.get('jd_id', 'N/A')}")
                    print(f"  Title    : {active_jd.get('job_title', 'N/A')}")
                    print(f"  Level    : {active_jd.get('job_level', 'N/A')}")
                    print(f"  Location : {active_jd.get('location', 'N/A')}")
                    req = active_jd.get('required_skills', [])
                    nice = active_jd.get('nice_to_have_skills', [])
                    if isinstance(req, str):
                        import json as _json
                        try:
                            req = _json.loads(req)
                        except Exception:
                            req = [req]
                    if isinstance(nice, str):
                        import json as _json
                        try:
                            nice = _json.loads(nice)
                        except Exception:
                            nice = [nice]
                    print(f"  Must-Have: {', '.join(req[:8]) if req else 'N/A'}")
                    print(f"  Nice-Have: {', '.join(nice[:5]) if nice else 'N/A'}")
                else:
                    print("  No active JD context. Ask about a JD first.")
                    print("  Example: 'what is the JD summarize it'")
                print(f"  Session  : {session_id or 'not started yet'}")
                print("="*80 + "\n")
                continue
            
            # Check if user wants to send email
            if query.lower() == 'email':
                if not MCP_AVAILABLE:
                    print("\n❌ MCP not available. Run: uv pip install mcp")
                    continue
                
                print("\n📧 SEND INTERVIEW INVITE")
                print("="*80)
                
                resume_id = input("Resume ID: ").strip()
                job_role = input("Job Role (e.g., Senior Python Developer): ").strip()
                company_name = input("Company Name: ").strip()
                interview_datetime = input("Interview Date/Time (e.g., Feb 5, 2026 at 3 PM): ").strip()
                interview_location = input("Location/Platform (e.g., Google Meet): ").strip()
                interviewer_name = input("Interviewer Name: ").strip()
                
                print("\n⏳ Sending email via MCP server...")
                result = await send_interview_invite_mcp(
                    resume_id=resume_id,
                    job_role=job_role,
                    company_name=company_name,
                    interview_datetime=interview_datetime,
                    interview_location=interview_location,
                    interviewer_name=interviewer_name
                )
                
                print("\n📬 Email Result:")
                print("="*80)
                print(f"Status: {result.get('status', 'unknown')}")
                print(f"Message: {result.get('message', 'No message')}")
                if result.get('to'):
                    print(f"Sent to: {result['to']}")
                if result.get('subject'):
                    print(f"Subject: {result['subject']}")
                if result.get('body'):
                    print(f"\nEmail Preview:\n{result['body'][:200]}...")
                print("="*80)
                
                logger.log(f"Email sent: {result.get('status')} to {result.get('to')}", "EMAIL")
                continue
            
            # Execute query
            query_count += 1
            logger.log_section(f"QUERY #{query_count}: {query}")
            
            # Show what we're doing
            logger.log("Sending to agent...", "EXEC")
            
            # Get answer - pass conversation_context for email field persistence
            result = agent.query(query, session_id, verbose=True, conversation_context=conversation_context)
            
            # Update session_id and conversation_context for next query
            session_id = result['session_id']
            conversation_context = result.get('conversation_context', {})
            answer = result['answer']

            # ── JD Routing Debug Summary ──────────────────────────────────────
            query_analysis = result.get('query_analysis', {})
            is_jd_info  = query_analysis.get('is_jd_info_query', False) or query_analysis.get('query_type') == 'jd_info'
            is_jd_match = query_analysis.get('is_jd_match_query', False) or query_analysis.get('query_type') == 'jd_match'
            active_jd   = conversation_context.get('active_jd', {})
            if is_jd_info or is_jd_match:
                from app.workflows.intelligent_agent import _classify_jd_info_subintent
                route_label  = 'jd_match' if is_jd_match else 'jd_info'
                subintent    = _classify_jd_info_subintent(query) if is_jd_info else 'N/A'
                active_jd_id = active_jd.get('jd_id', 'none') if active_jd else 'none'
                print(f"\n📋 JD Route: {route_label} | Sub-intent: {subintent} | Active JD: {active_jd_id}")

            # ── Context Status Line ────────────────────────────────────────────
            active_jd_title = active_jd.get('job_title', '') if active_jd else ''
            ctx_parts = []
            if active_jd_title:
                ctx_parts.append(f"active_jd={active_jd_title}")
            if session_id:
                ctx_parts.append(f"session={session_id[:8]}...")
            if ctx_parts:
                print(f"🔗 Context: {' | '.join(ctx_parts)}")

            # Log to file only (verbose mode already printed everything to console)
            logger.log_file.write(f"[{datetime.now().strftime('%H:%M:%S')}] QUERY: {query}\n")
            logger.log_file.write(f"[{datetime.now().strftime('%H:%M:%S')}] SESSION: {session_id}, CANDIDATES: {len(result.get('candidate_ids', []))}\n\n")
            logger.log_file.flush()
            
            # ✅ If agent is collecting tool fields, collect ALL fields via form-style input
            if conversation_context.get("pending_tool_action"):
                pending = conversation_context["pending_tool_action"]
                missing = pending.get("missing_fields", [])
                server_id = pending.get("server_id", "")
                
                # Dynamic field labels from registry (schema-driven)
                _registry = MCPRegistry()
                field_examples = _registry.get_field_examples(server_id) if server_id else {}
                field_prompts = {
                    k: field_examples.get(k, {}).get("label", k.replace("_", " ").title())
                    for k in missing
                }
                
                print("\n" + "-"*50)
                print("📝 Fill in the details below (press Enter after each):")
                print("-"*50)
                
                collected = {}
                for i, field_key in enumerate(missing, 1):
                    prompt_label = field_prompts.get(field_key, field_key)
                    meta = field_examples.get(field_key, {})
                    example_text = meta.get("example", "") if isinstance(meta, dict) else str(meta)
                    hint = f" ({example_text})" if example_text else ""
                    value = input(f"  {i}. {prompt_label}{hint}: ").strip()
                    if value.lower() == 'exit':
                        break
                    collected[field_key] = value
                
                if len(collected) == len(missing):
                    # Build a complete query string with all fields for the agent
                    parts = [f"{field_prompts[k]}: {v}" for k, v in collected.items()]
                    next_query = ", ".join(parts)
                    print(f"\n⏳ Sending all details to agent...")
                    continue
                else:
                    print("\n❌ Action cancelled.")
                    conversation_context = {}  # Clear pending action
                    continue
                
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


def main():
    """Wrapper to run async main"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()





