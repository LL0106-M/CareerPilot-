# Journey Future Letter Design

## Goal

Add a lightweight future-simulation experience to the existing Journey path view without replacing its current task, calendar, footprint, or external-app flows.

## Product behavior

- The existing focus action remains the primary object on screen.
- A tertiary action, “给未来的我写一句话”, opens a translucent glass panel below the focus card.
- CareerPilot makes one structured model call and returns exactly three scenarios: continuing the current route, taking an adjacent route, and an unexpected third route.
- Scenarios describe plausible changes, tensions, evidence, and one open question. They never present probabilities, guaranteed outcomes, salaries, or specific employers as facts.
- “问未来的我” reuses the existing chat route with temporary scenario context.
- “带回一个问题” requires explicit confirmation and stores only the chosen question as a Journey takeaway. It does not create a task or memory.

## Data boundary

Future letters and their takeaways are owner-scoped Journey artifacts. Generated prose is not canonical memory and is not counted as a footprint. The server validates the three scenario kinds and persists the artifact separately from existing Journey tasks.

## Visual direction

Match the selected mock while preserving the current design system: translucent warm glass, backdrop blur, hairline white borders, soft pine and gold accents, and the existing typography. Avoid paper textures, stamps, or opaque paper cards. The panel must remain subordinate to the current focus action and work in one-column mobile layouts.

