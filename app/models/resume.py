from pydantic import BaseModel, Field
from typing import Optional, Annotated

class WorkExperience(BaseModel):
    """Single job entry"""
    company: str
    role: str
    start_date: Optional[str] = None  # Separate start date
    end_date: Optional[str] = None    # Separate end date  
    duration: Optional[str] = None    # Keep for backward compatibility
    responsibilities: Optional[list[str]] = None

class Education(BaseModel):
    institute: str
    degree: str
    year: Optional[str] = None

class Project(BaseModel):
    """Single project entry"""
    name: str
    description: str
    technologies: Optional[list[str]] = None
    duration: Optional[str] = None
    role: Optional[str] = None  # Role in the project

class ParsedResume(BaseModel):
    candidate_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    
    total_experience_years: Optional[float] = None
    current_role: Optional[str] = None
    
    # More detailed skills
    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)  # For everything else
    
    work_experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)  # NEW