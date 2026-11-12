from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from careerpilot.memory.migration import GovernedMemoryMigrator
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import SqliteUnifiedMemoryStore


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit and migrate legacy CareerPilot memory into the governed pipeline."
    )
    parser.add_argument("--db", type=Path, required=True, help="Path to the SQLite memory DB")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply local quarantine/dedupe/sync-ledger changes (default is dry-run)",
    )
    args = parser.parse_args()

    store = SqliteUnifiedMemoryStore(args.db, read_only=not args.apply)
    try:
        report = GovernedMemoryMigrator(MemoryService(store)).run(dry_run=not args.apply)
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
