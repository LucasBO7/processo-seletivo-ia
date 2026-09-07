from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime
from html.parser import HTMLParser
from uuid import UUID, uuid5

from app.application.contracts.knowledge_ingestion import (
    FetchedKnowledgeContent,
    KnowledgeContentType,
    KnowledgeSource,
    NormalizedKnowledgeDocument,
)

KNOWLEDGE_NAMESPACE = UUID("65d26d43-1f7c-5a5f-9ce3-e5ce0f52b64e")
_BLOCKED_TAGS = {"script", "style", "nav", "footer", "noscript", "svg"}
_BLOCK_TAGS = {"p", "div", "li", "tr", "pre", "code", "br", "section", "article"}


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.blocked_depth = 0
        self.heading: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in _BLOCKED_TAGS:
            self.blocked_depth += 1
        elif self.blocked_depth == 0 and tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.heading = tag
            self.parts.append("\n# ")
        elif self.blocked_depth == 0 and tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCKED_TAGS and self.blocked_depth:
            self.blocked_depth -= 1
        elif self.blocked_depth == 0 and (tag in _BLOCK_TAGS or tag == self.heading):
            self.parts.append("\n")
            if tag == self.heading:
                self.heading = None

    def handle_data(self, data: str) -> None:
        if self.blocked_depth == 0:
            self.parts.append(data)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_text(body: str, content_type: KnowledgeContentType) -> str:
    if content_type is KnowledgeContentType.HTML:
        parser = _ReadableHtmlParser()
        parser.feed(body)
        value = "".join(parser.parts)
    else:
        value = body
    value = html.unescape(value).replace("\r\n", "\n").replace("\r", "\n")
    if content_type is KnowledgeContentType.MARKDOWN:
        value = re.sub(r"!\[[^]]*]\([^)]*\)", "", value)
        value = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", value)
        value = re.sub(r"^\s{0,3}#{1,6}\s+", "# ", value, flags=re.MULTILINE)
        value = re.sub(r"[*_`]{1,3}", "", value)
    value = "\n".join(re.sub(r"[\t ]+", " ", line).strip() for line in value.splitlines())
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    return value


def normalize_document(
    source: KnowledgeSource,
    fetched: FetchedKnowledgeContent,
    *,
    ingested_at: datetime,
    pipeline_version: str,
) -> NormalizedKnowledgeDocument:
    content = normalize_text(fetched.body, fetched.content_type)
    if not content:
        raise ValueError("knowledge_document_empty")
    document_id = uuid5(KNOWLEDGE_NAMESPACE, source.source_key)
    return NormalizedKnowledgeDocument(
        document_id=document_id,
        source_key=source.source_key,
        title=fetched.title.strip(),
        technology=source.technology,
        source_url=str(source.canonical_url),
        content_type=fetched.content_type,
        content=content,
        published_at=fetched.published_at,
        ingested_at=ingested_at,
        content_hash=sha256_text(content),
        pipeline_version=pipeline_version,
    )
