"""Per-shot state — `output/state.json`, the answer to "how real is this cut?"

FR-08 asks for a per-shot state manifest and a percentage of the cut that is
real. The cut manifest already knows most of it, but it is written by an
encode and is therefore only as fresh as the last render. State is a question
people ask *between* renders — a UI polling for what would happen if the cut
were rebuilt now, someone checking whether their footage drop was picked up.

So this composes from what is on disk right now: the shot-source seam for the
picture, the audio index for the sound, the motion index for why a selected
beat has no clip. It runs in milliseconds, spends nothing, and needs no
encoder.

**Three states, not two.** FR-07 says "animatic or footage", but the cut has a
third: a beat with generated motion is still animatic and still not real
footage, yet calling it a still misdescribes what is on screen. `state` carries
all three; `is_real` carries the binary FR-07 asks for.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from animatic.core.s3_writer import put_bytes
from animatic.core.shot_sources import MissingShotError, resolve_shot
from animatic.core.script_source import script_id

logger = logging.getLogger(__name__)

LOCAL_STATE = Path("output/state.json")
_S3_STATE_KEY = "state.json"

STATE_VERSION = "v1"

# What the viewer is actually looking at, most-real first.
_STATE_FOR_SOURCE = {
    "footage": "footage",
    "motion": "animatic_motion",
    "still": "animatic_still",
}


def build_state(
    beats_doc: dict[str, Any],
    audio_index: dict[str, Any] | None = None,
    motion_index: dict[str, Any] | None = None,
    cut_index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Per-shot state for every beat, plus the totals FR-08 requires."""
    audio_index = audio_index or {}
    motion_index = motion_index or {}
    cut_index = cut_index or {}

    clips = {c["beat_id"]: c for c in audio_index.get("clips", [])}
    motion = {m["beat_id"]: m for m in motion_index.get("beats", [])}

    shots: list[dict[str, Any]] = []
    for beat in beats_doc["beats"]:
        beat_id = beat["beat_id"]
        clip = clips.get(beat_id)
        motion_entry = motion.get(beat_id)

        try:
            source = resolve_shot(beat_id)
            kind, path, source_reason = source.kind, str(source.path), source.reason
        except MissingShotError as exc:
            kind, path, source_reason = "missing", "", str(exc)

        shots.append(
            {
                "beat_id": beat_id,
                "scene": beat["scene"],
                "beat": beat["beat"],
                "type": beat.get("type"),
                "state": _STATE_FOR_SOURCE.get(kind, "missing"),
                "is_real": kind == "footage",
                "shot_source": kind,
                "shot_source_path": path,
                "shot_source_reason": source_reason,
                "shot_secs": _shot_secs(beat, clip),
                "has_audio": bool(clip and clip.get("local_path")),
                "audio_kind": clip.get("kind") if clip else None,
                "voice": clip.get("voice") if clip else None,
                # Present only when a beat was selected for motion, so the UI
                # can say "we tried and it was refused" rather than implying
                # the beat was never a candidate.
                "motion_selected": bool(motion_entry and motion_entry.get("motion")),
                "motion_reason": motion_entry.get("motion_reason") if motion_entry else None,
                "motion_outcome": motion_entry.get("source") if motion_entry else None,
            }
        )

    return _totals(shots, beats_doc, audio_index, motion_index, cut_index)


def _shot_secs(beat: dict[str, Any], clip: dict[str, Any] | None) -> float:
    """Same rule the assembler cuts on: the audio index wins."""
    if clip and clip.get("shot_secs"):
        return float(clip["shot_secs"])
    return float(beat["duration_secs"])


def _totals(
    shots: list[dict[str, Any]],
    beats_doc: dict[str, Any],
    audio_index: dict[str, Any],
    motion_index: dict[str, Any],
    cut_index: dict[str, Any],
) -> dict[str, Any]:
    ordered = sorted(shots, key=lambda s: (s["scene"], s["beat"]))
    total_secs = round(sum(s["shot_secs"] for s in ordered), 2)
    real_secs = round(sum(s["shot_secs"] for s in ordered if s["is_real"]), 2)

    by_state: dict[str, int] = {}
    for shot in ordered:
        by_state[shot["state"]] = by_state.get(shot["state"], 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "state_version": STATE_VERSION,
        "script": script_id(),
        "total_shots": len(ordered),
        "shots_by_state": by_state,
        "total_secs": total_secs,
        "real_footage_secs": real_secs,
        # FR-08. By SCREEN TIME, not shot count — one 12-second replaced shot
        # is more of the cut than three 2-second ones. Matches how the cut
        # manifest computes it, deliberately.
        "real_footage_pct": round(100 * real_secs / total_secs, 1) if total_secs else 0.0,
        "real_footage_beat_ids": [s["beat_id"] for s in ordered if s["is_real"]],
        "motion_beat_ids": [
            s["beat_id"] for s in ordered if s["state"] == "animatic_motion"
        ],
        "missing_beat_ids": [s["beat_id"] for s in ordered if s["state"] == "missing"],
        "shots_without_audio": [s["beat_id"] for s in ordered if not s["has_audio"]],
        # Whether the cut on disk reflects this state, or whether a rebuild is
        # pending. The whole reason state is computed separately from the cut.
        "cut_path": cut_index.get("cut_path"),
        "cut_generated_at": cut_index.get("generated_at"),
        "cut_is_current": _cut_is_current(ordered, cut_index),
        "beats_generated_at": beats_doc.get("generated_at", ""),
        "audio_generated_at": audio_index.get("generated_at", ""),
        "motion_generated_at": motion_index.get("generated_at", ""),
        "s3_ok": None,
        "s3_reason": "not yet written",
        "shots": ordered,
    }


def _cut_is_current(shots: list[dict[str, Any]], cut_index: dict[str, Any]) -> bool | None:
    """Does the rendered cut match what the pipeline would render now?

    None when there is no cut to compare against. Compares the per-shot source
    kinds rather than timestamps — a rebuild that changed nothing should not
    report stale, and a footage drop that changed one shot should.
    """
    if not cut_index.get("shots"):
        return None
    rendered = {s["beat_id"]: s.get("shot_source") for s in cut_index["shots"]}
    current = {s["beat_id"]: s["shot_source"] for s in shots}
    return rendered == current


def write_state(state: dict[str, Any]) -> dict[str, Any]:
    """Write locally then to S3, never claiming an unwritten state."""
    _write_local(state)

    result = put_bytes(
        _S3_STATE_KEY,
        json.dumps(state, indent=2).encode("utf-8"),
        content_type="application/json",
    )
    state["s3_ok"] = result.ok
    state["s3_reason"] = result.error or "put_object succeeded"
    _write_local(state)

    return {
        "local_path": str(LOCAL_STATE),
        "s3_uri": result.uri,
        "s3_ok": result.ok,
        "s3_reason": state["s3_reason"],
    }


def _write_local(state: dict[str, Any]) -> None:
    LOCAL_STATE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_STATE.write_text(json.dumps(state, indent=2))
