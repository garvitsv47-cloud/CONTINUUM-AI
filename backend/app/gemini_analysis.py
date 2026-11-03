import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, ValidationError

from app.github_ingestion import RepositoryContext


DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_TIMEOUT_SECONDS = 45
MAX_PROMPT_CHARS = 120_000


class GeminiConfigurationError(Exception):
    pass


class GeminiRequestError(Exception):
    pass


class EvidenceReference(BaseModel):
    path: str
    lines: str


class ModuleExplanation(BaseModel):
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class DependencySummary(BaseModel):
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(default_factory=list)


class RiskSummary(BaseModel):
    title: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    requires_review: bool = True
    evidence: list[EvidenceReference] = Field(default_factory=list)


class GeminiRepositoryAnalysis(BaseModel):
    architecture_summary: str = Field(min_length=1)
    modules: list[ModuleExplanation] = Field(default_factory=list)
    dependencies: list[DependencySummary] = Field(default_factory=list)
    risks: list[RiskSummary] = Field(default_factory=list)
    knowledge_gaps: list[str] = Field(default_factory=list)
    interpretations: list[str] = Field(default_factory=list)
    verification_items: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class GeminiAnalyzer:
    api_key: str | None = None
    model: str | None = None
    opener: Any = urlopen

    def analyze(self, context: RepositoryContext) -> GeminiRepositoryAnalysis:
        key = self.api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise GeminiConfigurationError(
                "Gemini analysis is unavailable because GEMINI_API_KEY is not configured."
            )

        payload = {
            "contents": [{"parts": [{"text": self._prompt(context)}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        model = self.model or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
        endpoint = f"{GEMINI_ENDPOINT}/{quote(model, safe='')}:generateContent?key={quote(key)}"
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "continuum-ai/1.0",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=GEMINI_TIMEOUT_SECONDS) as response:
                raw = response.read(512 * 1024)
        except HTTPError as error:
            if error.code in {401, 403}:
                raise GeminiRequestError("Gemini rejected the configured API key.") from error
            if error.code == 429:
                raise GeminiRequestError("Gemini rate limit reached. Try again later.") from error
            if error.code == 404:
                raise GeminiRequestError(
                    f"Gemini model '{model}' is unavailable for generateContent."
                ) from error
            raise GeminiRequestError(f"Gemini request failed ({error.code}).") from error
        except (URLError, TimeoutError, OSError) as error:
            raise GeminiRequestError("Gemini could not be reached before the timeout.") from error

        try:
            response = json.loads(raw)
            text = response["candidates"][0]["content"]["parts"][0]["text"]
            result = GeminiRepositoryAnalysis.model_validate_json(self._clean_json(text))
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValidationError) as error:
            raise GeminiRequestError("Gemini returned an invalid structured analysis.") from error
        self._validate_evidence(result, context)
        return result

    @staticmethod
    def _clean_json(text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return cleaned

    @staticmethod
    def _validate_evidence(result: GeminiRepositoryAnalysis, context: RepositoryContext) -> None:
        known_paths = {item.path for item in context.files}
        references = [
            reference
            for module in result.modules
            for reference in module.evidence
        ]
        references.extend(
            reference
            for dependency in result.dependencies
            for reference in dependency.evidence
        )
        references.extend(
            reference
            for risk in result.risks
            for reference in risk.evidence
        )
        if any(reference.path not in known_paths for reference in references):
            raise GeminiRequestError("Gemini returned evidence for a file outside the ingested repository.")

    @staticmethod
    def _prompt(context: RepositoryContext) -> str:
        excerpts = json.dumps(context.excerpts(), ensure_ascii=True)
        excerpts = excerpts[:MAX_PROMPT_CHARS]
        return f"""Analyze only the repository evidence below. Do not invent files, dependencies, architecture, risks, or ownership.
Return JSON only with this exact shape:
{{
  "architecture_summary": "string",
  "modules": [{{"name":"string","purpose":"string","evidence":[{{"path":"real path","lines":"1-10"}}]}}],
  "dependencies": [{{"name":"string","purpose":"string","evidence":[{{"path":"real path","lines":"1-10"}}]}}],
  "risks": [{{"title":"string","detail":"string","requires_review":true,"evidence":[{{"path":"real path","lines":"1-10"}}]}}],
  "knowledge_gaps": ["string"],
  "interpretations": ["string"],
  "verification_items": ["string"]
}}
Any unsupported interpretation must be placed in verification_items or knowledge_gaps. Evidence paths must exactly match the supplied paths.
Repository: {context.owner}/{context.name}
Default branch: {context.default_branch}
Languages: {", ".join(context.languages)}
Evidence:
{excerpts}"""
