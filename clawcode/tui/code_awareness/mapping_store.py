"""Persistence helpers for code awareness architecture maps."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .state import ArchitectureMap, FileChangeEvent

_MAP_DIR = ".clawcode/code_awareness"
_MAP_FILE = "architecture_map.json"
_MAX_EVENTS = 200


def map_file_path(working_directory: str) -> Path:
    root = Path(working_directory).expanduser()
    return root / _MAP_DIR / _MAP_FILE


def load_architecture_map(working_directory: str) -> ArchitectureMap | None:
    path = map_file_path(working_directory)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    try:
        event_rows = data.get("file_events", [])
        file_events: list[FileChangeEvent] = []
        for row in event_rows:
            if not isinstance(row, dict):
                continue
            file_events.append(
                FileChangeEvent(
                    timestamp=float(row.get("timestamp", 0.0) or 0.0),
                    path=str(row.get("path", "")),
                    directory=str(row.get("directory", "")),
                    layer=str(row.get("layer", "Other")),
                    kind=str(row.get("kind", "modified")),
                )
            )
        return ArchitectureMap(
            version=int(data.get("version", 1) or 1),
            project_root=str(data.get("project_root", "")),
            updated_at=float(data.get("updated_at", 0.0) or 0.0),
            source=str(data.get("source", "fallback_rules")),
            model_info=dict(data.get("model_info", {})),
            layers={k: list(v) for k, v in dict(data.get("layers", {})).items()},
            dir_to_layer={k: str(v) for k, v in dict(data.get("dir_to_layer", {})).items()},
            layer_descriptions={
                k: str(v) for k, v in dict(data.get("layer_descriptions", {})).items()
            },
            layer_order=[str(x) for x in list(data.get("layer_order", []))],
            file_events=file_events[:_MAX_EVENTS],
        )
    except Exception:
        return None


def save_architecture_map(working_directory: str, mapping: ArchitectureMap) -> Path:
    path = map_file_path(working_directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for ev in mapping.file_events[-_MAX_EVENTS:]:
        rows.append(
            {
                "timestamp": ev.timestamp,
                "path": ev.path,
                "directory": ev.directory,
                "layer": ev.layer,
                "kind": ev.kind,
            }
        )
    payload = {
        "version": mapping.version,
        "project_root": mapping.project_root,
        "updated_at": mapping.updated_at or time.time(),
        "source": mapping.source,
        "model_info": mapping.model_info,
        "layers": mapping.layers,
        "dir_to_layer": mapping.dir_to_layer,
        "layer_descriptions": mapping.layer_descriptions,
        "layer_order": mapping.layer_order,
        "file_events": rows,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path

