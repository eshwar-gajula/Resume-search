"""
Authentication Router - Login, Register, and Token Management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import (
    UserCreate, UserResponse, LoginRequest, Token, TokenData
)
from app.services.auth_utils import (
    verify_password, hash_password, create_access_token,
    get_current_user_required
)
from app.services.audit_logger import AuditLogger

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user (recruiter or job_seeker).
    Returns JWT token on successful registration.
    """
    # Check if email already exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    db_user = User(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        email=user_data.email,
        mobile=user_data.mobile,
        password_hash=hash_password(user_data.password),
        user_type=user_data.user_type.value if hasattr(user_data.user_type, 'value') else user_data.user_type,
        has_experience=user_data.has_experience,
        years_of_experience=user_data.years_of_experience,
        graduation_year=user_data.graduation_year,
        notice_period=user_data.notice_period,
        gender=user_data.gender,
        country=user_data.country,
        preferred_location=user_data.preferred_location,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create access token
    access_token = create_access_token(
        data={
            "user_id": db_user.user_id,
            "email": db_user.email,
            "user_type": db_user.user_type
        }
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(db_user)
    )


@router.post("/login", response_model=Token)
def login(credentials: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Login with email and password.
    Returns JWT token on successful authentication.
    """
    # Find user by email
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "user_id": user.user_id,
            "email": user.email,
            "user_type": user.user_type
        }
    )
    
    # Log successful login
    AuditLogger.log(
        db=db,
        action="login",
        user_id=user.user_id,
        resource_type="user",
        resource_id=user.user_id,
        details={"email": user.email, "user_type": user.user_type},
        ip_address=AuditLogger.get_client_ip(request)
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user: User = Depends(get_current_user_required)):
    """Get the current authenticated user's profile"""
    return current_user


@router.post("/token", response_model=Token)
def login_for_oauth_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    OAuth2 compatible token endpoint for Swagger UI authentication.
    Uses form data (username=email, password).
    """
    # Find user by email (OAuth2 uses "username" field)
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "user_id": user.user_id,
            "email": user.email,
            "user_type": user.user_type
        }
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )
