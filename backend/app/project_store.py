import logging
import os
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


logger = logging.getLogger(__name__)


class ProjectStoreError(Exception):
    pass


class ProjectStoreConfigurationError(ProjectStoreError):
    pass


class _DatabaseDiagnostic(Exception):
    pass


def _database_error_category(error: psycopg.Error) -> str:
    sqlstate = getattr(error, "sqlstate", None) or ""
    if sqlstate.startswith("28"):
        return "authentication_failure"
    if sqlstate == "42501":
        return "permission_denied"
    if sqlstate == "42P01":
        return "missing_table"
    if isinstance(error, psycopg.errors.OperationalError):
        message = str(error).lower()
        if "ssl" in message or "certificate" in message:
            return "ssl_failure"
        return "network_or_connection_failure"
    if isinstance(error, psycopg.errors.ProgrammingError):
        return "sql_or_schema_error"
    return "database_error"


def _raise_database_error(operation: str, error: psycopg.Error, message: str) -> None:
    category = _database_error_category(error)
    logger.exception(
        "project store database operation failed",
        extra={"operation": operation, "category": category},
        exc_info=(type(error), _DatabaseDiagnostic(category), None),
    )
    raise ProjectStoreError(message) from error


class ProjectStore:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url

    def _connection(self):
        database_url = self.database_url or os.getenv("DATABASE_URL")
        if not database_url:
            logger.error(
                "project store database configuration failed",
                extra={"operation": "connect", "category": "missing_database_url"},
            )
            raise ProjectStoreConfigurationError(
                "Project persistence is unavailable because DATABASE_URL is not configured."
            )
        return psycopg.connect(database_url, sslmode="require", row_factory=dict_row)

    def create(self, project: dict[str, Any]) -> dict[str, Any]:
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    INSERT INTO public.projects
                        (id, name, description, repository_url, status, created_at)
                    VALUES (%(id)s, %(name)s, %(description)s, %(repository_url)s,
                            %(status)s, %(created_at)s)
                    RETURNING id, name, description, repository_url, status, created_at
                    """,
                    project,
                ).fetchone()
            return self._with_analysis(row)
        except psycopg.Error as error:
            _raise_database_error("create_project", error, "Unable to save the project.")

    def list(self) -> list[dict[str, Any]]:
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT p.id, p.name, p.description, p.repository_url, p.status,
                           p.created_at, a.analysis
                    FROM public.projects AS p
                    LEFT JOIN public.project_analyses AS a ON a.project_id = p.id
                    ORDER BY p.created_at DESC
                    """
                ).fetchall()
            return [self._normalize(row) for row in rows]
        except psycopg.Error as error:
            _raise_database_error("list_projects", error, "Unable to load projects.")

    def get(self, project_id: str) -> dict[str, Any] | None:
        try:
            with self._connection() as connection:
                row = connection.execute(
                    """
                    SELECT p.id, p.name, p.description, p.repository_url, p.status,
                           p.created_at, a.analysis
                    FROM public.projects AS p
                    LEFT JOIN public.project_analyses AS a ON a.project_id = p.id
                    WHERE p.id = %s
                    """,
                    (project_id,),
                ).fetchone()
            return self._normalize(row) if row else None
        except psycopg.Error as error:
            _raise_database_error("get_project", error, "Unable to load the project.")

    def update_status(self, project_id: str, status: str) -> None:
        try:
            with self._connection() as connection:
                connection.execute(
                    "UPDATE public.projects SET status = %s WHERE id = %s",
                    (status, project_id),
                )
        except psycopg.Error as error:
            _raise_database_error("update_project_status", error, "Unable to update project status.")

    def save_analysis(self, project_id: str, analysis: dict[str, Any]) -> None:
        try:
            with self._connection() as connection:
                connection.execute(
                    "UPDATE public.projects SET status = %s WHERE id = %s",
                    ("analyzed", project_id),
                )
                connection.execute(
                    """
                    INSERT INTO public.project_analyses (project_id, analysis, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (project_id) DO UPDATE
                    SET analysis = EXCLUDED.analysis, updated_at = NOW()
                    """,
                    (project_id, Jsonb(analysis)),
                )
        except psycopg.Error as error:
            _raise_database_error("save_project_analysis", error, "Unable to save project analysis.")

    def _with_analysis(self, row: dict[str, Any]) -> dict[str, Any]:
        result = self._normalize(row)
        result["analysis"] = None
        return result

    @staticmethod
    def _normalize(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        created_at = result.get("created_at")
        if isinstance(created_at, datetime):
            result["created_at"] = created_at.isoformat()
        return result
