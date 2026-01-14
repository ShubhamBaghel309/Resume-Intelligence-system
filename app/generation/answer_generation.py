# app/generation/answer_generation.py
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
# Initialize LLMs
load_dotenv()
# API key loaded from .env file

# Primary LLM: OpenAI (good balance, may have rate limits)
llm_openai = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    max_tokens=4096,
    openai_api_key=os.environ["OPENAI_API_KEY"]
)

# Fallback LLM 1: Groq (fast, 128K context)
llm_groq = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.1,
    max_tokens=4096
)

# Fallback LLM 2: Gemini (2M context, no rate limits)
llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.1,
    max_tokens=4096
)

# Use OpenAI as default
llm = llm_openai


def format_resume_for_context(resume_data: dict, include_full_text: bool = False) -> str:
    """
    Convert resume data into readable text for LLM context
    
    Args:
        resume_data: Resume dict from database
        include_full_text: If True, includes complete raw_text (for specific candidate queries)
    """
    
    parts = []
    
    # Basic info
    parts.append(f"**{resume_data['candidate_name']}**")
    
    if resume_data.get('current_role'):
        parts.append(f"Current Role: {resume_data['current_role']}")
    
    if resume_data.get('location'):
        parts.append(f"Location: {resume_data['location']}")
    
    if resume_data.get('total_experience_years'):
        parts.append(f"Experience: {resume_data['total_experience_years']} years")
    
    # Contact
    contact_info = []
    if resume_data.get('email'):
        contact_info.append(f"Email: {resume_data['email']}")
    if resume_data.get('phone'):
        contact_info.append(f"Phone: {resume_data['phone']}")
    if contact_info:
        parts.append(" | ".join(contact_info))
    
    # Skills
    if resume_data.get('skills'):
        try:
            skills = json.loads(resume_data['skills']) if isinstance(resume_data['skills'], str) else resume_data['skills']
            if skills:
                parts.append(f"Skills: {', '.join(skills)}")
        except:
            parts.append(f"Skills: {resume_data['skills']}")
    
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
    
    # Projects (CRITICAL: This was missing!)
    if resume_data.get('projects'):
        try:
            projects = json.loads(resume_data['projects']) if isinstance(resume_data['projects'], str) else resume_data['projects']
            if projects:
                parts.append("\nProjects:")
                for proj in projects:
                    proj_name = proj.get('name', 'Unnamed Project')
                    proj_desc = proj.get('description', 'No description')
                    proj_tech = proj.get('technologies', [])
                    
                    parts.append(f"  • {proj_name}")
                    parts.append(f"    Description: {proj_desc}")
                    if proj_tech:
                        tech_str = ', '.join(proj_tech) if isinstance(proj_tech, list) else proj_tech
                        parts.append(f"    Technologies: {tech_str}")
                    if proj.get('role'):
                        parts.append(f"    Role: {proj.get('role')}")
        except Exception as e:
            # If projects parsing fails, at least try to show raw data
            parts.append(f"\nProjects: {resume_data.get('projects', 'Error parsing projects')}")
    
    # ✅ FIX: Include matched vector chunks (project details, achievements, etc.)
    if resume_data.get('matched_chunks'):
        print(f"   🔍 DEBUG: Found {len(resume_data['matched_chunks'])} matched chunks for {resume_data.get('candidate_name')}")
        parts.append("\n--- Matched Content from Vector Search ---")
        for chunk in resume_data['matched_chunks']:
            chunk_type = chunk.get('chunk_type', 'unknown')
            chunk_text = chunk.get('chunk_text', '')
            if chunk_text:
                print(f"      - Including {chunk_type} chunk ({len(chunk_text)} chars)")
                parts.append(f"\n[{chunk_type.upper()}]")
                parts.append(chunk_text)  # NO TRUNCATION - include full content
    else:
        print(f"   ⚠️  DEBUG: No matched_chunks found for {resume_data.get('candidate_name')}")
    
    # ✅ CRITICAL FIX: Include full raw_text for comprehensive coverage
    # This ensures the LLM can answer questions about:
    # - Languages, Driving License, Hobbies, Interests
    # - References, Publications, Patents
    # - Certifications, Awards, Honors
    # - Coding platforms (LeetCode, Codeforces, etc.)
    # - ANY other resume section not in structured fields
    # 
    # NOTE: Only include for specific candidate queries (1-2 candidates)
    # to avoid overwhelming the LLM with too much text
    if include_full_text and resume_data.get('raw_text'):
        raw_text = resume_data['raw_text']
        print(f"   📄 Including full raw_text ({len(raw_text)} chars)")
        parts.append("\n--- COMPLETE RESUME TEXT ---")
        parts.append(raw_text)
    
    return "\n".join(parts)


def generate_answer(query: str, search_results: list, conversation_history: list = None) -> str:
    """
    Generate natural language answer from search results
    
    Args:
        query: User's question
        search_results: List of resume data dicts from hybrid search
        conversation_history: Optional previous messages for context
        
    Returns:
        Natural language answer
    """
    
    # Format context from search results
    if not search_results:
        return "I couldn't find any candidates matching your criteria. Try broadening your search or adjusting the filters."
    
    # ✅ Smart decision: Include full raw_text ONLY for specific queries (1-2 candidates)
    # For broader searches (3+ candidates), rely on structured fields + matched_chunks
    include_full_text = len(search_results) <= 2
    
    if include_full_text:
        print(f"   📋 Including FULL resume text for {len(search_results)} candidate(s)")
    else:
        print(f"   📋 Using structured fields only for {len(search_results)} candidates")
    
    context_parts = []
    for i, resume in enumerate(search_results, 1):
        formatted = format_resume_for_context(resume, include_full_text=include_full_text)
        context_parts.append(f"\n--- Candidate {i} ---\n{formatted}")
    
    context = "\n".join(context_parts)
    
    # Build conversation history if provided
    history_text = ""
    if conversation_history:
        history_text = "\n\nPrevious Conversation:\n"
        for msg in conversation_history[-3:]:  # Last 3 exchanges
            history_text += f"{msg['role']}: {msg['content']}\n"
    
    # Create prompt
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
  • Example: “Candidate Rahul Sharma has 5 years of backend experience in Java”
- If multiple candidates are involved, keep their information clearly separated
- If information is missing, unclear, or not present in a candidate’s resume, explicitly state:
  → "Not specified in this candidate’s resume"
- NEVER infer, guess, assume, or hallucinate details
- NEVER merge information from multiple resumes into one candidate

────────────────────────────────DATA SOURCES - USE ALL AVAILABLE
────────────────────────────────
You will receive resume data in multiple formats:
1. **Structured Fields**: skills, work_experience, education, projects (parsed)
2. **Matched Chunks**: Relevant sections from vector search
3. **Complete Resume Text**: Full raw resume (for specific queries)

**CRITICAL:** Always check ALL provided sections before saying "not specified":
- Check structured fields first
- Then check "Matched Content from Vector Search"
- Then check "COMPLETE RESUME TEXT" section (if present)
- Information like Languages, Driving License, References, Hobbies, Awards may ONLY be in the complete text

────────────────────────────────RESPONSE FORMAT GUIDELINES
────────────────────────────────
- Use a clear structure with bullet points or numbered lists when helpful
- Mention candidate names prominently
- Include only relevant skills and experience for the query
- Keep responses concise but informative
- Maintain a professional, recruiter-focused tone
- Provide contact information ONLY if explicitly requested

────────────────────────────────
DATA TRUST POLICY
────────────────────────────────
- Trust ONLY the provided resumes/search results
- Accuracy, attribution, and candidate separation are mandatory
- If uncertain, say “Not specified” rather than making assumptions
"""),
        
        ("user", """Question: {query}

{history}

Search Results:
{context}

Please provide a helpful answer based on these candidates.""")
    ])
    
    # Generate answer with fallback
    chain = prompt | llm | StrOutputParser()
    
    try:
        # Try OpenAI first
        answer = chain.invoke({
            "query": query,
            "context": context,
            "history": history_text
        })
    except Exception as e:
        # If OpenAI fails (rate limit), fallback to Groq
        if "rate_limit" in str(e).lower() or "429" in str(e):
            print("   ⚠️  OpenAI rate limit hit, falling back to Groq...")
            try:
                chain_groq = prompt | llm_groq | StrOutputParser()
                answer = chain_groq.invoke({
                    "query": query,
                    "context": context,
                    "history": history_text
                })
            except Exception as groq_error:
                # If Groq also fails, fallback to Gemini
                if "rate_limit" in str(groq_error).lower() or "429" in str(groq_error):
                    print("   ⚠️  Groq rate limit hit too, falling back to Gemini...")
                    chain_gemini = prompt | llm_gemini | StrOutputParser()
                    answer = chain_gemini.invoke({
                        "query": query,
                        "context": context,
                        "history": history_text
                    })
                else:
                    raise groq_error
        else:
            raise  # Re-raise if it's not a rate limit error
    
    return answer


def generate_summary(search_results: list) -> str:
    """Generate a quick summary of search results"""
    
    if not search_results:
        return "No candidates found."
    
    total = len(search_results)
    
    # Extract key stats (handle None values properly)
    with_experience = sum(1 for r in search_results if r.get('experience_years') is not None)
    
    # Calculate average experience (skip None values)
    exp_values = [r.get('experience_years', 0) for r in search_results if r.get('experience_years') is not None]
    avg_exp = sum(exp_values) / len(exp_values) if exp_values else 0
    
    # Top skills
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
    
    # Generate summary
    summary = f"Found {total} candidate(s). "
    
    if with_experience > 0:
        summary += f"Average experience: {avg_exp:.1f} years. "
    
    if top_skills:
        summary += f"Common skills: {', '.join(top_skills[:3])}. "
    
    return summary


# Example usage and testing
if __name__ == "__main__":
    # Test with mock data
    mock_results = [
        {
            "candidate_name": "Shubham Baghel",
            "email": "shubhambaghel307@gmail.com",
            "phone": "+91-8307489623",
            "location": "Rewari, Haryana",
            "experience_years": None,
            "current_role": None,
            "technical_skills": '["Python", "C", "C++", "SQL", "HTML", "CSS"]',
            "work_experience": None,
            "education": '[{"institute": "NIT Kurukshetra", "degree": "B.Tech CSE", "year": "2026"}]'
        }
    ]
    
    print("Testing Answer Generation...")
    print("="*70)
    
    query = "Find me a Python developer with machine learning skills"
    answer = generate_answer(query, mock_results)
    
    print(f"\nQuery: {query}")
    print(f"\nAnswer:\n{answer}")
    
    print("\n" + "="*70)
    print("Summary:", generate_summary(mock_results))