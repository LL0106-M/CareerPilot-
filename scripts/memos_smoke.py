from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime

from careerpilot.memory.memos import MemosCloudMemoryStore


async def main() -> None:
    api_key = os.environ.get("MEMOS_API_KEY", "")
    if not api_key.startswith("mpg-"):
        raise SystemExit("MEMOS_API_KEY is missing or does not start with mpg-")
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    user_id = f"careerpilot_code_smoke_{suffix}"
    conversation_id = f"careerpilot_code_smoke_conv_{suffix}"
    marker = f"云杉-{suffix}"
    store = MemosCloudMemoryStore(
        api_key,
        base_url=os.environ.get(
            "MEMOS_BASE_URL", "https://memos.memtensor.cn/api/openmem/v1"
        ),
    )
    try:
        await store.add_turn(
            user_id,
            conversation_id,
            f"CareerPilot 代码链路测试：记忆代号是{marker}。",
            "已收到这条合成测试信息。",
        )
        for _ in range(6):
            await asyncio.sleep(5)
            context = await store.search(
                user_id, conversation_id, "CareerPilot 代码链路测试的记忆代号是什么？"
            )
            recalled = [item.content for item in (*context.facts, *context.preferences)]
            if any(marker in item for item in recalled):
                print(
                    json.dumps(
                        {"status": "ok", "marker": marker, "retrieved": recalled},
                        ensure_ascii=False,
                    )
                )
                return
        raise SystemExit("MemOS write succeeded but marker was not recalled within 30 seconds")
    finally:
        await store.aclose()


if __name__ == "__main__":
    asyncio.run(main())
