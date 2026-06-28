#!/usr/bin/env python3
"""Shared local path registry for the storyboard video studio.

The video workflow spans a few local repos and output folders. Keep those
locations in ``studio_paths.json`` so bridge/dashboard scripts do not each
hardcode their own copy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PATHS_FILE = REPO_ROOT / "studio_paths.json"


def load_paths(path: Path = PATHS_FILE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def path_for(key: str, default: Path | None = None) -> Path:
    data = load_paths()
    value = data.get(key)
    if not value:
        if default is not None:
            return default
        raise KeyError(f"Missing studio path key: {key}")
    return Path(value)


def validate_paths() -> dict[str, Any]:
    data = load_paths()
    notes = data.get("notes", {})
    checks = []
    for key, value in data.items():
        if key == "notes":
            continue
        path = Path(value)
        checks.append(
            {
                "key": key,
                "path": str(path),
                "exists": path.exists(),
                "is_dir": path.is_dir(),
                "note": notes.get(key, ""),
            }
        )
    return {
        "paths_file": str(PATHS_FILE),
        "ok": all(item["exists"] and item["is_dir"] for item in checks),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local studio path links")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    result = validate_paths()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Studio paths: {result['paths_file']}")
        for item in result["checks"]:
            status = "OK" if item["exists"] and item["is_dir"] else "MISSING"
            print(f"{status:7} {item['key']}: {item['path']}")
            if item["note"]:
                print(f"        {item['note']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
