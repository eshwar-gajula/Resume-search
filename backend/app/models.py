"""
Database Models - 6 Tables: users_data, jobs_data, applications, job_questions, application_answers, audit_logs
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, 
    ForeignKey, DateTime, JSON, Numeric, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """Candidate/User table"""
    __tablename__ = "users_data"
    
    user_id = Column(Integer, primary_key=True, index=True)
    user_type = Column(String(20), default="job_seeker")  # "recruiter" or "job_seeker"
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    mobile = Column(String(20))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    resume_path = Column(String(500))
    resume_parsed = Column(JSON)  # LLM-extracted structured data
    has_experience = Column(Boolean, default=False)
    years_of_experience = Column(Integer, default=0)
    graduation_year = Column(Integer)
    notice_period = Column(Integer)  # in days
    gender = Column(String(20))
    country = Column(String(100))
    preferred_location = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    applications = relationship("Application", back_populates="user")


class Job(Base):
    """Job posting table"""
    __tablename__ = "jobs_data"
    
    job_id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("users_data.user_id"), nullable=True)  # Job owner
    job_location = Column(String(255))
    job_country = Column(String(100))
    role = Column(String(255), nullable=False)
    responsibilities = Column(Text)
    years_of_experience = Column(Integer, default=0)
    skills = Column(JSON)  # List of required skills
    description = Column(Text)
    highest_education_qualification = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    recruiter = relationship("User", foreign_keys=[recruiter_id])
    applications = relationship("Application", back_populates="job")
    questions = relationship("JobQuestion", back_populates="job", cascade="all, delete-orphan")


class Application(Base):
    """Job application table"""
    __tablename__ = "applications"
    
    application_id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs_data.job_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users_data.user_id"), nullable=False)
    
    # Screening & Scores
    screening_answers = Column(JSON)  # Application-time answers: [{question, answer, question_id, question_type}]
    test_score = Column(Integer)  # Optional auto-graded score
    match_score = Column(Numeric(5, 2))  # LLM matching score 0-100
    match_details = Column(JSON)  # Full LLM analysis with benchmarks
    
    # Plagiarism
    passed_plagiarism = Column(Boolean)
    plagiarism_score = Column(Numeric(5, 2))  # e.g., 25.50%
    
    # Status
    status = Column(String(50), default="pending")  # pending, shortlisted, accepted, flagged, rejected, legacy review
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    
    # Prevent duplicate applications
    __table_args__ = (
        UniqueConstraint('job_id', 'user_id', name='unique_application'),
    )


class JobQuestion(Base):
    """Skill test questions for a job"""
    __tablename__ = "job_questions"
    
    question_id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs_data.job_id"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), default="text")  # text, multiple_choice, code
    options = Column(JSON)  # For multiple choice: ["option1", "option2", ...]
    correct_answer = Column(Text)  # Optional: for auto-grading
    points = Column(Integer, default=10)  # Points for this question
    order = Column(Integer, default=0)  # Display order
    is_required = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    job = relationship("Job", back_populates="questions")
    answers = relationship("ApplicationAnswer", back_populates="question", cascade="all, delete-orphan")


class ApplicationAnswer(Base):
    """Candidate answers to post-application skill tests.

    Application-time screening answers are stored in applications.screening_answers.
    """
    __tablename__ = "application_answers"
    
    answer_id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.application_id"), nullable=False)
    question_id = Column(Integer, ForeignKey("job_questions.question_id"), nullable=False)
    answer_text = Column(Text)
    is_correct = Column(Boolean)  # For auto-graded questions
    score = Column(Integer)  # Points earned for this answer
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Skill-test answers are queried by application_id; inline screening answers use the JSON column above.
    question = relationship("JobQuestion", back_populates="answers")
    
    # Prevent duplicate answers
    __table_args__ = (
        UniqueConstraint('application_id', 'question_id', name='unique_answer'),
    )


class AuditLog(Base):
    """Audit log for tracking user actions"""
    __tablename__ = "audit_logs"
    
    log_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users_data.user_id"), nullable=True)
    action = Column(String(50), nullable=False, index=True)  # login, apply, status_change, resume_upload
    resource_type = Column(String(50))  # application, job, user
    resource_id = Column(Integer)
    details = Column(JSON)  # Additional context
    ip_address = Column(String(45))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
