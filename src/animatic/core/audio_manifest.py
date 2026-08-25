"""Audio index assembler — writes each clip to local disk and S3, and the
running `output/audio/index.json` that names every beat's audio, its voice,
its measured length, the shot length it implies, and a machine-readable
reason for each.

Follows `panel_manifest.py` exactly, including the two rules that phase paid
for:

- `write_index` is called after EACH beat resolves, not once at the end. A run
  interrupted at beat 40 of 49 keeps 40 entries on disk and in S3.
- filenames are built from `beat_id` asserted against `^s\\d+b\\d+$`, never
  from beat content.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from animatic.core.s3_writer import put_bytes

logger = logging.getLogger(__name__)

LOCAL_AUDIO_DIR = Path("output/audio")
_LOCAL_INDEX = Path("output/audio/index.json")
_S3_INDEX_KEY = "audio/index.json"
_S3_AUDIO_PREFIX = "audio"

_BEAT_ID_RE = re.compile(r"^s\d+b\d+$")
_CUE_ID_RE = re.compile(r"^scene\d+$")

_EXT_FOR_MIME = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/ogg": "ogg",
}


def write_clip(
    clip_id: str, audio_bytes: bytes, mime_type: str, prefix: str = ""
) -> tuple[str, Path, str, bool, str]:
    """Write one clip's bytes to local disk and S3.

    Returns (content_hash, local_path, s3_uri, s3_ok, s3_reason). `clip_id` is
    asserted against the beat-id or cue-id shape before it is used to build a
    path — no path segment is ever built from beat content.
    """
    assert _BEAT_ID_RE.match(clip_id) or _CUE_ID_RE.match(clip_id), (
        f"clip_id {clip_id!r} matches neither ^s\\d+b\\d+$ nor ^scene\\d+$"
    )
    ext = _EXT_FOR_MIME.get(mime_type.split(";")[0].strip(), "wav")
    filename = f"{prefix}{Path(clip_id).name}.{ext}"

    local_path = LOCAL_AUDIO_DIR / filename
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(audio_bytes)

    content_hash = hashlib.sha256(audio_bytes).hexdigest()

    result = put_bytes(
        f"{_S3_AUDIO_PREFIX}/{filename}", audio_bytes, content_type=mime_type
    )
    reason = result.error or "put_object succeeded"

    return content_hash, local_path, result.uri, result.ok, reason


def build_index(
    entries: list[dict[str, Any]],
    music: list[dict[str, Any]],
    cast: dict[str, dict[str, str]],
    beats_doc: dict[str, Any],
    beats_source: str,
    narrator_voice: str,
    audio_template_version: str,
) -> dict[str, Any]:
    """Assemble the index from every entry resolved so far.

    Entries are sorted into beat order before writing, so
    `output/audio/index.json` is always in the order Phase 7 assembles from,
    regardless of the order beats were processed or regenerated in.
    """
    ordered = sorted(entries, key=lambda e: (e["scene"], e["beat"]))

    dialogue = [e for e in ordered if e["kind"] == "dialogue"]
    narration = [e for e in ordered if e["kind"] == "narration"]
    widened = [e for e in ordered if e["shot_secs_source"] == "audio_floor"]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script": "rocky-1976",
        "beats_source": beats_source,
        "beats_generated_at": beats_doc.get("generated_at", ""),
        "audio_template_version": audio_template_version,
        "narrator_voice": narrator_voice,
        "cast": cast,
        "total_clips": len(ordered),
        "dialogue_count": len(dialogue),
        "narration_count": len(narration),
        "generated_count": sum(1 for e in ordered if e["source"] == "generated"),
        "reused_count": sum(1 for e in ordered if e["source"] == "reused"),
        "failed_count": sum(1 for e in ordered if e["source"] == "generation_failed"),
        # A clip kept because its regeneration could not run is neither a
        # success nor a failure, and counting it as either would misreport the
        # corpus. It is playable, and it is behind — both facts are recorded.
        "kept_after_failure_count": sum(
            1 for e in ordered if e["source"] == "reused_after_failure"
        ),
        "stale_beat_ids": sorted(e["beat_id"] for e in ordered if e.get("stale")),
        # Clips whose file predates the text the index records for them. Phase 7
        # must not caption these from `text`, and Phase 9 must not display it.
        "text_mismatch_beat_ids": sorted(
            e["beat_id"] for e in ordered if e.get("text_matches_audio") is False
        ),
        "shots_widened_count": len(widened),
        "shots_widened_secs": round(
            sum(e["shot_secs"] - e["beat_duration_secs"] for e in widened), 2
        ),
        "total_shot_secs": round(sum(e["shot_secs"] for e in ordered), 2),
        "music_cues": music,
        "s3_ok": None,
        "s3_reason": "not yet written",
        "clips": ordered,
    }


def write_index(index: dict[str, Any]) -> dict[str, Any]:
    """Write `index` to local disk and S3, local-then-S3.

    Mutates `index["s3_ok"]`/`index["s3_reason"]` in place and re-writes
    locally, so the on-disk copy is never stale about whether it reached the
    bucket.
    """
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


def load_previous_index(path: Path = _LOCAL_INDEX) -> dict[str, Any]:
    """The previous run's index, or an empty shell if there is none."""
    if not path.exists():
        return {"clips": [], "cast": {}, "music_cues": []}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        logger.warning("previous audio index at %s is unreadable (%s)", path, exc)
        return {"clips": [], "cast": {}, "music_cues": []}


def _write_local(index: dict[str, Any]) -> None:
    _LOCAL_INDEX.parent.mkdir(parents=True, exist_ok=True)
    _LOCAL_INDEX.write_text(json.dumps(index, indent=2))
