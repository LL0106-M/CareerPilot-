from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, Field

from careerpilot.rag.models import ChunkLevel, DocumentChunk, SourceDocument


class ExtractedRelation(BaseModel):
    subject: str = Field(description="规范化后的实体名称")
    predicate: str = Field(description="简洁、稳定的关系名称")
    object: str = Field(description="规范化后的实体名称或属性值")
    evidence_quote: str = Field(description="支持该关系的原文短句")


class GraphExtractionResult(BaseModel):
    relations: list[ExtractedRelation] = Field(default_factory=list)


class GraphExtractor(Protocol):
    def extract(
        self, document: SourceDocument, chunks: Sequence[DocumentChunk]
    ) -> Sequence[Mapping[str, Any]]: ...


class LlmGraphExtractor:
    """NER + OpenIE extractor constrained to source-grounded professional knowledge."""

    def __init__(
        self,
        model: Any,
        *,
        max_relations_per_chunk: int = 12,
        max_chunks: int | None = None,
    ) -> None:
        self._structured_model = model.with_structured_output(GraphExtractionResult)
        self._max_relations = max_relations_per_chunk
        self._max_chunks = max_chunks

    def extract(
        self, document: SourceDocument, chunks: Sequence[DocumentChunk]
    ) -> Sequence[Mapping[str, Any]]:
        results: list[dict[str, Any]] = []
        child_chunks = [chunk for chunk in chunks if chunk.chunk_level is ChunkLevel.CHILD]
        for chunk in _sample_evenly(child_chunks, self._max_chunks):
            prompt = (
                "你是职业知识库的信息抽取器。先识别并规范化实体，再抽取原文明示的关系。"
                "不得补充常识，不得推断；关系名要简短稳定；证据必须能在原文中逐字找到。"
                f"最多输出 {self._max_relations} 条。\n\n"
                f"文档：{document.title}\n章节：{chunk.heading}\n原文：\n{chunk.content}"
            )
            parsed = self._structured_model.invoke(prompt)
            if isinstance(parsed, Mapping):
                parsed = GraphExtractionResult.model_validate(parsed)
            for relation in parsed.relations[: self._max_relations]:
                subject = relation.subject.strip()
                predicate = relation.predicate.strip()
                object_value = relation.object.strip()
                evidence = relation.evidence_quote.strip()
                if (
                    not subject
                    or not predicate
                    or not object_value
                    or evidence not in chunk.content
                ):
                    continue
                results.append(
                    {
                        "subject": subject,
                        "predicate": predicate,
                        "object": object_value,
                        "evidence_quote": evidence,
                        "chunk_ordinal": chunk.ordinal,
                    }
                )
        return results


def _sample_evenly(
    chunks: Sequence[DocumentChunk], max_chunks: int | None
) -> Sequence[DocumentChunk]:
    if max_chunks is None or max_chunks >= len(chunks):
        return chunks
    if max_chunks <= 0:
        return ()
    return tuple(
        chunks[min(len(chunks) - 1, ((index + 1) * len(chunks)) // (max_chunks + 1))]
        for index in range(max_chunks)
    )
