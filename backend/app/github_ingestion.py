import json
import re
import zipfile
from io import BytesIO
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


MAX_FILES = 250
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 1 * 1024 * 1024
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 15
ALLOWED_HOSTS = {"github.com", "www.github.com"}
EXCLUDED_DIRECTORIES = {
    ".git",
    ".github",
    ".venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    "__pycache__",
}
EXCLUDED_SUFFIXES = {
    ".7z",
    ".avi",
    ".bin",
    ".bmp",
    ".class",
    ".dll",
    ".dmg",
    ".gif",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp3",
    ".mp4",
    ".o",
    ".pdf",
    ".png",
    ".pyc",
    ".so",
    ".tar",
    ".ttf",
    ".wav",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
}
SECRET_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
}
MANIFEST_NAMES = {
    "Cargo.toml",
    "Gemfile",
    "go.mod",
    "package.json",
    "poetry.lock",
    "pyproject.toml",
    "requirements.txt",
    "pom.xml",
}
SOURCE_SUFFIXES = {
    ".c",
    ".cpp",
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
}


class RepositoryIngestionError(Exception):
    """Raised when a public GitHub repository cannot be safely ingested."""


@dataclass(frozen=True)
class RepositoryFile:
    path: str
    content: str
    size: int

    @property
    def line_count(self) -> int:
        return self.content.count("\n") + (1 if self.content else 0)


@dataclass(frozen=True)
class RepositoryContext:
    owner: str
    name: str
    default_branch: str
    description: str
    stars: int
    languages: list[str]
    files: list[RepositoryFile]
    truncated: bool

    def excerpts(self) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        for repository_file in self.files:
            lines = repository_file.content.splitlines()
            excerpt_lines = lines[:20]
            numbered = "\n".join(
                f"{index}: {line[:240]}"
                for index, line in enumerate(excerpt_lines, start=1)
            )
            results.append(
                {
                    "path": repository_file.path,
                    "lines": f"1-{len(excerpt_lines)}",
                    "excerpt": numbered,
                }
            )
        return results


def parse_github_url(repository_url: str) -> tuple[str, str]:
    parsed = urlparse(repository_url.strip())
    try:
        port = parsed.port
    except ValueError as error:
        raise RepositoryIngestionError(
            "Only public HTTPS github.com repository URLs are supported."
        ) from error
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise RepositoryIngestionError(
            "Only public HTTPS github.com repository URLs are supported."
        )

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2 or any(
        not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts
    ):
        raise RepositoryIngestionError(
            "Repository URL must use the form https://github.com/owner/name."
        )
    return parts[0], parts[1].removesuffix(".git")


class GitHubIngestor:
    def __init__(self, opener=urlopen):
        self._opener = opener

    def ingest(self, repository_url: str) -> RepositoryContext:
        owner, name = parse_github_url(repository_url)
        base = f"https://api.github.com/repos/{owner}/{name}"
        try:
            metadata = self._get_json(base)
        except RepositoryIngestionError as error:
            if "403" in str(error):
                return self._ingest_archive(owner, name)
            raise
        default_branch = metadata.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            raise RepositoryIngestionError("GitHub repository has no default branch.")

        tree = self._get_json(f"{base}/git/trees/{default_branch}?recursive=1")
        entries = tree.get("tree")
        if not isinstance(entries, list):
            raise RepositoryIngestionError("GitHub returned an invalid repository tree.")

        selected = [
            entry
            for entry in entries
            if isinstance(entry, dict)
            and entry.get("type") == "blob"
            and self._is_allowed_path(str(entry.get("path", "")))
            and isinstance(entry.get("sha"), str)
        ]
        selection_truncated = len(selected) > MAX_FILES
        selected = selected[:MAX_FILES]
        files: list[RepositoryFile] = []
        total_bytes = 0
        for entry in selected:
            size = entry.get("size", 0)
            if not isinstance(size, int) or size > MAX_FILE_BYTES:
                continue
            content = self._get_raw_file(owner, name, default_branch, entry["path"])
            encoded_size = len(content.encode("utf-8"))
            if encoded_size > MAX_FILE_BYTES:
                continue
            if total_bytes + encoded_size > MAX_TOTAL_BYTES:
                break
            files.append(RepositoryFile(entry["path"], content, encoded_size))
            total_bytes += encoded_size

        if not files:
            raise RepositoryIngestionError("No readable source or documentation files found.")

        languages = self._get_languages(base)
        return RepositoryContext(
            owner=owner,
            name=name,
            default_branch=default_branch,
            description=str(metadata.get("description") or ""),
            stars=int(metadata.get("stargazers_count") or 0),
            languages=languages,
            files=files,
            truncated=bool(tree.get("truncated")) or selection_truncated or len(selected) > len(files),
        )

    def _ingest_archive(self, owner: str, name: str) -> RepositoryContext:
        page = self._get_text(f"https://github.com/{quote(owner)}/{quote(name)}")
        branch_match = re.search(r'"defaultBranch":"([^"]+)"', page)
        if not branch_match:
            raise RepositoryIngestionError("GitHub repository default branch was unavailable.")
        branch = branch_match.group(1)
        archive_url = (
            f"https://codeload.github.com/{quote(owner)}/{quote(name)}/zip/refs/heads/"
            f"{quote(branch, safe='')}"
        )
        archive = self._get_bytes(archive_url, MAX_ARCHIVE_BYTES)
        try:
            zip_file = zipfile.ZipFile(BytesIO(archive))
        except zipfile.BadZipFile as error:
            raise RepositoryIngestionError("GitHub returned an invalid repository archive.") from error

        entries = [
            item for item in zip_file.infolist()
            if not item.is_dir() and "/" in item.filename
        ]
        selected = [
            item for item in entries
            if self._is_allowed_path(item.filename.split("/", 1)[1])
        ]
        selection_truncated = len(selected) > MAX_FILES
        selected = selected[:MAX_FILES]
        files: list[RepositoryFile] = []
        total_bytes = 0
        for item in selected:
            path = item.filename.split("/", 1)[1]
            if item.file_size > MAX_FILE_BYTES:
                continue
            try:
                content_bytes = zip_file.read(item)
            except (OSError, RuntimeError, zipfile.BadZipFile) as error:
                raise RepositoryIngestionError("A repository archive entry could not be read.") from error
            if len(content_bytes) > MAX_FILE_BYTES or total_bytes + len(content_bytes) > MAX_TOTAL_BYTES:
                continue
            try:
                content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                continue
            files.append(RepositoryFile(path, content, len(content_bytes)))
            total_bytes += len(content_bytes)
        if not files:
            raise RepositoryIngestionError("No readable source or documentation files found.")
        languages = sorted({
            item.path.rsplit(".", 1)[-1].lower()
            for item in files
            if "." in item.path
            and f".{item.path.rsplit('.', 1)[-1].lower()}" in SOURCE_SUFFIXES
        })
        return RepositoryContext(
            owner=owner,
            name=name,
            default_branch=branch,
            description="",
            stars=0,
            languages=languages,
            files=files,
            truncated=selection_truncated or len(files) < len(selected),
        )

    def _get_json(self, url: str) -> dict[str, Any]:
        try:
            request = Request(
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "continuum-ai-ingestor/1.0",
                },
            )
            with self._opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                raw = response.read(MAX_TOTAL_BYTES + 1)
        except HTTPError as error:
            if error.code == 404:
                raise RepositoryIngestionError("GitHub repository was not found.") from error
            raise RepositoryIngestionError(f"GitHub API request failed ({error.code}).") from error
        except (URLError, TimeoutError, OSError) as error:
            raise RepositoryIngestionError("GitHub could not be reached.") from error
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RepositoryIngestionError("GitHub returned invalid JSON.") from error
        if not isinstance(payload, dict):
            raise RepositoryIngestionError("GitHub returned an invalid response.")
        return payload

    def _get_text(self, url: str) -> str:
        return self._get_bytes(url, MAX_TOTAL_BYTES).decode("utf-8")

    def _get_bytes(self, url: str, limit: int) -> bytes:
        try:
            request = Request(url, headers={"User-Agent": "continuum-ai-ingestor/1.0"})
            with self._opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = response.read(limit + 1)
        except HTTPError as error:
            raise RepositoryIngestionError(f"GitHub archive request failed ({error.code}).") from error
        except (URLError, TimeoutError, OSError) as error:
            raise RepositoryIngestionError("GitHub archive could not be reached.") from error
        if len(payload) > limit:
            raise RepositoryIngestionError("GitHub response exceeds the ingestion limit.")
        return payload

    def _get_raw_file(self, owner: str, name: str, branch: str, path: str) -> str:
        url = (
            f"https://raw.githubusercontent.com/{quote(owner)}/{quote(name)}/"
            f"{quote(branch, safe='')}/{quote(path, safe='/')}"
        )
        request = Request(url, headers={"User-Agent": "continuum-ai-ingestor/1.0"})
        try:
            with self._opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                decoded = response.read(MAX_FILE_BYTES + 1)
        except HTTPError as error:
            raise RepositoryIngestionError(
                f"GitHub file request failed ({error.code})."
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise RepositoryIngestionError("GitHub file content could not be reached.") from error
        if len(decoded) > MAX_FILE_BYTES:
            raise RepositoryIngestionError("A repository file exceeds the file-size limit.")
        try:
            return decoded.decode("utf-8")
        except UnicodeDecodeError as error:
            raise RepositoryIngestionError("A repository file was not valid UTF-8 text.") from error

    def _get_languages(self, base: str) -> list[str]:
        try:
            payload = self._get_json(f"{base}/languages")
        except RepositoryIngestionError:
            return []
        return [key for key, value in payload.items() if isinstance(value, int) and value > 0]

    @staticmethod
    def _is_allowed_path(path: str) -> bool:
        if not path or path.startswith("/") or ".." in path.split("/"):
            return False
        parts = path.split("/")
        if any(part in EXCLUDED_DIRECTORIES for part in parts):
            return False
        name = parts[-1]
        lowered = name.lower()
        if name in SECRET_NAMES or lowered.startswith(".env."):
            return False
        if lowered.endswith(tuple(EXCLUDED_SUFFIXES)):
            return False
        if name in MANIFEST_NAMES or name.lower().startswith("readme"):
            return True
        return lowered.endswith(tuple(SOURCE_SUFFIXES))
