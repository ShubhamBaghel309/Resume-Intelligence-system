from pydantic import BaseModel, Field
from typing import Optional, Annotated

class WorkExperience(BaseModel):
    """single job entry """
    company:str
    role:str
    duration:str
    responsibilities:Optional[list[str]]=None

class Education(BaseModel):
    institute:str
    degree:str
    year:Optional[str]=None

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