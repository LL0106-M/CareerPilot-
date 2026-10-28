# Chat Workspace Integration Design

## Intent

Turn the chat workspace from a mostly static mockup into a durable, responsive product surface. A signed-in user must see saved conversations, reopen them, receive model output incrementally, and see right-rail context derived from their own dashboard data.

## Goals

- Load, refresh, select, and reopen owner-scoped conversations through the existing backend store.
- Stream assistant text to the browser while preserving the existing JSON chat endpoint.
- Populate the right rail from the authenticated dashboard response instead of hard-coded copy.
- Accept authenticated same-origin mutations when the app is reached through a reverse proxy such as ngrok, without accepting arbitrary cross-site origins.
- Preserve the current visual language and responsive panel behavior.

## Non-goals

- Conversation folders, renaming, deletion, pagination, and search.
- A new state-management dependency.
- Redesigning the agent orchestration, retrieval policy, or model selection.

## Constraints

- Existing `/v1/chat` clients remain compatible.
- Streaming uses native `fetch` and SSE; no new frontend package.
- Conversation persistence remains owner-scoped and occurs only after a completed turn.
- Same-origin approval compares the browser origin with the effective forwarded host/protocol or configured CORS origins.

## Approaches

1. Poll the existing JSON endpoint and fake typing after completion. Smallest backend change, but it does not improve time-to-first-token and misrepresents actual latency.
2. Add a dedicated SSE endpoint backed by the existing harness event stream. Selected because it exposes real deltas, preserves `/v1/chat`, and reuses the current event-driven runtime.
3. Replace the chat API with WebSockets. Rejected because bidirectional transport is unnecessary for this request and adds deployment/state complexity.

## Design

`POST /v1/chat/stream` emits `delta`, `completed`, and `error` SSE events. `AgentService.stream_chat` owns the same understand/plan/execute/verify/learn lifecycle as `chat`; the JSON method collects the stream so the two paths cannot drift. On completion, the API persists the turn and emits the final response metadata.

The frontend API client parses SSE incrementally. `ChatPage` loads conversations and dashboard context on mount, refreshes the list after a completed turn, and loads messages when a conversation is selected. During a response it maintains one in-progress agent message and appends deltas to it.

The right rail selects the newest Dreaming item and the first pending/uncertain hypothesis from `getDashboard()`. Empty and failed states remain honest rather than showing demo content.
