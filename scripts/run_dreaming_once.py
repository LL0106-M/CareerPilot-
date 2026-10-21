"""Process at most one event-triggered Dreaming job; this is not a scheduler."""

import asyncio

from careerpilot.agent.model import create_reasoning_model
from careerpilot.config import Settings
from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.dreaming import DreamingProcessor
from careerpilot.memory.dreaming_llm import JsonDreamingAnalyzer


async def main() -> None:
    settings = Settings()
    store = SqliteCognitiveStore(settings.memory_db_path)
    try:
        processor = DreamingProcessor(
            store,
            JsonDreamingAnalyzer(create_reasoning_model(settings)),
        )
        processed = await processor.run_once()
        print("processed" if processed else "idle")
    finally:
        store.close()


if __name__ == "__main__":
    asyncio.run(main())

