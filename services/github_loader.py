from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests


class GitHubLoaderError(RuntimeError):
    """Raised when masterdata cannot be obtained from GitHub or cache."""


@dataclass(frozen=True)
class CacheStatus:
    path: Path
    exists: bool
    fresh: bool
    age_seconds: float | None


class GitHubExcelLoader:
    """Loads Excel workbooks from public or private GitHub repositories.

    Public repositories use raw.githubusercontent.com. Private repositories use
    GitHub's Contents API with a token stored in an environment variable.
    """

    def __init__(
        self,
        owner: str,
        repository: str,
        branch: str = "main",
        private_repository: bool = False,
        token: str | None = None,
        cache_enabled: bool = True,
        cache_directory: str | Path = "cache",
        cache_ttl_hours: float = 24,
        timeout_seconds: int = 30,
        allow_stale_on_error: bool = True,
        session: requests.Session | None = None,
    ) -> None:
        if not owner or not repository:
            raise ValueError("GitHub owner and repository are required.")
        self.owner = owner
        self.repository = repository
        self.branch = branch
        self.private_repository = private_repository
        self.token = token
        self.cache_enabled = cache_enabled
        self.cache_directory = Path(cache_directory)
        self.cache_ttl_seconds = float(cache_ttl_hours) * 3600
        self.timeout_seconds = timeout_seconds
        self.allow_stale_on_error = allow_stale_on_error
        self.session = session or requests.Session()
        if self.cache_enabled:
            self.cache_directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "GitHubExcelLoader":
        github = settings["github"]
        cache = settings["cache"]
        token = os.getenv(github.get("token_environment_variable", "VEMCI_GITHUB_TOKEN"))
        return cls(
            owner=github["owner"],
            repository=github["repository"],
            branch=github.get("branch", "main"),
            private_repository=bool(github.get("private_repository", False)),
            token=token,
            cache_enabled=bool(cache.get("enabled", True)),
            cache_directory=cache.get("directory", "cache"),
            cache_ttl_hours=float(cache.get("ttl_hours", 24)),
            timeout_seconds=int(github.get("timeout_seconds", 30)),
            allow_stale_on_error=bool(cache.get("allow_stale_on_error", True)),
        )

    @staticmethod
    def _normalise_path(relative_path: str) -> str:
        normalised = str(PurePosixPath(relative_path.strip().replace("\\", "/")))
        if normalised.startswith("../") or normalised in {"", "."}:
            raise ValueError(f"Invalid repository path: {relative_path}")
        return normalised

    def _cache_path(self, relative_path: str) -> Path:
        suffix = Path(relative_path).suffix or ".bin"
        digest = hashlib.sha256(
            f"{self.owner}/{self.repository}/{self.branch}/{relative_path}".encode("utf-8")
        ).hexdigest()[:20]
        filename = f"{Path(relative_path).stem}-{digest}{suffix}"
        return self.cache_directory / filename

    def cache_status(self, relative_path: str) -> CacheStatus:
        path = self._cache_path(self._normalise_path(relative_path))
        if not path.exists():
            return CacheStatus(path=path, exists=False, fresh=False, age_seconds=None)
        age = max(0.0, time.time() - path.stat().st_mtime)
        return CacheStatus(path=path, exists=True, fresh=age <= self.cache_ttl_seconds, age_seconds=age)

    def _request_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.raw+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "VEMCI-masterdata-loader",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _download(self, relative_path: str) -> bytes:
        encoded_path = quote(relative_path, safe="/")
        if self.private_repository:
            if not self.token:
                raise GitHubLoaderError(
                    "Private masterdata repository requires the configured GitHub token environment variable."
                )
            url = (
                f"https://api.github.com/repos/{self.owner}/{self.repository}"
                f"/contents/{encoded_path}?ref={quote(self.branch, safe='')}"
            )
            headers = self._request_headers()
        else:
            url = (
                f"https://raw.githubusercontent.com/{self.owner}/{self.repository}"
                f"/{quote(self.branch, safe='')}/{encoded_path}"
            )
            headers = {"User-Agent": "VEMCI-masterdata-loader"}
        try:
            response = self.session.get(url, headers=headers, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise GitHubLoaderError(f"GitHub download failed for '{relative_path}': {exc}") from exc
        if not response.content:
            raise GitHubLoaderError(f"GitHub returned an empty file for '{relative_path}'.")
        return response.content

    def get_bytes(self, relative_path: str, force_refresh: bool = False) -> bytes:
        relative_path = self._normalise_path(relative_path)
        status = self.cache_status(relative_path)
        if self.cache_enabled and status.fresh and not force_refresh:
            return status.path.read_bytes()
        try:
            payload = self._download(relative_path)
            if self.cache_enabled:
                status.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = status.path.with_suffix(status.path.suffix + ".tmp")
                temporary.write_bytes(payload)
                temporary.replace(status.path)
            return payload
        except GitHubLoaderError:
            if self.cache_enabled and status.exists and self.allow_stale_on_error:
                return status.path.read_bytes()
            raise

    def load_excel(
        self,
        relative_path: str,
        sheet_name: str | int | list[str | int] | None = 0,
        force_refresh: bool = False,
        **read_excel_kwargs: Any,
    ) -> pd.DataFrame | dict[str, pd.DataFrame]:
        payload = self.get_bytes(relative_path, force_refresh=force_refresh)
        try:
            return pd.read_excel(
                BytesIO(payload),
                sheet_name=sheet_name,
                engine="openpyxl",
                **read_excel_kwargs,
            )
        except Exception as exc:
            raise GitHubLoaderError(f"Could not parse Excel file '{relative_path}': {exc}") from exc

    def refresh_excel(self, relative_path: str, **kwargs: Any) -> pd.DataFrame | dict[str, pd.DataFrame]:
        return self.load_excel(relative_path, force_refresh=True, **kwargs)

    def clear_cache(self, relative_path: str | None = None) -> int:
        if not self.cache_directory.exists():
            return 0
        if relative_path:
            files = [self._cache_path(self._normalise_path(relative_path))]
        else:
            files = [file for file in self.cache_directory.iterdir() if file.is_file() and file.name != ".gitkeep"]
        deleted = 0
        for file in files:
            if file.exists():
                file.unlink()
                deleted += 1
        return deleted
