import hashlib
import json
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from careerpilot.rag.models import SourceDocument

_CORE_FIELDS = {
    "document_id",
    "content_type",
    "source_type",
    "title",
    "canonical_url",
    "published_at",
    "fetched_at",
}


def load_markdown(path: Path) -> SourceDocument:
    raw = path.read_text(encoding="utf-8")
    frontmatter, text = _split_frontmatter(raw)
    title = str(frontmatter.get("title") or _first_heading(text) or path.stem)
    source_uri = str(frontmatter.get("canonical_url") or path.resolve().as_uri())
    document_id = str(
        frontmatter.get("document_id")
        or _stable_id(source_uri, hashlib.sha256(text.encode()).hexdigest())
    )
    metadata = {key: value for key, value in frontmatter.items() if key not in _CORE_FIELDS}
    return SourceDocument(
        id=document_id,
        title=title,
        source_uri=source_uri,
        source_type=str(frontmatter.get("source_type") or "developer_upload"),
        domain=str(frontmatter.get("content_type") or "curated_document"),
        text=text.strip(),
        metadata=metadata,
        published_at=_optional_string(frontmatter.get("published_at")),
        fetched_at=_optional_string(frontmatter.get("fetched_at")),
    )


def load_pdf(path: Path, *, domain: str = "curated_document") -> SourceDocument:
    reader = PdfReader(path)
    page_texts: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        extracted = (page.extract_text() or "").strip()
        page_texts.append(f"## Page {page_number}\n\n{extracted}")
    text = "\n\n".join(page_texts)
    title = _optional_string((reader.metadata or {}).get("/Title")) or path.stem
    source_uri = path.resolve().as_uri()
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    return SourceDocument(
        id=_stable_id(source_uri, content_hash),
        title=title,
        source_uri=source_uri,
        source_type="developer_upload",
        domain=domain,
        text=text,
        metadata={"page_count": len(reader.pages), "content_hash": content_hash},
    )


def _split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---\n", 4)
    if end < 0:
        return {}, raw
    values: dict[str, Any] = {}
    for line in raw[4:end].splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = _parse_scalar(value.strip())
    return values, raw[end + 5 :]


def _parse_scalar(value: str) -> Any:
    if value in {"null", "~", ""}:
        return None
    if value.startswith(("[", "{")):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value.strip('"\'')


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _stable_id(source_uri: str, content_hash: str) -> str:
    digest = hashlib.sha256(f"{source_uri}:{content_hash}".encode()).hexdigest()[:24]
    return f"doc-{digest}"


def _optional_string(value: object) -> str | None:
    return str(value) if value not in (None, "") else None
