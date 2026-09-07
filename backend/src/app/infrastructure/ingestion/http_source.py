from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from app.application.contracts.knowledge_ingestion import (
    FetchedKnowledgeContent,
    KnowledgeSource,
)


class HttpKnowledgeSourceClient:
    def __init__(
        self,
        *,
        allowed_domains: set[str],
        timeout_seconds: float,
        max_bytes: int,
        max_redirects: int = 3,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._allowed_domains = {item.lower() for item in allowed_domains}
        self._max_bytes = max_bytes
        self._max_redirects = max_redirects
        self._max_retries = max_retries
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": "NVIDIA-Startup-Radar-Knowledge-Ingestion/1.0"},
        )

    async def fetch(self, source: KnowledgeSource) -> FetchedKnowledgeContent:
        for attempt in range(self._max_retries + 1):
            try:
                return await self._fetch_once(source)
            except httpx.HTTPStatusError as error:
                transient = error.response.status_code == 429 or error.response.status_code >= 500
                if not transient or attempt == self._max_retries:
                    raise RuntimeError("knowledge_fetch_failed") from error
            except (httpx.RequestError, UnicodeError) as error:
                if attempt == self._max_retries:
                    raise RuntimeError("knowledge_fetch_failed") from error
        raise RuntimeError("knowledge_fetch_failed")

    async def _fetch_once(self, source: KnowledgeSource) -> FetchedKnowledgeContent:
        url = str(source.canonical_url)
        for _ in range(self._max_redirects + 1):
            self._validate_url(url)
            response = await self._client.get(url)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("knowledge_fetch_failed")
                url = urljoin(url, location)
                continue
            response.raise_for_status()
            if len(response.content) > self._max_bytes:
                raise ValueError("knowledge_fetch_failed")
            content_type = response.headers.get("content-type", "").lower()
            if not any(item in content_type for item in ("text/", "html", "json", "xml")):
                raise ValueError("knowledge_fetch_failed")
            return FetchedKnowledgeContent(
                title=_html_title(response.text) or source.source_key.replace("-", " ").title(),
                body=response.text,
                content_type=source.content_type,
            )
        raise RuntimeError("knowledge_fetch_failed")

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in self._allowed_domains:
            raise ValueError("knowledge_source_invalid")


class FileKnowledgeSourceClient:
    def __init__(self, directory: Path) -> None:
        self._directory = directory.resolve()

    async def fetch(self, source: KnowledgeSource) -> FetchedKnowledgeContent:
        suffix = {
            "html": ".html",
            "markdown": ".md",
            "text": ".txt",
        }[source.content_type.value]
        path = (self._directory / f"{source.source_key}{suffix}").resolve()
        if path.parent != self._directory:
            raise ValueError("knowledge_source_invalid")
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as error:
            raise RuntimeError("knowledge_fetch_failed") from error
        return FetchedKnowledgeContent(
            title=_html_title(body) or source.source_key.replace("-", " ").title(),
            body=body,
            content_type=source.content_type,
        )


def _html_title(body: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    title = re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()
    return title[:500] or None
