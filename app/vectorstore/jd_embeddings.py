from typing import Dict, List

from app.models.jd import JobDescription


def _join_lines(values: list[str]) -> str:
    cleaned = [v.strip() for v in values if v and v.strip()]
    return "\n".join(f"- {v}" for v in cleaned)


def create_jd_chunks(jd: JobDescription) -> List[Dict[str, object]]:
    """
    Create focused chunks for JD retrieval.

    Strategy:
    1. Summary chunk
    2. Requirements chunk
    3. Responsibilities chunk
    4. Company/benefits chunk
    """
    chunks: List[Dict[str, object]] = []

    summary_parts = [f"Job Title: {jd.job_title}"]
    if jd.job_level:
        summary_parts.append(f"Level: {jd.job_level}")
    if jd.department:
        summary_parts.append(f"Department: {jd.department}")
    if jd.location:
        summary_parts.append(f"Location: {jd.location}")
    if jd.role_summary:
        summary_parts.append(f"Role Summary: {jd.role_summary}")

    chunks.append(
        {
            "type": "summary",
            "text": "\n".join(summary_parts),
            "metadata": {
                "chunk_type": "summary",
                "jd_id": jd.jd_id,
                "job_title": jd.job_title,
                "location": jd.location or "Not specified",
            },
        }
    )

    requirements_text = []
    if jd.required_skills:
        requirements_text.append("Required Skills:\n" + _join_lines(jd.required_skills))
    if jd.nice_to_have_skills:
        requirements_text.append("Nice to Have Skills:\n" + _join_lines(jd.nice_to_have_skills))

    if requirements_text:
        chunks.append(
            {
                "type": "requirements",
                "text": "\n\n".join(requirements_text),
                "metadata": {
                    "chunk_type": "requirements",
                    "jd_id": jd.jd_id,
                    "job_title": jd.job_title,
                    "num_required_skills": len(jd.required_skills),
                    "num_nice_to_have_skills": len(jd.nice_to_have_skills),
                },
            }
        )

    if jd.responsibilities:
        chunks.append(
            {
                "type": "responsibilities",
                "text": "Responsibilities:\n" + _join_lines(jd.responsibilities),
                "metadata": {
                    "chunk_type": "responsibilities",
                    "jd_id": jd.jd_id,
                    "job_title": jd.job_title,
                },
            }
        )

    culture_parts = []
    if jd.company_overview:
        culture_parts.append(f"Company Overview: {jd.company_overview}")
    if jd.benefits:
        culture_parts.append("Benefits:\n" + _join_lines(jd.benefits))
    if jd.posting_date:
        culture_parts.append(f"Posting Date: {jd.posting_date}")
    if jd.status:
        culture_parts.append(f"Status: {jd.status}")

    if culture_parts:
        chunks.append(
            {
                "type": "company_context",
                "text": "\n\n".join(culture_parts),
                "metadata": {
                    "chunk_type": "company_context",
                    "jd_id": jd.jd_id,
                    "job_title": jd.job_title,
                },
            }
        )

    if not chunks:
        chunks.append(
            {
                "type": "full_jd",
                "text": jd.original_text or "",
                "metadata": {
                    "chunk_type": "full_jd",
                    "jd_id": jd.jd_id,
                    "job_title": jd.job_title,
                },
            }
        )

    return chunks


def create_jd_metadata(jd: JobDescription, document_id: str) -> Dict[str, object]:
    """Create JD-level metadata that applies to all chunks."""
    return {
        "document_id": document_id or "",
        "jd_id": jd.jd_id,
        "job_title": jd.job_title,
        "job_level": jd.job_level or "Not specified",
        "department": jd.department or "Not specified",
        "location": jd.location or "Not specified",
        "status": jd.status or "open",
        "num_required_skills": len(jd.required_skills),
        "num_nice_to_have_skills": len(jd.nice_to_have_skills),
    }
