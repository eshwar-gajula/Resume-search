"""
Pydantic Schemas for API request/response validation
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any, Literal
from datetime import datetime
from enum import Enum


# ============== Auth Schemas ==============

class UserType(str, Enum):
    recruiter = "recruiter"
    job_seeker = "job_seeker"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenData(BaseModel):
    user_id: int
    email: str
    user_type: str


# ============== User Schemas ==============


class UserBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    user_type: UserType = UserType.job_seeker
    mobile: Optional[str] = None
    has_experience: Optional[bool] = False
    years_of_experience: Optional[int] = 0
    graduation_year: Optional[int] = None
    notice_period: Optional[int] = None
    gender: Optional[str] = None
    country: Optional[str] = None
    preferred_location: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)


class UserResponse(UserBase):
    user_id: int
    resume_path: Optional[str] = None
    resume_parsed: Optional[dict] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    mobile: Optional[str] = None
    has_experience: Optional[bool] = None
    years_of_experience: Optional[int] = None
    graduation_year: Optional[int] = None
    notice_period: Optional[int] = None
    gender: Optional[str] = None
    country: Optional[str] = None
    preferred_location: Optional[str] = None


# ============== Job Schemas ==============

class JobBase(BaseModel):
    role: str
    job_location: Optional[str] = None
    job_country: Optional[str] = None
    responsibilities: Optional[str] = None
    years_of_experience: Optional[int] = 0
    skills: Optional[List[str]] = []
    description: Optional[str] = None
    highest_education_qualification: Optional[str] = None


class JobCreate(JobBase):
    pass


class JobResponse(JobBase):
    job_id: int
    recruiter_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class ApplicationJobResponse(JobResponse):
    """Job details embedded in applications, including test availability."""
    has_questions: bool = False


class JobUpdate(BaseModel):
    role: Optional[str] = None
    job_location: Optional[str] = None
    job_country: Optional[str] = None
    responsibilities: Optional[str] = None
    years_of_experience: Optional[int] = None
    skills: Optional[List[str]] = None
    description: Optional[str] = None
    highest_education_qualification: Optional[str] = None
    is_active: Optional[bool] = None


# ============== Application Schemas ==============

class ScreeningAnswer(BaseModel):
    """Single screening question answer"""
    question_id: int = Field(gt=0)
    question: str = Field(max_length=1000)
    answer: str = Field(max_length=20000)


class ApplicationCreate(BaseModel):
    job_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    screening_answers: Optional[List[ScreeningAnswer]] = Field(default=None, max_length=100)


class ApplicationResponse(BaseModel):
    application_id: int
    job_id: int
    user_id: int
    screening_answers: Optional[List[dict]] = None  # [{question_id, question, answer}]
    test_score: Optional[int] = None
    match_score: Optional[float] = None
    match_details: Optional[dict] = None  # Full LLM analysis with benchmarks
    passed_plagiarism: Optional[bool] = None
    plagiarism_score: Optional[float] = None
    status: str
    applied_at: datetime
    resume_required: bool = False
    
    class Config:
        from_attributes = True


class ApplicationCandidateView(BaseModel):
    """Applicant data returned to recruiters, anonymized unless explicitly revealed."""
    user_id: int
    display_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    years_of_experience: Optional[int] = None
    graduation_year: Optional[int] = None
    country: Optional[str] = None
    preferred_location: Optional[str] = None
    resume_parsed: Optional[dict] = None
    has_resume: bool = False

    class Config:
        from_attributes = True


class ApplicationWithDetails(ApplicationResponse):
    user: Optional[ApplicationCandidateView] = None
    job: Optional[ApplicationJobResponse] = None
    test_answers: Optional[List[dict]] = None
    revealed_pii: bool = False


# ============== Resume Parsed Schema ==============

class ParsedEducation(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    year: Optional[int] = None
    field: Optional[str] = None


class ParsedExperience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None


class ParsedResume(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: Optional[List[str]] = []
    education: Optional[List[ParsedEducation]] = []
    experience: Optional[List[ParsedExperience]] = []
    certifications: Optional[List[str]] = []
    summary: Optional[str] = None


# ============== LLM Response Schemas ==============

class MatchResult(BaseModel):
    match_score: float
    reasoning: str
    matched_skills: List[str]
    missing_skills: List[str]


# ============== Search Schemas ==============

class CandidateSearchRequest(BaseModel):
    job_id: Optional[int] = None
    query: Optional[str] = Field(default=None, max_length=600)
    skills: Optional[List[str]] = None
    min_experience: Optional[int] = Field(default=None, ge=0, le=80)
    max_experience: Optional[int] = Field(default=None, ge=0, le=80)
    min_match_score: Optional[float] = Field(default=None, ge=0, le=100)
    location: Optional[str] = Field(default=None, max_length=255)
    status: Optional[Literal["pending", "shortlisted", "accepted", "rejected"]] = None


class BulkApplicationAction(BaseModel):
    application_ids: List[int] = Field(min_length=1, max_length=100)
    action: Literal["shortlist"]


# ============== Question Schemas ==============

class QuestionBase(BaseModel):
    question_text: str
    question_type: Optional[str] = "text"  # text, multiple_choice, code
    options: Optional[List[str]] = None  # For multiple choice
    correct_answer: Optional[str] = None
    points: Optional[int] = 10
    order: Optional[int] = 0
    is_required: Optional[bool] = True


class QuestionCreate(QuestionBase):
    job_id: int


class QuestionResponse(QuestionBase):
    question_id: int
    job_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class QuestionPublicResponse(BaseModel):
    """Question fields visible to candidates; never expose grading answers."""
    question_id: int
    job_id: int
    question_text: str
    question_type: Optional[str] = "text"
    options: Optional[List[str]] = None
    points: Optional[int] = 10
    order: Optional[int] = 0
    is_required: Optional[bool] = True
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    points: Optional[int] = None
    order: Optional[int] = None
    is_required: Optional[bool] = None


# ============== Answer Schemas ==============

class AnswerBase(BaseModel):
    answer_text: str


class AnswerCreate(AnswerBase):
    question_id: int = Field(gt=0)


class AnswerResponse(AnswerBase):
    answer_id: int
    application_id: int
    question_id: int
    is_correct: Optional[bool] = None
    score: Optional[int] = None
    submitted_at: datetime
    
    class Config:
        from_attributes = True


class AnswerSubmission(BaseModel):
    """For submitting multiple answers at once"""
    answers: List[AnswerCreate]


# ============== Job with Questions ==============

class JobWithQuestions(JobResponse):
    questions: List[QuestionResponse] = []
