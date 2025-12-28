# app/parsing/resume_parser.py
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from app.models.resume import ParsedResume
import uuid
import json
import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()
# ============= API KEY =============
# OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

# ============= OLLAMA SETUP =============
llm = ChatOllama(
    model="llama3.1:8b",
    temperature=0.1,
    num_ctx=8192,
    num_predict=4096,
)


parser = PydanticOutputParser(pydantic_object=ParsedResume)

prompt = PromptTemplate(
    template="""You are a resume parsing assistant. Extract structured information from the following resume text.

IMPORTANT - Categorize technical skills precisely:
- programming_languages: Python, Java, C++, JavaScript, SQL, etc.
- frameworks: PyTorch, TensorFlow, React, Django, FastAPI, LangChain, Hugging Face, Scikit-learn, OpenCV, etc.
- tools: VS Code, GitHub, Docker, AWS, Azure, Postman, Jupyter, Google Colab, Ollama, etc.
- technical_skills: Any other technical competencies (databases, methodologies, domains, etc.)

Extract ALL skills mentioned in the resume, not just the top few.

{format_instructions}

Resume Text:
{resume_text}

Return ONLY valid JSON matching the schema above. Be precise and thorough.""",
    input_variables=["resume_text"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

chain = prompt | llm | parser


def parse_resume_with_llm(raw_text: str) -> ParsedResume:
    """Parse resume text using Groq LLM"""
    result = chain.invoke({"resume_text": raw_text})
    return result


def save_parsed_resume(document_id: str, parsed_resume: ParsedResume) -> str:
    """Save parsed resume data to database and update document status"""
    
    resume_id = str(uuid.uuid4())
    
    # Convert lists/objects to JSON strings
    skills_json = json.dumps(parsed_resume.technical_skills)
    programming_languages_json = json.dumps(parsed_resume.programming_languages)
    frameworks_json = json.dumps(parsed_resume.frameworks)
    tools_json = json.dumps(parsed_resume.tools)
    work_json = json.dumps([job.model_dump() for job in parsed_resume.work_experience])
    education_json = json.dumps([edu.model_dump() for edu in parsed_resume.education])
    
    # Connect to database
    conn = sqlite3.connect("resumes.db")
    cursor = conn.cursor()
    
    # Calculate experience if not provided by LLM
    calculated_experience = calculate_total_experience(parsed_resume.work_experience)
    final_experience = parsed_resume.total_experience_years or calculated_experience
    
    # Insert parsed resume data with categorized skills
    cursor.execute("""
        INSERT INTO parsed_resumes (
            resume_id, document_id, candidate_name, email, phone, location,
            total_experience_years, current_role, technical_skills,
            programming_languages, frameworks, tools,
            work_experience, education
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        resume_id,
        document_id,
        parsed_resume.candidate_name,
        parsed_resume.email,
        parsed_resume.phone,
        parsed_resume.location,
        final_experience,
        parsed_resume.current_role,
        skills_json,
        programming_languages_json,
        frameworks_json,
        tools_json,
        work_json,
        education_json
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


def calculate_total_experience(work_experience: list) -> float:
    """
    Calculate total years of experience from work history
    
    Args:
        work_experience: List of WorkExperience objects or dicts
    
    Returns:
        Total years (float). Returns 0 if cannot calculate.
    
    Examples:
        "2020-2023" → 3 years
        "Jan 2020 - Dec 2023" → 4 years
        "2020 - Present" → (2025 - 2020) = 5 years
        "6 months" → 0.5 years
    """
    import re
    from datetime import datetime
    
    total_months = 0
    current_year = datetime.now().year
    
    for job in work_experience:
        # Handle both dict and WorkExperience object
        if hasattr(job, 'duration'):
            duration = job.duration  # ✅ Object attribute
        elif isinstance(job, dict):
            duration = job.get('duration', '')  # ✅ Dictionary key
        else:
            continue
        
        if not duration:
            continue
        
        try:
            # Pattern 1: "2020-2023" or "2020 - 2023"
            year_match = re.search(r'(\d{4})\s*-\s*(\d{4})', duration)
            if year_match:
                start_year = int(year_match.group(1))
                end_year = int(year_match.group(2))
                total_months += (end_year - start_year) * 12
                continue
            
            # Pattern 2: "2020 - Present" or "2020-present"
            present_match = re.search(r'(\d{4})\s*-\s*(?:present|current|now)', duration, re.IGNORECASE)
            if present_match:
                start_year = int(present_match.group(1))
                total_months += (current_year - start_year) * 12
                continue
            
            # Pattern 3: "Jan 2020 - Dec 2023"
            month_year_match = re.search(r'(\w+)\s+(\d{4})\s*-\s*(\w+)\s+(\d{4})', duration)
            if month_year_match:
                start_year = int(month_year_match.group(2))
                end_year = int(month_year_match.group(4))
                total_months += (end_year - start_year) * 12
                continue
            
            # Pattern 4: "6 months" or "2 years"
            duration_match = re.search(r'(\d+)\s*(month|year)', duration, re.IGNORECASE)
            if duration_match:
                value = int(duration_match.group(1))
                unit = duration_match.group(2).lower()
                if 'year' in unit:
                    total_months += value * 12
                else:
                    total_months += value
                continue
                
        except Exception as e:
            # If we can't parse this job, skip it
            continue
    
    # Convert months to years (round to 1 decimal)
    return round(total_months / 12, 1) if total_months > 0 else 0.0