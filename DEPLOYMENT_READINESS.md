# CONTINUUM AI Deployment Readiness

## Current assessment

**Status: READY FOR CONFIGURED HACKATHON DEPLOYMENT, WITH LIVE GEMINI AND BACKEND HOSTING CONFIGURATION REQUIRED.**

The application builds and the existing local API workflow is intact. Projects are currently stored in process memory, so this is suitable for a demo but not production persistence.

## Checks

| Area | Status | Result |
|---|---|---|
| Git status | PASS | Repository is uncommitted/local-only and contains no tracked history yet. Review `git status` before the first commit. |
| Frontend build | PASS | `npm run build` passes. |
| Frontend lint | PASS | `npm run lint` passes. |
| Backend tests | PASS | `python -m unittest discover -s tests -v` passes. |
| Backend syntax | PASS | Application modules compile with `python -m py_compile`. |
| Local API health | PASS | `GET /api/health` returns 200 on port 8001. |
| API contracts | PASS | Frontend uses `/api/projects/`, `POST /api/projects/`, and `POST /api/projects/{id}/analyze`; these routes remain unchanged. |
| Local proxy | PASS | Vite uses port 5174 and proxies `/api` to `http://127.0.0.1:8001`. |
| Production API routing | PASS | Frontend uses `VITE_API_URL` when configured; otherwise it uses the local relative `/api` path. |
| SPA deep links | PASS | `frontend/vercel.json` rewrites routes such as `/projects` to `index.html`. |
| CORS | PASS | FastAPI reads comma-separated `CORS_ORIGINS`, with local defaults and no credential sharing. |
| Secret exposure | PASS | Gemini is read only by the backend environment. No frontend reference to `GEMINI_API_KEY` exists. |
| Ignore rules | PASS | `.env`, virtual environments, `node_modules`, build output, caches, keys, and local tooling are ignored. |
| GitHub ingestion | PASS | Public GitHub URL validation, source ingestion, file limits, exclusions, and evidence generation are implemented and tested. |
| Gemini live analysis | REQUIRE CONFIGURATION | Integration and mocked tests exist, but a real `GEMINI_API_KEY` is required for a live request. |
| Persistence | DEMO LIMITATION | Projects reset when the backend process restarts. |
| Auth/private repositories | NOT IMPLEMENTED | Only public GitHub repositories are supported. |

## Required deployment environment variables

### Vercel frontend

Set:

```text
VITE_API_URL=https://<your-backend-domain>
```

Use the backend origin only, without `/api`. Vite exposes only variables prefixed with `VITE_` to browser code.

### FastAPI backend

Set:

```text
GEMINI_API_KEY=<real Gemini API key>
CORS_ORIGINS=https://<your-vercel-domain>
```

For a preview deployment, include each exact allowed origin as a comma-separated value:

```text
CORS_ORIGINS=https://continuum-ai.vercel.app,https://preview-name.vercel.app
```

Never put `GEMINI_API_KEY` in Vercel or frontend environment variables.

## Deployment instructions

### Frontend on Vercel

1. Import the repository into Vercel.
2. Set **Root Directory** to `frontend`.
3. Keep the framework preset as Vite.
4. Set `VITE_API_URL` to the deployed FastAPI origin.
5. Deploy.
6. Verify `/` and `/projects` directly; `frontend/vercel.json` handles SPA routing.

### Backend

From the `backend` directory, install and start:

```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Set `GEMINI_API_KEY` and `CORS_ORIGINS` in the backend provider's secret/environment settings, not in source control.

Verify:

```text
GET https://<your-backend-domain>/api/health
```

## Remaining blockers

- Configure and live-test `GEMINI_API_KEY`.
- Deploy a backend with a stable public HTTPS origin.
- Set the exact deployed frontend origin in `CORS_ORIGINS`.
- Replace in-memory project storage before treating the service as production-grade.
- Add authentication and private repository support if required.
