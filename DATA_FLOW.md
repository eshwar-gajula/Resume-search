# ResumeAI Data Flow

## Candidate application

1. A candidate creates an account, browses active jobs, and opens a job’s screening questions.
2. The candidate answers required questions and submits the application. The API validates ownership, job state, question IDs, required answers, answer sizes, and multiple-choice selections, then saves the application and answers before calling external checks.
3. Free-text answers are checked by two separate providers: the RapidAPI AI-writing detector and the RapidAPI web-source similarity checker. Multiple-choice selections are excluded from text checks.
4. The application enters recruiter-only manual review when the AI service reports likely AI text or cannot classify it, when web similarity is above its threshold, or when either check is insufficient, unconfigured, or unavailable. This is a review route, not a finding of misconduct. The candidate sees a generic application status and cannot see the flag, provider verdict, or reason.
5. If checks clear, the candidate uploads a PDF/DOCX resume if one is not already on file. The backend extracts text, masks contact details and profile links before sending it to the LLM, stores the parsed profile, then calculates a job match score.
6. A match-analysis originality estimate below 40 also routes the application to manual review. This estimate remains distinct from the RapidAPI AI-writing verdict and web-source overlap.
7. Candidates can see their own application status and any remaining resume step. They cannot self-declare AI use or change internal review status.

## Recruiter review

1. The recruiter sees only applications for jobs they own. The default view uses a per-application label and omits names, email, phone, location, and profile links.
2. The recruiter can review submitted answers, AI-writing estimate, web-source similarity, match-analysis originality, resume-derived qualifications, and routing reasons.
3. The recruiter may explicitly reveal applicant identity. That event is written to `audit_logs`. A resume download also requires an owned application, identity reveal, and a separate audit event.
4. A recruiter approves a flagged application to return it to Pending, or rejects the application after human review. Approval leaves the candidate’s existing data intact; rejection does not delete the account or application.
5. Normal status changes and bulk shortlist/invite actions are blocked for flagged applications. Shortlisting is also blocked while a resume step is still outstanding.
6. Recruiters can search their applications using BM25-style text ranking over job, skills, experience, and answers, apply filters, bulk shortlist and invite up to 100 candidates, and export non-flagged records to CSV. Identity is omitted from CSV unless explicitly requested; identity-bearing exports are audit-logged.

## Notifications and audit

Resend sends application-received and status-update messages only when configured. Audit records cover application submission, status changes, manual flag decisions, recruiter searches, identity reveal, resume downloads, and bulk shortlist/export actions. Audit metadata avoids writing applicant answer text or credentials.

## Provider and fairness limits

The AI-writing detector is a probabilistic classifier; it can produce false positives and false negatives. “Human-written” is not proof either. Web similarity detects source overlap, not AI authorship. A missing or inconclusive provider result is routed to a recruiter because the configured checks could not clear the application. Recruiters must consider the full answer and context before deciding.
