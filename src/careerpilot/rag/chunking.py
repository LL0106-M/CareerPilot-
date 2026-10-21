import hashlib
import re

from careerpilot.rag.models import DocumentChunk, SourceDocument

_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")


def chunk_document(
    document: SourceDocument,
    *,
    max_chars: int = 900,
    overlap_chars: int = 100,
) -> tuple[DocumentChunk, ...]:
    if max_chars < 20:
        raise ValueError("max_chars must be at least 20")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be between 0 and max_chars")

    sections = _markdown_sections(document.text, document.title)
    chunks: list[DocumentChunk] = []
    ordinal = 0
    for heading, body in sections:
        for content in _split_text(body, max_chars, overlap_chars):
            digest = hashlib.sha256(
                f"{document.id}:{ordinal}:{heading}:{content}".encode()
            ).hexdigest()[:20]
            chunks.append(
                DocumentChunk(
                    id=f"chunk-{digest}",
                    document_id=document.id,
                    ordinal=ordinal,
                    title=document.title,
                    heading=heading,
                    content=content,
                    source_uri=document.source_uri,
                    source_type=document.source_type,
                    domain=document.domain,
                    metadata=dict(document.metadata),
                    knowledge_origin=document.knowledge_origin,
                    owner_user_id=document.owner_user_id,
                )
            )
            ordinal += 1
    return tuple(chunks)


def _markdown_sections(text: str, default_heading: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading = default_heading
    lines: list[str] = []
    for raw_line in text.splitlines():
        match = _HEADING.match(raw_line.strip())
        if match:
            body = "\n".join(lines).strip()
            if body:
                sections.append((heading, body))
            heading = match.group(1).strip()
            lines = []
        else:
            lines.append(raw_line)
    body = "\n".join(lines).strip()
    if body:
        sections.append((heading, body))
    return sections or [(default_heading, text.strip())]


def _split_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    clean = re.sub(r"[ \t]+", " ", text).strip()
    if not clean:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(start + max_chars, len(clean))
        if end < len(clean):
            boundary = max(
                clean.rfind("\n", start + max_chars // 2, end),
                clean.rfind("。", start + max_chars // 2, end),
                clean.rfind("；", start + max_chars // 2, end),
            )
            if boundary > start:
                end = boundary + 1
        chunk = clean[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(clean):
            break
        start = max(end - overlap_chars, start + 1)
    return chunks
