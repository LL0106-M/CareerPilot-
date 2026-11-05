# CBT-Informed Response Strategy Design

## Intent

CareerPilot must make emotional companionship visible in the answer itself. The system
should not merely label emotion or make every reply warmer. It should choose a response
move that matches the user's current state, preserve user control, and render the answer
with readable Markdown structure.

## Goals

- Turn affect appraisal into an explicit response contract consumed by the model.
- Use CBT-informed separation of situation, feeling, judgment, and evidence only when a
  negative automatic thought or self-judgment is present.
- Treat tentative positive interest as exploration, not distress and not a firm decision.
- Control warmth, initiative, verbosity, question target, prohibited moves, and Markdown
  presentation per turn.
- Keep safety, memory, task intent, and external-action authorization in CareerPilot.

## Non-goals and boundaries

- Do not diagnose mental illness or present CBT as therapy.
- Do not infer MBTI or fixed personality traits.
- Do not model the assistant as being hurt, attached, or emotionally dependent.
- Do not add a Node.js runtime or a second memory/relationship store.
- Do not force cognitive reframing when the user is sharing, curious, or asking for action.

## Chosen approach

Implement a small Python-native response-strategy layer inspired by the MIT-licensed
`emoai-affect-engine` appraisal and response-control boundaries. Reuse the useful contract
concepts—bounded appraisal, warmth, caution, initiative, verbosity, and explicit host-side
prompt placement—without importing its character relationship or neurochemical state.

The layer produces an immutable `ResponseContract` from the current message,
`SupportDecision`, and `IntentFrame`. `CareerContextCompiler` builds this contract after
intent routing and passes it to `PromptComposer`. The prompt places the contract near the
final response instructions so it changes what the model says, not merely what telemetry
records.

## Response behavior

For tentative interest such as “我有点想做 Agent 后端开发”, the contract should:

- reflect tentative interest;
- use moderate warmth, low initiative, and short output;
- explore the source of attraction with at most one easy question;
- prohibit a role lecture, multi-question intake, and premature planning.

For a negative automatic thought such as “我技术太差，肯定做不了”, the contract should:

- acknowledge the concrete concern;
- distinguish current facts from the user's conclusion without arguing with them;
- ask for the concrete blocker with at most one question;
- avoid diagnosis, forced positivity, and action pressure.

Explicit listen, organize, explore, and act requests remain authoritative. CBT changes the
shape of a response; it must not override safety routing or user-selected support mode.

## Presentation contract

- Use 2–4 short paragraphs by default, with blank lines between them.
- Bold only the single most useful distinction, conclusion, or next step.
- Use bullets when presenting two or more parallel items.
- Use headings only for genuinely longer structured answers.
- In emotionally intense listen mode, avoid report-like headings and dense numbered steps.
- Keep to one question when a question is needed.

The chat UI must render this restricted Markdown safely. It supports short paragraphs,
bold emphasis, unordered lists, and small headings, while treating model-produced HTML as
plain text. This ensures the response contract changes what the user actually sees rather
than exposing raw Markdown markers in a single text block.

## Attribution

The implementation is informed by the architecture and response-control vocabulary of
Elaine-wy/emoai-affect-engine (MIT). CareerPilot code remains an independent Python
implementation; third-party provenance is documented in the module and repository notice.
