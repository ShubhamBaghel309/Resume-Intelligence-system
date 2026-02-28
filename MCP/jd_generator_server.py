# MCP/jd_generator_server.py
"""
Job Description Generator — LOCAL MCP Server (uses OpenAI API).

Generates a professional job description based on role, skills, experience,
and company info. Useful for the Resume Intelligence System to:
  - Create JDs to match candidates against
  - Draft postings after identifying a talent gap
"""

from fastmcp import FastMCP
from typing import Annotated
from pydantic import Field
from openai import OpenAI
from dotenv import load_dotenv
import os
import json

load_dotenv()

mcp = FastMCP("JobDescriptionGenerator")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@mcp.tool()
def generate_job_description(
    job_title: Annotated[str | None, Field(description="Job title (e.g., 'Senior Python Developer', 'ML Engineer')")] = None,
    required_skills: Annotated[str | None, Field(description="Key skills comma-separated (e.g., 'Python, TensorFlow, SQL')")] = None,
    experience_level: Annotated[str | None, Field(description="Experience level (e.g., 'Entry-level', '3-5 years', 'Senior')")] = None,
    company_name: Annotated[str | None, Field(description="Company name (e.g., 'Google', 'Startup XYZ')")] = None,
    location: Annotated[str | None, Field(description="Work location (e.g., 'Remote', 'Bangalore', 'Hybrid - NYC')")] = None,
    tone: Annotated[str, Field(description="Tone: 'formal', 'startup-casual', or 'friendly'")] = "formal",
) -> dict:
    """
    Generate a professional job description using AI.

    Returns a structured JD with sections: overview, responsibilities,
    requirements, nice-to-haves, and benefits.
    """

    # ── Server-side validation ──────────────────────────────────
    missing = []
    if not job_title:
        missing.append("job_title")
    if not required_skills:
        missing.append("required_skills")
    if not experience_level:
        missing.append("experience_level")
    if not company_name:
        missing.append("company_name")
    if not location:
        missing.append("location")

    if missing:
        return {
            "status": "missing_fields",
            "missing_fields": missing,
            "message": f"Missing: {', '.join(missing)}",
        }

    # ── Generate JD via OpenAI ──────────────────────────────────
    prompt = f"""Generate a professional job description with these details:

- Job Title: {job_title}
- Required Skills: {required_skills}
- Experience Level: {experience_level}
- Company: {company_name}
- Location: {location}
- Tone: {tone}

Format the JD with these sections:
1. **Job Overview** (2-3 sentences)
2. **Key Responsibilities** (5-6 bullet points)
3. **Requirements** (5-6 bullet points based on skills and experience)
4. **Nice-to-Have** (3-4 bullet points)
5. **What We Offer** (4-5 bullet points - benefits/perks)

Keep it concise, professional, and engaging. Use markdown formatting."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert HR recruiter who writes compelling job descriptions."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1000,
        )
        jd_text = response.choices[0].message.content.strip()
    except Exception as e:
        return {"status": "error", "message": f"OpenAI API error: {str(e)}"}

    return {
        "status": "success",
        "message": f"Job description generated for {job_title} at {company_name}",
        "job_description": jd_text,
        "metadata": {
            "job_title": job_title,
            "company": company_name,
            "skills": required_skills,
            "experience": experience_level,
            "location": location,
        },
    }


if __name__ == "__main__":
    mcp.run()
