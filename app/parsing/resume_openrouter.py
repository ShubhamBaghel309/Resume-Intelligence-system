# app/parsing/resume_parser.py
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from app.models.resume import ParsedResume
import uuid
import json
import os
import sqlite3
from dotenv import load_dotenv

# OpenRouter API Key (free models available)
load_dotenv()

# Use OpenRouter instead of Groq/Gemini
llm = ChatOpenAI(
    model="mistralai/mistral-7b-instruct",
    temperature=0.2,
    max_tokens=4096,
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"]
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
    """Parse resume text using LLM and return structured ParsedResume"""
    result = chain.invoke({"resume_text": raw_text})
    return result


def save_parsed_resume(document_id: str, parsed_resume: ParsedResume) -> str:
    """Save parsed resume data to database and update document status"""
    
    resume_id = str(uuid.uuid4())
    
    skills_json = json.dumps(parsed_resume.technical_skills)
    programming_languages_json = json.dumps(parsed_resume.programming_languages)
    frameworks_json = json.dumps(parsed_resume.frameworks)
    tools_json = json.dumps(parsed_resume.tools)
    work_json = json.dumps([job.model_dump() for job in parsed_resume.work_experience])
    education_json = json.dumps([edu.model_dump() for edu in parsed_resume.education])
    
    conn = sqlite3.connect("resumes.db")
    cursor = conn.cursor()
    
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
        parsed_resume.total_experience_years,
        parsed_resume.current_role,
        skills_json,
        programming_languages_json,
        frameworks_json,
        tools_json,
        work_json,
        education_json
    ))
    
    cursor.execute("""
        UPDATE documents
        SET status = 'parsed'
        WHERE document_id = ?
    """, (document_id,))
    
    conn.commit()
    conn.close()
    
    return resume_id
