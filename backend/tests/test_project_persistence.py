import unittest
from unittest.mock import patch

import psycopg

from app.projects import (
    Analysis,
    ProjectCreate,
    configure_project_store,
    create_project,
    list_projects,
    _analyze_project,
)
from app.project_store import (
    ProjectStore,
    ProjectStoreConfigurationError,
    ProjectStoreError,
    _database_error_category,
)


class FakeProjectStore:
    def __init__(self, shared=None, analyses=None):
        self.projects = shared if shared is not None else {}
        self.analyses = analyses if analyses is not None else {}

    def create(self, project):
        self.projects[project["id"]] = dict(project)
        return {**project, "analysis": None}

    def list(self):
        return [
            {**project, "analysis": self.analyses.get(project_id)}
            for project_id, project in self.projects.items()
        ]

    def get(self, project_id):
        project = self.projects.get(project_id)
        if project is None:
            return None
        return {**project, "analysis": self.analyses.get(project_id)}

    def update_status(self, project_id, project_status):
        self.projects[project_id]["status"] = project_status

    def save_analysis(self, project_id, analysis):
        self.projects[project_id]["status"] = "analyzed"
        self.analyses[project_id] = analysis


class FakeDbConnection:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return self.rows.pop(0)

    def fetchall(self):
        return self.rows


class ProjectPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.shared_projects = {}
        self.shared_analyses = {}
        self.store = FakeProjectStore(self.shared_projects, self.shared_analyses)
        configure_project_store(self.store)

    def tearDown(self):
        configure_project_store(FakeProjectStore())

    def test_create_list_and_reinitialize_storage(self):
        created = create_project(ProjectCreate(
            name="Persistent demo",
            description="handover",
            repository_url="https://github.com/tiangolo/fastapi",
        ))["project"]

        self.assertEqual(list_projects()["projects"][0].id, created.id)

        reinitialized_store = FakeProjectStore(self.shared_projects, self.shared_analyses)
        configure_project_store(reinitialized_store)
        restored = list_projects()["projects"][0]
        self.assertEqual(restored.id, created.id)
        self.assertEqual(restored.repository_url, created.repository_url)

    def test_analysis_is_saved_and_restored(self):
        created = create_project(ProjectCreate(
            name="Analyzed demo",
            repository_url="https://github.com/tiangolo/fastapi",
        ))["project"]

        class Context:
            owner = "tiangolo"
            name = "fastapi"
            default_branch = "master"
            description = "web framework"
            stars = 1
            languages = ["Python"]
            truncated = False
            files = []

            @staticmethod
            def excerpts():
                return []

        class Ingestor:
            @staticmethod
            def ingest(_url):
                return Context()

        class AnalyzerResult:
            architecture_summary = "A web service."
            modules = []
            dependencies = []
            risks = []
            knowledge_gaps = []
            interpretations = []
            verification_items = []

        class Analyzer:
            @staticmethod
            def analyze(_context):
                return AnalyzerResult()

        analysis = _analyze_project(created.id, Ingestor(), Analyzer())
        self.assertIsInstance(analysis, Analysis)

        configure_project_store(FakeProjectStore(self.shared_projects, self.shared_analyses))
        restored = list_projects()["projects"][0]
        self.assertEqual(restored.status, "analyzed")
        self.assertEqual(restored.analysis["architecture_summary"], "A web service.")

    def test_invalid_project_id_is_reported(self):
        from fastapi import HTTPException
        from app.projects import _find_project

        with self.assertRaisesRegex(HTTPException, "Project not found"):
            _find_project("missing")

    def test_database_configuration_failure_is_explicit(self):
        with self.assertLogs("app.project_store", level="ERROR") as logs:
            with self.assertRaisesRegex(ProjectStoreConfigurationError, "DATABASE_URL"):
                ProjectStore(database_url="").list()
        self.assertEqual(logs.records[0].category, "missing_database_url")

    def test_database_store_uses_parameterized_queries(self):
        row = {
            "id": "project-1",
            "name": "Demo",
            "description": "",
            "repository_url": "https://github.com/tiangolo/fastapi",
            "status": "connected",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        connection = FakeDbConnection([row])
        with patch("app.project_store.psycopg.connect", return_value=connection):
            stored = ProjectStore("postgresql://test").create(row)

        self.assertEqual(stored["id"], "project-1")
        self.assertIn("VALUES (%(id)s", connection.calls[0][0])
        self.assertEqual(connection.calls[0][1]["id"], "project-1")

    def test_database_errors_are_classified_without_connection_details(self):
        self.assertEqual(
            _database_error_category(psycopg.OperationalError("connection refused")),
            "network_or_connection_failure",
        )
        self.assertEqual(
            _database_error_category(psycopg.OperationalError("SSL certificate verify failed")),
            "ssl_failure",
        )
        self.assertEqual(
            _database_error_category(psycopg.errors.InsufficientPrivilege()),
            "permission_denied",
        )

    def test_database_failure_is_logged_and_returns_generic_error(self):
        error = psycopg.OperationalError("password=secret host=db.example")
        with patch("app.project_store.psycopg.connect", side_effect=error), self.assertLogs(
            "app.project_store",
            level="ERROR",
        ) as logs:
            with self.assertRaisesRegex(ProjectStoreError, "Unable to load projects"):
                ProjectStore("postgresql://redacted").list()

        self.assertIn("network_or_connection_failure", logs.output[0])
        self.assertNotIn("password=secret", logs.output[0])
        self.assertNotIn("db.example", logs.output[0])


if __name__ == "__main__":
    unittest.main()
