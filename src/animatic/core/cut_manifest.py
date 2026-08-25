"""The cut manifest — what the assembled video is made of, and what is real.

`output/video/index.json`, written alongside the MP4. Follows the same shape as
the panel and audio indexes: beat order, per-shot reasons, honest `s3_ok`.

It carries one thing they do not: `real_footage_pct`. FR-08 requires the system
to report what fraction of the cut is real footage rather than animatic, and
this is where that number is computed — from the shots actually assembled, not
from a count of files in a directory.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from animatic.core.s3_writer import put_bytes
from animatic.core.script_source import script_id

logger = logging.getLogger(__name__)

LOCAL_VIDEO_DIR = Path("output/video")
_LOCAL_INDEX = LOCAL_VIDEO_DIR / "index.json"
_S3_INDEX_KEY = "video/index.json"
_S3_VIDEO_PREFIX = "video"


def build_index(
    entries: list[dict[str, Any]],
    beats_doc: dict[str, Any],
    audio_index: dict[str, Any],
    panel_index: dict[str, Any],
    cut_path: Path | None,
    measured_secs: float | None,
    cut_template_version: str,
) -> dict[str, Any]:
    """Assemble the cut manifest from the shots that were encoded."""
    ordered = sorted(entries, key=lambda e: (e["scene"], e["beat"]))
    by_source: dict[str, int] = {}
    for entry in ordered:
        by_source[entry["shot_source"]] = by_source.get(entry["shot_source"], 0) + 1

    planned = round(sum(e["shot_secs"] for e in ordered), 2)
    # A daily IS real footage — 22 seconds of actual film reported as animatic
    # would understate the cut by exactly the amount that matters most.
    _REAL = ("footage", "daily")
    footage_secs = round(
        sum(e["shot_secs"] for e in ordered if e["shot_source"] in _REAL), 2
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script": script_id(),
        "cut_template_version": cut_template_version,
        "beats_generated_at": beats_doc.get("generated_at", ""),
        "audio_generated_at": audio_index.get("generated_at", ""),
        "audio_template_version": audio_index.get("audio_template_version", ""),
        "panels_generated_at": panel_index.get("generated_at", ""),
        "total_shots": len(ordered),
        "shots_by_source": by_source,
        "planned_secs": planned,
        "measured_secs": round(measured_secs, 2) if measured_secs else None,
        # FR-08: the fraction of the cut that is real footage, by SCREEN TIME
        # rather than by shot count — one 12-second replaced shot is worth more
        # of the cut than three 2-second ones.
        "real_footage_pct": round(100 * footage_secs / planned, 1) if planned else 0.0,
        "real_footage_secs": footage_secs,
        # A daily collapses several beats into one shot, so the cut has fewer
        # shots than the beat list has beats. Saying so keeps the two
        # reconcilable.
        "beats_covered_by_dailies": sorted(
            b for e in ordered for b in e.get("covers_beat_ids", [])
        ),
        "hand_edited_beat_ids": [e["beat_id"] for e in ordered if e.get("hand_made")],
        # Carried from the audio index so a viewer of this file does not have to
        # open that one to learn the cut contains stale or mislabelled audio.
        "stale_audio_beat_ids": audio_index.get("stale_beat_ids", []),
        "text_mismatch_beat_ids": audio_index.get("text_mismatch_beat_ids", []),
        "cut_path": str(cut_path) if cut_path else None,
        "cut_sha256": _sha256(cut_path) if cut_path else None,
        "s3_ok": None,
        "s3_reason": "not yet written",
        "shots": ordered,
    }


def write_cut(cut_path: Path) -> tuple[str, bool, str]:
    """Upload the finished MP4. Returns (s3_uri, ok, reason)."""
    result = put_bytes(
        f"{_S3_VIDEO_PREFIX}/{cut_path.name}",
        cut_path.read_bytes(),
        content_type="video/mp4",
    )
    return result.uri, result.ok, result.error or "put_object succeeded"


def write_index(index: dict[str, Any]) -> dict[str, Any]:
    """Write the manifest locally then to S3, never claiming an unwritten state."""
    _write_local(index)

    result = put_bytes(
        _S3_INDEX_KEY,
        json.dumps(index, indent=2).encode("utf-8"),
        content_type="application/json",
    )
    index["s3_ok"] = result.ok
    index["s3_reason"] = result.error or "put_object succeeded"
    _write_local(index)

    return {
        "local_path": str(_LOCAL_INDEX),
        "s3_uri": result.uri,
        "s3_ok": result.ok,
        "s3_reason": index["s3_reason"],
    }


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _write_local(index: dict[str, Any]) -> None:
    _LOCAL_INDEX.parent.mkdir(parents=True, exist_ok=True)
    _LOCAL_INDEX.write_text(json.dumps(index, indent=2))
