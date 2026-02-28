# MCP/interview_invite_sender.py
from fastmcp import FastMCP
from openai import OpenAI
import os
import sys
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import json
from typing import Annotated
from pydantic import Field

load_dotenv()
TEST_MODE=False  # Set to True to send to test emails instead of real candidates
TEST_EMAILS = [
    "depana4927@gmail.com",
    "123108022@nitkkr.ac.in"
]
mcp = FastMCP("InterviewInviteSender")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Database path
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    "resumes.db"
)


@mcp.tool()
def send_interview_invite(
    resume_id: Annotated[str, Field(description="Candidate's resume ID from database")],
    job_role: Annotated[str | None, Field(description="Position they're being interviewed for (e.g., 'Senior Python Developer')")] = None,
    company_name: Annotated[str | None, Field(description="Your company name (e.g., 'Google', 'Microsoft')")] = None,
    interview_datetime: Annotated[str | None, Field(description="Date and time (e.g., 'January 30, 2026 at 2:00 PM')")] = None,
    interview_location: Annotated[str | None, Field(description="Location or platform (e.g., 'Google Meet', 'Office - 5th Floor')")] = None,
    interviewer_name: Annotated[str | None, Field(description="Who will conduct the interview (e.g., 'Dr. Sharma', 'John from HR')")] = None,
    tone: Annotated[str, Field(description="Email tone - 'professional', 'friendly', or 'enthusiastic'")] = "professional"
):
    """
    Send personalized interview invitation email to a candidate.

    All fields except resume_id are optional so the server can validate and
    return a structured missing_fields response rather than crashing.

    Args:
        resume_id: Candidate's resume ID from database
        job_role: Position they're being interviewed for (e.g., "Senior Python Developer")
        company_name: Your company name
        interview_datetime: Date and time (e.g., "January 30, 2026 at 2:00 PM")
        interview_location: Location or platform (e.g., "Google Meet" or "Office - 5th Floor")
        interviewer_name: Who will conduct the interview
        tone: Email tone - "professional", "friendly", or "enthusiastic"

    Returns:
        Dict with status:
        - {"status": "success" | "sent" | "draft_only", "message": "...", "to": "...", ...}
        - {"status": "missing_fields", "missing_fields": [...], "message": "..."}
        - {"status": "error", "message": "..."}
    """

    # ============= Server-side field validation =============
    # Validation lives HERE in the server, not in the agent.
    # Adding a new required field only needs a change in this file + mcp_config.json.
    missing_fields = []
    if not job_role:
        missing_fields.append("job_role")
    if not company_name:
        missing_fields.append("company_name")
    if not interview_datetime:
        missing_fields.append("interview_datetime")
    if not interview_location:
        missing_fields.append("interview_location")
    if not interviewer_name:
        missing_fields.append("interviewer_name")

    if missing_fields:
        return {
            "status": "missing_fields",
            "missing_fields": missing_fields,
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }

    # Step 1: Fetch candidate details from database
    # Special case: External candidates (not in database) have resume_id starting with "external_"
    if resume_id.startswith("external_"):
        # Extract email from resume_id (format: external_email_at_domain)
        external_email = resume_id.replace("external_", "").replace("_at_", "@")
        candidate_name = "Candidate"  # Will be overridden if provided
        candidate_email = external_email
        candidate_skills = "N/A"
        
        print(f"External candidate detected: {candidate_email}")
    else:
        # Regular database lookup
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT candidate_name, email, skills, total_experience_years, current_role
                FROM parsed_resumes
                WHERE resume_id = ?
            """, (resume_id,))
            
            candidate = cursor.fetchone()
            conn.close()
            
            if not candidate:
                return {"status": "error", "message": f"Candidate with resume_id {resume_id} not found"}
            
            candidate_name = candidate["candidate_name"]
            candidate_email = candidate["email"]
            candidate_skills_raw = candidate["skills"]

            # ✅ FIX: Truncate skills to prevent token overflow
            if candidate_skills_raw:
                try:
                    import json
                    skills_list = json.loads(candidate_skills_raw)
                    # Take only first 10 skills
                    candidate_skills = ", ".join(skills_list[:10])
                except:
                    # If JSON parsing fails, truncate string
                    candidate_skills = candidate_skills_raw[:200]
            else:
                candidate_skills = "Various technical skills"

            # TEST MODE: Send to your test emails instead of real candidates
            if TEST_MODE:
                import random
                candidate_email = random.choice(TEST_EMAILS)
                # Note: Avoid emojis in print() to prevent Windows encoding issues
                    
            if not candidate_email:
                return {"status": "error", "message": f"No email found for {candidate_name}"}
            
        except Exception as e:
            return {"status": "error", "message": f"Database error: {str(e)}"}
    
    # Step 2: Generate personalized email using GPT
    try:
        prompt = f"""Write a professional interview invitation email:

Candidate Name: {candidate_name}
Job Role: {job_role}
Company: {company_name}
Interview Date/Time: {interview_datetime}
Location/Platform: {interview_location}
Interviewer: {interviewer_name}
Candidate's Skills: {candidate_skills}
Tone: {tone}

Write an email that:
1. Warmly congratulates them on being shortlisted
2. Mentions specific skills that impressed us (from their resume)
3. Clearly states interview details (date, time, location)
4. Provides what to prepare/bring
5. Contact info if they need to reschedule
6. Professional signature

Keep it concise (under 200 words), warm, and {tone}.
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        email_body = response.choices[0].message.content.strip()
        
        # Generate subject
        subject_prompt = f"Write a professional email subject line for interview invitation to {candidate_name} for {job_role} position. Just return the subject line."
        
        subject_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": subject_prompt}],
            temperature=0.5
        )
        
        subject = subject_response.choices[0].message.content.strip()
        
    except Exception as e:
        return {"status": "error", "message": f"Email generation failed: {str(e)}"}
    
    # Step 3: Send email via SMTP
    try:
        # Get email credentials from environment
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        sender_email = os.getenv("SENDER_EMAIL")
        sender_password = os.getenv("SENDER_PASSWORD")
        
        if not sender_email or not sender_password:
            return {
                "status": "draft_only",
                "message": "SMTP credentials not configured. Email drafted but not sent.",
                "to": candidate_email,
                "subject": subject,
                "body": email_body
            }
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = candidate_email
        msg['Subject'] = subject
        msg.attach(MIMEText(email_body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        return {
            "status": "sent",
            "message": f"Interview invite sent successfully to {candidate_name}",
            "to": candidate_email,
            "subject": subject,
            "body": email_body
        }
        
    except Exception as e:
        return {
            "status": "draft_only",
            "message": f"Email drafted but sending failed: {str(e)}",
            "to": candidate_email,
            "subject": subject,
            "body": email_body
        }


@mcp.tool()
def send_bulk_interview_invites(
    resume_ids_json: Annotated[str, Field(description="JSON array of resume IDs, e.g., '[\"id1\", \"id2\"]'")],
    job_role: Annotated[str, Field(description="Position they're being interviewed for (e.g., 'Senior Python Developer')")],
    company_name: Annotated[str, Field(description="Your company name (e.g., 'Google', 'Microsoft')")],
    interview_datetime: Annotated[str, Field(description="Date and time (e.g., 'January 30, 2026 at 2:00 PM')")],
    interview_location: Annotated[str, Field(description="Location or platform (e.g., 'Google Meet', 'Office - 5th Floor')")],
    interviewer_name: Annotated[str, Field(description="Who will conduct the interview (e.g., 'Dr. Sharma', 'John from HR')")],
    tone: Annotated[str, Field(description="Email tone - 'professional', 'friendly', or 'enthusiastic'")] = "professional"
):
    """
    Send interview invites to multiple candidates at once.
    
    Args:
        resume_ids_json: JSON array of resume IDs, e.g., ["id1", "id2", "id3"]
        job_role: Position they're being interviewed for
        company_name: Your company name
        interview_datetime: Date and time
        interview_location: Location or platform
        interviewer_name: Who will conduct the interview
        tone: Email tone
    
    Returns:
        Dict with results for each candidate
    """
    
    try:
        resume_ids = json.loads(resume_ids_json)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format for resume_ids"}
    
    results = []
    
    for resume_id in resume_ids:
        result = send_interview_invite(
            resume_id=resume_id,
            job_role=job_role,
            company_name=company_name,
            interview_datetime=interview_datetime,
            interview_location=interview_location,
            interviewer_name=interviewer_name,
            tone=tone
        )
        results.append(result)
    
    successful = len([r for r in results if r.get("status") == "sent"])
    
    return {
        "total": len(resume_ids),
        "sent": successful,
        "failed": len(resume_ids) - successful,
        "results": results
    }


@mcp.resource("smtp://config", mime_type="text/plain")
def smtp_configuration():
    """Show SMTP configuration instructions."""
    return """
SMTP CONFIGURATION FOR SENDING EMAILS
======================================

Add these to your .env file:

# Gmail Example:
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password

# For Gmail, you need an "App Password":
1. Go to Google Account Settings
2. Security → 2-Step Verification (enable it)
3. Search "App passwords"
4. Generate password for "Mail"
5. Copy the 16-character password to SENDER_PASSWORD

# Other Email Providers:
- Outlook: smtp.office365.com, port 587
- Yahoo: smtp.mail.yahoo.com, port 587

NOTE: Without SMTP config, emails will be drafted but not sent.
"""


if __name__ == "__main__":
    mcp.run()