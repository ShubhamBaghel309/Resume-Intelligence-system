# app/generation/answer_generation.py
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import os
import json
import re
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


def _extract_company_filter_from_query(query: str) -> str | None:
    """Extract a likely company constraint from queries like 'work experience at WhiteHat Jr'."""
    query_text = query or ""
    patterns = [
        r"\bat\s+([A-Za-z][A-Za-z0-9&.,\- ]{1,60})",
        r"\bwith\s+([A-Za-z][A-Za-z0-9&.,\- ]{1,60})",
    ]
    split_pattern = r"(?:\?|\.|,|\bfor\b|\bwho\b|\bthat\b|\bhaving\b|\bwhere\b)"
    for pattern in patterns:
        match = re.search(pattern, query_text, flags=re.IGNORECASE)
        if not match:
            continue
        raw_value = match.group(1).strip()
        cleaned = re.split(split_pattern, raw_value, maxsplit=1)[0].strip(" .,'\"")
        if cleaned:
            return cleaned
    return None


def _filter_work_experience_for_query(resume_data: dict, query: str) -> dict:
    """Limit work experience to the requested company so answers stay on-point."""
    query_lower = (query or "").lower()
    if not any(token in query_lower for token in ["work experience", "work ex", "worked", "experience", "role"]):
        return resume_data

    company_filter = _extract_company_filter_from_query(query)
    if not company_filter:
        return resume_data

    work_items = _safe_json_list(resume_data.get("work_experience"))
    if not work_items:
        return resume_data

    company_filter_lower = company_filter.lower()
    filtered_items = []
    for item in work_items:
        if not isinstance(item, dict):
            continue
        haystack = " ".join(
            str(item.get(key, "")) for key in ["company", "role", "duration", "responsibilities"]
        ).lower()
        if company_filter_lower in haystack:
            filtered_items.append(item)

    if not filtered_items:
        return resume_data

    filtered_resume = dict(resume_data)
    filtered_resume["work_experience"] = json.dumps(filtered_items)
    # Avoid giving the model unrelated raw text when the user asked about a single company stint.
    filtered_resume["raw_text"] = None
    return filtered_resume


def generate_compact_list(search_results: list, query: str) -> str:
    """
    Generate compact list of ALL candidates (not detailed profiles)
    Used when user asks for 'list of all', 'all candidates', etc.
    
    Args:
        search_results: List of resume data dicts
        query: Original user query
        
    Returns:
        Compact markdown table/list of all candidates
    """
    print(f"   📋 Generating compact list of {len(search_results)} candidates...")
    
    lines = []
    lines.append(f"**Found {len(search_results)} candidates matching your criteria:**\n")
    lines.append("| # | Name | Experience | Current Role | Key Skills | Location |")
    lines.append("|---|------|------------|--------------|------------|----------|")
    
    for i, resume in enumerate(search_results, 1):
        try:
            name = resume.get('candidate_name') or 'Unknown'
            
            # Safe experience handling
            exp_val = resume.get('total_experience_years')
            exp = f"{exp_val} yrs" if exp_val is not None else "N/A"
            
            role = resume.get('current_role') or 'Not specified'
            location = resume.get('location') or 'N/A'
            
            # Get top 3 skills
            skills_str = "N/A"
            skills_data = resume.get('skills')
            if skills_data:
                try:
                    skills = json.loads(skills_data) if isinstance(skills_data, str) else skills_data
                    if skills and isinstance(skills, list) and len(skills) > 0:
                        skills_str = ', '.join(str(s) for s in skills)
                except Exception:
                    # If parsing fails, use raw value
                    skills_str = str(skills_data) if skills_data else "N/A"
            
            # Ensure all values are strings
            name = str(name)
            exp = str(exp)
            role = str(role)
            location = str(location)
            skills_str = str(skills_str)
            
            lines.append(f"| {i} | {name} | {exp} | {role} | {skills_str} | {location} |")
        except Exception as e:
            # If any error, add a placeholder row
            print(f"   ⚠️  Error processing candidate {i}: {e}")
            lines.append(f"| {i} | Error processing candidate | N/A | N/A | N/A | N/A |")
    
    lines.append(f"\n**Total: {len(search_results)} candidates**")
    lines.append("\n💡 *You can ask follow-up questions like:*")
    lines.append("- \"Show me detailed profiles of candidates 1-5\"")
    lines.append("- \"Among these, who has experience in machine learning?\"")
    lines.append("- \"Filter to candidates with 5+ years experience\"")
    
    return "\n".join(lines)


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
                for job in work:
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


def _safe_json_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _generate_rule_based_answer(query: str, search_results: list, dropped_filters: list = None) -> str:
    """Local fallback answer generation when remote LLMs are unavailable."""
    if not search_results:
        return "I couldn't find any candidates matching your criteria. Try broadening your search or adjusting the filters."

    query_lower = (query or "").lower()
    intro = ""
    if dropped_filters:
        intro = (
            f"I couldn't satisfy the exact constraints, so I broadened the search by dropping: {', '.join(dropped_filters)}.\n\n"
        )

    if len(search_results) == 1:
        candidate = search_results[0]
        name = candidate.get("candidate_name") or "Unknown candidate"
        role = candidate.get("current_role") or "Role not specified"
        exp = candidate.get("total_experience_years")
        exp_text = f"{exp} years of experience" if exp is not None else "experience not specified"

        if any(token in query_lower for token in ["experience", "work", "worked", "role"]):
            jobs = _safe_json_list(candidate.get("work_experience"))
            lines = [f"{name} is currently listed as {role} with {exp_text}."]
            if jobs:
                lines.append("Work experience:")
                for job in jobs[:6]:
                    if isinstance(job, dict):
                        company = job.get("company", "Unknown company")
                        job_role = job.get("role", "Role not specified")
                        duration = job.get("duration", "Duration not specified")
                        lines.append(f"- {job_role} at {company} ({duration})")
            return intro + "\n".join(lines)

        if "project" in query_lower:
            projects = _safe_json_list(candidate.get("projects"))
            if projects:
                lines = [f"Projects for {name}:"]
                for project in projects[:6]:
                    if isinstance(project, dict):
                        project_name = project.get("name", "Unnamed project")
                        tech = project.get("technologies", [])
                        tech_text = ", ".join(tech[:5]) if isinstance(tech, list) else str(tech)
                        suffix = f" | Technologies: {tech_text}" if tech_text else ""
                        lines.append(f"- {project_name}{suffix}")
                return intro + "\n".join(lines)

        if any(token in query_lower for token in ["education", "degree", "college", "university", "institute"]):
            education = _safe_json_list(candidate.get("education"))
            if education:
                lines = [f"Education for {name}:"]
                for item in education[:4]:
                    if isinstance(item, dict):
                        degree = item.get("degree", "Degree not specified")
                        institute = item.get("institute", "Institute not specified")
                        year = item.get("year", "Year not specified")
                        lines.append(f"- {degree} from {institute} ({year})")
                return intro + "\n".join(lines)

        if "skill" in query_lower:
            skills = _safe_json_list(candidate.get("skills"))
            if skills:
                return intro + f"Skills for {name}: {', '.join(str(skill) for skill in skills[:15])}"

        return intro + f"{name} is currently listed as {role} with {exp_text}."

    lines = [f"Found {len(search_results)} candidates:"]
    for index, candidate in enumerate(search_results[:10], start=1):
        name = candidate.get("candidate_name") or "Unknown candidate"
        role = candidate.get("current_role") or "Role not specified"
        exp = candidate.get("total_experience_years")
        location = candidate.get("location") or "Location not specified"
        exp_text = f"{exp} yrs" if exp is not None else "exp n/a"
        lines.append(f"{index}. {name} | {role} | {exp_text} | {location}")

    return intro + "\n".join(lines)


def generate_answer(query: str, search_results: list, conversation_history: list = None, format_as_list: bool = False, dropped_filters: list = None) -> str:
    """
    Generate natural language answer from search results
    
    Args:
        query: User's question
        search_results: List of resume data dicts from hybrid search
        conversation_history: Optional previous messages for context
        format_as_list: If True, return compact list of ALL candidates (not detailed profiles)
        
    Returns:
        Natural language answer
    """
    
    # Format context from search results
    if not search_results:
        return "I couldn't find any candidates matching your criteria. Try broadening your search or adjusting the filters."
    
    # ✅ LIST ALL mode: Provide compact summary of ALL candidates
    if format_as_list:
        return generate_compact_list(search_results, query)

    search_results_for_query = [
        _filter_work_experience_for_query(resume, query) for resume in search_results
    ]
    
    # ✅ Smart decision: Include full raw_text ONLY for specific queries (1-2 candidates)
    # For broader searches (3+ candidates), rely on structured fields + matched_chunks
    include_full_text = len(search_results_for_query) <= 2
    
    if include_full_text:
        print(f"   📋 Including FULL resume text for {len(search_results)} candidate(s)")
    else:
        print(f"   📋 Using structured fields only for {len(search_results)} candidates")
    
    context_parts = []
    for i, resume_for_query in enumerate(search_results_for_query, 1):
        formatted = format_resume_for_context(resume_for_query, include_full_text=include_full_text and resume_for_query.get("raw_text") is not None)
        context_parts.append(f"\n--- Candidate {i} ---\n{formatted}")
    
    context = "\n".join(context_parts)
    
    # Build conversation history if provided
    history_text = ""
    if conversation_history:
        history_text = "\n\nPrevious Conversation:\n"
        for msg in conversation_history[-3:]:  # Last 3 exchanges
            history_text += f"{msg['role']}: {msg['content']}\n"
            
    dropped_filters_text = ""
    if dropped_filters:
        dropped_filters_text = f"\n⚠️ NOTE TO AI: The user's query was originally too strict and returned 0 results. To find candidates, the following strict filters were gracefully dropped by the system: {', '.join(dropped_filters)}. You MUST inform the user about this in your response and ask a clarifying question if needed.\n"

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
1. **Focus:** Only answer what the user asks
2. **Comparisons:** Use bullet points or a short markdown table
3. **Clarity:** Keep sentences short and clear
4. **Accuracy:** Use exact quotes or snippets when asked to summarize experience
5. **No Hallucinations:** Say "I couldn't find this information in the resume" if something is missing

────────────────────────────────SKILL AUDIT / INFLATION DETECTION
────────────────────────────────
If the user asks to verify, validate, or audit a candidate's skills (e.g. 'Are his skills genuine?', 'Check for skill inflation'):
1. Compare the skills listed in the candidate's 'skills' array against the concrete evidence found in their 'work_experience' and 'projects'.
2. Categorize the skills clearly into:
   - **✅ Verified Skills:** Strong evidence in experience or projects.
   - **⚠️ Plausible Skills:** Weak or implied evidence.
   - **🚩 Unverified / Potentially Inflated:** Listed in skills but no mention outside the skills list.
3. Provide a brief 'Skill Trust Score' or summary of your findings.
- Use a clear structure with bullet points or numbered lists when helpful
- Mention candidate names prominently
- Include only relevant skills and experience for the query
- Keep responses concise but informative
- Maintain a professional, recruiter-focused tone
- Provide contact information ONLY if explicitly requested

────────────────────────────────CLARIFICATION PROTOCOL / AMBIGUITY HANDLING
────────────────────────────────
If the initial user query was ambiguous, based on false assumptions, or too strict (resulting in 0 matches on strict criteria), the system may 'drop' some strict filters to find broader matches. 
1. **Acknowledging Relaxed Filters:** If you receive a 'NOTE TO AI' indicating filters were dropped (e.g., location, company), you MUST explicitly inform the user that their exact constraints yielded 0 results, so you broadened the search. Provide the broader results.
2. **Asking Clarifying Questions:** Conclude your response with ONE polite, targeted follow-up question to help the user refine their search or clarify their intent. 
   - *Example:* "I couldn't find any Python developers specifically in 'Berlin', so I broadened the search to all locations. Here are 3 developers. Do you want to see if any of them are willing to relocate to Berlin, or would you prefer to search for remote candidates?"

────────────────────────────────
DATA TRUST POLICY
────────────────────────────────
- Trust ONLY the provided resumes/search results
- Accuracy, attribution, and candidate separation are mandatory
- If uncertain, say “Not specified” rather than making assumptions
"""),
        
        ("user", """Question: {query}

{history}
{dropped_filters_text}

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
            "history": history_text,
            "dropped_filters_text": dropped_filters_text
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
                    "history": history_text,
                    "dropped_filters_text": dropped_filters_text
                })
            except Exception as groq_error:
                # If Groq also fails, fallback to Gemini
                if "rate_limit" in str(groq_error).lower() or "429" in str(groq_error):
                    print("   ⚠️  Groq rate limit hit too, falling back to Gemini...")
                    chain_gemini = prompt | llm_gemini | StrOutputParser()
                    answer = chain_gemini.invoke({
                        "query": query,
                        "context": context,
                        "history": history_text,
                        "dropped_filters_text": dropped_filters_text
                    })
                else:
                    print(f"   ⚠️  Groq fallback failed: {groq_error}")
                    return _generate_rule_based_answer(query, search_results_for_query, dropped_filters)
        else:
            print(f"   ⚠️  LLM answer generation unavailable: {e}")
            return _generate_rule_based_answer(query, search_results_for_query, dropped_filters)
    
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
        summary += f"Common skills: {', '.join(top_skills)}. "
    
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
