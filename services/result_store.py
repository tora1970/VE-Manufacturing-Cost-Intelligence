from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ResultStore:
    def __init__(self, directory: str | Path = "results") -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, technology: str, inputs: dict[str, Any], result: dict[str, Any]) -> Path:
        timestamp = datetime.now(timezone.utc)
        payload = {
            "schema_version": "1.0",
            "created_at_utc": timestamp.isoformat(),
            "technology": technology,
            "inputs": inputs,
            "result": result,
        }
        filename = f"{technology.lower()}-{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        target = self.directory / filename
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)
        return target
