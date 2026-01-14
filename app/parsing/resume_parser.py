# app/parsing/resume_parser.py
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from app.models.resume import ParsedResume
from app.utils.experience_calculator import calculate_years_of_experience
import uuid
import json
import os
import sqlite3
import time
from dotenv import load_dotenv

load_dotenv()

# ============= LLM Setup =============

# Primary LLM: OpenAI
llm_openai = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    max_tokens=4096,
    openai_api_key=os.environ["OPENAI_API_KEY"]
)

# Fallback LLM 1: Groq
llm_groq = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.1,
    max_tokens=4096
)

# Fallback LLM 2: Gemini
llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.1,
    max_tokens=4096
)

# Use OpenAI as default
llm = llm_openai

parser = PydanticOutputParser(pydantic_object=ParsedResume)

prompt = PromptTemplate(
    template="""You are a resume parsing assistant. Extract structured information from the following resume text.

IMPORTANT - Categorize technical skills precisely:
- programming_languages: Python, Java, C++, JavaScript, SQL, etc.
- frameworks: PyTorch, TensorFlow, React, Django, FastAPI, LangChain, Hugging Face, Scikit-learn, OpenCV, etc.
- tools: VS Code, GitHub, Docker, AWS, Azure, Postman, Jupyter, Google Colab, Ollama, etc.
- technical_skills: Any other technical competencies (databases, methodologies, domains, etc.)

WORK EXPERIENCE:
- Extract company name (required), role/title (if available, use "Unknown" if not specified)
- Extract start_date and end_date separately (e.g., "January 2021", "Present")
- Extract responsibilities as a list
- If role is not clear from the resume, use "Unknown" or infer from responsibilities
- If total_experience_years is not explicitly mentioned, leave it as null (we'll calculate it)

EDUCATION:
- Extract institute name (required), degree/qualification (if available, use "Unknown" if not specified)
- If degree type is unclear, use descriptive text like "Schooling", "Higher Education", etc.

PROJECTS:
- Extract all projects mentioned (personal, academic, professional)
- For each project: name, description, technologies used, duration (if mentioned), role
- Look for sections like "Projects", "Side Projects", "Academic Projects", "Portfolio"

ADDITIONAL INFORMATION:
- Extract any other sections not covered above into the "additional_information" field
- This includes: Achievements, Awards, Publications, References, Certifications, Volunteer Work, Languages, Hobbies, Patents, etc.
- Preserve the section structure (e.g., "Achievements: ... Awards: ... References: ...")

Extract ALL skills and projects mentioned in the resume, not just the top few.

IMPORTANT: For missing or unclear fields, use "Unknown" or descriptive placeholders instead of null/None.

{format_instructions}

Resume Text:
{resume_text}

Return ONLY valid JSON matching the schema above. Be precise and thorough.""",
    input_variables=["resume_text"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

# Create OpenAI chain
chain = prompt | llm | parser


def parse_resume_with_llm(raw_text: str, max_retries: int = 3) -> ParsedResume:
    """Parse resume text using LLM with fallback: OpenAI -> Groq -> Gemini"""
    
    # Try OpenAI first
    for attempt in range(max_retries):
        try:
            result = chain.invoke({"resume_text": raw_text})
            return result
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if it's a rate limit error
            if "rate" in error_str or "429" in error_str or "limit" in error_str or "quota" in error_str:
                if attempt < max_retries - 1:
                    wait_time = 10 * (2 ** attempt)
                    print(f"   ⏸️  OpenAI rate limited (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # OpenAI exhausted, try Groq
                    print("   ⚠️  OpenAI rate limit exhausted, falling back to Groq...")
                    break
            else:
                # Non-rate-limit error from OpenAI, try Groq immediately
                print(f"   ⚠️  OpenAI error, trying Groq: {str(e)}")
                break
    
    # Fallback to Groq
    chain_groq = prompt | llm_groq | parser
    for attempt in range(max_retries):
        try:
            result = chain_groq.invoke({"resume_text": raw_text})
            return result
        except Exception as e:
            error_str = str(e).lower()
            
            if "rate" in error_str or "429" in error_str or "limit" in error_str:
                if attempt < max_retries - 1:
                    wait_time = 15 * (2 ** attempt)
                    print(f"   ⏸️  Groq rate limited (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # Groq exhausted, try Gemini
                    print("   ⚠️  Groq rate limit exhausted, falling back to Gemini...")
                    break
            else:
                # Non-rate-limit error from Groq, try Gemini
                print(f"   ⚠️  Groq error, trying Gemini: {str(e)}")
                break
    
    # Final fallback to Gemini
    chain_gemini = prompt | llm_gemini | parser
    for attempt in range(max_retries):
        try:
            result = chain_gemini.invoke({"resume_text": raw_text})
            return result
        except Exception as e:
            error_str = str(e).lower()
            
            if "rate" in error_str or "429" in error_str or "limit" in error_str:
                if attempt < max_retries - 1:
                    wait_time = 20 * (2 ** attempt)
                    print(f"   ⏸️  Gemini rate limited (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"❌ All LLMs (OpenAI, Groq, Gemini) rate limited or exhausted after {max_retries} attempts each")
            else:
                raise Exception(f"❌ Gemini API error: {str(e)}")
    
    raise Exception("❌ Maximum retries exceeded for all LLM providers")


def save_parsed_resume(document_id: str, parsed_resume: ParsedResume) -> str:
    """Save parsed resume data to database and update document status"""
    
    resume_id = str(uuid.uuid4())
    
    # Auto-calculate total_experience_years if LLM didn't provide it
    if parsed_resume.total_experience_years is None or parsed_resume.total_experience_years == 0:
        calculated_years = calculate_years_of_experience(parsed_resume.work_experience)
        if calculated_years:
            parsed_resume.total_experience_years = calculated_years
            print(f"   📊 Auto-calculated experience: {calculated_years} years")
    
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
    
    # Insert parsed resume data with additional_information field
    cursor.execute("""
        INSERT INTO parsed_resumes (
            resume_id, document_id, candidate_name, email, phone, location,
            total_experience_years, current_role, skills,
            work_experience, education, projects, additional_information
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        projects_json,
        parsed_resume.additional_information  # NEW
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