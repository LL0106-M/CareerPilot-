# Global Bobo Companion Design

## Intent

CareerPilot should feel like one Personal Agent accompanying the user across the product, not a collection of disconnected pages. Every protected page gets a context-aware Bobo entry point. Clicking Bobo opens a side conversation without hiding the page; the full chat page remains the place for history and long conversations.

## Goals

- Keep one continuous Bobo conversation across route changes and hand it off to the full chat page.
- Give each page a distinct Bobo mood, motion, accent, greeting, and page-aware suggestions.
- Send bounded page context to the agent without mixing that metadata into the user's message or long-term memory.
- Reuse the existing `/v1/chat/stream`, conversation history, direction-signal, and memory pipeline.
- Make memory behavior visible and link to the existing memory management experience.

## Non-goals

- Do not create a second chat backend or a second memory store.
- Do not give Bobo permission to mutate memory or product state without the existing confirmation rules.
- Do not add generated character assets in this slice; use the existing Bobo asset with distinct motion and visual treatments.
- Do not redesign individual product pages.

## Chosen approach

### Considered

1. **Independent Bobo per page:** easy page customization, but fragments conversations and memory.
2. **Link every Bobo to `/chat`:** simple, but removes in-context collaboration and makes the page feel static.
3. **One global companion layer:** a route-aware dock and drawer live in `AppShell`, share one conversation ID, and hand off to `/chat` when the user wants depth.

Choose approach 3. It preserves continuity while keeping each page visually and behaviorally distinct.

## Interaction design

- On non-chat pages, Bobo appears as a small animated dock at bottom right with a short route-specific prompt.
- Clicking the dock opens a non-modal right drawer. The current page remains visible.
- The drawer shows the current page label, shared conversation messages, a compact composer, memory-write status, a link to memory management, and a link to open the same conversation in full chat.
- On `/chat`, the global dock is hidden because the page-level Bobo and full workspace already represent the same agent.
- Route changes retain the shared conversation ID in local storage. The new route updates Bobo's mood and context, but does not silently send a message.
- Reduced-motion users receive static presentation.

## Page personalities

- Home: `idle`, gentle floating, “从一件小事开始”.
- Compass: `explore`, searching arc accent, “一起看看这个方向还缺什么”.
- Journey: `act`, forward-leaning pulse, “现在只推进下一步”.
- Knowledge: `organize`, sorting rhythm, “我可以帮你把资料和方向连起来”.
- Dreaming: `dreaming`, slow orbit, “最近的线索正在连接”.
- Settings and Memory: `organize`, quiet motion, “这些内容由你控制”.

## Conversation and memory contract

- Sidebar and full chat use the same API and `conversation_id`.
- The full chat route accepts a conversation ID in route state and opens it.
- `page_context` is a validated request object containing route, page key, label, and optional entity/state summaries.
- Backend appends page context to the system prompt only. The raw user message is what conversation history, direction detection, and memory extraction receive.
- Memory-write status is shown after each response. Detailed confirm/pause/edit/delete remains in `/memory`.

## Accessibility and responsive behavior

- Dock is a real button with an explicit label and expanded state.
- Drawer has a named complementary region, close control, live message stream, and labeled composer.
- Escape closes the drawer. Mobile drawer fills the viewport width below the top bar.
- Focus returns to the dock after closing when possible.
