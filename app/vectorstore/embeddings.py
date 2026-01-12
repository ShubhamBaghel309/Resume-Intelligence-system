from app.models.resume import ParsedResume
from typing import List, Dict
import json

def create_resume_chunks(parsed_resume: ParsedResume, raw_text: str = None) -> List[Dict[str, str]]:
    """
    Create semantic chunks from resume following role-based chunking strategy
    
    CHUNKING RULES:
    1. One chunk per job role (prevents semantic dilution)
    2. Optional summary chunk for high-level overview
    3. DO NOT chunk skills/education (SQL has them)
    4. Target: 100-300 tokens per chunk, max 400
    
    Returns:
        List of {
            "type": "summary" | "experience" | "project",
            "text": str,
            "metadata": {...}  # For explainability
        }
    """
    chunks = []
    
    # =========================================================================
    # Chunk 1: Resume Summary (Optional, 1 chunk)
    # =========================================================================
    # Purpose: High-level professional overview for "Tell me about X" queries
    
    summary_parts = []
    summary_parts.append(f"Professional Summary: {parsed_resume.candidate_name}")
    
    if parsed_resume.current_role:
        summary_parts.append(f"Current Role: {parsed_resume.current_role}")
    
    if parsed_resume.total_experience_years:
        summary_parts.append(f"Total Experience: {parsed_resume.total_experience_years} years")
    
    if parsed_resume.location:
        summary_parts.append(f"Location: {parsed_resume.location}")
    
    # Brief career overview from most recent role
    if parsed_resume.work_experience and len(parsed_resume.work_experience) > 0:
        latest_job = parsed_resume.work_experience[0]
        summary_parts.append(f"Currently/Recently: {latest_job.role} at {latest_job.company}")
    
    summary_text = ". ".join(summary_parts)
    
    chunks.append({
        "type": "summary",
        "text": summary_text,
        "metadata": {
            "chunk_type": "summary",
            "candidate_name": parsed_resume.candidate_name or "Unknown"
        }
    })
    
    # =========================================================================
    # Chunk 2+: Work Experience (MANDATORY - One chunk per job role)
    # =========================================================================
    # Purpose: Enable role-specific semantic search (e.g., "GenAI experience")
    # CRITICAL: Do NOT merge multiple roles into one chunk
    
    for job in parsed_resume.work_experience:
        # Build experience chunk for this specific role
        experience_parts = []
        
        # Header with role and company
        experience_parts.append(
            f"{job.role} at {job.company}"
        )
        
        # Duration
        if job.start_date and job.end_date:
            duration = f"({job.start_date} to {job.end_date})"
            experience_parts.append(duration)
        
        # Responsibilities (the key semantic content)
        if job.responsibilities:
            if isinstance(job.responsibilities, list):
                # Join responsibilities with clear separation
                resp_text = " • " + " • ".join(job.responsibilities)
                experience_parts.append(f"Responsibilities: {resp_text}")
            else:
                experience_parts.append(f"Responsibilities: {job.responsibilities}")
        
        experience_text = f"Work Experience of {parsed_resume.candidate_name}: " + " ".join(experience_parts)
        
        # Truncate if too long (max 400 tokens ≈ 1600 chars)
        if len(experience_text) > 1600:
            experience_text = experience_text[:1600] + "..."
        
        # Extract year from dates for metadata
        start_year = None
        end_year = None
        try:
            if job.start_date:
                start_year = int(job.start_date.split()[-1]) if job.start_date else None
            if job.end_date and job.end_date.lower() != "present":
                end_year = int(job.end_date.split()[-1]) if job.end_date else None
        except:
            pass
        
        chunks.append({
            "type": "experience",
            "text": experience_text,
            "metadata": {
                "chunk_type": "experience",
                "candidate_name": parsed_resume.candidate_name or "Unknown",
                "role": job.role or "Not specified",
                "company": job.company or "Not specified",
                "start_year": start_year if start_year is not None else "Unknown",
                "end_year": end_year if end_year is not None else "Present"
            }
        })
    
    # =========================================================================
    # Chunk 3+: Projects (One chunk per project)
    # =========================================================================
    # Purpose: Enable project-specific search ("RAG chatbot project", "ML deployment")
    # CRITICAL: One chunk per project
    
    for project in parsed_resume.projects:
        # Build project chunk
        project_parts = []
        
        # Header with project name
        project_parts.append(f"Project: {project.name}")
        
        # Description (the key semantic content)
        if project.description:
            project_parts.append(f"Description: {project.description}")
        
        # Technologies used
        if project.technologies:
            tech_list = ", ".join(project.technologies)
            project_parts.append(f"Technologies: {tech_list}")
        
        # Role in project
        if project.role:
            project_parts.append(f"Role: {project.role}")
        
        # Duration
        if project.duration:
            project_parts.append(f"Duration: {project.duration}")
        
        project_text = f"Project by {parsed_resume.candidate_name}: " + ". ".join(project_parts)
        
        # Truncate if too long (max 400 tokens ≈ 1600 chars)
        if len(project_text) > 1600:
            project_text = project_text[:1600] + "..."
        
        chunks.append({
            "type": "project",
            "text": project_text,
            "metadata": {
                "chunk_type": "project",
                "candidate_name": parsed_resume.candidate_name or "Unknown",
                "project_name": project.name or "Unnamed Project",
                "technologies": ", ".join(project.technologies) if project.technologies else "Not specified",
                "role": project.role or "Not specified"
            }
        })
    
    
    # =========================================================================
    # Chunk N: Additional Information (Catch-all for uncategorized content)
    # =========================================================================
    # Purpose: Capture achievements, certifications, courses, publications, awards, etc.
    # This handles resume sections not covered by structured chunks
    
    if raw_text:
        additional_info = extract_additional_info(raw_text, parsed_resume.candidate_name)
        if additional_info:
            chunks.append({
                "type": "additional_info",
                "text": additional_info,
                "metadata": {
                    "chunk_type": "additional_info",
                    "candidate_name": parsed_resume.candidate_name
                }
            })
    
    # NOTE: Skills and Education are NOT chunked separately - they're in SQL
    # NOTE: The full_resume chunk ensures NOTHING is missed (achievements, awards, references, etc.)
    
    return chunks


def extract_additional_info(raw_text: str, candidate_name: str) -> str:
    """
    Extract ALL miscellaneous content from resume not covered by structured chunks
    
    Strategy: Take the full raw_text and create a comprehensive additional_info chunk
    This ensures NOTHING is missed (interests, certifications, coding platforms, hobbies, etc.)
    """
    
    if not raw_text or len(raw_text.strip()) < 50:
        return None
    
    # Clean up the raw text
    lines = raw_text.split('\n')
    cleaned_lines = []
    
    # Sections to SKIP (already in structured chunks)
    skip_section_keywords = [
        "work experience", "employment history", "professional experience", "experience",
        "education", "academic background", "qualifications",
        "projects", "personal projects", "academic projects", "project"
    ]
    
    # Keywords for sections we WANT to keep
    keep_section_keywords = [
        "skill", "certification", "certificate", "award", "achievement",
        "honor", "recognition", "course", "training", "publication",
        "patent", "volunteer", "language", "interest", "hobby",
        "reference", "coding", "platform", "profile"
    ]
    
    skip_mode = False
    last_was_section_header = False
    
    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        
        # Skip empty lines in skip mode
        if not line_stripped:
            if not skip_mode:
                cleaned_lines.append("")  # Preserve spacing
            continue
        
        # Check if this is a section header we should skip
        is_skip_section = any(keyword in line_lower for keyword in skip_section_keywords)
        
        # Section headers are SHORT (< 40 chars), ALL CAPS or title case, and may end with colon
        is_likely_section_header = (
            len(line_stripped) < 40 and
            (line_stripped.isupper() or 
             line_stripped.istitle() or
             line_stripped.endswith(':'))
        )
        
        if is_skip_section and is_likely_section_header:
            # Entering a section we already have in structured chunks
            skip_mode = True
            continue
        
        # Check if this is a section we want to KEEP
        is_keep_section = any(keyword in line_lower for keyword in keep_section_keywords)
        
        if is_keep_section and is_likely_section_header:
            skip_mode = False  # Start capturing
            # Add section header with formatting
            cleaned_lines.append(f"\n**{line_stripped}**")
            last_was_section_header = True
            continue
        
        # Capture line if not in skip mode
        if not skip_mode:
            cleaned_lines.append(line_stripped)
            last_was_section_header = False
    
    # Join and create the additional info chunk
    if cleaned_lines:
        additional_text = f"Additional Information for {candidate_name}:\n\n" + "\n".join(cleaned_lines)
        # NO TRUNCATION - capture everything (References, Interests are usually at the end)
        return additional_text
    
    return None


def create_resume_metadata(parsed_resume: ParsedResume, document_id: str, resume_id: str) -> Dict:
    """
    Create document-level metadata (chunk-specific metadata is in chunks themselves)
    
    This provides basic resume-level info that applies to all chunks.
    Individual chunks have their own metadata (role, company, years, etc.)
    
    IMPORTANT: ChromaDB does NOT accept None values - all must be strings/numbers
    """
    
    return {
        # IDs for database joins
        "document_id": document_id or "",
        "resume_id": resume_id or "",
        
        # Basic candidate info (for all chunks) - NO None values allowed
        "candidate_name": parsed_resume.candidate_name or "Unknown",
        "total_experience_years": float(parsed_resume.total_experience_years) if parsed_resume.total_experience_years is not None else 0.0,
        "current_role": parsed_resume.current_role or "Not specified",
        "location": parsed_resume.location or "Not specified",
        "num_skills": len(parsed_resume.technical_skills) if parsed_resume.technical_skills else 0
    }