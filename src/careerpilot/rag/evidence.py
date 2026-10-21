import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from careerpilot.rag.models import (
    DocumentChunk,
    EvidenceKind,
    EvidenceUnit,
    KnowledgeTriple,
    SourceDocument,
)


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
) -> tuple[EvidenceUnit, ...]:
    units: list[EvidenceUnit] = [_passage_unit(chunk) for chunk in chunks]
    units.extend(_triple_units(document, chunks))
    units.extend(_table_units(document))
    return tuple(units)


def _passage_unit(chunk: DocumentChunk) -> EvidenceUnit:
    return EvidenceUnit(
        id=f"evidence-{chunk.id}",
        kind=EvidenceKind.PASSAGE,
        document_id=chunk.document_id,
        parent_id=chunk.document_id,
        title=chunk.title,
        embedding_text=f"[PASSAGE heading={chunk.heading}] {chunk.content}",
        source_uri=chunk.source_uri,
        source_type=chunk.source_type,
        domain=chunk.domain,
        metadata={**chunk.metadata, "chunk_id": chunk.id, "heading": chunk.heading},
        knowledge_origin=chunk.knowledge_origin,
        owner_user_id=chunk.owner_user_id,
    )


def _triple_units(
    document: SourceDocument,
    chunks: Sequence[DocumentChunk],
) -> list[EvidenceUnit]:
    raw_triples = document.metadata.get("triples")
    if not isinstance(raw_triples, list):
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
                metadata={**provenance, "chunk_id": parent_id},
                subject=subject,
                predicate=predicate,
                object=object_value,
                knowledge_origin=document.knowledge_origin,
                owner_user_id=document.owner_user_id,
            )
        )
    return units


def _table_units(document: SourceDocument) -> list[EvidenceUnit]:
    raw_rows = document.metadata.get("table_rows")
    if not isinstance(raw_rows, list):
        return []
    table_name = str(document.metadata.get("table_name") or "table")
    units: list[EvidenceUnit] = []
    provenance = _provenance_metadata(document)
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
                parent_id=document.id,
                title=document.title,
                embedding_text=linearize_table_row(table_name, row_id, values),
                source_uri=document.source_uri,
                source_type=document.source_type,
                domain=document.domain,
                metadata={
                    **provenance,
                    "table_name": table_name,
                    "row_id": row_id,
                    "values": dict(values),
                },
                knowledge_origin=document.knowledge_origin,
                owner_user_id=document.owner_user_id,
            )
        )
        for field, value in values.items():
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


def _evidence_id(value: str) -> str:
    return f"evidence-{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def _provenance_metadata(document: SourceDocument) -> dict[str, Any]:
    keys = ("source_tier", "source_level", "status", "content_hash")
    return {key: document.metadata[key] for key in keys if key in document.metadata}


def _display(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
