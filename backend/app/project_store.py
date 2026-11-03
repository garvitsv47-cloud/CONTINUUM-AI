import os
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class ProjectStoreError(Exception):
    pass


class ProjectStoreConfigurationError(ProjectStoreError):
    pass


class ProjectStore:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url

    def _connection(self):
        database_url = self.database_url or os.getenv("DATABASE_URL")
        if not database_url:
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
            raise ProjectStoreError("Unable to save the project.") from error

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
            raise ProjectStoreError("Unable to load projects.") from error

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
            raise ProjectStoreError("Unable to load the project.") from error

    def update_status(self, project_id: str, status: str) -> None:
        try:
            with self._connection() as connection:
                connection.execute(
                    "UPDATE public.projects SET status = %s WHERE id = %s",
                    (status, project_id),
                )
        except psycopg.Error as error:
            raise ProjectStoreError("Unable to update project status.") from error

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
            raise ProjectStoreError("Unable to save project analysis.") from error

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
