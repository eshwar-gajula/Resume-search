"""
Applications Router - Job applications, matching, and plagiarism check
"""
import csv
import io
import logging
import math
from pathlib import Path
import re
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Application, ApplicationAnswer, User, Job, JobQuestion
from app.schemas import (
    ApplicationCreate, ApplicationResponse, ApplicationWithDetails, JobResponse,
    CandidateSearchRequest, BulkApplicationAction
)
from app.services.llm_provider import get_llm, LLMProvider
from app.services.plagiarism import get_plagiarism_checker, PlagiarismChecker
from app.services.ai_detection import get_ai_content_detector, AIContentDetector
from app.services.integrity_review import (
    analyze_answer_integrity,
    attach_match_originality,
    store_integrity_result,
)
from app.services.auth_utils import require_recruiter, require_job_seeker, get_current_user_required
from app.services.email_service import get_email_service, EmailService
from app.services.audit_logger import AuditLogger
from app.services.resume_parser import get_resume_parser, ResumeParser
from app.services.integrity_review import integrity_routing_decision
from app.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _serialize_test_answers(db: Session, application: Application) -> List[dict]:
    """Return submitted skill-test answers, falling back to inline application answers."""
    records = (
        db.query(ApplicationAnswer)
        .filter(ApplicationAnswer.application_id == application.application_id)
        .order_by(ApplicationAnswer.answer_id)
        .all()
    )
    serialized = [
            {
                "question_id": record.question_id,
                "question": record.question.question_text if record.question else "",
                "question_type": record.question.question_type if record.question else "text",
                "answer_text": record.answer_text or "",
                "is_correct": record.is_correct,
                "score": record.score,
                "source": "skill_test",
            }
            for record in records
    ]

    seen = {(item["question_id"], item["answer_text"]) for item in serialized}
    for answer in application.screening_answers or []:
        answer_text = answer.get("answer", "")
        key = (answer.get("question_id"), answer_text)
        if key in seen:
            continue
        serialized.append({
            "question_id": answer.get("question_id"),
            "question": answer.get("question", ""),
            "question_type": answer.get("question_type", "text"),
            "answer_text": answer_text,
            "is_correct": None,
            "score": None,
            "source": "application_screening",
        })
        seen.add(key)
    return serialized


def _serialize_application_job(db: Session, job: Optional[Job]) -> Optional[dict]:
    """Add test availability to the job embedded in an application response."""
    if job is None:
        return None
    result = JobResponse.model_validate(job).model_dump()
    result["has_questions"] = db.query(JobQuestion.question_id).filter(
        JobQuestion.job_id == job.job_id
    ).first() is not None
    return result


def check_application_ownership(app: Application, current_user: User):
    """Check if application's job belongs to current recruiter, raise 403 if not"""
    job = app.job
    if job.recruiter_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to manage this application"
        )


def _candidate_visible_status(app_status: str) -> str:
    """Keep recruiter-only review flags out of candidate responses."""
    return "pending" if app_status in {"flagged", "review"} else app_status


def _resume_is_ready(user: User) -> bool:
    parsed = user.resume_parsed or {}
    return bool(user.resume_path and parsed and not parsed.get("error"))


def _resume_for_matching(parsed: dict) -> dict:
    """Strip direct identifiers from legacy parsed resumes before sending them to an LLM."""
    direct_identifiers = {"name", "email", "phone", "mobile", "address", "social_links", "linkedin", "github", "institution", "school", "university", "company", "employer"}
    cleaned = {}
    for key, value in (parsed or {}).items():
        if key.casefold() in direct_identifiers:
            continue
        if key in {"education", "experience"} and isinstance(value, list):
            cleaned[key] = [
                {field: item for field, item in entry.items() if field.casefold() not in direct_identifiers}
                if isinstance(entry, dict) else entry
                for entry in value
            ]
        else:
            cleaned[key] = value
    return cleaned


def _resume_required(app: Application) -> bool:
    if app.status in {"flagged", "review", "rejected"}:
        return False
    return not bool(app.user.resume_path)


def _application_user_view(app: Application, *, reveal_pii: bool) -> dict:
    user = app.user
    parsed = user.resume_parsed or {}
    if reveal_pii:
        safe_parsed = parsed
        first_name, last_name, email, mobile = user.first_name, user.last_name, user.email, user.mobile
        display_name = f"{user.first_name} {user.last_name}".strip()
    else:
        # Keep resume content useful for evaluation while dropping direct identifiers and links.
        allowed_resume_fields = {"skills", "education", "experience", "certifications", "projects", "summary"}
        safe_parsed = _resume_for_matching({key: value for key, value in parsed.items() if key in allowed_resume_fields})
        first_name = last_name = email = mobile = None
        display_name = f"Candidate #{app.application_id}"

    return {
        "user_id": user.user_id,
        "display_name": display_name,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "mobile": mobile,
        "years_of_experience": user.years_of_experience,
        "graduation_year": user.graduation_year,
        "country": user.country if reveal_pii else None,
        "preferred_location": user.preferred_location if reveal_pii else None,
        "resume_parsed": safe_parsed or None,
        "has_resume": bool(user.resume_path),
    }


def _serialize_application(
    db: Session,
    app: Application,
    *,
    recruiter_view: bool,
    reveal_pii: bool = False,
) -> dict:
    can_reveal = recruiter_view and reveal_pii
    return {
        "application_id": app.application_id,
        "job_id": app.job_id,
        "user_id": app.user_id,
        "screening_answers": app.screening_answers,
        "test_score": app.test_score,
        "match_score": float(app.match_score) if app.match_score is not None and (recruiter_view or app.status != "flagged") else None,
        "match_details": app.match_details if recruiter_view else None,
        "passed_plagiarism": app.passed_plagiarism if recruiter_view else None,
        "plagiarism_score": float(app.plagiarism_score) if recruiter_view and app.plagiarism_score is not None else None,
        "status": app.status if recruiter_view else _candidate_visible_status(app.status),
        "applied_at": app.applied_at,
        "resume_required": _resume_required(app),
        "revealed_pii": can_reveal,
        "user": _application_user_view(app, reveal_pii=can_reveal or not recruiter_view),
        "job": _serialize_application_job(db, app.job),
        "test_answers": _serialize_test_answers(db, app),
    }


def _match_originality_score(match_details: Optional[dict]) -> Optional[float]:
    """Return a valid match originality score, or None when no score was produced."""
    assessment = (
        (match_details or {}).get("benchmarks", {})
        .get("screening_questions", {})
        .get("originality_assessment", {})
    )
    if not isinstance(assessment, dict):
        return None
    try:
        score = float(assessment.get("originality_score"))
    except (TypeError, ValueError):
        return None
    return score if math.isfinite(score) and 0 <= score <= 100 else None


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    application: ApplicationCreate,
    db: Session = Depends(get_db),
    llm: LLMProvider = Depends(get_llm),
    checker: PlagiarismChecker = Depends(get_plagiarism_checker),
    ai_detector: AIContentDetector = Depends(get_ai_content_detector),
    email_service: EmailService = Depends(get_email_service),
    current_user: User = Depends(require_job_seeker),
):
    """Run the screening and integrity review before matching or requesting a resume."""
    if application.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only apply for yourself")

    user = db.query(User).filter(User.user_id == application.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    job = db.query(Job).filter(Job.job_id == application.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.is_active:
        raise HTTPException(status_code=400, detail="This job is no longer accepting applications")

    existing = db.query(Application).filter(
        Application.job_id == application.job_id,
        Application.user_id == application.user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already applied to this job")

    questions = db.query(JobQuestion).filter(JobQuestion.job_id == job.job_id).all()
    answers_by_id = {answer.question_id: answer for answer in application.screening_answers or []}
    if len(answers_by_id) != len(application.screening_answers or []):
        raise HTTPException(status_code=400, detail="A screening question was answered more than once")

    required_ids = {question.question_id for question in questions if question.is_required}
    missing_ids = required_ids - set(answers_by_id)
    if missing_ids:
        raise HTTPException(status_code=400, detail="Please answer all required screening questions before applying")

    screening_answers_json = []
    screening_for_llm = []
    total_answer_characters = 0
    question_by_id = {question.question_id: question for question in questions}
    for answer in application.screening_answers or []:
        question = question_by_id.get(answer.question_id)
        if question is None:
            raise HTTPException(status_code=400, detail="A screening answer does not belong to this job")
        answer_text = answer.answer.strip()
        total_answer_characters += len(answer_text)
        if len(answer_text) > 20000 or total_answer_characters > 30000:
            raise HTTPException(status_code=413, detail="Screening answers exceed the allowed text length")
        if question.question_type == "multiple_choice" and question.options and answer_text not in question.options:
            raise HTTPException(status_code=400, detail="A screening answer is not one of the listed choices")
        if question.is_required and not answer_text:
            raise HTTPException(status_code=400, detail="Please answer all required screening questions before applying")
        screening_answers_json.append({
            "question_id": question.question_id,
            "question": question.question_text,
            "question_type": question.question_type or "text",
            "answer": answer_text,
        })
        screening_for_llm.append({"question": question.question_text, "answer": answer_text})

    db_application = Application(
        job_id=application.job_id,
        user_id=application.user_id,
        screening_answers=screening_answers_json or None,
        status="pending",
    )
    db.add(db_application)
    db.commit()
    db.refresh(db_application)

    if screening_answers_json:
        try:
            report = await analyze_answer_integrity(
                screening_answers_json,
                checker,
                ai_detector,
            )
            store_integrity_result(db_application, report)
            routing = report.get("routing") or integrity_routing_decision(report)
            if routing.get("decision") != "cleared":
                db_application.status = "flagged"
        except Exception as exc:
            logger.warning("Application integrity review failed: %s", type(exc).__name__)
            db_application.status = "flagged"
            details = dict(db_application.match_details or {})
            details["skill_test_integrity"] = {
                "checked_at": None,
                "ai_detection": {"status": "unavailable", "verdict": "unknown", "summary": "The AI detector could not complete the check."},
                "web_similarity": {"status": "unavailable", "score": None, "passed": None, "summary": "The web-similarity check could not complete."},
                "routing": {"decision": "manual_review", "reasons": ["integrity_check_unavailable"]},
                "notice": "Automated indicators are not proof; recruiter review is required.",
            }
            db_application.match_details = details
        db.commit()
        db.refresh(db_application)

    # Only after the integrity gate clears may the resume be used for matching.
    if db_application.status != "flagged" and _resume_is_ready(user):
        try:
            match_result = await llm.match_candidate(
                job_description=f"{job.description or ''} {job.responsibilities or ''}",
                job_skills=job.skills or [],
                candidate_resume=_resume_for_matching(user.resume_parsed),
                screening_questions=screening_for_llm or None,
            )
            details = dict(match_result or {})
            if db_application.match_details and db_application.match_details.get("skill_test_integrity"):
                assessment = details.get("benchmarks", {}).get("screening_questions", {}).get("originality_assessment")
                details["skill_test_integrity"] = attach_match_originality(
                    db_application.match_details["skill_test_integrity"], assessment
                )
            db_application.match_score = details.get("match_score")
            db_application.match_details = details
            originality_score = _match_originality_score(details)
            if originality_score is not None and originality_score < 40:
                db_application.status = "flagged"
        except Exception as exc:
            logger.warning("AI match calculation was skipped: %s", type(exc).__name__)

    db.commit()
    db.refresh(db_application)

    await email_service.send_application_submitted(
        applicant_email=user.email,
        applicant_name=f"{user.first_name} {user.last_name}",
        job_title=job.role,
        company_name=None,
    )

    AuditLogger.log(
        db=db,
        action="apply",
        user_id=application.user_id,
        resource_type="application",
        resource_id=db_application.application_id,
        details={"job_id": application.job_id, "job_title": job.role, "screening_completed": bool(screening_answers_json)},
    )

    return {
        "application_id": db_application.application_id,
        "job_id": db_application.job_id,
        "user_id": db_application.user_id,
        "screening_answers": db_application.screening_answers,
        "test_score": db_application.test_score,
        "match_score": float(db_application.match_score) if db_application.match_score is not None and db_application.status != "flagged" else None,
        "match_details": None,
        "passed_plagiarism": None,
        "plagiarism_score": None,
        "status": _candidate_visible_status(db_application.status),
        "applied_at": db_application.applied_at,
        "resume_required": _resume_required(db_application),
    }


@router.get("/", response_model=List[ApplicationWithDetails])
async def list_applications(
    job_id: Optional[int] = None,
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    List applications with optional filters.
    - Job seekers: Can only see their own applications (user_id filter enforced)
    - Recruiters: Can only see applications for their own jobs
    """
    query = db.query(Application)
    
    is_recruiter = current_user.user_type == "recruiter"
    if is_recruiter:
        # Recruiters see only applications for jobs they own
        query = query.join(Job).filter(Job.recruiter_id == current_user.user_id)
    else:
        # Job seekers can only see their own applications
        query = query.filter(Application.user_id == current_user.user_id)
    
    if job_id:
        query = query.filter(Application.job_id == job_id)
    
    # For job seekers, ignore user_id param (already filtered above)
    # For recruiters, allow filtering by specific user
    if user_id and current_user.user_type == "recruiter":
        query = query.filter(Application.user_id == user_id)
    
    if status:
        query = query.filter(Application.status == status)
    
    applications = query.offset(skip).limit(limit).all()
    
    # Load relationships
    return [
        _serialize_application(db, app, recruiter_view=is_recruiter)
        for app in applications
    ]


@router.get("/review", response_model=List[ApplicationWithDetails])
def get_applications_for_review(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)
):
    """Get applications flagged for plagiarism review (Recruiter only, filtered by their jobs)"""
    applications = db.query(Application).join(Job).filter(
        Application.status == "review",
        Job.recruiter_id == current_user.user_id
    ).all()
    
    return [_serialize_application(db, app, recruiter_view=True) for app in applications]


@router.get("/export")
def export_candidates_csv(
    job_id: Optional[int] = None,
    application_ids: Optional[List[int]] = Query(default=None),
    reveal_pii: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """Export owned, non-flagged applications; identity is omitted unless explicitly requested."""
    query = db.query(Application).join(Job).filter(
        Job.recruiter_id == current_user.user_id,
        Application.status.notin_(["flagged", "review"]),
    )
    if job_id is not None:
        query = query.filter(Application.job_id == job_id)
    if application_ids:
        if len(application_ids) > 500:
            raise HTTPException(status_code=400, detail="Export is limited to 500 selected applications")
        query = query.filter(Application.application_id.in_(set(application_ids)))
    applications = query.order_by(Application.applied_at.desc()).limit(500).all()
    if application_ids and {app.application_id for app in applications} != set(application_ids):
        raise HTTPException(status_code=404, detail="One or more selected applications are unavailable")

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    columns = ["application_id", "candidate", "job", "status", "match_score", "years_experience", "skills", "applied_at"]
    if reveal_pii:
        columns[1:1] = ["name", "email", "location"]
    writer.writerow(columns)

    def safe_cell(value):
        value = "" if value is None else str(value)
        return "'" + value if value.startswith(("=", "+", "-", "@")) else value

    for app in applications:
        skills = (app.user.resume_parsed or {}).get("skills") or []
        row = [
            app.application_id,
            f"Candidate #{app.application_id}",
            app.job.role,
            app.status,
            float(app.match_score) if app.match_score is not None else "",
            app.user.years_of_experience or 0,
            ", ".join(str(skill) for skill in skills if skill),
            app.applied_at.isoformat() if app.applied_at else "",
        ]
        if reveal_pii:
            row[1:1] = [
                f"{app.user.first_name} {app.user.last_name}".strip(),
                app.user.email,
                app.user.preferred_location or app.user.country or "",
            ]
        writer.writerow([safe_cell(value) for value in row])

    if reveal_pii:
        AuditLogger.log(
            db=db,
            action="candidate_export_identity_revealed",
            user_id=current_user.user_id,
            resource_type="job" if job_id else "application_export",
            resource_id=job_id,
            details={"application_count": len(applications)},
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="resumeai-candidates.csv"'},
    )


# ============== Flagged Applications (must be before /{application_id} routes) ==============

@router.get("/flagged", response_model=List[ApplicationWithDetails])
def get_flagged_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)
):
    """Get all flagged applications requiring manual review (Recruiter only, filtered by their jobs)"""
    applications = db.query(Application).join(Job).filter(
        Application.status == "flagged",
        Job.recruiter_id == current_user.user_id
    ).order_by(Application.applied_at.desc()).all()
    
    return [_serialize_application(db, app, recruiter_view=True) for app in applications]


@router.get("/{application_id}", response_model=ApplicationWithDetails)
def get_application(
    application_id: int,
    reveal_pii: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """Get a specific application with details"""
    app = db.query(Application).filter(
        Application.application_id == application_id
    ).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    is_recruiter = current_user.user_type == "recruiter"
    if is_recruiter:
        check_application_ownership(app, current_user)
    elif app.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this application")
    
    if is_recruiter and reveal_pii:
        AuditLogger.log(
            db=db,
            action="candidate_identity_revealed",
            user_id=current_user.user_id,
            resource_type="application",
            resource_id=application_id,
            details={"reason": "recruiter_explicitly_opened_identity"},
        )
    return _serialize_application(db, app, recruiter_view=is_recruiter, reveal_pii=reveal_pii)


@router.post("/{application_id}/plagiarism-check", response_model=ApplicationResponse)
async def run_plagiarism_check(
    application_id: int,
    test_response: str,
    db: Session = Depends(get_db),
    checker: PlagiarismChecker = Depends(get_plagiarism_checker),
    current_user: User = Depends(require_recruiter),
):
    """
    Run a web-source similarity check and save its result without changing routing status.
    """
    app = db.query(Application).filter(
        Application.application_id == application_id
    ).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    check_application_ownership(app, current_user)
    
    # Run plagiarism check
    result = await checker.check_text(test_response)

    if result["score"] is None or result["passed"] is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result["details"],
        )
    
    app.plagiarism_score = result["score"]
    app.passed_plagiarism = result["passed"]
    
    db.commit()
    db.refresh(app)
    AuditLogger.log(
        db=db,
        action="web_similarity_check",
        user_id=current_user.user_id,
        resource_type="application",
        resource_id=application_id,
        details={"result": "above_threshold" if not result["passed"] else "below_threshold"},
    )
    
    return {
        "application_id": app.application_id,
        "job_id": app.job_id,
        "user_id": app.user_id,
        "screening_answers": app.screening_answers,
        "test_score": app.test_score,
        "match_score": float(app.match_score) if app.match_score is not None else None,
        "match_details": app.match_details,
        "passed_plagiarism": app.passed_plagiarism,
        "plagiarism_score": float(app.plagiarism_score) if app.plagiarism_score is not None else None,
        "status": app.status,
        "applied_at": app.applied_at,
        "resume_required": _resume_required(app),
    }


@router.post("/{application_id}/integrity-check", response_model=ApplicationWithDetails)
async def run_application_integrity_check(
    application_id: int,
    db: Session = Depends(get_db),
    checker: PlagiarismChecker = Depends(get_plagiarism_checker),
    ai_detector: AIContentDetector = Depends(get_ai_content_detector),
    current_user: User = Depends(require_recruiter),
):
    """Run or refresh answer integrity checks for an application owned by this recruiter."""
    app = db.query(Application).filter(
        Application.application_id == application_id
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    check_application_ownership(app, current_user)

    answers = _serialize_test_answers(db, app)
    if not any(str(answer.get("answer_text", "")).strip() for answer in answers):
        raise HTTPException(status_code=400, detail="No submitted answers are available to check")

    existing_ai_assessment = (
        (app.match_details or {}).get("benchmarks", {})
        .get("screening_questions", {})
        .get("originality_assessment")
    )
    report = await analyze_answer_integrity(
        answers, checker, ai_detector, existing_ai_assessment=existing_ai_assessment
    )
    store_integrity_result(app, report)
    routing = report.get("routing") or integrity_routing_decision(report)
    if app.status in {"pending", "review"} and routing.get("decision") != "cleared":
        app.status = "flagged"
    db.commit()
    db.refresh(app)
    AuditLogger.log(
        db=db,
        action="integrity_check",
        user_id=current_user.user_id,
        resource_type="application",
        resource_id=application_id,
        details={"routing": routing.get("decision")},
    )

    return _serialize_application(db, app, recruiter_view=True)


@router.post("/{application_id}/resume", response_model=ApplicationWithDetails)
async def upload_application_resume(
    application_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    parser: ResumeParser = Depends(get_resume_parser),
    llm: LLMProvider = Depends(get_llm),
    current_user: User = Depends(require_job_seeker),
):
    """Accept a resume only after the screening gate has cleared."""
    app = db.query(Application).filter(Application.application_id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="You cannot upload a resume for this application")
    if app.status in {"flagged", "review"}:
        raise HTTPException(status_code=409, detail="The next application step is not available yet")
    if app.status == "rejected":
        raise HTTPException(status_code=409, detail="This application is closed")
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in {"pdf", "docx"}:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX resumes are supported")
    settings = get_settings()
    content = await file.read(settings.max_file_size + 1)
    if len(content) > settings.max_file_size:
        raise HTTPException(status_code=413, detail="Resume exceeds the configured upload limit")
    if (ext == "pdf" and not content.startswith(b"%PDF-")) or (ext == "docx" and not content.startswith(b"PK")):
        raise HTTPException(status_code=400, detail="The uploaded file does not match its filename extension")

    file_path = parser.save_uploaded_file(content, file.filename, current_user.user_id)
    try:
        parsed_data = await parser.parse_resume(file_path)
    except Exception as exc:
        logger.warning("Resume parsing failed: %s", type(exc).__name__)
        parsed_data = {"error": "Resume parsing is unavailable; the uploaded file was retained for recruiter review."}
    if not isinstance(parsed_data, dict):
        parsed_data = {"error": "Resume parsing returned an invalid result; the uploaded file was retained for recruiter review."}

    app.user.resume_path = file_path
    app.user.resume_parsed = parsed_data
    if parsed_data.get("skills"):
        app.user.has_experience = True
    db.commit()

    if _resume_is_ready(app.user):
        try:
            screening_questions = [
                {"question": answer.get("question", ""), "answer": answer.get("answer", "")}
                for answer in (app.screening_answers or [])
            ]
            match_result = await llm.match_candidate(
                job_description=f"{app.job.description or ''} {app.job.responsibilities or ''}",
                job_skills=app.job.skills or [],
                candidate_resume=_resume_for_matching(app.user.resume_parsed),
                screening_questions=screening_questions or None,
            )
            details = dict(match_result or {})
            if app.match_details and app.match_details.get("skill_test_integrity"):
                assessment = details.get("benchmarks", {}).get("screening_questions", {}).get("originality_assessment")
                details["skill_test_integrity"] = attach_match_originality(
                    app.match_details["skill_test_integrity"], assessment
                )
            app.match_score = details.get("match_score")
            app.match_details = details
            originality_score = _match_originality_score(details)
            if originality_score is not None and originality_score < 40:
                app.status = "flagged"
        except Exception as exc:
            logger.warning("Resume match calculation was skipped: %s", type(exc).__name__)

    db.commit()
    db.refresh(app)
    AuditLogger.log(
        db=db,
        action="resume_upload",
        user_id=current_user.user_id,
        resource_type="application",
        resource_id=application_id,
        details={"file_type": ext, "parsed_success": not bool(parsed_data.get("error"))},
    )
    return _serialize_application(db, app, recruiter_view=False)


@router.get("/{application_id}/resume")
def download_application_resume(
    application_id: int,
    reveal_pii: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """Download a resume only after the recruiter explicitly reveals applicant identity."""
    app = db.query(Application).filter(Application.application_id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    check_application_ownership(app, current_user)
    if app.status in {"flagged", "review"}:
        raise HTTPException(status_code=409, detail="Resume access is available after manual review")
    if not reveal_pii:
        raise HTTPException(status_code=403, detail="Reveal applicant identity before downloading the resume")
    if not app.user.resume_path:
        raise HTTPException(status_code=404, detail="No resume is available")

    upload_root = Path(get_settings().upload_dir).resolve()
    resume_path = Path(app.user.resume_path).resolve()
    if not resume_path.is_relative_to(upload_root) or not resume_path.is_file():
        raise HTTPException(status_code=404, detail="Resume file is unavailable")
    AuditLogger.log(
        db=db,
        action="resume_download",
        user_id=current_user.user_id,
        resource_type="application",
        resource_id=application_id,
        details={"file_type": resume_path.suffix.lower()},
    )
    return FileResponse(resume_path, filename=f"resume-{application_id}{resume_path.suffix.lower()}")


@router.put("/{application_id}/status", response_model=ApplicationResponse)
async def update_application_status(
    application_id: int,
    new_status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    email_service: EmailService = Depends(get_email_service)
):
    """
    Update application status (Recruiter only, owner only).
    Valid statuses: pending, shortlisted, accepted, rejected. Flagged applications use manual-review actions.
    """
    valid_statuses = ["pending", "shortlisted", "accepted", "rejected"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )
    
    app = db.query(Application).filter(
        Application.application_id == application_id
    ).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    check_application_ownership(app, current_user)
    if app.status in {"flagged", "review"}:
        raise HTTPException(
            status_code=400,
            detail="Flagged applications must be approved or rejected from manual review.",
        )
    if new_status in {"shortlisted", "accepted"} and _resume_required(app):
        raise HTTPException(
            status_code=409,
            detail="The candidate has not completed the resume step for this application.",
        )
    
    old_status = app.status
    app.status = new_status
    db.commit()
    db.refresh(app)
    
    # Send email notification for status changes
    if new_status != old_status:
        user = app.user
        job = app.job
        await email_service.send_status_update(
            applicant_email=user.email,
            applicant_name=f"{user.first_name} {user.last_name}",
            job_title=job.role,
            new_status=new_status
        )
        
        # Log status change
        AuditLogger.log(
            db=db,
            action="status_change",
            user_id=current_user.user_id,
            resource_type="application",
            resource_id=application_id,
            details={"old_status": old_status, "new_status": new_status, "applicant_id": app.user_id}
        )

    return {
        "application_id": app.application_id,
        "job_id": app.job_id,
        "user_id": app.user_id,
        "screening_answers": app.screening_answers,
        "test_score": app.test_score,
        "match_score": float(app.match_score) if app.match_score is not None else None,
        "match_details": app.match_details,
        "passed_plagiarism": app.passed_plagiarism,
        "plagiarism_score": float(app.plagiarism_score) if app.plagiarism_score is not None else None,
        "status": app.status,
        "applied_at": app.applied_at,
        "resume_required": _resume_required(app),
    }


@router.post("/search", response_model=List[ApplicationWithDetails])
def search_candidates(
    search: CandidateSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """Filter and rank owned applicants with lexical search and existing match scores."""
    query = db.query(Application).join(User).join(Job).filter(
        Job.recruiter_id == current_user.user_id,
        Application.status.notin_(["flagged", "review"]),
    )
    if search.job_id is not None:
        query = query.filter(Application.job_id == search.job_id)
    if search.min_experience is not None:
        query = query.filter(User.years_of_experience >= search.min_experience)
    if search.max_experience is not None:
        query = query.filter(User.years_of_experience <= search.max_experience)
    if search.min_match_score is not None:
        query = query.filter(Application.match_score >= search.min_match_score)
    if search.status:
        query = query.filter(Application.status == search.status)
    if search.location:
        query = query.filter(User.preferred_location.ilike(f"%{search.location}%"))

    applications = query.all()
    requested_skills = {value.strip().casefold() for value in (search.skills or []) if value.strip()}
    if requested_skills:
        applications = [
            app for app in applications
            if requested_skills.issubset({str(skill).casefold() for skill in ((app.user.resume_parsed or {}).get("skills") or [])})
        ]

    if search.query and applications:
        tokens = re.findall(r"[a-z0-9+#.]{2,}", search.query.casefold())[:120]
        documents = {}
        for app in applications:
            parts = [
                " ".join(str(item) for item in ((app.user.resume_parsed or {}).get("skills") or [])),
                " ".join(str(item) for item in ((app.user.resume_parsed or {}).get("experience") or [])),
                " ".join(str(item) for item in ((app.user.resume_parsed or {}).get("education") or [])),
                " ".join(str(item) for item in ((app.user.resume_parsed or {}).get("projects") or [])),
                str((app.user.resume_parsed or {}).get("summary") or ""),
                " ".join(str(answer.get("answer", "")) for answer in (app.screening_answers or [])),
            ]
            documents[app.application_id] = re.findall(r"[a-z0-9+#.]{2,}", " ".join(parts).casefold())

        average_length = sum(len(doc) for doc in documents.values()) / max(len(documents), 1)
        document_frequency = {token: sum(token in set(doc) for doc in documents.values()) for token in set(tokens)}
        scores = {}
        for app in applications:
            doc = documents[app.application_id]
            frequencies = {}
            for token in doc:
                frequencies[token] = frequencies.get(token, 0) + 1
            score = 0.0
            for token in tokens:
                tf = frequencies.get(token, 0)
                if tf == 0:
                    continue
                df = document_frequency.get(token, 0)
                idf = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
                score += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * len(doc) / max(average_length, 1)))
            scores[app.application_id] = score
        applications.sort(
            key=lambda app: (scores.get(app.application_id, 0), float(app.match_score or 0)),
            reverse=True,
        )
    else:
        applications.sort(key=lambda app: float(app.match_score or 0), reverse=True)

    AuditLogger.log(
        db=db,
        action="candidate_search",
        user_id=current_user.user_id,
        resource_type="job" if search.job_id is not None else "application_search",
        resource_id=search.job_id,
        details={"result_count": len(applications), "has_query": bool(search.query)},
    )
    return [_serialize_application(db, app, recruiter_view=True) for app in applications]


@router.post("/bulk-action")
async def bulk_application_action(
    request: BulkApplicationAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    email_service: EmailService = Depends(get_email_service),
):
    """Shortlist a bounded set of owned, resume-complete applications and send invitations."""
    requested_ids = set(request.application_ids)
    if len(requested_ids) != len(request.application_ids):
        raise HTTPException(status_code=400, detail="Application IDs must be unique")
    applications = db.query(Application).join(Job).filter(
        Application.application_id.in_(requested_ids),
        Job.recruiter_id == current_user.user_id,
    ).all()
    if len(applications) != len(requested_ids):
        raise HTTPException(status_code=404, detail="One or more selected applications are unavailable")
    if any(app.status in {"flagged", "review"} for app in applications):
        raise HTTPException(status_code=409, detail="Flagged applications must be resolved in manual review first")
    if any(_resume_required(app) for app in applications):
        raise HTTPException(status_code=409, detail="Every selected candidate must complete the resume step first")

    changed = []
    for app in applications:
        if app.status == "pending":
            app.status = "shortlisted"
            changed.append(app)
    db.commit()
    for app in changed:
        await email_service.send_status_update(
            applicant_email=app.user.email,
            applicant_name=f"{app.user.first_name} {app.user.last_name}",
            job_title=app.job.role,
            new_status="shortlisted",
        )
    AuditLogger.log(
        db=db,
        action="bulk_shortlist",
        user_id=current_user.user_id,
        resource_type="application",
        details={"selected_count": len(requested_ids), "updated_count": len(changed)},
    )
    return {"action": "shortlist", "updated_count": len(changed), "application_ids": [app.application_id for app in changed]}


@router.post("/{application_id}/recalculate-match", response_model=ApplicationResponse)
async def recalculate_match_score(
    application_id: int,
    db: Session = Depends(get_db),
    llm: LLMProvider = Depends(get_llm),
    current_user: User = Depends(require_recruiter),
):
    """Recalculate match score for an application, including screening question answers"""
    app = db.query(Application).filter(
        Application.application_id == application_id
    ).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    check_application_ownership(app, current_user)
    
    user = app.user
    job = app.job
    
    if not user.resume_parsed or user.resume_parsed.get("error"):
        raise HTTPException(status_code=400, detail="Resume not parsed")
    
    # Use screening_answers JSON column
    screening_questions = None
    if app.screening_answers:
        screening_questions = [
            {"question": a.get("question", ""), "answer": a.get("answer", "")}
            for a in app.screening_answers
        ]
    
    # Calculate match score with screening questions
    match_result = await llm.match_candidate(
        job_description=f"{job.description or ''} {job.responsibilities or ''}",
        job_skills=job.skills or [],
        candidate_resume=_resume_for_matching(user.resume_parsed),
        screening_questions=screening_questions
    )
    
    details = dict(match_result or {})
    if app.match_details and app.match_details.get("skill_test_integrity"):
        assessment = details.get("benchmarks", {}).get("screening_questions", {}).get("originality_assessment")
        details["skill_test_integrity"] = attach_match_originality(
            app.match_details["skill_test_integrity"], assessment
        )
    app.match_score = details.get("match_score", 0)
    app.match_details = details
    originality_score = _match_originality_score(details)
    if app.status == "pending" and originality_score is not None and originality_score < 40:
        app.status = "flagged"
    db.commit()
    db.refresh(app)
    AuditLogger.log(
        db=db,
        action="match_recalculated",
        user_id=current_user.user_id,
        resource_type="application",
        resource_id=application_id,
        details={"match_score": float(app.match_score) if app.match_score is not None else None},
    )

    return {
        "application_id": app.application_id,
        "job_id": app.job_id,
        "user_id": app.user_id,
        "screening_answers": app.screening_answers,
        "test_score": app.test_score,
        "match_score": float(app.match_score) if app.match_score is not None else None,
        "match_details": app.match_details,
        "passed_plagiarism": app.passed_plagiarism,
        "plagiarism_score": float(app.plagiarism_score) if app.plagiarism_score is not None else None,
        "status": app.status,
        "applied_at": app.applied_at,
        "resume_required": _resume_required(app),
    }



@router.post("/{application_id}/approve-flag", response_model=ApplicationResponse)
def approve_flagged_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)
):
    """Approve a flagged application for review (moves to pending status)"""
    app = db.query(Application).filter(
        Application.application_id == application_id
    ).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    check_application_ownership(app, current_user)
    if app.status != "flagged":
        raise HTTPException(status_code=400, detail="Application is not flagged")
    
    app.status = "pending"
    db.commit()
    db.refresh(app)
    AuditLogger.log(
        db=db,
        action="flagged_application_approved",
        user_id=current_user.user_id,
        resource_type="application",
        resource_id=application_id,
        details={"new_status": "pending"},
    )
    return {
        "application_id": app.application_id,
        "job_id": app.job_id,
        "user_id": app.user_id,
        "screening_answers": app.screening_answers,
        "test_score": app.test_score,
        "match_score": float(app.match_score) if app.match_score is not None else None,
        "match_details": None,
        "passed_plagiarism": None,
        "plagiarism_score": None,
        "status": app.status,
        "applied_at": app.applied_at,
        "resume_required": _resume_required(app),
    }


@router.post("/{application_id}/reject-flag", response_model=ApplicationResponse)
def reject_flagged_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)
):
    """Reject a flagged application after recruiter review."""
    app = db.query(Application).filter(
        Application.application_id == application_id
    ).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    check_application_ownership(app, current_user)
    if app.status != "flagged":
        raise HTTPException(status_code=400, detail="Application is not flagged")
    
    app.status = "rejected"
    db.commit()
    db.refresh(app)
    AuditLogger.log(
        db=db,
        action="flagged_application_rejected",
        user_id=current_user.user_id,
        resource_type="application",
        resource_id=application_id,
        details={"new_status": "rejected", "manual_review": True},
    )
    return {
        "application_id": app.application_id,
        "job_id": app.job_id,
        "user_id": app.user_id,
        "screening_answers": app.screening_answers,
        "test_score": app.test_score,
        "match_score": float(app.match_score) if app.match_score is not None else None,
        "match_details": None,
        "passed_plagiarism": None,
        "plagiarism_score": None,
        "status": app.status,
        "applied_at": app.applied_at,
        "resume_required": False,
    }
