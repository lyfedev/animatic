"""Motion index — `output/motion/index.json`.

Same shape as the panel, audio and cut manifests: beat order, a reason on
every entry, honest `s3_ok`.

One difference worth stating: this index covers **every beat**, not only the
ones that got motion. ROADMAP criterion 2 is "every beat carries motion
true/false and a motion reason", so a 49-beat corpus with a budget of 4
produces 49 entries, 45 of which explain why they are stills.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from animatic.core.s3_writer import put_bytes
from animatic.core.script_source import script_id

logger = logging.getLogger(__name__)

LOCAL_MOTION_DIR = Path("output/motion")
_LOCAL_INDEX = LOCAL_MOTION_DIR / "index.json"
_S3_INDEX_KEY = "motion/index.json"
_S3_MOTION_PREFIX = "motion"


def build_index(
    entries: list[dict[str, Any]],
    beats_doc: dict[str, Any],
    beats_source: str,
    budget: int,
    motion_prompt_version: str,
    halted_reason: str | None = None,
) -> dict[str, Any]:
    """Assemble the index from every beat's decision."""
    ordered = sorted(entries, key=lambda e: (e["scene"], e["beat"]))
    # Selected for motion is not the same as HAS motion, and reporting the
    # first as though it were the second is how a run with a refused beat
    # reads as complete. s8b6 was selected, refused by Veo's content
    # guardrails, and falls back to its panel; the cut has three moving shots,
    # not four.
    selected = [e for e in ordered if e["motion"]]
    with_motion = [
        e for e in ordered
        if e["motion"] and e["source"] in ("generated", "reused", "reused_after_failure")
    ]
    fell_back = [e for e in selected if e not in with_motion]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script": script_id(),
        "beats_source": beats_source,
        "beats_generated_at": beats_doc.get("generated_at", ""),
        "motion_prompt_version": motion_prompt_version,
        "budget": budget,
        "total_beats": len(ordered),
        "selected_count": len(selected),
        "motion_count": len(with_motion),
        "still_count": len(ordered) - len(with_motion),
        # Criterion 1 is about how many beats were SELECTED — the budget caps
        # what may be spent, and a beat that was spent and refused still cost
        # a call.
        "within_budget": len(selected) <= budget,
        "selected_beat_ids": [e["beat_id"] for e in selected],
        "motion_beat_ids": [e["beat_id"] for e in with_motion],
        # Criterion 4, stated as data: selected, but the cut uses its panel.
        "fell_back_to_still_beat_ids": [e["beat_id"] for e in fell_back],
        "motion_by_type": dict(Counter(e["type"] for e in with_motion)),
        "sources": dict(Counter(e["source"] for e in ordered)),
        "failed_beat_ids": [
            e["beat_id"] for e in ordered if e["source"] == "generation_failed"
        ],
        "stale_beat_ids": sorted(e["beat_id"] for e in ordered if e.get("stale")),
        "halted_reason": halted_reason,
        "s3_ok": None,
        "s3_reason": "not yet written",
        "beats": ordered,
    }


def write_clip(beat_id: str, path: Path) -> tuple[str, bool, str]:
    """Upload one motion clip. Returns (s3_uri, ok, reason)."""
    result = put_bytes(
        f"{_S3_MOTION_PREFIX}/{path.name}",
        path.read_bytes(),
        content_type="video/mp4",
    )
    return result.uri, result.ok, result.error or "put_object succeeded"


def write_index(index: dict[str, Any]) -> dict[str, Any]:
    """Write locally then to S3, never claiming an unwritten state."""
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
        return {"beats": []}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        logger.warning("previous motion index at %s is unreadable (%s)", path, exc)
        return {"beats": []}


def _write_local(index: dict[str, Any]) -> None:
    _LOCAL_INDEX.parent.mkdir(parents=True, exist_ok=True)
    _LOCAL_INDEX.write_text(json.dumps(index, indent=2))
