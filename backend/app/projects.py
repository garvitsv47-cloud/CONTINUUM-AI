from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.github_ingestion import (
    GitHubIngestor,
    RepositoryIngestionError,
    parse_github_url,
)
from app.gemini_analysis import (
    GeminiAnalyzer,
    GeminiConfigurationError,
    GeminiRequestError,
)
from app.project_store import (
    ProjectStore,
    ProjectStoreConfigurationError,
    ProjectStoreError,
)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    repository_url: HttpUrl

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, value: HttpUrl) -> HttpUrl:
        try:
            parse_github_url(str(value))
        except RepositoryIngestionError as error:
            raise ValueError(str(error)) from error
        return value


class Project(BaseModel):
    id: str
    name: str
    description: str
    repository_url: str
    status: str
    created_at: str
    analysis: dict | None = None


class Analysis(BaseModel):
    project_id: str
    status: str
    observed_facts: list[str]
    interpretations: list[str]
    verification_items: list[str]
    evidence: list[dict[str, str]]
    repository_context: dict[str, object]
    architecture_summary: str
    modules: list[dict[str, object]]
    dependencies: list[dict[str, object]]
    risks: list[dict[str, object]]
    knowledge_gaps: list[str]
    analyzed_at: str


project_store: ProjectStore = ProjectStore()


def configure_project_store(store: ProjectStore) -> None:
    global project_store
    project_store = store


def _find_project(project_id: str) -> Project:
    try:
        stored_project = project_store.get(project_id)
    except ProjectStoreConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except ProjectStoreError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    if stored_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return Project.model_validate(stored_project)


@router.post("/")
def create_project(payload: ProjectCreate):
    project_data = {
        "id": str(uuid4()),
        "name": payload.name,
        "description": payload.description,
        "repository_url": str(payload.repository_url),
        "status": "connected",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        project = Project.model_validate(project_store.create(project_data))
    except ProjectStoreConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except ProjectStoreError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return {"message": "Project connected successfully", "project": project}


@router.get("/")
def list_projects():
    try:
        projects = [Project.model_validate(item) for item in project_store.list()]
    except ProjectStoreConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except ProjectStoreError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return {"projects": projects}


@router.post("/{project_id}/analyze", response_model=Analysis)
def analyze_project(project_id: str):
    return _analyze_project(project_id)


def _analyze_project(
    project_id: str,
    ingestor: GitHubIngestor | None = None,
    analyzer: GeminiAnalyzer | None = None,
):
    project = _find_project(project_id)
    try:
        context = (ingestor or GitHubIngestor()).ingest(project.repository_url)
    except RepositoryIngestionError as error:
        _persist_status(project.id, "ingestion_failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    try:
        ai_analysis = (analyzer or GeminiAnalyzer()).analyze(context)
    except GeminiConfigurationError as error:
        _persist_status(project.id, "analysis_unavailable")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except GeminiRequestError as error:
        _persist_status(project.id, "analysis_failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    manifest_names = {
        "Cargo.toml", "Gemfile", "go.mod", "package.json", "poetry.lock",
        "pom.xml", "pyproject.toml", "requirements.txt",
    }
    source_suffixes = {
        "c", "cpp", "cs", "go", "java", "js", "jsx", "kt", "php", "py",
        "rb", "rs", "sql", "swift", "ts", "tsx",
    }
    manifest_paths = [
        item.path for item in context.files if item.path.split("/")[-1] in manifest_names
    ]
    source_paths = [
        item.path for item in context.files
        if "." in item.path and item.path.rsplit(".", 1)[-1].lower() in source_suffixes
    ]
    analysis = Analysis(
        project_id=project.id,
        status="ready_for_review",
        observed_facts=[
            f"GitHub repository {context.owner}/{context.name} uses the {context.default_branch} default branch.",
            f"Ingested {len(context.files)} text files ({sum(item.size for item in context.files)} bytes) within safety limits.",
            f"Detected {len(source_paths)} source files and {len(manifest_paths)} dependency manifests.",
        ],
        interpretations=ai_analysis.interpretations,
        verification_items=ai_analysis.verification_items,
        evidence=context.excerpts(),
        repository_context={
            "repository": f"{context.owner}/{context.name}",
            "default_branch": context.default_branch,
            "description": context.description,
            "stars": context.stars,
            "languages": context.languages,
            "file_count": len(context.files),
            "truncated": context.truncated,
            "manifest_paths": manifest_paths,
            "source_paths": source_paths,
        },
        architecture_summary=ai_analysis.architecture_summary,
        modules=[item.model_dump() for item in ai_analysis.modules],
        dependencies=[item.model_dump() for item in ai_analysis.dependencies],
        risks=[item.model_dump() for item in ai_analysis.risks],
        knowledge_gaps=ai_analysis.knowledge_gaps,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        project_store.save_analysis(project.id, analysis.model_dump())
    except ProjectStoreConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except ProjectStoreError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return analysis


def _persist_status(project_id: str, project_status: str) -> None:
    try:
        project_store.update_status(project_id, project_status)
    except ProjectStoreConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except ProjectStoreError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
