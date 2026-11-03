# CONTINUUM AI

## Run locally

Start the API from `backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

Start the Vite app from `frontend`:

```powershell
npm run dev
```

The Vite proxy forwards `/api` requests to `http://127.0.0.1:8001`.

## MVP workflow

1. Open **Connect repository** from the overview.
2. Add a project name and GitHub URL.
3. Select **Reconstruct knowledge**.
4. Review the separate observed facts, interpretations, and verification items.

Projects are stored in backend memory for this hackathon MVP and reset when the API restarts.
