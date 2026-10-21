# CareerPilot Agentic RAG MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the keyword-only RAG baseline with a compact evidence-centric hybrid retriever supporting structured linearization, optional dense retrieval, query-to-triple graph expansion, RRF fusion, and bounded sufficiency decisions.

**Architecture:** Keep SQLite as the single MVP evidence store. Passage, triple, table-row, and API-object records share one Evidence Unit collection and one FTS index; optional OpenAI-compatible embeddings add dense retrieval without making it a hard dependency. A lightweight provenance graph implements LightRAG-style local expansion, while query-to-triple linking and clues implement HippoRAG2-style iterative retrieval without Neo4j or Milvus.

**Tech Stack:** Python 3.12, SQLite FTS5, LangChain OpenAI-compatible clients, pytest, Ruff.

**Spec:** `PRD/CareerPilot-Memory-RAG-Technical-Design.md` sections 8.1–8.8, amended by the approved LightRAG/HippoRAG2/StructGPT design in this task.

## Global Constraints

- Exploration temperature is exactly `0.4`; evidence reasoning temperature is exactly `0.0`.
- Memory remains in MemOS and is never written into the external evidence store.
- Every graph fact used by retrieval retains a source Evidence Unit or parent chunk.
- Retrieval is hybrid by default; graph retrieval is an enhancement, never the only fallback.
- Maximum retrieval depth is 2 for the MVP.
- No Neo4j, Milvus, dedicated cross-encoder service, or mandatory local embedding download.
- Existing sparse-only deployments continue to work when embeddings are not configured.

## Review Focus

- Empty/blank queries return no evidence rather than issuing invalid FTS SQL.
- A configured dense provider failing at runtime degrades to sparse retrieval.
- Triples without provenance never enter graph expansion.
- Duplicate evidence returned by sparse, dense, and graph paths is fused once.
- Repeated retrieval that adds no new evidence stops before the maximum depth.

---

### Task 1: Temperature-separated model configuration

**Files:**
- Modify: `src/careerpilot/config.py`
- Modify: `src/careerpilot/agent/model.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`
- Test: `tests/agent/test_model.py`

**Interfaces:**
- Produces: `Settings.exploration_temperature`, `Settings.reasoning_temperature`, `create_exploration_model(settings)`, and `create_reasoning_model(settings)`.

- [ ] Write failing tests asserting exact temperatures `0.4` and `0.0` and separate model factories.
- [ ] Run the focused tests and verify they fail because the settings/factories do not exist.
- [ ] Implement the settings and factories while preserving `create_qwen_model` as the exploration-compatible alias.
- [ ] Run focused tests and the existing suite.

### Task 2: Unified Evidence Units and StructGPT-style linearization

**Files:**
- Create: `src/careerpilot/rag/evidence.py`
- Modify: `src/careerpilot/rag/models.py`
- Modify: `src/careerpilot/rag/indexer.py`
- Test: `tests/rag/test_evidence.py`
- Test: `tests/rag/test_indexer.py`

**Interfaces:**
- Produces: `EvidenceUnit`, `EvidenceKind`, `KnowledgeTriple`, `linearize_triple`, `linearize_table_row`, and `build_evidence_units(document, chunks)`.

- [ ] Write failing tests for passage, triple, and table-row linearization with stable provenance IDs.
- [ ] Verify RED.
- [ ] Implement minimal immutable models and metadata-driven evidence construction.
- [ ] Update the indexer to build evidence units without requiring LLM extraction.
- [ ] Verify GREEN and run existing chunk/index tests.

### Task 3: One physical hybrid index with graceful dense fallback

**Files:**
- Create: `src/careerpilot/rag/embeddings.py`
- Modify: `src/careerpilot/rag/store.py`
- Test: `tests/rag/test_store.py`

**Interfaces:**
- Consumes: `EvidenceUnit` from Task 2.
- Produces: `EmbeddingProvider.embed_documents`, `EmbeddingProvider.embed_query`, `SqliteRagStore.search_sparse`, `search_dense`, `neighbors`, and `upsert_evidence`.

- [ ] Write failing tests for storing/searching different Evidence Unit kinds, cosine dense retrieval with a fake embedder, provenance graph neighbors, and dense failure fallback.
- [ ] Verify RED.
- [ ] Add one Evidence Unit table, one FTS table, JSON vector storage, and provenance edges to SQLite.
- [ ] Preserve the legacy chunk API as a compatibility adapter.
- [ ] Verify GREEN and run all store/index tests.

### Task 4: Hybrid retrieval, reranking, clues, and bounded stopping

**Files:**
- Rewrite: `src/careerpilot/rag/retrieval.py`
- Modify: `src/careerpilot/rag/tool.py`
- Modify: `src/careerpilot/api/dependencies.py`
- Test: `tests/rag/test_retrieval.py`
- Test: `tests/rag/test_tool.py`

**Interfaces:**
- Consumes: Task 3 sparse/dense/graph search APIs.
- Produces: semantic `QueryPlan`, RRF-fused `RetrievalResult`, `RetrievalClue`, per-hit channel/role metadata, and stop reasons `enough`, `no_new_evidence`, `max_depth`, or `needs_online_search`.

- [ ] Write failing tests proving sparse+dense+triple fusion, source/facet coverage, no-new-evidence early stop, duplicate suppression, and online-search fallback.
- [ ] Verify RED.
- [ ] Implement low-cost baseline hybrid retrieval for every query, query-to-triple linking, one-hop provenance expansion, RRF, deterministic quality reranking, and two-round stopping.
- [ ] Update tool JSON to expose channels, clues, coverage, and stop reason.
- [ ] Verify GREEN, run the complete test suite, and run Ruff.

### Task 5: Operational documentation

**Files:**
- Modify: `PRD/CareerPilot-RAG-MVP-Design.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: all runtime interfaces above.
- Produces: setup instructions for sparse-only and optional dense modes, plus explicit deferred items.

- [ ] Document the three-store logical architecture while stating the MVP uses one SQLite evidence database plus source files.
- [ ] Document periodic web ingestion as a source-registry contract, not a crawler bundled into the query path.
- [ ] Document that automatic LLM triple extraction, production pgvector, and cross-encoder reranking are deferred behind evaluation gates.
- [ ] Run link/path checks with `rg` and the full verification commands.
