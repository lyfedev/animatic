"""Beat list assembler — collects beats from all scenes, writes to S3 and local."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from animatic.core.beat_extractor import Beat
from animatic.core.s3_writer import put_bytes
from animatic.core.script_source import script_id

logger = logging.getLogger(__name__)

_LOCAL_OUTPUT = Path("output/beats.json")
_S3_KEY = "beats/latest.json"


def assemble_and_write(scenes_beats: dict[int, list[Beat]]) -> str:
    """Assemble beat list from all scenes and write to S3 and local.

    Args:
        scenes_beats: dict mapping scene_number → list of Beat objects.

    Returns:
        S3 URI of the written beat list (e.g. s3://bucket/beats/latest.json).
    """
    beat_list = _build_beat_list(scenes_beats)
    _write_local(beat_list)
    s3_uri = _write_s3(beat_list)
    return s3_uri


def _build_beat_list(scenes_beats: dict[int, list[Beat]]) -> dict[str, Any]:
    """Build the full beat list manifest."""
    all_beats = []
    for scene_num in sorted(scenes_beats.keys()):
        all_beats.extend(b.to_dict() for b in scenes_beats[scene_num])

    total_duration = sum(b["duration_secs"] for b in all_beats)
    motion_count = sum(1 for b in all_beats if b["motion_candidate"])
    pct_motion = round(motion_count / len(all_beats) * 100, 1) if all_beats else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script": script_id(),
        "scenes": sorted(scenes_beats.keys()),
        "total_beats": len(all_beats),
        "total_duration_secs": round(total_duration, 1),
        "pct_motion_candidates": pct_motion,
        "beats": all_beats,
    }


def _write_local(beat_list: dict[str, Any]) -> None:
    """Write beat list to local output file."""
    _LOCAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCAL_OUTPUT, "w") as f:
        json.dump(beat_list, f, indent=2)
    logger.info("Beat list written locally to %s", _LOCAL_OUTPUT)


def _write_s3(beat_list: dict[str, Any]) -> str:
    """Write beat list to S3, return S3 URI.

    Routes through the shared `s3_writer.put_bytes` (T-03-05 honesty) —
    session/profile handling now lives in one place. The return contract is
    unchanged from before this refactor (a real `s3://...` URI on success,
    a `local://...` marker on failure) so Phase 2's API and CLI stay
    untouched; only the log level moves from WARNING to ERROR, and the
    `local://` marker is now returned from the one place that genuinely
    knows the write failed rather than being fabricated inline.
    """
    body = json.dumps(beat_list, indent=2).encode("utf-8")
    result = put_bytes(_S3_KEY, body, content_type="application/json")
    if not result.ok:
        logger.error("S3 write failed (%s) — local output only", result.error)
        return f"local://{_LOCAL_OUTPUT}"
    logger.info("Beat list written to %s", result.uri)
    return result.uri
