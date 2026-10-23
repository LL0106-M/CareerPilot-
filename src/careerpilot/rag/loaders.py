import hashlib
import importlib
import io
import json
import re
import zipfile
from contextlib import redirect_stdout
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree

from pypdf import PdfReader

from careerpilot.rag.models import KnowledgeOrigin, SourceDocument

_CORE_FIELDS = {
    "document_id",
    "content_type",
    "source_type",
    "title",
    "canonical_url",
    "published_at",
    "fetched_at",
    "knowledge_origin",
    "owner_user_id",
}
_WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}


def load_document(
    path: Path,
    *,
    domain: str = "curated_document",
    source_type: str = "developer_upload",
    knowledge_origin: KnowledgeOrigin = KnowledgeOrigin.SYSTEM_CURATED,
    owner_user_id: str | None = None,
    asset_dir: Path | None = None,
) -> SourceDocument:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        return load_markdown(
            path,
            default_domain=domain,
            default_source_type=source_type,
            knowledge_origin=knowledge_origin,
            owner_user_id=owner_user_id,
        )
    if suffix == ".pdf":
        return load_pdf(
            path,
            domain=domain,
            source_type=source_type,
            knowledge_origin=knowledge_origin,
            owner_user_id=owner_user_id,
            asset_dir=asset_dir,
        )
    if suffix == ".docx":
        return load_docx(
            path,
            domain=domain,
            source_type=source_type,
            knowledge_origin=knowledge_origin,
            owner_user_id=owner_user_id,
            asset_dir=asset_dir,
        )
    raise ValueError(f"unsupported document type: {suffix or '<none>'}")


def load_markdown(
    path: Path,
    *,
    default_domain: str = "curated_document",
    default_source_type: str = "developer_upload",
    knowledge_origin: KnowledgeOrigin = KnowledgeOrigin.SYSTEM_CURATED,
    owner_user_id: str | None = None,
) -> SourceDocument:
    raw = path.read_text(encoding="utf-8")
    frontmatter, text = _split_frontmatter(raw)
    title = str(frontmatter.get("title") or _first_heading(text) or path.stem)
    source_uri = str(frontmatter.get("canonical_url") or path.resolve().as_uri())
    document_id = str(
        frontmatter.get("document_id")
        or _stable_id(source_uri, hashlib.sha256(text.encode()).hexdigest())
    )
    metadata = {key: value for key, value in frontmatter.items() if key not in _CORE_FIELDS}
    metadata.update(_extract_markdown_assets(text, path.parent))
    origin = _knowledge_origin(frontmatter.get("knowledge_origin"), knowledge_origin)
    owner = _optional_string(frontmatter.get("owner_user_id")) or owner_user_id
    return SourceDocument(
        id=document_id,
        title=title,
        source_uri=source_uri,
        source_type=str(frontmatter.get("source_type") or default_source_type),
        domain=str(frontmatter.get("content_type") or default_domain),
        text=text.strip(),
        metadata=metadata,
        published_at=_optional_string(frontmatter.get("published_at")),
        fetched_at=_optional_string(frontmatter.get("fetched_at")),
        knowledge_origin=origin,
        owner_user_id=owner,
    )


def load_pdf(
    path: Path,
    *,
    domain: str = "curated_document",
    source_type: str = "developer_upload",
    knowledge_origin: KnowledgeOrigin = KnowledgeOrigin.SYSTEM_CURATED,
    owner_user_id: str | None = None,
    asset_dir: Path | None = None,
) -> SourceDocument:
    try:
        return _load_pdf_layout(
            path,
            domain=domain,
            source_type=source_type,
            knowledge_origin=knowledge_origin,
            owner_user_id=owner_user_id,
            asset_dir=asset_dir,
        )
    except Exception:
        return _load_pdf_fallback(
            path,
            domain=domain,
            source_type=source_type,
            knowledge_origin=knowledge_origin,
            owner_user_id=owner_user_id,
            asset_dir=asset_dir,
        )


def _load_pdf_layout(
    path: Path,
    *,
    domain: str,
    source_type: str,
    knowledge_origin: KnowledgeOrigin,
    owner_user_id: str | None,
    asset_dir: Path | None,
) -> SourceDocument:
    output_dir = _asset_output_dir(asset_dir, path)
    with redirect_stdout(io.StringIO()):
        pymupdf4llm = importlib.import_module("pymupdf4llm")
    pages = pymupdf4llm.to_markdown(
        str(path),
        page_chunks=True,
        write_images=output_dir is not None,
        image_path=str(output_dir or ""),
        image_format="png",
        show_progress=False,
    )
    page_texts: list[str] = []
    tables: list[object] = []
    images: list[object] = []
    metadata: dict[str, object] = {}
    for page_number, page in enumerate(pages, start=1):
        page_text = str(page.get("text") or "").strip()
        page_texts.append(f"## Page {page_number}\n\n{page_text}")
        parsed = _extract_markdown_assets(page_text, output_dir or path.parent)
        for table in parsed.get("tables", []):
            table["table_name"] = f"page-{page_number}-{table['table_name']}"
            tables.append(table)
        for image in parsed.get("images", []):
            images.append(_scope_pdf_image(image, page_number))
        if not metadata and isinstance(page.get("metadata"), dict):
            metadata = dict(page["metadata"])
    text = "\n\n".join(page_texts)
    source_uri = path.resolve().as_uri()
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    title = _optional_string(metadata.get("title")) or path.stem
    return SourceDocument(
        id=_stable_id(source_uri, content_hash),
        title=title,
        source_uri=source_uri,
        source_type=source_type,
        domain=domain,
        text=text,
        metadata={
            "page_count": len(pages),
            "content_hash": content_hash,
            "parser": "pymupdf4llm",
            "tables": tables,
            "images": images,
        },
        knowledge_origin=knowledge_origin,
        owner_user_id=owner_user_id,
    )


def _load_pdf_fallback(
    path: Path,
    *,
    domain: str,
    source_type: str,
    knowledge_origin: KnowledgeOrigin,
    owner_user_id: str | None,
    asset_dir: Path | None,
) -> SourceDocument:
    reader = PdfReader(path)
    page_texts: list[str] = []
    images: list[dict[str, object]] = []
    output_dir = _asset_output_dir(asset_dir, path)
    for page_number, page in enumerate(reader.pages, start=1):
        extracted = (page.extract_text() or "").strip()
        page_texts.append(f"## Page {page_number}\n\n{extracted}")
        if output_dir is not None:
            for image_number, image in enumerate(getattr(page, "images", ()), start=1):
                extension = Path(image.name).suffix or ".bin"
                target = output_dir / f"page-{page_number}-image-{image_number}{extension}"
                target.write_bytes(image.data)
                images.append(
                    {
                        "page_number": page_number,
                        "object_uri": target.resolve().as_uri(),
                        "image_type": extension.lstrip(".") or "image",
                        "source_name": image.name,
                    }
                )
    text = "\n\n".join(page_texts)
    title = _optional_string((reader.metadata or {}).get("/Title")) or path.stem
    source_uri = path.resolve().as_uri()
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    parsed = _extract_markdown_assets(text, path.parent)
    return SourceDocument(
        id=_stable_id(source_uri, content_hash),
        title=title,
        source_uri=source_uri,
        source_type=source_type,
        domain=domain,
        text=text,
        metadata={
            "page_count": len(reader.pages),
            "content_hash": content_hash,
            "parser": "pypdf_fallback",
            "tables": parsed.get("tables", []),
            "images": images,
        },
        knowledge_origin=knowledge_origin,
        owner_user_id=owner_user_id,
    )


def load_docx(
    path: Path,
    *,
    domain: str = "curated_document",
    source_type: str = "developer_upload",
    knowledge_origin: KnowledgeOrigin = KnowledgeOrigin.SYSTEM_CURATED,
    owner_user_id: str | None = None,
    asset_dir: Path | None = None,
) -> SourceDocument:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
        relationships = _docx_relationships(archive)
        blocks: list[str] = []
        tables: list[dict[str, object]] = []
        body = root.find("w:body", _WORD_NS)
        for child in () if body is None else body:
            if child.tag.endswith("}p"):
                value = "".join(
                    node.text or "" for node in child.findall(".//w:t", _WORD_NS)
                ).strip()
                if value:
                    blocks.append(value)
            elif child.tag.endswith("}tbl"):
                table = _docx_table(child, len(tables) + 1)
                if table:
                    tables.append(table)
                    blocks.append(_table_as_markdown(table))
        images = _extract_docx_images(archive, relationships, asset_dir, path)
        properties = _docx_properties(archive)
    text = "\n\n".join(blocks)
    source_uri = path.resolve().as_uri()
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    title = properties.get("title") or _first_heading(text) or path.stem
    return SourceDocument(
        id=_stable_id(source_uri, content_hash),
        title=title,
        source_uri=source_uri,
        source_type=source_type,
        domain=domain,
        text=text,
        metadata={"content_hash": content_hash, "tables": tables, "images": images},
        knowledge_origin=knowledge_origin,
        owner_user_id=owner_user_id,
    )


def _extract_markdown_assets(text: str, base_dir: Path) -> dict[str, object]:
    tables: list[dict[str, object]] = []
    lines = text.splitlines()
    index = 0
    while index + 1 < len(lines):
        header = _markdown_cells(lines[index])
        divider = _markdown_cells(lines[index + 1])
        if (
            header
            and len(header) == len(divider)
            and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in divider)
        ):
            rows: list[dict[str, object]] = []
            cursor = index + 2
            while cursor < len(lines):
                values = _markdown_cells(lines[cursor])
                if not values or len(values) != len(header):
                    break
                rows.append(
                    {
                        "row_id": f"row-{len(rows) + 1}",
                        "values": dict(zip(header, values, strict=True)),
                    }
                )
                cursor += 1
            tables.append(
                {"table_name": f"table-{len(tables) + 1}", "columns": header, "rows": rows}
            )
            index = cursor
            continue
        index += 1
    images: list[dict[str, object]] = []
    for ordinal, match in enumerate(
        re.finditer(r"!\[([^]]*)\]\(([^)\s]+)(?:\s+[^)]*)?\)", text), 1
    ):
        caption, target = match.groups()
        uri = target
        candidate = base_dir / target
        if "://" not in target and candidate.exists():
            uri = candidate.resolve().as_uri()
        page_number = max(1, text[: match.start()].count("## Page "))
        images.append(
            {
                "image_id": f"markdown-image-{ordinal}",
                "page_number": page_number,
                "object_uri": uri,
                "caption": caption or None,
            }
        )
    result: dict[str, object] = {}
    if tables:
        result["tables"] = tables
    if images:
        result["images"] = images
    return result


def _markdown_cells(line: str) -> list[str]:
    stripped = line.strip()
    return [cell.strip() for cell in stripped.strip("|").split("|")] if "|" in stripped else []


def _scope_pdf_image(image: dict[str, object], page_number: int) -> dict[str, object]:
    scoped = dict(image)
    scoped["page_number"] = page_number
    scoped["image_id"] = f"page-{page_number}-{image['image_id']}"
    return scoped


def _docx_table(element: ElementTree.Element, ordinal: int) -> dict[str, object] | None:
    matrix = [
        [
            "".join(node.text or "" for node in cell.findall(".//w:t", _WORD_NS)).strip()
            for cell in row.findall("w:tc", _WORD_NS)
        ]
        for row in element.findall("w:tr", _WORD_NS)
    ]
    matrix = [row for row in matrix if row]
    if not matrix:
        return None
    columns = [value or f"column-{index + 1}" for index, value in enumerate(matrix[0])]
    rows = []
    for row_number, values in enumerate(matrix[1:], 1):
        padded = values + [""] * (len(columns) - len(values))
        rows.append(
            {
                "row_id": f"row-{row_number}",
                "values": dict(zip(columns, padded[: len(columns)], strict=True)),
            }
        )
    return {"table_name": f"table-{ordinal}", "columns": columns, "rows": rows}


def _table_as_markdown(table: dict[str, object]) -> str:
    columns = [str(value) for value in table["columns"]]  # type: ignore[index]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in table["rows"]:  # type: ignore[union-attr,index]
        values = row["values"]
        lines.append("| " + " | ".join(str(values.get(column, "")) for column in columns) + " |")
    return "\n".join(lines)


def _docx_relationships(archive: zipfile.ZipFile) -> dict[str, str]:
    name = "word/_rels/document.xml.rels"
    if name not in archive.namelist():
        return {}
    root = ElementTree.fromstring(archive.read(name))
    return {
        str(item.attrib.get("Id")): str(item.attrib.get("Target"))
        for item in root.findall("r:Relationship", _REL_NS)
    }


def _extract_docx_images(
    archive: zipfile.ZipFile, relationships: dict[str, str], asset_dir: Path | None, source: Path
) -> list[dict[str, object]]:
    output_dir = _asset_output_dir(asset_dir, source)
    if output_dir is None:
        return []
    images: list[dict[str, object]] = []
    for relationship_id, target in relationships.items():
        if "media/" not in target:
            continue
        archive_path = str(PurePosixPath("word") / target)
        if archive_path not in archive.namelist():
            continue
        destination = output_dir / Path(target).name
        destination.write_bytes(archive.read(archive_path))
        images.append(
            {
                "image_id": relationship_id,
                "page_number": 1,
                "object_uri": destination.resolve().as_uri(),
                "image_type": destination.suffix.lstrip(".") or "image",
            }
        )
    return images


def _docx_properties(archive: zipfile.ZipFile) -> dict[str, str]:
    name = "docProps/core.xml"
    if name not in archive.namelist():
        return {}
    root = ElementTree.fromstring(archive.read(name))
    return {element.tag.rsplit("}", 1)[-1]: element.text or "" for element in root}


def _asset_output_dir(asset_dir: Path | None, source: Path) -> Path | None:
    if asset_dir is None:
        return None
    output = asset_dir / source.stem
    output.mkdir(parents=True, exist_ok=True)
    return output


def _split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---\n", 4)
    if end < 0:
        return {}, raw
    values: dict[str, Any] = {}
    for line in raw[4:end].splitlines():
        if line.strip() and ":" in line:
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
    return value.strip("\"'")


def _first_heading(text: str) -> str | None:
    return next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), None)


def _stable_id(source_uri: str, content_hash: str) -> str:
    return f"doc-{hashlib.sha256(f'{source_uri}:{content_hash}'.encode()).hexdigest()[:24]}"


def _knowledge_origin(value: object, default: KnowledgeOrigin) -> KnowledgeOrigin:
    return default if value in (None, "") else KnowledgeOrigin(str(value))


def _optional_string(value: object) -> str | None:
    return str(value) if value not in (None, "") else None
