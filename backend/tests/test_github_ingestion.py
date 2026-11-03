import json
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError

from pydantic import ValidationError

from app.github_ingestion import (
    GitHubIngestor,
    RepositoryIngestionError,
    parse_github_url,
)
from app.gemini_analysis import (
    DEFAULT_GEMINI_MODEL,
    GeminiAnalyzer,
    GeminiConfigurationError,
    GeminiRequestError,
)
from app.projects import ProjectCreate, _analyze_project, configure_project_store, create_project


class TestProjectStore:
    def __init__(self):
        self.projects = {}

    def create(self, project):
        self.projects[project["id"]] = {**project, "analysis": None}
        return self.projects[project["id"]]

    def get(self, project_id):
        return self.projects.get(project_id)

    def update_status(self, project_id, status):
        self.projects[project_id]["status"] = status

    def save_analysis(self, project_id, analysis):
        self.projects[project_id]["status"] = "analyzed"
        self.projects[project_id]["analysis"] = analysis

    def list(self):
        return list(self.projects.values())


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        if isinstance(self.payload, str):
            return self.payload.encode("utf-8")
        return json.dumps(self.payload).encode("utf-8")


class GitHubIngestionTests(unittest.TestCase):
    def setUp(self):
        configure_project_store(TestProjectStore())

    @staticmethod
    def _gemini_context():
        context = Mock()
        context.owner = "example"
        context.name = "demo"
        context.default_branch = "main"
        context.languages = ["python"]
        context.files = [Mock(path="app/main.py")]
        context.excerpts.return_value = [{"path": "app/main.py", "lines": "1-2", "excerpt": "1: app"}]
        return context

    @staticmethod
    def _valid_gemini_payload():
        return {
            "candidates": [{
                "content": {"parts": [{"text": json.dumps({
                    "architecture_summary": "A small web service.",
                    "modules": [{"name": "app", "purpose": "Application entrypoint.", "evidence": [{"path": "app/main.py", "lines": "1-2"}]}],
                    "dependencies": [],
                    "risks": [],
                    "knowledge_gaps": [],
                    "interpretations": [],
                    "verification_items": [],
                })}]},
            }],
        }

    def test_valid_repository_is_ingested_with_line_numbered_evidence(self):
        files = {
            "README.md": "# FastAPI\n\nA web framework.",
            "pyproject.toml": "[project]\nname = 'demo'",
            "app/main.py": "from fastapi import FastAPI\n\napp = FastAPI()\n",
        }

        def opener(request, timeout=None):
            self.assertEqual(timeout, 15)
            url = request.full_url
            if url.endswith("/languages"):
                return FakeResponse({"Python": 100})
            if "/git/trees/" in url:
                return FakeResponse({
                    "tree": [
                        {"path": "README.md", "type": "blob", "sha": "sha0"},
                        {"path": "pyproject.toml", "type": "blob", "sha": "sha1"},
                        {"path": "app/main.py", "type": "blob", "sha": "sha2"},
                        {"path": "node_modules/pkg/index.js", "type": "blob", "sha": "skip1"},
                        {"path": ".env", "type": "blob", "sha": "skip2"},
                        {"path": "logo.png", "type": "blob", "sha": "skip3"},
                    ],
                    "truncated": False,
                })
            if "raw.githubusercontent.com" in url:
                path = url.split("/main/", 1)[1]
                return FakeResponse(files[path])
            return FakeResponse({
                "default_branch": "main",
                "description": "Demo repository",
                "stargazers_count": 10,
            })

        context = GitHubIngestor(opener).ingest("https://github.com/example/demo")
        self.assertEqual([item.path for item in context.files], [
            "README.md", "pyproject.toml", "app/main.py",
        ])
        self.assertIn("1: # FastAPI", context.excerpts()[0]["excerpt"])
        self.assertEqual(context.languages, ["Python"])

    def test_invalid_urls_are_rejected(self):
        for value in [
            "http://github.com/example/demo",
            "https://github.com/example/demo?token=secret",
            "https://github.com/example/demo/../../etc",
            "https://example.com/example/demo",
            "https://github.com:invalid/example/demo",
        ]:
            with self.subTest(value=value):
                with self.assertRaises(RepositoryIngestionError):
                    parse_github_url(value)
        with self.assertRaises(ValidationError):
            ProjectCreate(name="Demo", repository_url="https://example.com/demo")

    def test_unavailable_repository_is_reported(self):
        def opener(_request, timeout=None):
            error = Mock(code=404)
            from urllib.error import HTTPError
            raise HTTPError("url", 404, "not found", {}, None)

        with self.assertRaisesRegex(RepositoryIngestionError, "not found"):
            GitHubIngestor(opener).ingest("https://github.com/example/missing")

    def test_ingestion_failure_does_not_mark_analysis_ready(self):
        configure_project_store(TestProjectStore())
        project = ProjectCreate(
            name="Demo",
            description="",
            repository_url="https://github.com/example/demo",
        )
        created = create_project(project)["project"]

        class FailingIngestor:
            def ingest(self, _url):
                raise RepositoryIngestionError("upstream timeout")

        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            _analyze_project(created.id, FailingIngestor(), Mock())
        from app.projects import project_store
        self.assertEqual(project_store.get(created.id)["status"], "ingestion_failed")

    def test_gemini_response_is_validated_and_evidence_is_checked(self):
        configure_project_store(TestProjectStore())
        context = Mock()
        context.owner = "example"
        context.name = "demo"
        context.default_branch = "main"
        context.languages = ["python"]
        context.files = [Mock(path="app/main.py")]
        context.excerpts.return_value = [{"path": "app/main.py", "lines": "1-2", "excerpt": "1: app"}]
        payload = {
            "candidates": [{
                "content": {"parts": [{"text": json.dumps({
                    "architecture_summary": "A small web service.",
                    "modules": [{"name": "app", "purpose": "Application entrypoint.", "evidence": [{"path": "app/main.py", "lines": "1-2"}]}],
                    "dependencies": [],
                    "risks": [],
                    "knowledge_gaps": ["Deployment ownership is not documented."],
                    "interpretations": ["The service is Python-based."],
                    "verification_items": ["Confirm runtime configuration with the maintainer."],
                })}]},
            }],
        }

        requests = []
        result = GeminiAnalyzer(
            api_key="test-key",
            opener=lambda request, **_kwargs: (
                requests.append(request) or FakeResponse(payload)
            ),
        ).analyze(context)
        self.assertEqual(result.modules[0].evidence[0].path, "app/main.py")
        self.assertIn("Deployment", result.knowledge_gaps[0])
        self.assertIn(
            f"/models/{DEFAULT_GEMINI_MODEL}:generateContent",
            requests[0].full_url,
        )

    def test_gemini_model_404_is_reported_as_model_configuration_error(self):
        context = Mock()
        context.owner = "example"
        context.name = "demo"
        context.default_branch = "main"
        context.languages = []
        context.excerpts.return_value = []
        context.files = []

        def unavailable_model(_request, **_kwargs):
            raise HTTPError("url", 404, "not found", {}, None)

        with self.assertRaisesRegex(
            GeminiRequestError,
            "Gemini model 'retired-model' is unavailable",
        ):
            GeminiAnalyzer(
                api_key="test-key",
                model="retired-model",
                opener=unavailable_model,
            ).analyze(context)

    def test_gemini_retries_transient_503_then_succeeds(self):
        attempts = 0
        sleeps = []

        def opener(_request, **_kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise HTTPError("url", 503, "unavailable", {"Retry-After": "0"}, None)
            return FakeResponse(self._valid_gemini_payload())

        result = GeminiAnalyzer(
            api_key="test-key",
            opener=opener,
            sleeper=sleeps.append,
            jitter=lambda _low, _high: 0.0,
        ).analyze(self._gemini_context())
        self.assertEqual(result.architecture_summary, "A small web service.")
        self.assertEqual(attempts, 2)
        self.assertEqual(sleeps, [0.0])

    def test_gemini_exhausts_retries_for_repeated_503(self):
        attempts = 0
        sleeps = []

        def opener(_request, **_kwargs):
            nonlocal attempts
            attempts += 1
            raise HTTPError("url", 503, "unavailable", {}, None)

        with self.assertRaisesRegex(GeminiRequestError, "Gemini request failed \\(503\\)"):
            GeminiAnalyzer(
                api_key="test-key",
                opener=opener,
                sleeper=sleeps.append,
                jitter=lambda _low, _high: 0.0,
            ).analyze(self._gemini_context())
        self.assertEqual(attempts, 4)
        self.assertEqual(sleeps, [0.0, 0.0, 0.0])

    def test_gemini_does_not_retry_permanent_errors(self):
        for code in (400, 404):
            attempts = 0

            def opener(_request, status=code, **_kwargs):
                nonlocal attempts
                attempts += 1
                raise HTTPError("url", status, "permanent", {}, None)

            with self.subTest(code=code):
                with self.assertRaises(GeminiRequestError):
                    GeminiAnalyzer(
                        api_key="test-key",
                        model="retired-model",
                        opener=opener,
                        sleeper=lambda _delay: self.fail("permanent error was retried"),
                    ).analyze(self._gemini_context())
                self.assertEqual(attempts, 1)

    def test_gemini_rejects_malformed_response(self):
        with self.assertRaisesRegex(GeminiRequestError, "invalid structured analysis"):
            GeminiAnalyzer(
                api_key="test-key",
                opener=lambda *_args, **_kwargs: FakeResponse({"unexpected": "shape"}),
            ).analyze(self._gemini_context())

    def test_gemini_requires_credentials(self):
        with self.assertRaises(GeminiConfigurationError):
            GeminiAnalyzer(api_key="").analyze(Mock())

    def test_gemini_rejects_unknown_evidence(self):
        context = Mock()
        context.owner = "example"
        context.name = "demo"
        context.default_branch = "main"
        context.languages = []
        context.excerpts.return_value = []
        context.files = [Mock(path="README.md")]
        payload = {
            "candidates": [{"content": {"parts": [{"text": json.dumps({
                "architecture_summary": "Summary",
                "modules": [{"name": "bad", "purpose": "bad", "evidence": [{"path": "secret.txt", "lines": "1"}]}],
                "dependencies": [], "risks": [], "knowledge_gaps": [],
                "interpretations": [], "verification_items": [],
            })}]}}],
        }
        with self.assertRaises(GeminiRequestError):
            GeminiAnalyzer(api_key="test-key", opener=lambda *_args, **_kwargs: FakeResponse(payload)).analyze(context)


if __name__ == "__main__":
    unittest.main()
