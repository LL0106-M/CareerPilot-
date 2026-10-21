"""Read-only MemOS connectivity smoke test; never prints secrets or memory content."""

import asyncio

from careerpilot.config import Settings
from careerpilot.memory.memos import MemosCloudMemoryStore


async def main() -> None:
    settings = Settings()
    if settings.memos_api_key is None:
        raise RuntimeError("MEMOS_API_KEY is not configured")
    store = MemosCloudMemoryStore(
        settings.memos_api_key.get_secret_value(),
        base_url=settings.memos_base_url,
    )
    try:
        context = await store.search(
            "careerpilot-integration-smoke",
            "careerpilot-smoke-thread",
            "career exploration",
        )
        print(
            "MemOS live search OK: "
            f"facts={len(context.facts)}, preferences={len(context.preferences)}"
        )
    finally:
        await store.aclose()


if __name__ == "__main__":
    asyncio.run(main())
