# ResumeAI Architecture

## Components

- **Frontend:** Next.js App Router and React pages for job seekers and recruiters. It calls the FastAPI JSON API at `NEXT_PUBLIC_API_URL` and stores the signed-in session token in browser storage.
- **Backend:** FastAPI routers for authentication, users, jobs, applications, and screening questions. Authorization is checked on the backend for every candidate and recruiter resource.
- **Persistence:** SQLAlchemy models for users, jobs, applications, job questions, application answers, and audit logs. SQLite is the unchanged local default. MySQL 8.4 is an optional dialect through PyMySQL; PostgreSQL remains supported through psycopg.
- **Resume processing:** PyMuPDF and python-docx extract PDF/DOCX text. Direct contact details and profile links are redacted before an external LLM parses role-relevant data. Matching removes legacy parsed identity fields before sending the resume profile to the LLM.
- **Integrity services:** A RapidAPI AI-generated-content detector estimates writing authorship separately from Smodin web-source similarity. The two reports stay separate in the recruiter view.
- **Notifications:** Resend sends application and recruiter status notifications when configured.

## Database model

The existing six-table schema is retained so the current SQLite database needs no destructive reset:

| Table | Purpose |
|---|---|
| `users_data` | Candidate and recruiter accounts, profile and parsed resume |
| `jobs_data` | Recruiter-owned job posts |
| `applications` | Candidate/job relationship, screening answers, scores and status |
| `job_questions` | Recruiter-defined screening questions and optional answer keys |
| `application_answers` | Additional legacy skill-test answers |
| `audit_logs` | Recruiter actions and application lifecycle events |

SQLite and MySQL are configured by `DATABASE_URL`. Switching that URL selects a separate database; it does not copy the SQLite rows. The app uses `create_all` for missing tables and does not drop existing tables.

## Access and privacy boundaries

- Candidates can read and update their own profile and applications only.
- Recruiters can review applications only for jobs they own.
- Recruiter candidate lists default to pseudonymous identifiers and redact direct identity fields and profile links.
- Revealing applicant identity and downloading a resume require an explicit recruiter action and create audit entries.
- Applicant screening answers and integrity reports are visible only to the applicant and their job-owning recruiter; integrity results and internal flags are omitted from candidate responses.
- Resume upload through the application API is blocked until the answer-integrity gate clears. The legacy profile upload path is disabled and points to the application-scoped flow.
- CSV exports omit identity by default, exclude flagged applications, cap exports at 500 rows, and escape spreadsheet formula prefixes.

## Matching and human decisions

The AI detector estimates likely AI-writing patterns; web-source similarity reports overlap with indexed web content. Neither can prove who wrote an answer. AI detector results do not share a field or score with web similarity. Match-analysis originality remains a separate estimate. Any routing signal creates a recruiter review task; it does not automatically reject or delete an applicant.

## Optional services

Groq enables resume parsing and match analysis. RapidAPI enables AI-writing and web-similarity checks. Resend enables transactional email. Each integration can be disabled by leaving its credentials unset. Integrity provider failures are recorded and routed to manual review; unavailable matching does not prevent an application from being saved.
