from pydantic import BaseModel, Field
from typing import Optional


class SalaryRange(BaseModel):
    """Optional compensation information for a job description."""

    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    currency: Optional[str] = None
    period: Optional[str] = None  # yearly, monthly, hourly


class JobDescription(BaseModel):
    """Structured representation of a job description."""

    jd_id: str
    job_title: str
    job_level: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None

    role_summary: Optional[str] = None
    company_overview: Optional[str] = None

    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)

    benefits: list[str] = Field(default_factory=list)
    salary_range: Optional[SalaryRange] = None

    posting_date: Optional[str] = None
    status: str = "open"

    original_text: Optional[str] = None
