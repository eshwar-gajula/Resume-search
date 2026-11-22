"""Run an authenticated API smoke check against a local server."""
import asyncio
import os
import uuid

import httpx


API_ROOT = os.getenv("API_ROOT", "http://127.0.0.1:8010")


async def run_api_smoke():
    async with httpx.AsyncClient(base_url=API_ROOT, timeout=30.0) as client:
        response = await client.get("/health")
        response.raise_for_status()
        assert response.json()["status"] == "healthy"
        print("PASS health check")

        identity = uuid.uuid4().hex[:10]
        recruiter_response = await client.post(
            "/api/auth/register",
            json={
                "first_name": "Smoke",
                "last_name": "Recruiter",
                "email": f"recruiter-{identity}@example.com",
                "password": "SafeTestPassword123",
                "user_type": "recruiter",
            },
        )
        recruiter_response.raise_for_status()
        recruiter = recruiter_response.json()
        recruiter_headers = {"Authorization": f"Bearer {recruiter['access_token']}"}
        print("PASS recruiter registration")

        denied = await client.post(
            "/api/jobs/",
            json={"role": "Should be blocked", "skills": []},
        )
        assert denied.status_code == 401
        print("PASS recruiter endpoints require authentication")

        job_response = await client.post(
            "/api/jobs/",
            headers=recruiter_headers,
            json={
                "role": "Smoke Test Engineer",
                "job_location": "Remote",
                "description": "Test API workflow",
                "skills": ["Python", "FastAPI"],
                "years_of_experience": 1,
            },
        )
        job_response.raise_for_status()
        job = job_response.json()
        print("PASS recruiter job creation")

        question_response = await client.post(
            "/api/questions/",
            headers=recruiter_headers,
            json={
                "job_id": job["job_id"],
                "question_text": "What is a Python virtual environment?",
                "question_type": "text",
                "correct_answer": "An isolated Python environment",
            },
        )
        question_response.raise_for_status()
        question = question_response.json()

        candidate_response = await client.post(
            "/api/auth/register",
            json={
                "first_name": "Smoke",
                "last_name": "Candidate",
                "email": f"candidate-{identity}@example.com",
                "password": "SafeTestPassword123",
                "user_type": "job_seeker",
            },
        )
        candidate_response.raise_for_status()
        candidate = candidate_response.json()
        candidate_headers = {"Authorization": f"Bearer {candidate['access_token']}"}
        print("PASS candidate registration")

        public_questions = await client.get(f"/api/questions/job/{job['job_id']}")
        public_questions.raise_for_status()
        assert "correct_answer" not in public_questions.json()[0]
        print("PASS candidate question response hides grading answer")

        application_response = await client.post(
            "/api/applications/",
            headers=candidate_headers,
            json={
                "job_id": job["job_id"],
                "user_id": candidate["user"]["user_id"],
                "screening_answers": [
                    {
                        "question_id": question["question_id"],
                        "question": question["question_text"],
                        "answer": "It keeps dependencies isolated for the project.",
                    }
                ],
            },
        )
        application_response.raise_for_status()
        application = application_response.json()
        assert application["status"] == "pending"
        assert application["match_details"] is None
        print("PASS candidate application")

        candidate_apps = await client.get("/api/applications/", headers=candidate_headers)
        candidate_apps.raise_for_status()
        candidate_application = next(
            item for item in candidate_apps.json()
            if item["application_id"] == application["application_id"]
        )
        assert candidate_application["status"] == "pending"
        assert candidate_application["match_details"] is None
        print("PASS candidate responses hide recruiter-only flag details")

        flagged_apps = await client.get("/api/applications/flagged", headers=recruiter_headers)
        flagged_apps.raise_for_status()
        assert all(
            item["application_id"] != application["application_id"]
            for item in flagged_apps.json()
        )
        print("PASS missing originality or detector result does not create a flag")

        candidate_flagged_list = await client.get(
            "/api/applications/flagged", headers=candidate_headers
        )
        assert candidate_flagged_list.status_code == 403
        print("PASS candidates cannot access recruiter flagged list")

        if os.getenv("RUN_LIVE_PLAGIARISM") == "1":
            plagiarism_response = await client.post(
                f"/api/applications/{application['application_id']}/plagiarism-check",
                headers=recruiter_headers,
                params={
                    "test_response": (
                        "Synthetic plagiarism integration test text. "
                        "This contains no personal information and is only used to verify the API."
                    )
                },
            )
            plagiarism_response.raise_for_status()
            plagiarism_result = plagiarism_response.json()
            assert plagiarism_result["plagiarism_score"] is not None
            assert plagiarism_result["passed_plagiarism"] is not None
            print("PASS live plagiarism check and application result persistence")

        blocked_answers = await client.post(
            f"/api/questions/answers/{application['application_id']}",
            headers=candidate_headers,
            json={
                "answers": [
                    {
                        "question_id": question["question_id"],
                        "answer_text": "An isolated Python environment",
                    }
                ]
            },
        )
        assert blocked_answers.status_code == 400
        print("PASS skill-test submission is blocked before shortlisting")

        shortlist_response = await client.put(
            f"/api/applications/{application['application_id']}/status",
            headers=recruiter_headers,
            params={"new_status": "shortlisted"},
        )
        shortlist_response.raise_for_status()
        print("PASS recruiter shortlisting")

        answers_response = await client.post(
            f"/api/questions/answers/{application['application_id']}",
            headers=candidate_headers,
            json={
                "answers": [
                    {
                        "question_id": question["question_id"],
                        "answer_text": "An isolated Python environment",
                    }
                ],
            },
        )
        answers_response.raise_for_status()
        assert answers_response.json()[0]["is_correct"] is True
        print("PASS skill-test answer submission and scoring")

        recruiter_apps = await client.get("/api/applications/", headers=recruiter_headers)
        recruiter_apps.raise_for_status()
        reviewed_application = next(
            item for item in recruiter_apps.json()
            if item["application_id"] == application["application_id"]
        )
        assert reviewed_application["status"] == "shortlisted"
        assert "ai_detection" in reviewed_application["match_details"]["skill_test_integrity"]
        candidate_apps = await client.get("/api/applications/", headers=candidate_headers)
        candidate_apps.raise_for_status()
        candidate_application = next(
            item for item in candidate_apps.json()
            if item["application_id"] == application["application_id"]
        )
        assert candidate_application["status"] == "shortlisted"
        assert candidate_application["match_details"] is None
        print("PASS AI and web checks do not override the data-flow application status")

        login_response = await client.post(
            "/api/auth/login",
            json={"email": f"candidate-{identity}@example.com", "password": "SafeTestPassword123"},
        )
        login_response.raise_for_status()
        print("PASS login")


if __name__ == "__main__":
    asyncio.run(run_api_smoke())
