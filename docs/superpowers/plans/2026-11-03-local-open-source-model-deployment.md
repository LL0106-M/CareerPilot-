# Local Open-Source Model Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run CareerPilot against a free, local Qwen3-4B GGUF model served by llama.cpp through the existing OpenAI-compatible model boundary.

**Architecture:** Extend the existing Compose application with a `local-llm` service based on the official llama.cpp server image. CareerPilot calls the model over the private Compose network while the host receives a localhost-only debug endpoint; model weights live in a persistent volume. Existing paid DashScope search remains disabled when its credentials are absent and is not replaced in this plan.

**Tech Stack:** Docker Desktop, Docker Compose, llama.cpp server, Qwen3-4B GGUF Q4_K_M, Python 3.12, Pydantic Settings, pytest

**Spec:** `docs/superpowers/specs/2026-11-03-local-open-source-model-deployment-design.md`

## Global Constraints

- Use `Qwen/Qwen3-4B-GGUF:Q4_K_M`; do not add a paid model dependency.
- Bind the host model endpoint only to `127.0.0.1:8081`; CareerPilot keeps host port `8080`.
- Use context length 4096 and one parallel decode for the conservative CPU baseline.
- Persist downloaded model data in a named Docker volume.
- Do not configure DashScope or MemOS Cloud credentials.
- Do not use the generation model as an embedding model in this plan.
- Preserve every unrelated modification in the existing dirty worktree.

## Review Focus

- Docker is missing or not started: preflight must fail with an actionable message before attempting Compose startup; pinned to Task 3.
- The model is still loading: smoke verification must retry boundedly instead of reporting an immediate failure; pinned to Task 3.
- The model container restarts: the named cache volume must prevent a second model download; pinned to Task 2.
- A LAN client attempts to reach the model port: Compose must bind `127.0.0.1:8081`, not `0.0.0.0:8081`; pinned to Task 2.
- Paid search credentials are absent: application startup must leave search unconfigured without raising; pinned to Task 1.

---

### Task 1: Make the local open-source model the default configuration

**Files:**
- Modify: `src/careerpilot/config.py`
- Modify: `tests/test_config.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: existing `Settings` environment-variable contract.
- Produces: defaults `model_base_url="http://127.0.0.1:8081/v1"`, `model_name="Qwen3-4B-GGUF"`; existing `Settings.search_configured: bool` remains false without both DashScope values.

- [ ] **Step 1: Change the configuration test to assert local defaults**

Rename the paid-model default test to `test_defaults_use_local_open_source_model_without_paid_search` and assert the exact base URL and model name above, plus `search_configured is False`.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests\test_config.py::test_defaults_use_local_open_source_model_without_paid_search -q`

Expected: FAIL because the current default name is `qwen3.7-plus-2026-05-26` and the current port is `8000`.

- [ ] **Step 3: Change only the generation-model defaults**

Update `Settings.model_base_url` and `Settings.model_name`. Keep the optional DashScope connector code backward-compatible, but rewrite `.env.example` so the active example points to the local llama.cpp endpoint and all paid-provider settings are commented as optional legacy configuration.

- [ ] **Step 4: Run configuration tests**

Run: `.venv\Scripts\python.exe -m pytest tests\test_config.py -q`

Expected: all configuration tests PASS, including the no-credentials search assertion.

- [ ] **Step 5: Commit only Task 1 files**

```powershell
git add src/careerpilot/config.py tests/test_config.py .env.example
git commit -m "feat: default to local open source model"
```

### Task 2: Add llama.cpp and Qwen3-4B to the existing Compose stack

**Files:**
- Modify: `compose.yaml`
- Create: `tests/deployment/test_compose_contract.py`

**Interfaces:**
- Consumes: local model defaults from Task 1 and existing `careerpilot` Compose service.
- Produces: Compose service `local-llm`, named volume `local-llm-cache`, private endpoint `http://local-llm:8080/v1`, host endpoint `http://127.0.0.1:8081/v1`.

- [ ] **Step 1: Write the deployment contract test**

Create a test that reads `compose.yaml` and asserts these security-critical exact fragments: service name `local-llm`, image `ghcr.io/ggml-org/llama.cpp:server`, host binding `127.0.0.1:8081:8080`, model selector `Qwen/Qwen3-4B-GGUF:Q4_K_M`, context value `4096`, parallel value `1`, cache volume, model health check, CareerPilot internal model URL, and a dependency on a healthy model service. Keep this test intentionally narrow; Docker Compose performs semantic validation later.

- [ ] **Step 2: Run the deployment contract test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests\deployment\test_compose_contract.py -q`

Expected: FAIL because `local-llm` is absent.

- [ ] **Step 3: Extend `compose.yaml`**

Add `local-llm` with the official server image, `-hf Qwen/Qwen3-4B-GGUF:Q4_K_M`, `--host 0.0.0.0`, container port `8080`, `-c 4096`, `-np 1`, named cache volume, restart policy, and `/health` health check. Override the CareerPilot model URL/name/key in its service environment and require the model health check before app startup.

- [ ] **Step 4: Run the deployment contract test**

Run: `.venv\Scripts\python.exe -m pytest tests\deployment\test_compose_contract.py -q`

Expected: PASS.

- [ ] **Step 5: Run Docker semantic validation when Docker is available**

Run: `docker compose config --quiet`

Expected: exit code 0 with no output. If Docker is not installed yet, defer this check to Task 4 rather than weakening the contract.

- [ ] **Step 6: Commit only Task 2 files**

```powershell
git add compose.yaml tests/deployment/test_compose_contract.py
git commit -m "feat: add local llama cpp model service"
```

### Task 3: Add bounded local-model smoke verification and operator documentation

**Files:**
- Create: `scripts/smoke_local_model.py`
- Create: `tests/scripts/test_smoke_local_model.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: host model endpoint `http://127.0.0.1:8081/v1` from Task 2.
- Produces: command `python scripts/smoke_local_model.py --base-url URL --timeout-seconds N`, returning exit code 0 only after health, model listing, and one chat completion succeed.

- [ ] **Step 1: Write tests for the smoke verifier**

Use a local standard-library fixture HTTP server. Assert that the verifier retries HTTP 503 during model loading, validates `/health`, `/v1/models`, and `/v1/chat/completions`, succeeds on valid JSON, and fails clearly when Docker/model service is unreachable or the timeout expires.

- [ ] **Step 2: Run the smoke verifier tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests\scripts\test_smoke_local_model.py -q`

Expected: FAIL because `scripts/smoke_local_model.py` does not exist.

- [ ] **Step 3: Implement the smoke verifier**

Use only Python standard-library HTTP and JSON modules. Default to `http://127.0.0.1:8081/v1`, use bounded retry with a monotonic deadline, and never print prompts containing user data; the smoke prompt is a fixed non-sensitive Chinese sentence.

- [ ] **Step 4: Document setup and lifecycle commands**

Add a README section covering Docker Desktop prerequisite, first model download size, `docker compose up -d`, logs, smoke verification, stop/restart, cache persistence, CPU expectations, localhost security, and how to raise context only after measuring memory.

- [ ] **Step 5: Run script tests and lint**

Run: `.venv\Scripts\python.exe -m pytest tests\scripts\test_smoke_local_model.py -q`

Run: `.venv\Scripts\python.exe -m ruff check scripts\smoke_local_model.py tests\scripts\test_smoke_local_model.py`

Expected: both commands PASS.

- [ ] **Step 6: Commit only Task 3 files**

```powershell
git add scripts/smoke_local_model.py tests/scripts/test_smoke_local_model.py README.md
git commit -m "docs: add local model deployment verification"
```

### Task 4: Install Docker Desktop and perform live deployment verification

**Files:**
- No repository files unless live verification reveals a configuration defect.

**Interfaces:**
- Consumes: Compose stack and smoke verifier from Tasks 1-3.
- Produces: a running local Qwen3-4B endpoint and recorded verification evidence in the final handoff.

- [ ] **Step 1: Check the Windows package manager**

Run: `winget --version`

Expected: a version string. If unavailable, use Docker Desktop's official installer with explicit user approval for the system-level action.

- [ ] **Step 2: Install Docker Desktop**

Run with escalated approval: `winget install --exact --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements`

Expected: Docker Desktop installs successfully; a Windows sign-out, reboot, or first-run WSL2 setup may be required.

- [ ] **Step 3: Verify Docker is running**

Run: `docker version`

Run: `docker compose version`

Expected: both client and server information are available. If the server is unavailable, start Docker Desktop and complete its first-run setup before continuing.

- [ ] **Step 4: Validate and start the stack**

Run: `docker compose config --quiet`

Run: `docker compose up -d local-llm`

Expected: configuration validation succeeds and the model container starts. The first run downloads roughly 2.5 GB of model weights plus the image.

- [ ] **Step 5: Perform live model smoke verification**

Run: `.venv\Scripts\python.exe scripts\smoke_local_model.py --base-url http://127.0.0.1:8081/v1 --timeout-seconds 600`

Expected: health, model listing, and chat completion all PASS.

- [ ] **Step 6: Start and verify CareerPilot**

Run: `docker compose up -d careerpilot`

Run: `.venv\Scripts\python.exe scripts\smoke_deployment.py --base-url http://127.0.0.1:8080`

Expected: CareerPilot deployment smoke test passes and its model requests use `local-llm`, with no paid provider credentials configured.

### Task 5: Regression verification and handoff

**Files:**
- No planned modifications.

**Interfaces:**
- Consumes: all previous task outputs.
- Produces: verified deployment status, measured first-response behavior, and any environment-only follow-up such as reboot requirements.

- [ ] **Step 1: Run focused regression tests**

Run: `.venv\Scripts\python.exe -m pytest tests\test_config.py tests\deployment\test_compose_contract.py tests\scripts\test_smoke_local_model.py tests\agent\test_model.py -q`

Expected: all tests PASS.

- [ ] **Step 2: Run formatting/lint checks for modified Python files**

Run: `.venv\Scripts\python.exe -m ruff check src\careerpilot\config.py tests\test_config.py tests\deployment\test_compose_contract.py scripts\smoke_local_model.py tests\scripts\test_smoke_local_model.py`

Expected: PASS.

- [ ] **Step 3: Inspect the scoped diff**

Run: `git diff -- .env.example compose.yaml README.md src/careerpilot/config.py tests/test_config.py tests/deployment/test_compose_contract.py scripts/smoke_local_model.py tests/scripts/test_smoke_local_model.py docs/superpowers/specs/2026-11-03-local-open-source-model-deployment-design.md docs/superpowers/plans/2026-11-03-local-open-source-model-deployment.md`

Expected: only the approved local-model deployment changes appear; unrelated dirty files remain untouched.

- [ ] **Step 4: Report live evidence without overstating completion**

Report model name, endpoint, health status, smoke result, whether Docker required restart, and any step that could not run. Do not claim the model is deployed unless the live chat completion succeeded.

