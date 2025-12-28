# app/generation/answer_generation.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import os
import json
from dotenv import load_dotenv

# Initialize OpenRouter LLM
# load_dotenv()
# API key loaded from .env file
os.environ["OPENROUTER_API_KEY"] = "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"
llm = ChatOpenAI(
    model="nousresearch/nous-hermes-2-mistral-7b",
    temperature=0.1,  # Slightly creative but factual
    max_tokens=2048,
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY")
)


def format_resume_for_context(resume_data: dict) -> str:
    """Convert resume data into readable text for LLM context"""
    
    parts = []
    
    # Basic info
    parts.append(f"**{resume_data['candidate_name']}**")
    
    if resume_data.get('current_role'):
        parts.append(f"Current Role: {resume_data['current_role']}")
    
    if resume_data.get('location'):
        parts.append(f"Location: {resume_data['location']}")
    
    if resume_data.get('experience_years'):
        parts.append(f"Experience: {resume_data['experience_years']} years")
    
    # Contact
    contact_info = []
    if resume_data.get('email'):
        contact_info.append(f"Email: {resume_data['email']}")
    if resume_data.get('phone'):
        contact_info.append(f"Phone: {resume_data['phone']}")
    if contact_info:
        parts.append(" | ".join(contact_info))
    
    # Skills
    if resume_data.get('technical_skills'):
        try:
            skills = json.loads(resume_data['technical_skills']) if isinstance(resume_data['technical_skills'], str) else resume_data['technical_skills']
            if skills:
                parts.append(f"Skills: {', '.join(skills)}")
        except:
            parts.append(f"Skills: {resume_data['technical_skills']}")
    
    # Work experience
    if resume_data.get('work_experience'):
        try:
            work = json.loads(resume_data['work_experience']) if isinstance(resume_data['work_experience'], str) else resume_data['work_experience']
            if work:
                parts.append("\nWork Experience:")
                for job in work[:3]:  # Limit to top 3 jobs
                    parts.append(f"  • {job.get('role', 'N/A')} at {job.get('company', 'N/A')} ({job.get('duration', 'N/A')})")
        except:
            pass
    
    # Education
    if resume_data.get('education'):
        try:
            edu = json.loads(resume_data['education']) if isinstance(resume_data['education'], str) else resume_data['education']
            if edu:
                parts.append("\nEducation:")
                for degree in edu:
                    parts.append(f"  • {degree.get('degree', 'N/A')} from {degree.get('institute', 'N/A')}")
        except:
            pass
    
    # Add full resume text for detailed queries
    if resume_data.get('raw_text'):
        parts.append("\n=== FULL RESUME CONTENT ===")
        parts.append(resume_data['raw_text'][:2000])  # First 2000 chars
    
    return "\n".join(parts)


def generate_answer(query: str, search_results: list, conversation_history: list = None) -> str:
    """
    Generate natural language answer from search results
    """
    
    if not search_results:
        return "I couldn't find any candidates matching your criteria. Try broadening your search or adjusting the filters."
    
    context_parts = []
    for i, resume in enumerate(search_results, 1):
        formatted = format_resume_for_context(resume)
        context_parts.append(f"\n--- Candidate {i} ---\n{formatted}")
    
    context = "\n".join(context_parts)
    
    history_text = ""
    if conversation_history:
        history_text = "\n\nPrevious Conversation:\n"
        for msg in conversation_history[-3:]:
            history_text += f"{msg['role']}: {msg['content']}\n"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an intelligent recruitment assistant that helps recruiters find, analyze, and evaluate candidates strictly from a provided resume database (search results).

You must operate ONLY on the information explicitly present in the resumes. 
You are a strict resume analyst — not a general-purpose AI.

────────────────────────────────
CORE RESPONSIBILITIES
────────────────────────────────
- Answer questions using ONLY the provided resume/search results
- Be specific, factual, and concise
- Use exact candidate names, skills, job titles, projects, tools, and years of experience as stated
- Highlight the most relevant candidates for the recruiter’s query
- When comparing candidates, present a clear, structured comparison
- When recommending candidates, explain precisely WHY each candidate is suitable using resume evidence

────────────────────────────────
CRITICAL RULES (NON-NEGOTIABLE)
────────────────────────────────
- NEVER mix up information between different candidates
- ALWAYS attribute skills, experience, projects, and achievements to the correct candidate
- If multiple candidates are involved, keep their information clearly separated
- If information is missing, unclear, or not present in a candidate’s resume, explicitly state:
  → "Not specified in this candidate’s resume"
- NEVER infer, guess, assume, or hallucinate details
- NEVER merge information from multiple resumes into one candidate
"""),
        
        ("user", """Question: {query}

{history}

Search Results:
{context}

Please provide a helpful answer based on these candidates.""")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    answer = chain.invoke({
        "query": query,
        "context": context,
        "history": history_text
    })
    
    return answer


def generate_summary(search_results: list) -> str:
    """Generate a quick summary of search results"""
    
    if not search_results:
        return "No candidates found."
    
    total = len(search_results)
    
    with_experience = sum(1 for r in search_results if r.get('experience_years') is not None)
    
    exp_values = [r.get('experience_years', 0) for r in search_results if r.get('experience_years') is not None]
    avg_exp = sum(exp_values) / len(exp_values) if exp_values else 0
    
    all_skills = []
    for r in search_results:
        if r.get('technical_skills'):
            try:
                skills = json.loads(r['technical_skills']) if isinstance(r['technical_skills'], str) else r['technical_skills']
                all_skills.extend(skills)
            except:
                pass
    
    from collections import Counter
    top_skills = [skill for skill, _ in Counter(all_skills).most_common(5)]
    
    summary = f"Found {total} candidate(s). "
    
    if with_experience > 0:
        summary += f"Average experience: {avg_exp:.1f} years. "
    
    if top_skills:
        summary += f"Common skills: {', '.join(top_skills[:3])}. "
    
    return summary
