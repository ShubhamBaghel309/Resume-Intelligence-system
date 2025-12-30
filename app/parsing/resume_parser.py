# app/parsing/resume_parser.py
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from app.models.resume import ParsedResume
import uuid
import json
import os
import sqlite3
import time
from dotenv import load_dotenv

load_dotenv()

# ============= LLM Setup with Fallback =============

# Primary: Groq (fast, but rate lim ited on free tier)
groq_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.1,
    max_tokens=1024,
    api_key=os.environ["GROQ_API_KEY"]
)

# Fallback: Gemini (generous free tier)
gemini_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.1,
    max_output_tokens=1024
)

parser = PydanticOutputParser(pydantic_object=ParsedResume)

prompt = PromptTemplate(
    template="""You are a resume parsing assistant. Extract structured information from the following resume text.

IMPORTANT - Categorize technical skills precisely:
- programming_languages: Python, Java, C++, JavaScript, SQL, etc.
- frameworks: PyTorch, TensorFlow, React, Django, FastAPI, LangChain, Hugging Face, Scikit-learn, OpenCV, etc.
- tools: VS Code, GitHub, Docker, AWS, Azure, Postman, Jupyter, Google Colab, Ollama, etc.
- technical_skills: Any other technical competencies (databases, methodologies, domains, etc.)

WORK EXPERIENCE:
- Extract start_date and end_date separately (e.g., "January 2021", "Present")
- Extract responsibilities as a list

PROJECTS:
- Extract all projects mentioned (personal, academic, professional)
- For each project: name, description, technologies used, duration (if mentioned), role
- Look for sections like "Projects", "Side Projects", "Academic Projects", "Portfolio"

Extract ALL skills and projects mentioned in the resume, not just the top few.

{format_instructions}

Resume Text:
{resume_text}

Return ONLY valid JSON matching the schema above. Be precise and thorough.""",
    input_variables=["resume_text"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

# Create chains for both LLMs
groq_chain = prompt | groq_llm | parser
gemini_chain = prompt | gemini_llm | parser

# Track which LLM to use (switch to Gemini if Groq rate limited)
_use_gemini_fallback = False


def parse_resume_with_llm(raw_text: str, max_retries: int = 5) -> ParsedResume:
    """Parse resume text using LLM with retry logic and exponential backoff for rate limits"""
    
    # Try Groq first with retries
    for attempt in range(max_retries):
        try:
            result = groq_chain.invoke({"resume_text": raw_text})
            return result
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if it's a rate limit error
            if "rate" in error_str or "429" in error_str or "limit" in error_str or "quota" in error_str:
                if attempt < max_retries - 1:
                    # Exponential backoff: 2, 4, 8, 16 seconds
                    wait_time = 2 ** (attempt + 1)
                    print(f"   ⚠️  Rate limited (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # Groq exhausted, try Gemini
                    print(f"   ⚠️  Groq rate limit exhausted. Switching to Gemini...")
                    break
            else:
                # Non-rate-limit error, try Gemini immediately
                print(f"   ⚠️  Groq error: {str(e)[:100]}. Trying Gemini...")
                break
    
    # Fallback to Gemini with retries
    for attempt in range(max_retries):
        try:
            result = gemini_chain.invoke({"resume_text": raw_text})
            return result
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if it's a rate limit error
            if "rate" in error_str or "429" in error_str or "limit" in error_str or "quota" in error_str or "resource" in error_str:
                if attempt < max_retries - 1:
                    # Exponential backoff: 4, 8, 16, 32 seconds (longer for Gemini)
                    wait_time = 2 ** (attempt + 2)
                    print(f"   ⚠️  Gemini rate limited (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # Both APIs exhausted
                    raise Exception(f"❌ Both Groq and Gemini rate limits exhausted. Error: {str(e)}")
            else:
                # Non-rate-limit error from Gemini
                raise Exception(f"❌ Gemini API error: {str(e)}")
    
    raise Exception("❌ Maximum retries exceeded for both APIs")


def save_parsed_resume(document_id: str, parsed_resume: ParsedResume) -> str:
    """Save parsed resume data to database and update document status"""
    
    
    resume_id = str(uuid.uuid4())
    
    # Merge all skill categories into single list (deduplicated)
    all_skills = list(set(
        parsed_resume.programming_languages + 
        parsed_resume.frameworks + 
        parsed_resume.tools + 
        parsed_resume.technical_skills
    ))
    skills_json = json.dumps(all_skills)
    
    work_json = json.dumps([job.model_dump() for job in parsed_resume.work_experience])
    education_json = json.dumps([edu.model_dump() for edu in parsed_resume.education])
    projects_json = json.dumps([proj.model_dump() for proj in parsed_resume.projects])
    
    # Connect to database
    conn = sqlite3.connect("resumes.db")
    cursor = conn.cursor()
    
    # Insert parsed resume data with merged skills and projects
    cursor.execute("""
        INSERT INTO parsed_resumes (
            resume_id, document_id, candidate_name, email, phone, location,
            total_experience_years, current_role, skills,
            work_experience, education, projects
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        resume_id,
        document_id,
        parsed_resume.candidate_name,
        parsed_resume.email,
        parsed_resume.phone,
        parsed_resume.location,
        parsed_resume.total_experience_years,
        parsed_resume.current_role,
        skills_json,
        work_json,
        education_json,
        projects_json
    ))
    
    # Update document status from 'extracted' to 'parsed'
    cursor.execute("""
        UPDATE documents
        SET status = 'parsed'
        WHERE document_id = ?
    """, (document_id,))
    
    conn.commit()
    conn.close()
    
    return resume_id