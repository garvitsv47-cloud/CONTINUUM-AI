# CONTINUUM AI

> **People Move On. Knowledge Moves Forward.**

**AI-Powered Engineering Knowledge Continuity & Developer Handover Platform**

Built by **IdeaOrbit** for the Round 2 hackathon submission.

CONTINUUM AI helps engineering teams turn repository structure, source files, documentation, and AI-assisted interpretation into a reviewable handover workspace. It is designed to make the difference between observed repository facts, AI interpretations, and items requiring human verification explicit.

## The problem

When engineers leave a project or ownership changes, important context often leaves with them. Architectural decisions may be undocumented, documentation may be stale, and the reasoning behind dependencies, risks, and conventions can be scattered across source code, commits, and repository files.

The result is a costly handover: new engineers must reconstruct how an unfamiliar system works before they can safely maintain it.

## Our solution

CONTINUUM AI connects to a public GitHub repository, indexes a bounded set of relevant source and documentation files, preserves line-numbered source references, and uses a structured Gemini analysis workflow to produce an engineering knowledge view.

The product separates:

- **Observed facts**: information directly obtained from repository metadata and files.
- **Interpretations**: AI-generated explanations grounded in the ingested evidence.
- **Verification items**: uncertain or consequential conclusions that a human should review.
- **Source evidence**: repository paths, line ranges, and excerpts supporting the workspace output.

The goal is not to replace engineering judgment. It is to give the next engineer a faster, evidence-backed starting point for review and handover.

## Live links

- **Frontend:** [continuum-ai-snowy.vercel.app](https://continuum-ai-snowy.vercel.app/)
- **Backend:** [continuum-ai-backend-azly.onrender.com](https://continuum-ai-backend-azly.onrender.com/)
- **GitHub:** [github.com/garvitsv47-cloud/CONTINUUM-AI](https://github.com/garvitsv47-cloud/CONTINUUM-AI)

## Features and implementation status

### Implemented and locally verified

- React project dashboard and overview pages.
- FastAPI backend with health and project APIs.
- Public GitHub repository URL validation.
- GitHub repository metadata and tree ingestion.
- Archive fallback when the GitHub API is rate-limited.
- File filtering, size limits, excluded directories, and secret-file exclusions.
- Line-numbered source excerpts and repository evidence references.
- Structured Gemini analysis integration with Pydantic validation.
- Evidence-path validation to reject AI references to files outside the ingested repository.
- Bounded retry handling for transient Gemini errors (`429`, `500`, `502`, `503`, and `504`).
- PostgreSQL project and analysis persistence implementation using psycopg 3.
- Restoration of projects and completed analyses after backend reinitialization.
- Separate observed facts, interpretations, verification items, risks, dependencies, and knowledge gaps.
- Report copy and print actions for completed analyses.
- Frontend lint and production build.
- Backend automated tests, including ingestion, Gemini error handling, persistence, and safe database diagnostics.

### Implemented but not fully verified in production

- Supabase-compatible PostgreSQL persistence through `DATABASE_URL`.
  The deployed backend currently returns HTTP 503 for `GET /api/projects/` because the production database connection is failing. Safe diagnostic logging has been deployed so the Render logs can identify the failure category; live database recovery is not claimed here.
- End-to-end Gemini analysis in the deployed Render environment.
  The integration code and local tests are present, but a real production analysis request has not been verified end to end.
- Production persistence of completed analysis results.
  The database schema and storage code are implemented, but this depends on resolving the production PostgreSQL connection.

### Demo-only functionality

- **DEMO MODE** on the Projects page.
- Demo project metadata is saved in browser `localStorage` and survives refreshes in that browser.
- Demo projects are visibly labeled **DEMO ONLY**.
- Demo projects are not reported as saved to Supabase.
- Demo projects cannot run repository ingestion or Gemini analysis; no fabricated analysis or evidence is shown.

### Planned features

These are not presented as implemented:

- Authentication, project ownership, and team/workspace access controls.
- Private GitHub repository support and GitHub authorization.
- A complete review/approval workflow for handover claims.
- Handover report export and sharing controls.
- Change-aware re-indexing and stale-knowledge detection.
- Production-grade observability and database health dashboards.

## How it works

The intended product workflow is:

**CONNECT -> RECONSTRUCT -> VERIFY -> REVIEW -> HANDOVER**

1. **CONNECT** — enter a public GitHub repository URL and project context.
2. **RECONSTRUCT** — implemented repository ingestion selects bounded source and documentation files; the Gemini integration can create a structured analysis from those excerpts.
3. **VERIFY** — implemented output distinguishes observed facts, interpretations, verification items, and source evidence.
4. **REVIEW** — the current UI presents architecture, modules, dependencies, risks, knowledge gaps, and evidence for human review. Formal approval states are planned.
5. **HANDOVER** — the current UI supports reviewing, copying, and printing an analysis. A richer export and team handover workflow is planned.

If the backend database is unavailable, the frontend remains usable in DEMO MODE for project metadata only. It does not simulate repository analysis.

## Technical architecture

```text
React + Vite frontend
        |
        | /api rewrite in development and Vercel
        v
FastAPI backend
   |              |
   |              +--> GitHub public repository ingestion
   |
   +--> Gemini structured analysis
   |
   +--> PostgreSQL / Supabase persistence
```

### Frontend

- React 19
- TypeScript
- Vite
- Tailwind CSS v4
- React Router
- Lucide React
- Vercel deployment with API rewrites and SPA fallback

### Backend

- Python 3.12 development target
- FastAPI
- Pydantic v2
- Uvicorn
- psycopg 3 with binary support
- Google Gemini REST API integration
- Python standard-library HTTP clients for GitHub and Gemini requests

### Persistence

The backend uses these existing PostgreSQL tables:

- `public.projects`
  - `id`, `name`, `description`, `repository_url`, `status`, `created_at`
- `public.project_analyses`
  - `project_id`, JSONB `analysis`, `updated_at`

The frontend never receives `DATABASE_URL` or database credentials. The current deployment issue is database connectivity, not a local-storage replacement for production persistence.

## API surface

The FastAPI application exposes:

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/` | Backend welcome/status response |
| `GET` | `/api/health` | Health response that does not require the database |
| `GET` | `/api/projects/` | List persisted projects and saved analyses |
| `POST` | `/api/projects/` | Validate and create a project |
| `POST` | `/api/projects/{project_id}/analyze` | Ingest the repository and run structured analysis |

The frontend normalizes API paths to avoid trailing-slash redirect problems in production. Vercel rewrites API requests to the Render backend and routes non-API paths to the SPA entry point.

## Run locally

### Prerequisites

- Node.js and npm
- Python 3.12
- A backend virtual environment
- Optional: Gemini and PostgreSQL credentials for live integrations

### Start the backend

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

### Configure the backend

Copy the safe template and set secrets outside source control:

```text
GEMINI_API_KEY=<your Gemini API key>
GEMINI_MODEL=gemini-3.6-flash
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<database>?sslmode=require
CORS_ORIGINS=http://127.0.0.1:5174,http://localhost:5174
```

The backend template is [backend/.env.example](backend/.env.example). Never commit a real `.env` file, API key, or database URL.

### Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

The Vite development proxy forwards `/api` requests to `http://127.0.0.1:8001`. The normal local frontend is available at `http://127.0.0.1:5174`.

### Validate locally

```powershell
cd frontend
npm run lint
npm run build
```

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Demo walkthrough

1. Open the frontend and go to **Projects**.
2. If project storage is available, use **Connect repository** and enter a public GitHub URL such as `https://github.com/tiangolo/fastapi`.
3. If storage is unavailable, select **Try DEMO MODE** or enable **DEMO MODE** in the project form.
4. Enter a project name and repository URL.
5. Save the demo project. It will remain in this browser and be labeled **DEMO ONLY**.
6. For a real project, use **Reconstruct knowledge** only when the backend, PostgreSQL, GitHub access, and Gemini configuration are available.

Demo mode is intentionally honest: it demonstrates the dashboard and project workflow, but it does not invent repository findings or claim persistence in Supabase.

## Security and scope notes

- Only public HTTPS `github.com` repository URLs are accepted.
- The ingestor excludes common build directories, binary files, environment files, and private key filenames.
- Repository file and archive sizes are bounded.
- Gemini credentials are backend-only.
- Database credentials are backend-only.
- The current MVP does not implement user authentication or project ownership. Persistent project endpoints should not be treated as suitable for private or multi-tenant data until access control is added.
- DEMO MODE stores metadata in the browser's local storage and should not be used for confidential project information.

## Current limitations

- Production PostgreSQL connectivity is currently failing; the public health endpoint can still return 200 because it does not query the database.
- Gemini production access and a complete live analysis flow remain unverified.
- Only public GitHub repositories are supported.
- No user authentication, private repository access, or tenant isolation is implemented.
- Demo projects are browser-local metadata only and cannot be analyzed.

## Repository guide

```text
backend/
  app/main.py              FastAPI app, CORS, and health route
  app/projects.py          Project and analysis API routes
  app/github_ingestion.py  Public GitHub ingestion and evidence excerpts
  app/gemini_analysis.py   Structured Gemini request and validation workflow
  app/project_store.py     PostgreSQL persistence and diagnostics
  tests/                   Backend automated tests

frontend/
  src/pages/Projects.tsx   Project workspace, API loading, and DEMO MODE
  src/pages/Dashboard.tsx  Overview metrics
  src/lib/api.ts           API URL normalization and response parsing
  vercel.json              API rewrites and SPA fallback
```

