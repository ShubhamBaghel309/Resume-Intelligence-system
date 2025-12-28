from app.models.resume import ParsedResume
from typing import List, Dict
import json

def create_resume_chunks(parsed_resume: ParsedResume, raw_text: str = None) -> List[Dict[str, str]]:
    """
    Convert ParsedResume into searchable chunks (improved for domain matching)
    
    Why multiple chunks?
    - Summary: Quick overview with ALL key skills
    - Technical Profile: Detailed skills breakdown (languages, frameworks, tools)
    - Work Experience: Job history and responsibilities
    - Education: Academic background
    - Full Content: Complete resume text (for projects, achievements, everything!)
    
    Returns:
        List of {"type": str, "text": str}
    """
    chunks = []
    
    # =========================================================================
    # Chunk 1: Enhanced Summary (High-level overview with comprehensive skills)
    # =========================================================================
    # Purpose: Match broad queries like "Python developer" or "ML engineer"
    summary_parts = [
        parsed_resume.candidate_name,
        f"{parsed_resume.current_role or 'Professional'}"
    ]
    
    if parsed_resume.total_experience_years:
        summary_parts.append(f"{parsed_resume.total_experience_years} years experience")
    
    if parsed_resume.location:
        summary_parts.append(f"located in {parsed_resume.location}")
    
    # Add ALL skills categorically (no truncation)
    skill_highlights = []
    
    if parsed_resume.programming_languages:
        skill_highlights.append(f"Programming: {', '.join(parsed_resume.programming_languages)}")
    
    if parsed_resume.frameworks:
        skill_highlights.append(f"Frameworks: {', '.join(parsed_resume.frameworks)}")
    
    if parsed_resume.tools:
        skill_highlights.append(f"Tools: {', '.join(parsed_resume.tools)}")
    
    if parsed_resume.technical_skills:
        skill_highlights.append(f"Other Skills: {', '.join(parsed_resume.technical_skills)}")
    
    if skill_highlights:
        summary_parts.append(" | ".join(skill_highlights))
    
    summary_text = " | ".join(summary_parts)
    chunks.append({"type": "summary", "text": summary_text})
    
    
    # =========================================================================
    # Chunk 2: Technical Profile (Detailed skills breakdown)
    # =========================================================================
    # Purpose: Match domain-specific queries like "Generative AI with LangChain"
    # Emphasizes frameworks and tools which indicate specialization
    tech_profile_parts = []
    
    # Frameworks FIRST (most important for domain matching)
    if parsed_resume.frameworks:
        frameworks_text = f"Expert in frameworks: {', '.join(parsed_resume.frameworks)}"
        tech_profile_parts.append(frameworks_text)
    
    # Programming languages
    if parsed_resume.programming_languages:
        langs_text = f"Programming languages: {', '.join(parsed_resume.programming_languages)}"
        tech_profile_parts.append(langs_text)
    
    # Developer tools and platforms
    if parsed_resume.tools:
        tools_text = f"Developer tools and platforms: {', '.join(parsed_resume.tools)}"
        tech_profile_parts.append(tools_text)
    
    # Additional technical skills
    if parsed_resume.technical_skills:
        other_skills_text = f"Additional competencies: {', '.join(parsed_resume.technical_skills)}"
        tech_profile_parts.append(other_skills_text)
    
    tech_profile_text = ". ".join(tech_profile_parts) if tech_profile_parts else "No technical skills specified"
    chunks.append({"type": "technical_profile", "text": tech_profile_text})
    
    
    # =========================================================================
    # Chunk 3: Work Experience (Detailed job history)
    # =========================================================================
    # Purpose: Domain/role matching - "worked at Google on ML systems"
    experience_parts = []
    
    for job in parsed_resume.work_experience:
        # Build detailed job description
        job_text = f"{job.role} at {job.company} ({job.duration})"
        
        # Add responsibilities if available
        if job.responsibilities:
            responsibilities = ". ".join(job.responsibilities[:3])  # Limit to 3
            job_text += f". Responsibilities: {responsibilities}"
        
        experience_parts.append(job_text)
    
    # Join all jobs with clear separator
    experience_text = " || ".join(experience_parts) if experience_parts else "No work experience listed"
    chunks.append({"type": "experience", "text": experience_text})
    
    
    # =========================================================================
    # Chunk 4: Education (Academic background)
    # =========================================================================
    # Purpose: Match educational requirements - "MS in Computer Science"
    education_parts = []
    
    if parsed_resume.education:
        for edu in parsed_resume.education:
            edu_text = f"{edu.degree} from {edu.institute}"
            if edu.year:
                edu_text += f" ({edu.year})"
            education_parts.append(edu_text)
    
    education_text = ". ".join(education_parts) if education_parts else "No education information listed"
    chunks.append({"type": "education", "text": education_text})
    
    
    # =========================================================================
    # Chunk 5: FULL RAW TEXT (Projects, Achievements, Everything!)
    # =========================================================================
    # Purpose: Find detailed information like "RAG projects", "LLM finetuning", achievements
    # This is the KEY chunk for comprehensive search
    if raw_text:
        chunks.append({"type": "full_content", "text": raw_text})
    
    return chunks


def create_resume_metadata(parsed_resume: ParsedResume, document_id: str, resume_id: str) -> Dict:
    """
    Create metadata dict for Chroma filtering
    
    Why metadata?
    - Enables fast pre-filtering (SQL-like queries)
    - Example: Filter by experience > 10 BEFORE semantic search
    - Reduces search space = faster + cheaper
    """
    
    # Extract company names for filtering
    companies = [job.company for job in parsed_resume.work_experience]
    
    # Combine all skills for metadata filtering
    all_skills = (
        parsed_resume.programming_languages + 
        parsed_resume.frameworks + 
        parsed_resume.tools + 
        parsed_resume.technical_skills
    )
    
    return {
        # IDs for database joins
        "document_id": document_id,
        "resume_id": resume_id,
        
        # Filtering fields (for WHERE clauses)
        "candidate_name": parsed_resume.candidate_name or "Unknown",
        "total_experience_years": parsed_resume.total_experience_years or 0.0,
        "current_role": parsed_resume.current_role or "Not specified",
        "location": parsed_resume.location or "Not specified",
        
        # JSON arrays for $contains queries
        "all_skills": json.dumps(all_skills),
        "programming_languages": json.dumps(parsed_resume.programming_languages),
        "frameworks": json.dumps(parsed_resume.frameworks),
        "tools": json.dumps(parsed_resume.tools),
        "companies": json.dumps(companies),
        
        # Counts for filtering
        "num_skills": len(all_skills),
        "num_frameworks": len(parsed_resume.frameworks),
        "num_jobs": len(parsed_resume.work_experience),
        "num_degrees": len(parsed_resume.education)
    }