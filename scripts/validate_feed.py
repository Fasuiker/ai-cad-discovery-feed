from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/latest.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload.get("schema_version") == 1
    assert isinstance(payload.get("profile"), str) and payload.get("profile")
    candidates = payload.get("candidates")
    assert isinstance(candidates, list)
    stable_ids: set[str] = set()
    for row in candidates:
        assert row.get("stable_id")
        assert row.get("title")
        assert row["stable_id"] not in stable_ids
        stable_ids.add(row["stable_id"])
    assert payload.get("count") == len(candidates)
    print(f"OK: {len(candidates)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
