# Private User Documents and Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add authenticated Supabase-backed user document upload, private retrieval, reviewed profile extraction, and Agent context integration to CareerPilot.

**Architecture:** FastAPI validates Supabase access tokens, writes private files through Supabase Storage, and stores user-scoped metadata, chunks, vectors, claims, and facts through PostgREST/RPC protected by RLS. A separate polling worker claims durable ingestion jobs, parses and indexes documents, and proposes profile claims; the Agent reads only confirmed profile facts and task-relevant private evidence.

**Tech Stack:** Python 3.12, FastAPI, httpx, PyJWT with cryptography, pypdf, python-docx, PostgreSQL, pgvector, Supabase Auth/Storage/PostgREST, pytest.

**Spec:** `docs/superpowers/specs/2026-10-21-private-user-documents-profile-design.md`

## Global Constraints

- Use Supabase PostgreSQL, pgvector, Storage, Auth, and RLS; do not add a second cloud database.
- First release accepts PDF, DOCX, and TXT only; OCR and image resumes remain out of scope.
- Default upload limits are 15 MB per file and 100 active files per user, both configurable.
- User identity comes only from the verified Supabase JWT; never authorize with a request-body `user_id`.
- Raw documents and extracted fields never write automatically to MemOS.
- Unconfirmed `profile_claims` never enter normal Agent context.
- Every private retrieval result carries document ID, version, and page or section provenance.
- Document processing runs in the standalone durable worker, not a FastAPI background task.
- Preserve existing public RAG and MemOS behavior when Supabase is unconfigured; private-document capability reports unavailable.
- Per user request, every task ends with `git add` and a staged-diff check; do not create Git commits.

## Review Focus

- A forged request-body user ID with a valid token must still access only the token subject; Task 1 pins this in auth/API tests.
- A same-name or same-hash file owned by another user must never deduplicate across users; Task 3 pins user-scoped idempotency.
- A PDF with no extractable text must become `ocr_required`, not `ready` with empty chunks; Task 4 pins this state.
- Deleting the sole source of a confirmed fact must make the fact `disputed` before retrieval resumes; Task 7 pins deletion propagation.
- A normal emotional-support turn must not load resume content; Task 6 pins purpose-based private retrieval.

---

## File Structure

New modules are grouped by responsibility:

```text
supabase/migrations/20261021_private_documents.sql  Schema, RLS, Storage policies, RPCs
src/careerpilot/auth/models.py                      Authenticated principal
src/careerpilot/auth/supabase.py                    JWT verification and legacy fallback
src/careerpilot/cloud/supabase.py                   PostgREST, RPC, and Storage HTTP gateway
src/careerpilot/documents/models.py                 Document, version, job, chunk contracts
src/careerpilot/documents/validation.py             File type/signature/limit validation
src/careerpilot/documents/repository.py             User-scoped persistence contract + Supabase adapter
src/careerpilot/documents/service.py                Upload/list/detail/replace/delete orchestration
src/careerpilot/documents/parsers.py                PDF/DOCX/TXT parsing with provenance
src/careerpilot/documents/worker.py                 Durable ingestion job runner
src/careerpilot/profile/models.py                   Claim/fact contracts
src/careerpilot/profile/extractor.py                Structured claim extraction
src/careerpilot/profile/service.py                  Claim review and profile reads
src/careerpilot/context/private.py                  Private corpus search and formatting
src/careerpilot/api/documents.py                    `/v1/me/documents` router
src/careerpilot/api/profile.py                      `/v1/me/profile` router
scripts/run_document_worker.py                      Worker entrypoint
```

Existing files changed together with those units: `pyproject.toml`, `.env.example`, `src/careerpilot/config.py`, `src/careerpilot/api/app.py`, `src/careerpilot/api/dependencies.py`, `src/careerpilot/api/schemas.py`, `src/careerpilot/agent/service.py`, `src/careerpilot/agent/prompt.py`, and focused tests under `tests/auth`, `tests/documents`, `tests/profile`, `tests/context`, `tests/api`, and `tests/agent`.

### Task 1: Supabase Configuration and Authenticated Principal

**Files:**
- Create: `src/careerpilot/auth/__init__.py`
- Create: `src/careerpilot/auth/models.py`
- Create: `src/careerpilot/auth/supabase.py`
- Create: `src/careerpilot/cloud/__init__.py`
- Create: `src/careerpilot/cloud/supabase.py`
- Modify: `src/careerpilot/config.py`
- Modify: `.env.example`
- Modify: `pyproject.toml`
- Modify: `src/careerpilot/api/dependencies.py`
- Modify: `src/careerpilot/api/schemas.py`
- Modify: `src/careerpilot/api/app.py`
- Test: `tests/auth/test_supabase.py`
- Test: `tests/api/test_auth.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Principal(user_id: str, tenant_id: str, access_token: str)`.
- Produces: `SupabaseAuthenticator.authenticate(token: str) -> Principal`.
- Produces: FastAPI dependency `get_current_principal(authorization: str = Header(...)) -> Principal`.
- Produces: `SupabaseGateway` methods for authenticated PostgREST/RPC calls and service-role Storage/worker calls.

- [ ] **Step 1: Write failing configuration and authentication tests**

Test `Settings` reads `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, bucket name, 15 MB limit, 100-file limit, and 1024 embedding dimensions. Test asymmetric JWT verification validates signature, issuer, audience `authenticated`, expiry, `sub`, and optional `tenant_id`; test legacy/HS256 tokens fall back to `GET /auth/v1/user`. Test missing, malformed, expired, and wrong-issuer tokens return HTTP 401.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_config.py tests/auth/test_supabase.py tests/api/test_auth.py -q`

Expected: FAIL because the auth package and Supabase settings do not exist.

- [ ] **Step 3: Implement configuration, gateway, and auth**

Add dependencies `PyJWT[crypto]>=2.10,<3`, `python-multipart>=0.0.20,<1`, and `python-docx>=1.1,<2`. Implement JWKS verification using `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, with the documented `/auth/v1/user` fallback for legacy shared-secret projects. Cache JWKS for at most ten minutes and never log tokens or keys.

- [ ] **Step 4: Change chat identity to the verified principal**

Remove authorization use of `ChatRequest.user_id`; pass `Principal.user_id` into `ChatCommand`. Keep the field temporarily optional for request compatibility and add a test proving a forged body value cannot change the selected user.

- [ ] **Step 5: Run focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_config.py tests/auth tests/api/test_auth.py tests/api/test_chat.py -q`

Expected: PASS.

- [ ] **Step 6: Stage without committing**

Run: `git add pyproject.toml uv.lock .env.example src/careerpilot/auth src/careerpilot/cloud src/careerpilot/config.py src/careerpilot/api tests/auth tests/api/test_auth.py tests/api/test_chat.py tests/test_config.py`

Verify: `git diff --cached --check` exits 0.

### Task 2: Supabase Schema, RLS, Storage Policies, and RPCs

**Files:**
- Create: `supabase/migrations/20261021_private_documents.sql`
- Create: `tests/supabase/test_private_documents_migration.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: JWT `sub` and `tenant_id` from Task 1.
- Produces: tables `user_documents`, `document_versions`, `document_chunks`, `profile_claims`, `profile_facts`, `document_ingestion_jobs`.
- Produces: RPCs `claim_document_ingestion_job`, `search_private_document_chunks`, `mark_document_deleted`, and `review_profile_claim`.

- [ ] **Step 1: Write failing migration contract tests**

Assert the migration enables `vector`, creates all six tables, enables RLS on each, adds indexes on `(tenant_id, user_id)`, creates Storage policies for bucket `careerpilot-user-documents`, declares `embedding extensions.vector(1024)`, and defines the four RPCs. Assert user-facing RPCs are security-invoker or explicitly filter `auth.uid()`, while worker RPC access is revoked from `anon` and `authenticated`.

- [ ] **Step 2: Run migration tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/supabase/test_private_documents_migration.py -q`

Expected: FAIL because the migration does not exist.

- [ ] **Step 3: Write the idempotent SQL migration**

Use `auth.uid()` and `coalesce(auth.jwt()->>'tenant_id', 'careerpilot')` in row policies. Add Storage `storage.objects` policies that require folder segments `{tenant_id}/{auth.uid()}`. Implement `claim_document_ingestion_job` with `FOR UPDATE SKIP LOCKED`, bounded attempts, and an idempotent lease; implement hybrid full-text/vector search filtered by tenant, user, active document version, and non-deleted status.

- [ ] **Step 4: Document Supabase setup**

Add migration, private bucket, key separation, and local-test instructions to `README.md`. Explicitly state that secret/service keys never enter the browser.

- [ ] **Step 5: Run focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/supabase -q`

Expected: PASS.

- [ ] **Step 6: Stage without committing**

Run: `git add supabase tests/supabase README.md`

Verify: `git diff --cached --check` exits 0.

### Task 3: Document Upload, Listing, Versioning, and Validation

**Files:**
- Create: `src/careerpilot/documents/__init__.py`
- Create: `src/careerpilot/documents/models.py`
- Create: `src/careerpilot/documents/validation.py`
- Create: `src/careerpilot/documents/repository.py`
- Create: `src/careerpilot/documents/service.py`
- Create: `src/careerpilot/api/documents.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `src/careerpilot/api/dependencies.py`
- Test: `tests/documents/test_validation.py`
- Test: `tests/documents/test_service.py`
- Test: `tests/api/test_documents.py`

**Interfaces:**
- Consumes: `Principal` and `SupabaseGateway` from Task 1; schema from Task 2.
- Produces: `DocumentService.upload(principal, upload, kind, title, replace_document_id) -> DocumentReceipt`.
- Produces: `DocumentService.list(principal) -> tuple[UserDocument, ...]` and `get(principal, document_id) -> UserDocumentDetail`.
- Produces: `/v1/me/documents` POST/GET and `/v1/me/documents/{id}` GET endpoints.

- [ ] **Step 1: Write failing file-validation tests**

Cover valid PDF/DOCX/TXT, extension/MIME/signature disagreement, encrypted PDF, macro-enabled OOXML, malformed ZIP, executable signature, empty file, over-15-MB file, and normalized display filenames. Assert rejected data never reaches Storage.

- [ ] **Step 2: Write failing service and API tests**

Assert upload returns HTTP 202 with `document_id`, `version_id`, `status=uploaded`, and status URL. Assert idempotency is scoped to `(tenant_id, user_id, sha256, kind)`, so another user's equal file creates a distinct record. Assert replacement creates a version without changing `current_version_id` before ingestion succeeds. Assert list/detail cannot read another user's records.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/documents tests/api/test_documents.py -q`

Expected: FAIL because document modules and routes do not exist.

- [ ] **Step 4: Implement document contracts and validation**

Define enums `DocumentKind`, `DocumentStatus`, and immutable receipt/detail dataclasses. Implement `validate_upload(filename: str, declared_mime: str | None, content: bytes, max_bytes: int) -> ValidatedUpload` without executing document content.

- [ ] **Step 5: Implement repository, service, and routes**

Upload to `careerpilot-user-documents/{tenant}/{user}/{document}/{version}/{sanitized_filename}`. Create metadata and durable job records through user-JWT PostgREST calls so RLS remains active. Compensate a failed Storage upload by marking the pending version failed; never expose partial records as ready.

- [ ] **Step 6: Run focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/documents tests/api/test_documents.py -q`

Expected: PASS.

- [ ] **Step 7: Stage without committing**

Run: `git add src/careerpilot/documents src/careerpilot/api tests/documents tests/api/test_documents.py`

Verify: `git diff --cached --check` exits 0.

### Task 4: Durable Parsing and Private Indexing Worker

**Files:**
- Create: `src/careerpilot/documents/parsers.py`
- Create: `src/careerpilot/documents/worker.py`
- Create: `scripts/run_document_worker.py`
- Test: `tests/documents/test_parsers.py`
- Test: `tests/documents/test_worker.py`

**Interfaces:**
- Consumes: `SupabaseGateway`, document repository, RPC `claim_document_ingestion_job`, and existing `EmbeddingProvider`.
- Produces: `parse_document(filename: str, mime_type: str, content: bytes) -> ParsedDocument`.
- Produces: `DocumentIngestionWorker.run_once() -> bool` and `run_forever(poll_seconds: float) -> None`.
- Produces: indexed `DocumentChunk` rows with `page_number` or `section_path`.

- [ ] **Step 1: Write failing parser tests**

Assert PDF page numbers, DOCX heading/paragraph/table provenance, TXT paragraph provenance, invalid encodings, encrypted PDFs, and empty/scanned PDFs. The empty/scanned PDF result must be `ocr_required` with zero chunks.

- [ ] **Step 2: Write failing worker tests**

Assert one claimed job moves through `parsing → indexing → review_required`; duplicate delivery replaces the same version's chunks rather than duplicating them; 1024-dimensional vectors are accepted; wrong dimensions fail deterministically; embedding failure writes text/FTS chunks and marks degraded indexing; leases and maximum attempts prevent endless retries.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/documents/test_parsers.py tests/documents/test_worker.py -q`

Expected: FAIL because parsers and worker do not exist.

- [ ] **Step 4: Implement parsers and provenance-aware chunking**

Define `ParsedBlock(text: str, page_number: int | None, section_path: str | None, ordinal: int)` and `ParsedDocument(blocks, status)`. Reuse the existing chunking principles but never pass private documents through `SqliteRagStore`.

- [ ] **Step 5: Implement the durable worker**

Use only the secret/service credential in the worker process. Claim one job atomically, download the private object, parse, replace chunks transactionally through RPC, generate embeddings when configured, update job/document statuses, and record only stage/error codes.

- [ ] **Step 6: Run focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/documents/test_parsers.py tests/documents/test_worker.py -q`

Expected: PASS.

- [ ] **Step 7: Stage without committing**

Run: `git add src/careerpilot/documents scripts/run_document_worker.py tests/documents`

Verify: `git diff --cached --check` exits 0.

### Task 5: Profile Claim Extraction and User Review

**Files:**
- Create: `src/careerpilot/profile/__init__.py`
- Create: `src/careerpilot/profile/models.py`
- Create: `src/careerpilot/profile/extractor.py`
- Create: `src/careerpilot/profile/service.py`
- Create: `src/careerpilot/api/profile.py`
- Modify: `src/careerpilot/documents/worker.py`
- Modify: `src/careerpilot/api/app.py`
- Modify: `src/careerpilot/api/dependencies.py`
- Test: `tests/profile/test_extractor.py`
- Test: `tests/profile/test_service.py`
- Test: `tests/api/test_profile.py`

**Interfaces:**
- Consumes: parsed chunks and current project model gateway.
- Produces: `ProfileExtractor.extract(document, chunks) -> tuple[ProfileClaimDraft, ...]`.
- Produces: `ProfileService.list_claims(principal)`, `review_claim(principal, claim_id, decision, edited_value)`, and `get_profile(principal)`.
- Produces: `/v1/me/profile`, `/v1/me/profile/claims`, and claim PATCH endpoint.

- [ ] **Step 1: Write failing extraction tests**

Assert structured extraction allows only the documented profile domains, requires evidence chunk IDs, uses confidence bands rather than numeric certainty, rejects evidence-free claims, and never emits psychological, moral, health, inferred-sensitive, or unsupported individual-credit labels.

- [ ] **Step 2: Write failing review/API tests**

Assert pending claims are excluded from `get_profile`; accept creates an active fact; edit preserves original candidate and audit fields; reject creates no fact; conflicts remain visible; another user cannot review the claim; malformed edits return 422.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/profile tests/api/test_profile.py -q`

Expected: FAIL because profile modules and routes do not exist.

- [ ] **Step 4: Implement schemas and structured extraction**

Use the existing OpenAI-compatible model path with deterministic temperature and Pydantic validation. Treat document text as untrusted quoted data. The worker stores validated drafts only and changes the document to `review_required` when at least one pending claim exists, otherwise `ready`.

- [ ] **Step 5: Implement review transactions and routes**

Call `review_profile_claim` RPC so claim status and versioned fact updates occur atomically. Require `edited_value` only for `edited`; use optimistic version checks and return HTTP 409 on conflicts.

- [ ] **Step 6: Run focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/profile tests/api/test_profile.py tests/documents/test_worker.py -q`

Expected: PASS.

- [ ] **Step 7: Stage without committing**

Run: `git add src/careerpilot/profile src/careerpilot/api src/careerpilot/documents/worker.py tests/profile tests/api/test_profile.py tests/documents/test_worker.py`

Verify: `git diff --cached --check` exits 0.

### Task 6: Private Corpus Retrieval and Agent Context Integration

**Files:**
- Create: `src/careerpilot/context/__init__.py`
- Create: `src/careerpilot/context/private.py`
- Modify: `src/careerpilot/agent/service.py`
- Modify: `src/careerpilot/agent/prompt.py`
- Modify: `src/careerpilot/api/dependencies.py`
- Test: `tests/context/test_private.py`
- Test: `tests/agent/test_service.py`
- Test: `tests/agent/test_prompt.py`

**Interfaces:**
- Consumes: confirmed profile facts, private search RPC, existing `MemoryStore`, support decision, and EmbeddingProvider.
- Produces: `PrivateContextPlanner.plan(message: str, support_mode: SupportMode) -> PrivateContextPlan`.
- Produces: `PrivateCorpusStore.search(user_id, tenant_id, query, document_ids, limit) -> tuple[PrivateDocumentHit, ...]`.
- Produces: `PersonalContext(profile_facts, private_hits, read_status)` injected by `PromptComposer`.

- [ ] **Step 1: Write failing routing and formatting tests**

Assert resume/job-fit, resume-editing, personal-statement, interview-evidence, and explicit-file questions request private context. Assert ordinary emotional-support, small talk, and unrelated public-knowledge questions do not. Assert hits render as untrusted evidence with document ID, version, page/section, and no executable instructions.

- [ ] **Step 2: Write failing Agent integration tests**

Assert the Agent combines MemOS, confirmed profile facts, private evidence, and public RAG in the specified order. Assert private-search failure degrades without claiming to know the resume. Assert pending claims never appear. Assert a forged body user ID cannot choose the private-search namespace.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/context tests/agent/test_service.py tests/agent/test_prompt.py -q`

Expected: FAIL because private context integration does not exist.

- [ ] **Step 4: Implement purpose planning and hybrid search**

Use deterministic intent rules for the first release, not an extra model call. Generate query embeddings only when configured, call the user-scoped hybrid RPC, cap private hits at five, deduplicate by chunk hash, and exclude non-current/deleting/deleted versions.

- [ ] **Step 5: Integrate into AgentService and PromptComposer**

Load confirmed profile facts for relevant career tasks; search document content only when the plan requests it. Keep existing listen-mode tool prohibition and MemOS failure behavior. Add internal status fields without exposing implementation details in the response text.

- [ ] **Step 6: Run focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/context tests/agent tests/api/test_chat.py -q`

Expected: PASS.

- [ ] **Step 7: Stage without committing**

Run: `git add src/careerpilot/context src/careerpilot/agent src/careerpilot/api/dependencies.py tests/context tests/agent tests/api/test_chat.py`

Verify: `git diff --cached --check` exits 0.

### Task 7: Replacement, Deletion Propagation, and Failure Recovery

**Files:**
- Modify: `src/careerpilot/documents/service.py`
- Modify: `src/careerpilot/documents/repository.py`
- Modify: `src/careerpilot/documents/worker.py`
- Modify: `src/careerpilot/api/documents.py`
- Modify: `supabase/migrations/20261021_private_documents.sql`
- Test: `tests/documents/test_lifecycle.py`
- Test: `tests/api/test_documents.py`

**Interfaces:**
- Consumes: document/version/job/profile contracts and deletion RPC from earlier tasks.
- Produces: `DocumentService.delete(principal, document_id) -> DeleteReceipt` and completed replacement activation.

- [ ] **Step 1: Write failing lifecycle tests**

Assert delete immediately hides download/search, then removes Storage and chunks, rejects pending claims, marks sole-source confirmed facts `disputed`, preserves facts with another active source, and is idempotent. Assert replacement atomically switches `current_version_id` only after indexing succeeds and preserves the old current version on failure.

- [ ] **Step 2: Write failing compensation tests**

Cover Storage upload succeeds/database finalization fails, database pending row succeeds/Storage upload fails, worker dies after claiming, deletion partially fails, and duplicate retry. Assert every case is retryable without duplicate versions, chunks, claims, or destructive cross-user effects.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/documents/test_lifecycle.py tests/api/test_documents.py -q`

Expected: FAIL until lifecycle orchestration and RPC behavior are complete.

- [ ] **Step 4: Implement lifecycle and compensation behavior**

Use durable states and RPC transactions for database changes; Storage deletion remains an idempotent external step. Do not return a completed deletion receipt until Storage, chunks, claims, fact disposition, and caches have all been verified.

- [ ] **Step 5: Run focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/documents tests/profile tests/api/test_documents.py -q`

Expected: PASS.

- [ ] **Step 6: Stage without committing**

Run: `git add src/careerpilot/documents src/careerpilot/api/documents.py supabase tests/documents tests/api/test_documents.py`

Verify: `git diff --cached --check` exits 0.

### Task 8: End-to-End Verification and Operator Documentation

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Create: `scripts/private_documents_smoke.py`
- Create: `tests/integration/test_private_documents_flow.py`
- Modify: any focused file required to fix failures found by this task

**Interfaces:**
- Consumes: all earlier task interfaces.
- Produces: documented setup, read-only-by-default smoke checks, and a complete staged implementation.

- [ ] **Step 1: Write the end-to-end test with fakes/local Supabase fixtures**

Exercise authenticate → upload → worker → pending claims → user review → private retrieval → Agent context → delete. Include cross-user denial at list, object, RPC, claim-review, and Agent layers.

- [ ] **Step 2: Add a safe smoke script**

Implement `private_documents_smoke.py` to verify configuration and read health without uploading by default. Require `--write-test` plus an explicit test user token to perform a disposable upload/search/delete round trip; never print secrets or document text.

- [ ] **Step 3: Complete operator documentation**

Document Supabase project setup, SQL migration, private bucket, environment variables, API examples, worker command, RLS verification, degraded modes, and deletion verification. Link the official Supabase Auth/JWT, private Storage, RLS, and pgvector RPC guidance used by the implementation.

- [ ] **Step 4: Run all quality gates**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: all tests PASS.

Run: `.venv\Scripts\ruff.exe check src tests scripts`

Expected: exit 0.

Run: `git diff --cached --check`

Expected: exit 0.

- [ ] **Step 5: Review staged scope**

Run: `git status --short` and `git diff --cached --stat`.

Expected: only the plan and implementation files listed above are staged; unrelated user files remain untouched and unstaged. Do not commit.

## Official Implementation References

- Supabase JWT verification and JWKS: https://supabase.com/docs/guides/auth/jwts
- Supabase Auth and RLS integration: https://supabase.com/docs/guides/auth
- Private Storage buckets and signed access: https://supabase.com/docs/guides/storage/buckets/fundamentals
- pgvector semantic search through PostgreSQL RPC: https://supabase.com/docs/guides/ai/semantic-search
