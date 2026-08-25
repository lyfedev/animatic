"""Per-beat directions from a human, kept outside `beats.json`.

`beats.json` is what the SCRIPT says. It is regenerated whenever beats are
re-parsed, and it should stay a faithful record of that parse — a hand-written
duration living inside it would be silently discarded by the next re-parse, or
worse, silently survive and be mistaken for something the parser derived.

So directions live in their own file, `output/beat-overrides.json`, and are
applied on top. Re-parsing the script does not touch them.

**The rule this file exists to honour (backlog S-02):** *extending a beat ADDS
time; it must not re-time other beats.* Phase 2's `fit_scene_to_budget` scales
every beat in a scene to hit the page-geometry target, so lengthening one beat
silently shortens its neighbours — beats the developer had already watched and
approved would change under them. An override sits outside that fitting
entirely: the scene simply gets longer.

Overrides are a floor, never a ceiling. A beat can be held longer than its
speech; it can never be cut shorter than it, because clipped dialogue is the
one defect a viewer cannot miss.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LOCAL_OVERRIDES = Path("output/beat-overrides.json")


def load_overrides(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Every recorded override, keyed by beat_id. Empty when there are none."""
    path = LOCAL_OVERRIDES if path is None else path
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        logger.warning("beat overrides at %s are unreadable (%s)", path, exc)
        return {}
    return doc.get("beats", {})


def set_duration(
    beat_id: str,
    secs: float,
    reason: str = "",
    path: Path | None = None,
) -> dict[str, Any]:
    """Hold `beat_id` for `secs`. Returns the stored record."""
    path = LOCAL_OVERRIDES if path is None else path
    overrides = load_overrides(path)
    overrides[beat_id] = {
        "beat_id": beat_id,
        "hold_secs": round(float(secs), 2),
        "reason": reason
        or f"held for {secs:.2f}s by explicit direction, above the script's own pacing",
        "set_at": datetime.now(timezone.utc).isoformat(),
    }
    _write(overrides, path)
    return overrides[beat_id]


def clear_duration(beat_id: str, path: Path | None = None) -> bool:
    """Drop `beat_id`'s override. True if there was one."""
    path = LOCAL_OVERRIDES if path is None else path
    overrides = load_overrides(path)
    if beat_id not in overrides:
        return False
    del overrides[beat_id]
    _write(overrides, path)
    return True


def apply(
    beat_id: str,
    secs: float,
    source: str,
    reason: str,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> tuple[float, str, str]:
    """Apply any override for `beat_id` to an already-resolved shot length.

    Returns (secs, source, reason) unchanged when there is no override, so
    callers can pipe every shot through this without branching.

    An override that is SHORTER than the resolved length is honoured only down
    to that length, and says so: the resolved length already accounts for the
    beat's own audio, and cutting below it would clip speech.
    """
    override = (overrides or {}).get(beat_id)
    if not override:
        return secs, source, reason

    hold = float(override["hold_secs"])
    if hold <= secs:
        return (
            secs,
            source,
            f"{reason}; a {hold:.2f}s hold was set for this beat but its audio "
            f"already needs {secs:.2f}s, so the longer of the two wins",
        )

    return (
        round(hold, 2),
        "hold_override",
        f"held {secs:.2f}s -> {hold:.2f}s by explicit direction. "
        f"{override.get('reason', '')}".strip(),
    )


def _write(overrides: dict[str, dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "note": (
                    "Directions from a human, applied on top of beats.json. "
                    "Re-parsing the script does not touch this file."
                ),
                "beats": dict(sorted(overrides.items())),
            },
            indent=2,
        )
    )
