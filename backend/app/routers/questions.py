"""
Questions Router - CRUD for job questions and candidate answers
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import JobQuestion, ApplicationAnswer, Job, Application, User
from app.schemas import (
    QuestionCreate, QuestionResponse, QuestionUpdate,
    AnswerCreate, AnswerResponse, AnswerSubmission,
    JobWithQuestions, QuestionPublicResponse
)
from app.services.auth_utils import get_current_user_required, require_recruiter, require_job_seeker
from app.services.plagiarism import get_plagiarism_checker, PlagiarismChecker
from app.services.ai_detection import get_ai_content_detector, AIContentDetector
from app.services.integrity_review import (
    analyze_answer_integrity,
    store_integrity_result,
)
from app.services.audit_logger import AuditLogger

router = APIRouter()
logger = logging.getLogger(__name__)


def _ensure_job_owner(job: Job, current_user: User):
    if job.recruiter_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot manage questions for this job")


def _ensure_application_access(application: Application, current_user: User):
    if current_user.user_type == "recruiter":
        _ensure_job_owner(application.job, current_user)
    elif application.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access these answers")


# ============== Questions CRUD ==============

@router.post("/", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
def create_question(
    question: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """Create a new question for a job"""
    # Verify job exists
    job = db.query(Job).filter(Job.job_id == question.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _ensure_job_owner(job, current_user)
    
    db_question = JobQuestion(
        job_id=question.job_id,
        question_text=question.question_text,
        question_type=question.question_type,
        options=question.options,
        correct_answer=question.correct_answer,
        points=question.points,
        order=question.order,
        is_required=question.is_required
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    AuditLogger.log(
        db, action="question_create", user_id=current_user.user_id,
        resource_type="job_question", resource_id=db_question.question_id,
        details={"job_id": job.job_id, "question_type": db_question.question_type},
    )
    return db_question


@router.get("/job/{job_id}", response_model=List[QuestionPublicResponse])
def get_questions_for_job(job_id: int, db: Session = Depends(get_db)):
    """Get all questions for a specific job"""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    questions = db.query(JobQuestion).filter(
        JobQuestion.job_id == job_id
    ).order_by(JobQuestion.order).all()
    return questions


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """Get a specific question"""
    question = db.query(JobQuestion).filter(
        JobQuestion.question_id == question_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    _ensure_job_owner(question.job, current_user)
    return question


@router.put("/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: int,
    question_update: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """Update a question"""
    question = db.query(JobQuestion).filter(
        JobQuestion.question_id == question_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    _ensure_job_owner(question.job, current_user)
    
    update_data = question_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(question, key, value)
    
    db.commit()
    db.refresh(question)
    AuditLogger.log(
        db, action="question_update", user_id=current_user.user_id,
        resource_type="job_question", resource_id=question.question_id,
        details={"updated_fields": sorted(update_data)},
    )
    return question


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """Delete a question"""
    question = db.query(JobQuestion).filter(
        JobQuestion.question_id == question_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    _ensure_job_owner(question.job, current_user)
    
    db.delete(question)
    db.commit()
    AuditLogger.log(
        db, action="question_delete", user_id=current_user.user_id,
        resource_type="job_question", resource_id=question_id,
    )
    return None


@router.post("/bulk/{job_id}", response_model=List[QuestionResponse], status_code=status.HTTP_201_CREATED)
def create_bulk_questions(
    job_id: int,
    questions: List[QuestionCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """Create multiple questions for a job at once"""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _ensure_job_owner(job, current_user)
    
    created_questions = []
    for i, q in enumerate(questions):
        db_question = JobQuestion(
            job_id=job_id,
            question_text=q.question_text,
            question_type=q.question_type,
            options=q.options,
            correct_answer=q.correct_answer,
            points=q.points,
            order=q.order if q.order else i,
            is_required=q.is_required
        )
        db.add(db_question)
        created_questions.append(db_question)
    
    db.commit()
    for q in created_questions:
        db.refresh(q)

    AuditLogger.log(
        db, action="question_bulk_create", user_id=current_user.user_id,
        resource_type="job", resource_id=job_id,
        details={"count": len(created_questions)},
    )
    
    return created_questions


# ============== Answers ==============

@router.post("/answers/{application_id}", response_model=List[AnswerResponse], status_code=status.HTTP_201_CREATED)
async def submit_answers(
    application_id: int,
    submission: AnswerSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_job_seeker),
    checker: PlagiarismChecker = Depends(get_plagiarism_checker),
    ai_detector: AIContentDetector = Depends(get_ai_content_detector),
):
    """Submit answers for an application"""
    application = db.query(Application).filter(
        Application.application_id == application_id
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    _ensure_application_access(application, current_user)
    if application.status != "shortlisted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The skill test is available after the recruiter shortlists your application",
        )
    
    created_answers = []
    submitted_answers = []
    total_score = 0
    max_score = 0
    
    for answer in submission.answers:
        # Get the question
        question = db.query(JobQuestion).filter(
            JobQuestion.question_id == answer.question_id
        ).first()
        if not question:
            raise HTTPException(
                status_code=404, 
                detail=f"Question {answer.question_id} not found"
            )
        if question.job_id != application.job_id:
            raise HTTPException(status_code=400, detail=f"Question {answer.question_id} does not belong to this application")
        
        # Check for duplicate answer
        existing = db.query(ApplicationAnswer).filter(
            ApplicationAnswer.application_id == application_id,
            ApplicationAnswer.question_id == answer.question_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Already answered question {answer.question_id}"
            )
        
        # Auto-grade if correct answer exists
        is_correct = None
        score = None
        if question.correct_answer:
            is_correct = answer.answer_text.strip().lower() == question.correct_answer.strip().lower()
            score = question.points if is_correct else 0
            total_score += score
        max_score += question.points
        
        db_answer = ApplicationAnswer(
            application_id=application_id,
            question_id=answer.question_id,
            answer_text=answer.answer_text,
            is_correct=is_correct,
            score=score
        )
        db.add(db_answer)
        created_answers.append(db_answer)
        submitted_answers.append({
            "question": question.question_text,
            "question_type": question.question_type,
            "answer": answer.answer_text,
        })
    
    # Update application test score
    if max_score > 0:
        application.test_score = int((total_score / max_score) * 100)

    db.commit()
    for a in created_answers:
        db.refresh(a)

    # Persist grades first so provider failures never discard a candidate's answers.
    try:
        all_answers = list(application.screening_answers or []) + submitted_answers
        existing_ai_assessment = (
            (application.match_details or {}).get("benchmarks", {})
            .get("screening_questions", {})
            .get("originality_assessment")
        )
        report = await analyze_answer_integrity(
            all_answers, checker, ai_detector, existing_ai_assessment=existing_ai_assessment
        )
        store_integrity_result(application, report)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Integrity analysis could not be saved: %s", type(exc).__name__)

    for a in created_answers:
        db.refresh(a)
    
    return created_answers


@router.get("/answers/{application_id}", response_model=List[AnswerResponse])
def get_answers(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """Get all answers for an application"""
    application = db.query(Application).filter(
        Application.application_id == application_id
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    _ensure_application_access(application, current_user)
    
    answers = db.query(ApplicationAnswer).filter(
        ApplicationAnswer.application_id == application_id
    ).all()
    return answers
