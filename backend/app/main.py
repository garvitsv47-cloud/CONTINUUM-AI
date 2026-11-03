import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.projects import router as projects_router


def _configured_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "")
    origins = [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    return origins or [
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]


app = FastAPI(
    title="CONTINUUM AI",
    description="AI-powered developer knowledge handover platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def home():
    return {
        "message": "Welcome to CONTINUUM AI",
        "status": "Backend is running successfully"
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "CONTINUUM AI",
        "message": "Frontend and backend connection ready"
    }


app.include_router(projects_router)
