# Knowledge Refresh, Intent, and Calendar Design

## Outcome

CareerPilot owns a usable local calendar instead of treating Feishu as the calendar. Users can add an event manually or by saying so in chat, attach a Tencent Meeting URL, choose a reminder, and optionally copy the event to Feishu after preview and confirmation. Knowledge pages show freshly collected material without implying that transient search results have already been saved.

## Confirmed root causes

1. `RuleBasedIntentInterpreter` has no calendar/reminder intent. Messages such as “提醒我明天下午面试” fall through to `general_question`.
2. `journey_tasks` only stores a display date and workflow state. There is no start time, end time, reminder, meeting URL, or general create endpoint.
3. The RAG tool only persists online results when the scope is `preparation`, while the Jobs page says any chat search is saved. The pages also fetch only on mount and expose no explicit refresh or last-updated state.

## Architecture and data flow

The existing owner-scoped `ProductStore` remains the source of truth. A backward-compatible migration adds `start_at`, `end_at`, `reminder_minutes`, `meeting_url`, `notes`, and `created_via` to journey tasks. `POST /v1/me/journey` creates both manual and chat-derived events. The dashboard continues returning journey items, so the current path, calendar, and footprint views stay connected.

At the API chat boundary, a small deterministic parser handles explicit create/remind language only. It extracts a title, common Chinese relative dates/times, a reminder lead time, and an optional Tencent Meeting URL. Ambiguous conversation remains a normal chat and does not create data. The intent classifier reports `calendar_management`, allowing prompts and telemetry to reflect what the user asked for.

The calendar form writes locally first. Browser notification permission is requested only after the user enables a reminder. While the app is open, upcoming reminders use the Notification API; the calendar also shows persistent reminder metadata after reload. Feishu remains an optional, separately confirmed sync action. Tencent Meeting is represented as an attached HTTPS meeting link in this release; direct Tencent API meeting creation is out of scope.

For knowledge, `save_to_library=true` persists validated online sources for either preparation or job scopes. Preparation sources retain the existing document path. Job sources are stored as honest “collected source” records with the source title and URL, rather than inventing structured company/deadline fields. The knowledge UI adds refresh controls and a last-updated indicator, refetches when revisited, and removes the false claim that every transient search is already saved.

## Errors, safety, and testing

All event writes are owner-scoped. The API rejects invalid time ranges, negative reminder values, and non-HTTP(S) meeting links. Chat creation requires both an action verb and a scheduling marker to avoid accidental writes. External Feishu writes retain preview/confirm semantics.

Tests cover intent classification, parser false positives, owner isolation, validation, manual UI creation, calendar rendering, reminder metadata, and knowledge refresh. Each production change begins with a failing test; the focused suites and then full backend/frontend suites are run before completion.
