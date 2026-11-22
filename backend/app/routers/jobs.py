"""
Jobs Router - Job posting CRUD operations
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Job, User
from app.schemas import JobCreate, JobResponse, JobUpdate
from app.services.auth_utils import require_recruiter, get_current_user
from app.services.audit_logger import AuditLogger

router = APIRouter()


def check_job_ownership(job: Job, current_user: User):
    """Check if job belongs to current user, raise 403 if not"""
    if job.recruiter_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to modify this job"
        )


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    job: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)
):
    """Create a new job posting (Recruiter only)"""
    db_job = Job(
        role=job.role,
        job_location=job.job_location,
        job_country=job.job_country,
        responsibilities=job.responsibilities,
        years_of_experience=job.years_of_experience,
        skills=job.skills,
        description=job.description,
        highest_education_qualification=job.highest_education_qualification,
        recruiter_id=current_user.user_id,  # Set job owner
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    AuditLogger.log(
        db, action="job_create", user_id=current_user.user_id,
        resource_type="job", resource_id=db_job.job_id,
    )
    return db_job


@router.get("/", response_model=List[JobResponse])
async def list_jobs(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    my_jobs_only: bool = False,
    location: Optional[str] = None,
    country: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """List all job postings with optional filters"""
    query = db.query(Job)
    
    if active_only:
        query = query.filter(Job.is_active == True)
    
    # Filter to show only current recruiter's jobs if requested
    if my_jobs_only and current_user and current_user.user_type == "recruiter":
        query = query.filter(Job.recruiter_id == current_user.user_id)
    
    if location:
        query = query.filter(Job.job_location.ilike(f"%{location}%"))
    
    if country:
        query = query.filter(Job.job_country.ilike(f"%{country}%"))
    
    jobs = query.offset(skip).limit(limit).all()
    return jobs


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get a specific job posting"""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    job_update: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)
):
    """Update a job posting (Recruiter only, owner only)"""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check ownership
    check_job_ownership(job, current_user)
    
    update_data = job_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(job, key, value)
    
    db.commit()
    db.refresh(job)
    AuditLogger.log(
        db, action="job_update", user_id=current_user.user_id,
        resource_type="job", resource_id=job.job_id,
        details={"updated_fields": sorted(update_data)},
    )
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)
):
    """Delete a job posting (Recruiter only, owner only)"""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check ownership
    check_job_ownership(job, current_user)
    
    db.delete(job)
    db.commit()
    AuditLogger.log(
        db, action="job_delete", user_id=current_user.user_id,
        resource_type="job", resource_id=job_id,
    )
    return None


@router.post("/{job_id}/toggle", response_model=JobResponse)
def toggle_job_status(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)
):
    """Toggle job active status (Recruiter only, owner only)"""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check ownership
    check_job_ownership(job, current_user)
    
    job.is_active = not job.is_active
    db.commit()
    db.refresh(job)
    AuditLogger.log(
        db, action="job_status_toggle", user_id=current_user.user_id,
        resource_type="job", resource_id=job.job_id,
        details={"is_active": job.is_active},
    )
    return job
