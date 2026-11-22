from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Application, ApplicationAnswer, Job, JobQuestion, User
from app.routers.applications import router as applications_router
from app.routers.questions import router as questions_router
from app.services.auth_utils import (
    get_current_user_required,
    require_job_seeker,
    require_recruiter,
)
from app.services.email_service import get_email_service
from app.services.integrity_review import (
    analyze_answer_integrity,
    store_integrity_result,
)
from app.services.ai_detection import get_ai_content_detector, AIContentDetector
from app.services.llm_provider import get_llm
from app.services.plagiarism import get_plagiarism_checker
from app.services.resume_parser import get_resume_parser


class FakeLLM:
    api_key = "test-key"

    def __init__(self, suspicion_level="high", originality_score=25):
        self.suspicion_level = suspicion_level
        self.originality_score = originality_score

    async def match_candidate(
        self, job_description, job_skills, candidate_resume, screening_questions=None
    ):
        assert screening_questions
        assert not {"name", "email", "phone", "social_links"}.intersection(candidate_resume)
        return {
            "match_score": 72,
            "benchmarks": {
                "screening_questions": {
                    "score": 12,
                    "originality_assessment": {
                        "originality_score": self.originality_score,
                        "suspicion_level": "high",
                        "suspicion_flags": ["generic_response"],
                        "assessment": "Synthetic low-originality result for testing.",
                    },
                }
            },
        }


class FakePlagiarismChecker:
    api_key = "test-key"
    threshold = 30

    def __init__(self, score=10):
        self.score = score

    async def check_text(self, text):
        assert text
        return {
            "score": self.score,
            "passed": self.score < self.threshold,
            "details": "Synthetic result for automated testing.",
        }


class FakeAIDetector:
    def __init__(self, verdict="ai_generated", configured=True):
        self.api_key = "test-key" if configured else ""
        self.verdict = verdict

    async def check_text(self, text):
        assert text
        if not self.api_key:
            return {
                "status": "not_configured",
                "verdict": "unknown",
                "summary": "Synthetic detector is not configured.",
            }
        return {
            "status": "checked",
            "verdict": self.verdict,
            "provider_result": self.verdict.replace("_", "-"),
            "summary": "Synthetic detector response for automated testing.",
        }


class FakeEmailService:
    async def send_application_submitted(self, **kwargs):
        return False


class FakeResumeParser:
    def save_uploaded_file(self, content, filename, user_id):
        return f"synthetic-upload/{user_id}/resume.{filename.rsplit('.', 1)[-1]}"

    async def parse_resume(self, file_path):
        return {
            "name": "Synthetic Candidate",
            "email": "synthetic@example.com",
            "phone": "555-555-1234",
            "skills": ["Python"],
            "experience": [{"title": "Developer", "company": "Synthetic Corp"}],
        }


@pytest.mark.asyncio
async def test_integrity_records_detector_and_similarity_without_changing_status():
    answer = {"question": "Explain the approach", "answer_text": "A detailed synthetic response. " * 8}
    report = await analyze_answer_integrity(
        [answer], FakePlagiarismChecker(score=42), FakeAIDetector("ai_generated")
    )

    assert report["ai_detection"]["verdict"] == "ai_generated"
    assert report["web_similarity"]["passed"] is False

    application = SimpleNamespace(
        match_details={}, status="pending", plagiarism_score=None, passed_plagiarism=None
    )
    store_integrity_result(application, report)

    assert application.status == "pending"
    assert application.match_details["skill_test_integrity"] == report
    assert application.plagiarism_score == 42
    assert application.passed_plagiarism is False


@pytest.mark.asyncio
async def test_missing_provider_keys_are_not_reported_as_passes():
    no_checker_key = SimpleNamespace(api_key="", threshold=30)
    report = await analyze_answer_integrity(
        [{"question": "Explain", "answer": "A synthetic response long enough to check. " * 4}],
        no_checker_key,
        FakeAIDetector(configured=False),
    )

    assert report["ai_detection"]["status"] == "not_configured"
    assert report["web_similarity"]["status"] == "not_configured"
    assert report["web_similarity"]["passed"] is None


@pytest.mark.asyncio
async def test_multiple_choice_answers_are_excluded_from_text_checks():
    report = await analyze_answer_integrity(
        [{"question_type": "multiple_choice", "question": "Pick one", "answer": "A" * 500}],
        FakePlagiarismChecker(),
        FakeAIDetector(),
    )

    assert report["answer_count"] == 1
    assert report["free_text_answer_count"] == 0
    assert report["ai_detection"]["status"] == "insufficient_text"
    assert report["web_similarity"]["status"] == "insufficient_text"


@pytest.mark.asyncio
async def test_match_originality_is_kept_separate_from_ai_detector_result():
    report = await analyze_answer_integrity(
        [{"question": "Explain the approach", "answer": "A specific synthetic answer. " * 8}],
        FakePlagiarismChecker(),
        FakeAIDetector("human_written"),
        existing_ai_assessment={
            "originality_score": 70,
            "suspicion_level": "low",
            "suspicion_flags": ["generic_response", "no_personal_examples"],
            "assessment": "A synthetic match-specificity assessment.",
        },
    )

    assert report["ai_detection"]["verdict"] == "human_written"
    assert report["match_originality"]["score"] == 70
    assert report["match_originality"]["signals"] == ["generic_response", "no_personal_examples"]
    assert "not the AI detector result" in report["match_originality"]["method"]
    assert "below 40 also routes to review" in report["notice"]


@pytest.mark.asyncio
async def test_rapidapi_ai_detector_sends_text_and_normalizes_result(monkeypatch):
    from app.services import ai_detection

    monkeypatch.setattr(ai_detection.settings, "rapidapi_key", "synthetic-test-key")
    monkeypatch.setattr(ai_detection.settings, "rapidapi_ai_detector_key", "")
    request = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True, "result": "AI-Generated"}

    class FakeClient:
        def __init__(self, timeout):
            assert timeout == 30.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, *, headers, json):
            request.update(url=url, headers=headers, body=json)
            return FakeResponse()

    monkeypatch.setattr(ai_detection.httpx, "AsyncClient", FakeClient)
    detector = AIContentDetector()
    result = await detector.check_text("Synthetic test answer for provider integration.")

    assert request["url"] == "https://ai-generated-content-detector.p.rapidapi.com/data"
    assert request["headers"]["X-RapidAPI-Host"] == "ai-generated-content-detector.p.rapidapi.com"
    assert request["headers"]["X-RapidAPI-Key"] == "synthetic-test-key"
    assert request["body"]["text"] == "Synthetic test answer for provider integration."
    assert result["status"] == "checked"
    assert result["verdict"] == "ai_generated"


def test_recruiter_integrity_endpoint_persists_and_returns_answer_review():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    seed = Session()
    recruiter = User(
        user_type="recruiter", first_name="Test", last_name="Recruiter",
        email="recruiter@example.com", password_hash="not-used",
    )
    candidate = User(
        user_type="job_seeker", first_name="Test", last_name="Candidate",
        email="candidate@example.com", password_hash="not-used",
    )
    seed.add_all([recruiter, candidate])
    seed.flush()
    job = Job(recruiter_id=recruiter.user_id, role="Synthetic Test Job", is_active=True)
    seed.add(job)
    seed.flush()
    question = JobQuestion(
        job_id=job.job_id,
        question_text="Explain a synthetic test concept",
        question_type="text",
        points=10,
    )
    seed.add(question)
    seed.flush()
    followup_question = JobQuestion(
        job_id=job.job_id,
        question_text="Describe a second synthetic test concept",
        question_type="text",
        points=10,
    )
    seed.add(followup_question)
    seed.flush()
    application = Application(job_id=job.job_id, user_id=candidate.user_id, status="pending")
    seed.add(application)
    seed.flush()
    answer_text = "Synthetic candidate answer for a recruiter integrity visibility test. " * 5
    seed.add(ApplicationAnswer(
        application_id=application.application_id,
        question_id=question.question_id,
        answer_text=answer_text,
    ))
    seed.commit()
    application_id = application.application_id
    seed.close()

    test_app = FastAPI()
    test_app.include_router(applications_router, prefix="/api/applications")
    test_app.include_router(questions_router, prefix="/api/questions")

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_db
    test_app.dependency_overrides[require_recruiter] = lambda: recruiter
    test_app.dependency_overrides[require_job_seeker] = lambda: candidate
    test_app.dependency_overrides[get_current_user_required] = lambda: recruiter
    test_app.dependency_overrides[get_llm] = lambda: FakeLLM("high")
    test_app.dependency_overrides[get_plagiarism_checker] = lambda: FakePlagiarismChecker(score=42)
    test_app.dependency_overrides[get_ai_content_detector] = lambda: FakeAIDetector("ai_generated")

    try:
        with TestClient(test_app) as client:
            test_submission = {
                "answers": [{
                    "question_id": followup_question.question_id,
                    "answer_text": "Synthetic candidate skill-test response for automatic AI-style and web similarity review. " * 4,
                }],
            }
            blocked_submission = client.post(
                f"/api/questions/answers/{application_id}",
                json=test_submission,
            )
            assert blocked_submission.status_code == 400

            db = Session()
            db.query(Application).filter(
                Application.application_id == application_id
            ).update({Application.status: "shortlisted"})
            db.commit()
            db.close()

            submitted = client.post(
                f"/api/questions/answers/{application_id}", json=test_submission
            )
            assert submitted.status_code == 201, submitted.text

            listed = client.get("/api/applications/")
            assert listed.status_code == 200, listed.text
            listed_data = next(item for item in listed.json() if item["application_id"] == application_id)
            assert len(listed_data["test_answers"]) == 2
            assert listed_data["job"]["has_questions"] is True
            assert listed_data["match_details"]["skill_test_integrity"]["ai_detection"]["verdict"] == "ai_generated"

            checked = client.post(f"/api/applications/{application_id}/integrity-check")
            assert checked.status_code == 200, checked.text
            checked_data = checked.json()
            assert checked_data["status"] == "shortlisted"
            assert len(checked_data["test_answers"]) == 2
            assert checked_data["match_details"]["skill_test_integrity"]["ai_detection"]["verdict"] == "ai_generated"

            listed = client.get("/api/applications/")
            listed_data = next(item for item in listed.json() if item["application_id"] == application_id)
            assert listed_data["status"] == "shortlisted"

            detail = client.get(f"/api/applications/{application_id}")
            assert detail.status_code == 200, detail.text
            assert detail.json()["status"] == "shortlisted"

            web_check = client.post(
                f"/api/applications/{application_id}/plagiarism-check",
                params={"test_response": "Synthetic copied-source test text."},
            )
            assert web_check.status_code == 200, web_check.text
            assert web_check.json()["passed_plagiarism"] is False
            assert web_check.json()["status"] == "shortlisted"
    finally:
        test_app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_data_flow_threshold_and_recruiter_manual_review_path():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    seed = Session()
    recruiter = User(
        user_type="recruiter", first_name="Flag", last_name="Reviewer",
        email="flag-reviewer@example.com", password_hash="not-used",
    )
    candidates = [
        User(
            user_type="job_seeker", first_name="Fresh", last_name="Candidate One",
            email="fresh-candidate-one@example.com", password_hash="not-used",
            resume_path="synthetic-resume-one.pdf",
            resume_parsed={"skills": ["Python"], "experience": [{"title": "Developer"}]},
        ),
        User(
            user_type="job_seeker", first_name="Fresh", last_name="Candidate Two",
            email="fresh-candidate-two@example.com", password_hash="not-used",
            resume_path="synthetic-resume-two.pdf",
            resume_parsed={"skills": ["Python"], "experience": [{"title": "Developer"}]},
        ),
        User(
            user_type="job_seeker", first_name="Fresh", last_name="Candidate Three",
            email="fresh-candidate-three@example.com", password_hash="not-used",
            resume_path="synthetic-resume-three.pdf",
            resume_parsed={"skills": ["Python"], "experience": [{"title": "Developer"}]},
        ),
        User(
            user_type="job_seeker", first_name="Fresh", last_name="Candidate Four",
            email="fresh-candidate-four@example.com", password_hash="not-used",
        ),
        User(
            user_type="job_seeker", first_name="Fresh", last_name="Candidate Five",
            email="fresh-candidate-five@example.com", password_hash="not-used",
        ),
    ]
    seed.add(recruiter)
    seed.add_all(candidates)
    seed.flush()
    job = Job(
        recruiter_id=recruiter.user_id,
        role="Synthetic Flagging Test",
        description="A synthetic role for exercising manual-review flagging.",
        skills=["Python"],
        is_active=True,
    )
    seed.add(job)
    seed.flush()
    question = JobQuestion(
        job_id=job.job_id,
        question_text="Describe your approach to this synthetic problem.",
        question_type="text",
        points=10,
    )
    seed.add(question)
    seed.commit()
    job_id = job.job_id
    question_id = question.question_id
    seed.close()

    active_candidate = {"user": candidates[0]}

    test_app = FastAPI()
    test_app.include_router(applications_router, prefix="/api/applications")

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_db
    test_app.dependency_overrides[require_recruiter] = lambda: recruiter
    test_app.dependency_overrides[require_job_seeker] = lambda: active_candidate["user"]
    originality = {"score": 39}
    detector_verdict = {"value": "human_written"}
    test_app.dependency_overrides[get_llm] = lambda: FakeLLM("low", originality_score=originality["score"])
    test_app.dependency_overrides[get_plagiarism_checker] = lambda: FakePlagiarismChecker(score=10)
    test_app.dependency_overrides[get_ai_content_detector] = lambda: FakeAIDetector(detector_verdict["value"])
    test_app.dependency_overrides[get_email_service] = lambda: FakeEmailService()
    test_app.dependency_overrides[get_resume_parser] = lambda: FakeResumeParser()
    test_app.dependency_overrides[get_current_user_required] = lambda: active_candidate["user"]

    def apply_as(client, candidate):
        active_candidate["user"] = candidate
        return client.post(
            "/api/applications/",
            json={
                "job_id": job_id,
                "user_id": candidate.user_id,
                "screening_answers": [{
                    "question_id": question_id,
                    "question": "Describe your approach to this synthetic problem.",
                    "answer": "A synthetic answer for the originality threshold workflow. " * 4,
                }],
            },
        )

    try:
        with TestClient(test_app) as client:
            first_response = apply_as(client, candidates[0])
            assert first_response.status_code == 201, first_response.text
            first = first_response.json()
            assert first["status"] == "pending"  # Candidate view hides the internal flag.
            assert first["match_details"] is None

            candidate_apps = client.get("/api/applications/")
            assert candidate_apps.status_code == 200, candidate_apps.text
            candidate_view = next(item for item in candidate_apps.json() if item["application_id"] == first["application_id"])
            assert candidate_view["status"] == "pending"
            assert candidate_view["match_details"] is None
            assert candidate_view["plagiarism_score"] is None
            candidate_detail = client.get(f"/api/applications/{first['application_id']}")
            assert candidate_detail.status_code == 200, candidate_detail.text
            assert candidate_detail.json()["status"] == "pending"
            assert candidate_detail.json()["match_details"] is None

            flagged = client.get("/api/applications/flagged")
            assert flagged.status_code == 200, flagged.text
            recruiter_view = next(item for item in flagged.json() if item["application_id"] == first["application_id"])
            assert recruiter_view["status"] == "flagged"
            assert recruiter_view["user"]["display_name"] == f"Candidate #{first['application_id']}"
            assert recruiter_view["user"]["email"] is None
            integrity = recruiter_view["match_details"]["skill_test_integrity"]
            assert integrity["ai_detection"]["verdict"] == "human_written"
            assert integrity["web_similarity"]["score"] == 10
            assert integrity["match_originality"]["score"] == 39

            active_candidate["user"] = recruiter
            revealed = client.get(f"/api/applications/{first['application_id']}?reveal_pii=true")
            assert revealed.status_code == 200, revealed.text
            assert revealed.json()["user"]["email"] == "fresh-candidate-one@example.com"
            assert revealed.json()["revealed_pii"] is True
            active_candidate["user"] = candidates[0]

            bypass = client.put(
                f"/api/applications/{first['application_id']}/status",
                params={"new_status": "pending"},
            )
            assert bypass.status_code == 400

            approved = client.post(f"/api/applications/{first['application_id']}/approve-flag")
            assert approved.status_code == 200, approved.text
            assert approved.json()["status"] == "pending"

            originality["score"] = 40
            second_response = apply_as(client, candidates[1])
            assert second_response.status_code == 201, second_response.text
            second = second_response.json()
            assert second["status"] == "pending"
            flagged_after_second = client.get("/api/applications/flagged")
            assert flagged_after_second.status_code == 200, flagged_after_second.text
            assert all(item["application_id"] != second["application_id"] for item in flagged_after_second.json())

            originality["score"] = 39
            third_response = apply_as(client, candidates[2])
            assert third_response.status_code == 201, third_response.text
            third = third_response.json()
            rejected = client.post(f"/api/applications/{second['application_id']}/reject-flag")
            assert rejected.status_code == 400  # Score 40 stays pending and is not in manual review.
            rejected = client.post(f"/api/applications/{third['application_id']}/reject-flag")
            assert rejected.status_code == 200, rejected.text
            assert rejected.json()["status"] == "rejected"

            remaining_flags = client.get("/api/applications/flagged")
            assert remaining_flags.status_code == 200, remaining_flags.text
            assert all(item["application_id"] not in {first["application_id"], second["application_id"], third["application_id"]} for item in remaining_flags.json())

            detector_verdict["value"] = "ai_generated"
            fourth_response = apply_as(client, candidates[3])
            assert fourth_response.status_code == 201, fourth_response.text
            fourth = fourth_response.json()
            assert fourth["status"] == "pending"
            assert fourth["match_score"] is None
            assert fourth["match_details"] is None
            candidate_four_apps = client.get("/api/applications/")
            candidate_four = next(item for item in candidate_four_apps.json() if item["application_id"] == fourth["application_id"])
            assert candidate_four["status"] == "pending"
            assert candidate_four["match_details"] is None
            assert candidate_four["resume_required"] is False

            blocked_resume = client.post(
                f"/api/applications/{fourth['application_id']}/resume",
                files={"file": ("resume.pdf", b"%PDF-synthetic", "application/pdf")},
            )
            assert blocked_resume.status_code == 409
            flagged_after_ai = client.get("/api/applications/flagged")
            fourth_reviewer_view = next(item for item in flagged_after_ai.json() if item["application_id"] == fourth["application_id"])
            assert fourth_reviewer_view["match_details"]["skill_test_integrity"]["ai_detection"]["verdict"] == "ai_generated"
            assert fourth_reviewer_view["match_details"]["skill_test_integrity"]["routing"]["decision"] == "manual_review"

            detector_verdict["value"] = "human_written"
            fifth_response = apply_as(client, candidates[4])
            assert fifth_response.status_code == 201, fifth_response.text
            fifth = fifth_response.json()
            assert fifth["resume_required"] is True
            assert fifth["match_score"] is None
            uploaded = client.post(
                f"/api/applications/{fifth['application_id']}/resume",
                files={"file": ("resume.pdf", b"%PDF-synthetic", "application/pdf")},
            )
            assert uploaded.status_code == 200, uploaded.text
            assert uploaded.json()["status"] == "pending"  # Match originality flag stays recruiter-only.
            assert uploaded.json()["match_score"] is None
            assert uploaded.json()["resume_required"] is False
            final_reviewer_view = next(
                item for item in client.get("/api/applications/flagged").json()
                if item["application_id"] == fifth["application_id"]
            )
            assert final_reviewer_view["match_details"]["skill_test_integrity"]["ai_detection"]["verdict"] == "human_written"
            assert final_reviewer_view["match_details"]["skill_test_integrity"]["match_originality"]["score"] == 39
    finally:
        test_app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()
