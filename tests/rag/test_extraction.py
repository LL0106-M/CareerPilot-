from careerpilot.rag.extraction import GraphExtractionResult, LlmGraphExtractor
from careerpilot.rag.models import DocumentChunk, SourceDocument


class RecordingStructuredGenerator:
    def __init__(self) -> None:
        self.calls = []

    def generate(self, prompt, response_model):
        self.calls.append((prompt, response_model))
        return GraphExtractionResult.model_validate(
            {
                "relations": [
                    {
                        "subject": "RAG",
                        "predicate": "使用",
                        "object": "向量检索",
                        "evidence_quote": "RAG 使用向量检索",
                    }
                ]
            }
        )


def test_llm_graph_extractor_uses_native_structured_generator() -> None:
    generator = RecordingStructuredGenerator()
    document = SourceDocument(
        "doc-1",
        "RAG",
        "file:///rag.md",
        "developer_upload",
        "preparation_material",
        "RAG 使用向量检索。",
    )
    chunks = (
        DocumentChunk(
            "chunk-1",
            "doc-1",
            0,
            "RAG",
            "Overview",
            "RAG 使用向量检索。",
            "file:///rag.md",
            "developer_upload",
            "preparation_material",
        ),
    )

    relations = LlmGraphExtractor(generator).extract(document, chunks)

    assert relations == [
        {
            "subject": "RAG",
            "predicate": "使用",
            "object": "向量检索",
            "evidence_quote": "RAG 使用向量检索",
            "chunk_ordinal": 0,
        }
    ]
    assert generator.calls[0][1] is GraphExtractionResult
