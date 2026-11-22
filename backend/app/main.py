"""
AI Resume Search Engine - FastAPI Application
"""
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.database import engine, init_db
from app.config import get_settings
from app.routers import users, jobs, applications, questions, auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Create tables
    init_db()
    logger.info("Database initialized")
    logger.info(f"Email Enabled: {settings.email_enabled}")
    yield
    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title="AI Resume Search Engine",
    description="AI-powered resume parsing and semantic job matching",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - parse origins from settings (comma-separated)
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",")]
logger.info(f"CORS origins configured: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(applications.router, prefix="/api/applications", tags=["Applications"])
app.include_router(questions.router, prefix="/api/questions", tags=["Questions"])


@app.get("/")
async def root():
    return {
        "message": "AI Resume Search Engine API",
        "docs": "/docs",
        "health": "ok"
    }


@app.get("/health")
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("Database health check failed")
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return {
        "status": "healthy",
        "database": "connected",
        "llm_configured": bool(settings.groq_api_key),
        "llm_model": settings.llm_model,
    }
