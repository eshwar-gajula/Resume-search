# Backend

The backend is a FastAPI service using SQLAlchemy. Follow the root [README](../README.md) for the complete Windows setup and candidate/recruiter workflow.

## Manual setup

From the project folder:

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Replace `JWT_SECRET` with at least 32 random characters if you copied the example manually. Keep `DATABASE_URL=sqlite:///./resume_search.db` to preserve the existing local SQLite database. The default relative path resolves inside `backend` when the API runs from this folder.

Start the API:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

The API docs are at `http://127.0.0.1:8010/docs` and its database health check is at `http://127.0.0.1:8010/health`.

## Database options

SQLite is the local default. MySQL 8.4 works with a `mysql+pymysql://...` SQLAlchemy URL; see the root [README](../README.md#mysql-optional) and `../deploy/docker-compose.mysql.yml`. PostgreSQL URLs are also accepted through the installed psycopg driver. Changing `DATABASE_URL` selects a different database; the app does not migrate SQLite rows automatically.

## Optional integrations

- `GROQ_API_KEY` enables resume parsing and match analysis.
- `RAPIDAPI_KEY` enables Smodin web-source similarity and is reused for the RapidAPI AI-writing detector unless `RAPIDAPI_AI_DETECTOR_KEY` is set.
- `EMAIL_ENABLED=true`, `RESEND_API_KEY`, and `RESEND_FROM_EMAIL` enable Resend notifications.

Provider results remain separate: AI-writing is an estimate, web similarity measures source overlap, and match originality is a separate LLM signal. A concerning, inconclusive, or unavailable answer check routes to recruiter manual review. No automated signal proves authorship or rejects an applicant.
