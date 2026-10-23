import os
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    input: str | list[str]
    model: str | None = None
    encoding_format: Literal["float"] = "float"
    dimensions: int | None = Field(default=None, ge=32, le=1024)


class EmbeddingEngine:
    def __init__(
        self,
        model_id: str,
        *,
        device: str = "cpu",
        batch_size: int = 16,
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.model_id = model_id
        self.device = device
        self.batch_size = batch_size
        if model_factory is None:
            from sentence_transformers import SentenceTransformer

            model_factory = SentenceTransformer
        self._model = model_factory(model_id, device=device, local_files_only=True)

    def encode(self, texts: list[str], *, dimensions: int | None = None) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            truncate_dim=dimensions,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def count_tokens(self, texts: list[str]) -> int:
        tokenizer = getattr(self._model, "tokenizer", None)
        if tokenizer is None:
            return sum(max(1, len(text) // 2) for text in texts)
        encoded = tokenizer(texts, truncation=True, padding=False)
        return sum(len(token_ids) for token_ids in encoded["input_ids"])


def create_embedding_app(engine: EmbeddingEngine | None = None) -> FastAPI:
    state: dict[str, EmbeddingEngine] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state["engine"] = engine or EmbeddingEngine(
            os.getenv("CAREERPILOT_LOCAL_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B"),
            device=os.getenv("CAREERPILOT_LOCAL_EMBEDDING_DEVICE", "cpu"),
            batch_size=int(os.getenv("CAREERPILOT_LOCAL_EMBEDDING_BATCH_SIZE", "16")),
        )
        yield

    app = FastAPI(title="CareerPilot Embedding Service", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, object]:
        active = state["engine"]
        return {"status": "ok", "model": active.model_id, "device": active.device}

    @app.get("/v1/models")
    def models() -> dict[str, object]:
        active = state["engine"]
        return {
            "object": "list",
            "data": [{"id": active.model_id, "object": "model", "owned_by": "careerpilot"}],
        }

    @app.post("/v1/embeddings")
    def embeddings(request: EmbeddingRequest) -> dict[str, object]:
        active = state["engine"]
        if request.model and request.model != active.model_id:
            raise HTTPException(status_code=404, detail=f"model not loaded: {request.model}")
        texts = [request.input] if isinstance(request.input, str) else request.input
        if not texts or len(texts) > 128 or any(not text.strip() for text in texts):
            raise HTTPException(
                status_code=422, detail="input must contain 1 to 128 non-empty texts"
            )
        started = time.perf_counter()
        vectors = active.encode(texts, dimensions=request.dimensions)
        prompt_tokens = active.count_tokens(texts)
        return {
            "object": "list",
            "model": active.model_id,
            "data": [
                {"object": "embedding", "index": index, "embedding": vector}
                for index, vector in enumerate(vectors)
            ],
            "usage": {"prompt_tokens": prompt_tokens, "total_tokens": prompt_tokens},
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    return app


app = create_embedding_app()
