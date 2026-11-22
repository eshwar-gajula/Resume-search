# API Endpoints

Base URL: `http://127.0.0.1:8010`. Interactive documentation is available at `/docs`; `/health` checks database connectivity.

Send `Authorization: Bearer <access_token>` except for registration/login, public job and question browsing, health, and documentation. Recruiters can access only jobs and applications they own. Candidates can access their own profile and applications.

## Authentication

| Method | Endpoint | Access | Description |
|---|---|---|---|
| POST | `/api/auth/register` | Public | Create candidate or recruiter account |
| POST | `/api/auth/login` | Public | Sign in |
| POST | `/api/auth/token` | Public form | OAuth2-compatible token endpoint for Swagger |
| GET | `/api/auth/me` | Signed in | Read current account |

## Users

| Method | Endpoint | Access | Description |
|---|---|---|---|
| POST | `/api/users/` | Public | Legacy candidate-only registration route |
| GET | `/api/users/` | Recruiter | Disabled; use anonymized application review |
| GET | `/api/users/{user_id}` | Owner | Read own profile |
| PUT | `/api/users/{user_id}` | Owner | Update own profile |
| DELETE | `/api/users/{user_id}` | Owner | Delete own profile |
| POST | `/api/users/{user_id}/resume` | Owner | Legacy endpoint; returns 409 and directs candidates to the application-scoped upload step |
| GET | `/api/users/{user_id}/resume/parsed` | Owner | Read own parsed resume |

## Jobs and screening questions

| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET | `/api/jobs/` | Public | List active jobs with location/country filters and pagination |
| GET | `/api/jobs/{job_id}` | Public | Read job details |
| POST | `/api/jobs/` | Recruiter | Create an owned job |
| PUT | `/api/jobs/{job_id}` | Owning recruiter | Update job |
| DELETE | `/api/jobs/{job_id}` | Owning recruiter | Delete job |
| POST | `/api/jobs/{job_id}/toggle` | Owning recruiter | Change active state |
| GET | `/api/questions/job/{job_id}` | Public | List screening questions without answer keys |
| POST | `/api/questions/` | Owning recruiter | Add a question |
| POST | `/api/questions/bulk/{job_id}` | Owning recruiter | Add several questions |
| GET | `/api/questions/{question_id}` | Owning recruiter | Read question and answer key |
| PUT | `/api/questions/{question_id}` | Owning recruiter | Update question |
| DELETE | `/api/questions/{question_id}` | Owning recruiter | Delete question |
| POST | `/api/questions/answers/{application_id}` | Candidate, legacy shortlisted flow | Submit additional test answers for older applications |
| GET | `/api/questions/answers/{application_id}` | Candidate or owning recruiter | Read answers for an application |

## Application workflow

The candidate submits the screening answers in `POST /api/applications/`. Required questions must be answered. The backend saves the answers first, then checks free-text answers with the AI-writing detector and the separate web-source similarity provider. It does not parse or match a resume before this gate.

If any check reports a likely-AI result, high web overlap, too little text, an inconclusive result, or an unavailable provider, the application is internally set to `flagged` and appears only in the owning recruiter’s manual-review queue. The candidate receives a generic application response; it contains no flag, check result, or reason. Once checks clear, `resume_required` tells the candidate whether a PDF/DOCX upload is needed. An existing profile resume is used for matching only after the screening checks complete. After resume matching, a match-analysis originality estimate below 40 also routes to manual review. These are review signals, not proof of misconduct.

| Method | Endpoint | Access | Description |
|---|---|---|---|
| POST | `/api/applications/` | Candidate | Apply with job ID, own user ID, and screening answers |
| GET | `/api/applications/` | Candidate or recruiter | List own applications or applications for owned jobs |
| GET | `/api/applications/{application_id}` | Candidate owner or owning recruiter | Read details; recruiter PII is hidden unless explicitly revealed |
| POST | `/api/applications/{application_id}/resume` | Candidate owner | Upload a PDF/DOCX after screening clears; parse and match afterward |
| GET | `/api/applications/{application_id}/resume?reveal_pii=true` | Owning recruiter | Download a resume after manual flags are resolved; access is audit-logged |
| GET | `/api/applications/flagged` | Recruiter | List flagged applications for owned jobs, anonymized by default |
| GET | `/api/applications/review` | Recruiter | List legacy review-status applications |
| PUT | `/api/applications/{application_id}/status?new_status=...` | Owning recruiter | Set pending, shortlisted, accepted, or rejected; flagged items use manual-review actions |
| POST | `/api/applications/{application_id}/approve-flag` | Owning recruiter | Manually clear a flag and return the application to Pending |
| POST | `/api/applications/{application_id}/reject-flag` | Owning recruiter | Reject after human review; the candidate record is retained |
| POST | `/api/applications/{application_id}/integrity-check` | Owning recruiter | Re-run detector and web-similarity checks on stored answers |
| POST | `/api/applications/{application_id}/plagiarism-check` | Owning recruiter | Run a separate web-source check on supplied text |
| POST | `/api/applications/{application_id}/recalculate-match` | Owning recruiter | Re-run resume matching |
| POST | `/api/applications/search` | Recruiter | Search owned applications using BM25-style text ranking and filters |
| POST | `/api/applications/bulk-action` | Recruiter | Shortlist and invite up to 100 owned, resume-complete applications |
| GET | `/api/applications/export` | Recruiter | Export up to 500 owned, non-flagged applications as CSV; identity is omitted by default |

Example apply request:

```json
{
  "job_id": 12,
  "user_id": 34,
  "screening_answers": [
    {
      "question_id": 56,
      "question": "How would you approach this problem?",
      "answer": "A concise answer from the candidate."
    }
  ]
}
```

Example search request:

```json
{
  "job_id": 12,
  "query": "React developer with API and PostgreSQL experience",
  "min_experience": 1,
  "max_experience": 8,
  "min_match_score": 40,
  "status": "pending"
}
```

Recruiter list responses pseudonymize applicant name, email, phone, location, and profile links by default. `GET /api/applications/{id}?reveal_pii=true` reveals identity for that owned application and records an audit event. Candidate responses never include flagged status, integrity reports, or plagiarism results. Automated AI-writing detection is uncertain and must be treated as a prompt for human review, not a definitive authorship verdict.
