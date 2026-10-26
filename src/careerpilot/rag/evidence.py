import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from careerpilot.rag.models import (
    ChunkLevel,
    DocumentChunk,
    EvidenceKind,
    EvidenceUnit,
    KnowledgeTriple,
    SourceDocument,
)
from careerpilot.rag.policy import allows_graph_index


def linearize_triple(triple: KnowledgeTriple) -> str:
    return f"[KG_TRIPLE] {triple.subject} | {triple.predicate} | {triple.object}"


def linearize_table_row(
    table_name: str,
    row_id: str,
    values: Mapping[str, Any],
) -> str:
    cells = " | ".join(f"({field}, {_display(value)})" for field, value in values.items())
    return f"[TABLE_ROW table={table_name} row={row_id}] {cells}"


def build_evidence_units(
    document: SourceDocument,
    chunks: Sequence[DocumentChunk],
    *,
    extracted_triples: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[EvidenceUnit, ...]:
    child_chunks = tuple(chunk for chunk in chunks if chunk.chunk_level is ChunkLevel.CHILD)
    units: list[EvidenceUnit] = [_passage_unit(document, chunk) for chunk in child_chunks]
    if allows_graph_index(document.domain, document.knowledge_origin):
        units.extend(_triple_units(document, child_chunks, extracted_triples))
    units.extend(_table_units(document))
    return tuple(units)


def _passage_unit(document: SourceDocument, chunk: DocumentChunk) -> EvidenceUnit:
    return EvidenceUnit(
        id=f"evidence-{chunk.id}",
        kind=EvidenceKind.PASSAGE,
        document_id=chunk.document_id,
        parent_id=chunk.parent_id or chunk.document_id,
        title=chunk.title,
        embedding_text=f"[PASSAGE heading={chunk.heading}] {chunk.content}",
        source_uri=chunk.source_uri,
        source_type=chunk.source_type,
        domain=chunk.domain,
        metadata={
            **_provenance_metadata(document),
            **chunk.metadata,
            "chunk_id": chunk.id,
            "heading": chunk.heading,
            "chunk_level": chunk.chunk_level.value,
            "parent_id": chunk.parent_id,
        },
        knowledge_origin=chunk.knowledge_origin,
        owner_user_id=chunk.owner_user_id,
    )


def _triple_units(
    document: SourceDocument,
    chunks: Sequence[DocumentChunk],
    extracted_triples: Sequence[Mapping[str, Any]] | None = None,
) -> list[EvidenceUnit]:
    metadata_triples = document.metadata.get("triples")
    raw_triples = extracted_triples if extracted_triples is not None else metadata_triples
    if not isinstance(raw_triples, (list, tuple)):
        return []
    by_ordinal = {chunk.ordinal: chunk for chunk in chunks}
    fallback_parent = chunks[0].id if chunks else None
    units: list[EvidenceUnit] = []
    provenance = _provenance_metadata(document)
    for raw in raw_triples:
        if not isinstance(raw, Mapping):
            continue
        subject = str(raw.get("subject") or "").strip()
        predicate = str(raw.get("relation") or raw.get("predicate") or "").strip()
        object_value = str(raw.get("object") or "").strip()
        if not all((subject, predicate, object_value)):
            continue
        triple = KnowledgeTriple(subject, predicate, object_value)
        ordinal = raw.get("chunk_ordinal")
        parent = by_ordinal.get(ordinal) if isinstance(ordinal, int) else None
        parent_id = parent.id if parent else fallback_parent
        if parent_id is None:
            continue
        identity = f"{document.id}:triple:{subject}:{predicate}:{object_value}:{parent_id}"
        units.append(
            EvidenceUnit(
                id=_evidence_id(identity),
                kind=EvidenceKind.KG_TRIPLE,
                document_id=document.id,
                parent_id=parent_id,
                title=document.title,
                embedding_text=linearize_triple(triple),
                source_uri=document.source_uri,
                source_type=document.source_type,
                domain=document.domain,
                metadata={
                    **provenance,
                    "chunk_id": parent_id,
                    "evidence_quote": str(raw.get("evidence_quote") or ""),
                },
                subject=subject,
                predicate=predicate,
                object=object_value,
                knowledge_origin=document.knowledge_origin,
                owner_user_id=document.owner_user_id,
            )
        )
    return units


def _table_units(document: SourceDocument) -> list[EvidenceUnit]:
    raw_tables = document.metadata.get("tables")
    tables: list[tuple[str, list[object], Mapping[str, Any]]] = []
    if isinstance(raw_tables, list):
        for ordinal, raw_table in enumerate(raw_tables, 1):
            if not isinstance(raw_table, Mapping):
                continue
            rows = raw_table.get("rows")
            if not isinstance(rows, list):
                continue
            descriptions = raw_table.get("column_descriptions")
            tables.append(
                (
                    str(raw_table.get("table_name") or f"table-{ordinal}"),
                    rows,
                    descriptions if isinstance(descriptions, Mapping) else {},
                )
            )
    legacy_rows = document.metadata.get("table_rows")
    if isinstance(legacy_rows, list):
        descriptions = document.metadata.get("table_column_descriptions")
        tables.append(
            (
                str(document.metadata.get("table_name") or "table"),
                legacy_rows,
                descriptions if isinstance(descriptions, Mapping) else {},
            )
        )
    return [
        unit
        for table_name, rows, descriptions in tables
        for unit in _single_table_units(document, table_name, rows, descriptions)
    ]


def _single_table_units(
    document: SourceDocument,
    table_name: str,
    raw_rows: Sequence[object],
    descriptions: Mapping[str, Any],
) -> list[EvidenceUnit]:
    units: list[EvidenceUnit] = []
    provenance = _provenance_metadata(document)
    valid_rows = [raw for raw in raw_rows if isinstance(raw, Mapping)]
    columns = tuple(
        dict.fromkeys(
            str(field)
            for raw in valid_rows
            for field in (
                raw.get("values", {}).keys() if isinstance(raw.get("values"), Mapping) else ()
            )
        )
    )
    table_evidence_id = _evidence_id(f"{document.id}:table:{table_name}")
    units.append(
        EvidenceUnit(
            id=table_evidence_id,
            kind=EvidenceKind.TABLE,
            document_id=document.id,
            parent_id=document.id,
            title=document.title,
            embedding_text=(
                f"[TABLE name={table_name}] columns: {', '.join(columns) or 'unknown'}; "
                f"rows: {len(valid_rows)}"
            ),
            source_uri=document.source_uri,
            source_type=document.source_type,
            domain=document.domain,
            metadata={
                **provenance,
                "table_id": table_evidence_id,
                "table_name": table_name,
                "columns": list(columns),
                "row_count": len(valid_rows),
            },
            knowledge_origin=document.knowledge_origin,
            owner_user_id=document.owner_user_id,
        )
    )
    column_ids: dict[str, str] = {}
    for column in columns:
        column_id = _evidence_id(f"{table_evidence_id}:column:{column}")
        column_ids[column] = column_id
        examples = _column_examples(valid_rows, column)
        description = str(descriptions.get(column) or "").strip()
        units.append(
            EvidenceUnit(
                id=column_id,
                kind=EvidenceKind.TABLE_COLUMN,
                document_id=document.id,
                parent_id=table_evidence_id,
                title=document.title,
                embedding_text=(
                    f"[TABLE_COLUMN table={table_name}] {column}"
                    f"{f' | {description}' if description else ''}"
                    f" | examples: {', '.join(examples) or 'unknown'}"
                ),
                source_uri=document.source_uri,
                source_type=document.source_type,
                domain=document.domain,
                metadata={
                    **provenance,
                    "table_id": table_evidence_id,
                    "table_name": table_name,
                    "column_id": column_id,
                    "column_name": column,
                    "description": description,
                    "examples": examples,
                },
                knowledge_origin=document.knowledge_origin,
                owner_user_id=document.owner_user_id,
            )
        )
    for ordinal, raw in enumerate(raw_rows):
        if not isinstance(raw, Mapping):
            continue
        row_id = str(raw.get("row_id") or f"row-{ordinal}")
        values = raw.get("values")
        if not isinstance(values, Mapping) or not values:
            continue
        row_evidence_id = _evidence_id(f"{document.id}:table:{table_name}:{row_id}")
        units.append(
            EvidenceUnit(
                id=row_evidence_id,
                kind=EvidenceKind.TABLE_ROW,
                document_id=document.id,
                parent_id=table_evidence_id,
                title=document.title,
                embedding_text=linearize_table_row(table_name, row_id, values),
                source_uri=document.source_uri,
                source_type=document.source_type,
                domain=document.domain,
                metadata={
                    **provenance,
                    "table_name": table_name,
                    "table_id": table_evidence_id,
                    "row_id": row_id,
                    "values": dict(values),
                },
                knowledge_origin=document.knowledge_origin,
                owner_user_id=document.owner_user_id,
            )
        )
        for field, value in values.items():
            if not _should_index_fact(field, value):
                continue
            units.append(
                EvidenceUnit(
                    id=_evidence_id(f"{row_evidence_id}:fact:{field}:{_display(value)}"),
                    kind=EvidenceKind.TABLE_FACT,
                    document_id=document.id,
                    parent_id=row_evidence_id,
                    title=document.title,
                    embedding_text=(
                        f"[ROW_FACT table={table_name}] {row_id} | {field} | {_display(value)}"
                    ),
                    source_uri=document.source_uri,
                    source_type=document.source_type,
                    domain=document.domain,
                    metadata={
                        **provenance,
                        "table_name": table_name,
                        "table_id": table_evidence_id,
                        "column_id": column_ids.get(str(field)),
                        "row_id": row_id,
                        "field": str(field),
                        "value": value,
                    },
                    subject=row_id,
                    predicate=str(field),
                    object=_display(value),
                    knowledge_origin=document.knowledge_origin,
                    owner_user_id=document.owner_user_id,
                )
            )
    return units


def _column_examples(rows: Sequence[Mapping[str, Any]], column: str) -> list[str]:
    examples: list[str] = []
    for row in rows:
        values = row.get("values")
        if not isinstance(values, Mapping):
            continue
        value = values.get(column)
        if not _should_index_fact(column, value):
            continue
        displayed = _display(value)
        if displayed not in examples:
            examples.append(displayed)
        if len(examples) == 3:
            break
    return examples


def _should_index_fact(field: object, value: object) -> bool:
    if value is None or isinstance(value, bool):
        return value is not None
    field_name = str(field).strip().lower()
    displayed = str(value).strip()
    if not displayed:
        return False
    if field_name in {"序号", "编号", "index", "ordinal"} and displayed.isdigit():
        return False
    return True


def _evidence_id(value: str) -> str:
    return f"evidence-{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def _provenance_metadata(document: SourceDocument) -> dict[str, Any]:
    keys = ("source_tier", "source_level", "status", "content_hash")
    provenance = {key: document.metadata[key] for key in keys if key in document.metadata}
    if document.published_at:
        provenance["published_at"] = document.published_at
    if document.fetched_at:
        provenance["fetched_at"] = document.fetched_at
    return provenance


def _display(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
