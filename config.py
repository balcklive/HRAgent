from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from enum import Enum

class SkillLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

class JobRequirement(BaseModel):
    position: str
    required_skills: List[str]
    preferred_skills: List[str]
    min_years_experience: int
    min_education_level: str
    industry: str
    
class CandidateProfile(BaseModel):
    name: str
    email: str
    phone: str
    education: List[Dict[str, Any]]
    skills: List[Dict[str, Any]]
    experience: List[Dict[str, Any]]
    certifications: List[str]
    languages: List[str]
    
class EvaluationResult(BaseModel):
    candidate_name: str
    overall_score: float
    skill_score: float
    experience_score: float
    education_score: float
    recommendation: str
    strengths: List[str]
    weaknesses: List[str]
    ranking: Optional[int] = None
    
class WorkflowState(BaseModel):
    raw_resume: str
    candidate_profile: Optional[CandidateProfile] = None
    job_requirement: Optional[JobRequirement] = None
    skill_evaluation: Optional[Dict[str, Any]] = None
    experience_evaluation: Optional[Dict[str, Any]] = None
    final_evaluation: Optional[EvaluationResult] = None
    error: Optional[str] = None