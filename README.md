# ResumeAI

ResumeAI is a job application and recruiter review system built with Next.js, FastAPI, and SQLAlchemy. It supports candidate and recruiter accounts, job posts and screening questions, pre-resume integrity checks, PDF/DOCX resume parsing, candidate matching, recruiter search, bulk shortlisting, audit logs, and application notifications.

## Requirements

- Windows 10/11
- Python 3.12 (64-bit)
- Node.js 20.9 or newer with npm
- Internet access for package installation and any enabled external provider
- SQLite is the default database. MySQL 8.4 is supported as an optional database.

Groq, RapidAPI, and Resend credentials are optional integrations. The app starts without them; an unavailable integrity provider sends a screened application to recruiter manual review.

## Quick setup on Windows

Open PowerShell in the project folder and run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

Setup creates a backend virtual environment, installs dependencies, creates `backend\.env` only if it does not exist, and installs frontend packages. Existing environment files, database, and uploads are preserved.

Start the backend and frontend in separate PowerShell windows:

```powershell
.\start-backend.ps1
```

```powershell
.\start-frontend.ps1
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). The API and interactive docs are at [http://127.0.0.1:8010](http://127.0.0.1:8010) and [http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs). Check database connectivity at [http://127.0.0.1:8010/health](http://127.0.0.1:8010/health).

## Manual setup

From the project folder:

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
$secret = & backend\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
$envText = Get-Content backend\.env -Raw
$envText = $envText -replace '(?m)^JWT_SECRET=.*$', "JWT_SECRET=$secret"
[IO.File]::WriteAllText((Join-Path (Get-Location) 'backend\.env'), $envText, [Text.UTF8Encoding]::new($false))
```

Run the backend from its folder so the relative SQLite and upload paths resolve consistently:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

In another PowerShell window:

```powershell
Set-Location frontend
npm ci
npm run dev -- --hostname 127.0.0.1
```

## Database setup

### SQLite (default)

`DATABASE_URL=sqlite:///./resume_search.db` stores the current database at `backend\resume_search.db` when the backend is started from `backend`. Startup creates any missing tables and leaves existing rows in place. Keep the default URL to continue using the database and applicant data already in this project.

### MySQL (optional)

The app also supports MySQL 8.4. From the project folder, create a local Compose environment file and edit both passwords:

```powershell
Copy-Item deploy\.env.mysql.example deploy\.env.mysql
```

Start only the local MySQL service:

```powershell
docker compose --env-file deploy/.env.mysql -f deploy/docker-compose.mysql.yml up -d mysql
```

Set `DATABASE_URL` in `backend\.env` to the `mysql+pymysql://...` value from `deploy\.env.mysql`, using the application password. URL-encode reserved characters in the password. Restart the backend after changing it. MySQL uses a separate database and does not copy rows from SQLite; the existing SQLite database remains unchanged.

## Optional integrations

### Resume parsing and matching

Set `GROQ_API_KEY` in `backend\.env` to enable Groq resume parsing and match analysis. `LLM_MODEL` defaults to `openai/gpt-oss-120b`. Resume contact details and profile links are redacted before parsing requests; legacy parsed identity fields are stripped before matching requests. Without a Groq key, the uploaded PDF/DOCX is retained, but automatic parsing and match scores are unavailable.

### AI and web-source checks

`RAPIDAPI_KEY` is used for Smodin web-source similarity and, by default, the separate AI-generated-content detector. Subscribe the same RapidAPI app to each API plan you want to use. The AI Generated Content Detector lists a BASIC plan, but the app must still be subscribed and subject to that plan's quota and terms. Set `RAPIDAPI_AI_DETECTOR_KEY` only when the detector uses another RapidAPI app key. The detector returns a probabilistic AI-writing signal; it cannot prove authorship.

On an application with screening answers, a likely-AI signal, high web similarity, insufficient text, an unavailable provider, or an inconclusive result routes the application to the recruiter-only manual-review queue. Applicants do not choose or declare whether they used AI. Recruiters review the answer and context before approving or rejecting. A separate match-analysis originality estimate below 40 also routes an application to review.

### Email notifications

Email is disabled by default. Configure `EMAIL_ENABLED=true`, `RESEND_API_KEY`, and a verified `RESEND_FROM_EMAIL` to send application and status messages.

## First-use workflow

1. Register a recruiter account, post a job, and add screening questions. Use free-text questions for AI-writing checks.
2. Register a job-seeker account and browse active jobs.
3. Answer the job’s required screening questions and submit the application. Free-text answers are sent to the enabled AI detector and web-similarity provider after the application is saved.
4. If checks clear and the candidate has no existing resume, the app asks them to upload a PDF or DOCX (up to 10 MB). Resume parsing and matching happen after the screening gate. A LinkedIn profile export saved as PDF can be uploaded here; the app does not scrape LinkedIn.
5. Recruiters review applications, search by pasted job description or keywords, filter candidates, shortlist and invite in bulk, and export a CSV. Applicant names/contact data are hidden by default; a recruiter must explicitly reveal identity, and the reveal is audit-logged.
6. Flagged applications stay out of ordinary status actions until a recruiter manually approves them back to Pending or rejects the application. Flags and integrity results are never shown in the candidate view, and no automated signal deletes or automatically rejects a candidate.

## Audit and privacy

Recruiter actions, status decisions, candidate identity reveals, resume downloads, bulk actions, exports, and searches are recorded in `audit_logs`. Recruiter application responses are anonymized by default. Resume downloads require an owned application and an explicit identity reveal. Candidate and recruiter APIs enforce application and job ownership.

## Useful files

- `DATA_FLOW.md` — end-to-end candidate and recruiter workflow
- `ARCHITECTURE.md` — components, integrations, and database choices
- `API_ENDPOINTS.md` — API contract and access rules
- `backend/.env.example` — local configuration template
- `deploy/docker-compose.mysql.yml` — optional local MySQL

## Verification

From the project folder:

```powershell
backend\.venv\Scripts\python.exe -m compileall -q backend\app backend\tests
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
npm run build
```

The health endpoint confirms the selected database connection; it does not validate external API keys. Provider checks must be verified separately using synthetic text.

## Troubleshooting

- If `py -3.12` fails, install Python 3.12 (64-bit) and ensure the Python launcher is available.
- If npm reports a Node version error, install Node.js 20.9 or newer and reopen PowerShell.
- If the browser cannot reach the API, start the backend and check `http://127.0.0.1:8010/health`.
- If port 8010 is in use, set `RESUMEAI_API_PORT` before running `start-backend.ps1` and update `NEXT_PUBLIC_API_URL` in `frontend\.env.local`.
- If an existing JWT secret is too short, replace it with a random secret of at least 32 characters and restart the backend.
- If RapidAPI returns a provider error, verify that the RapidAPI app is subscribed to the matching API and that the request quota has not been reached.
