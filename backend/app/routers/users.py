"""
Users Router - User/Candidate CRUD and Resume Upload
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserResponse, UserUpdate
from app.services.auth_utils import hash_password, get_current_user_required, require_recruiter

router = APIRouter()

def _ensure_user_access(user_id: int, current_user: User, *, recruiter_allowed: bool = False):
    if current_user.user_id != user_id and not (recruiter_allowed and current_user.user_type == "recruiter"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this user's data")


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user/candidate"""
    # Check if email exists
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_user = User(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        mobile=user.mobile,
        password_hash=hash_password(user.password),
        user_type="job_seeker",
        has_experience=user.has_experience,
        years_of_experience=user.years_of_experience,
        graduation_year=user.graduation_year,
        notice_period=user.notice_period,
        gender=user.gender,
        country=user.country,
        preferred_location=user.preferred_location,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/", response_model=List[UserResponse])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
):
    """Keep the global user directory closed; recruiters review applicants by owned job."""
    raise HTTPException(
        status_code=403,
        detail="Use the anonymized recruiter application review to find candidates.",
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """Get a specific user"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _ensure_user_access(user_id, current_user)
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """Update user profile"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _ensure_user_access(user_id, current_user, recruiter_allowed=False)
    
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """Delete a user"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _ensure_user_access(user_id, current_user, recruiter_allowed=False)
    
    db.delete(user)
    db.commit()
    return None


@router.post("/{user_id}/resume", response_model=UserResponse)
def upload_resume(
    user_id: int,
    current_user: User = Depends(get_current_user_required),
):
    """Retain the legacy path with a clear response so uploads stay application-scoped."""
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="You cannot upload a resume for this user")
    raise HTTPException(
        status_code=409,
        detail="Upload a resume from the application step after completing screening.",
    )


@router.get("/{user_id}/resume/parsed")
def get_parsed_resume(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """Get the parsed resume data for a user"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _ensure_user_access(user_id, current_user)
    
    if not user.resume_parsed:
        raise HTTPException(status_code=404, detail="Resume not parsed yet")
    
    return user.resume_parsed
