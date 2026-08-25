"""Which picture plays for a beat, and why.

This is the seam the rest of the project hangs off. Three phases want to put
something different on screen for the same beat:

- Phase 4 generated a still panel for every beat. That always exists.
- Phase 6 will generate motion for a handful of high-value beats.
- Phase 8 will accept real footage tagged with a beat number in its filename.

Rather than each of those teaching the assembler a new rule, they all write a
file into a known directory and this module picks the highest-priority one that
exists. Adding footage is then a copy, not a code change — which is precisely
what Phase 8's criterion asks for ("adding a beat-tagged MP4 and re-running
produces an updated cut with that shot replaced"), and removing the file
restores the animatic shot on the next run for free.

Priority is real footage, then motion, then the still. A beat with footage is
no longer an animatic shot; a beat with motion is animatic but moving; a beat
with neither is a held frame. Every shot records which it got and why, so the
cut can report what fraction of itself is real (FR-08).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

FOOTAGE_DIR = Path("assets/footage")
MOTION_DIR = Path("output/motion")
PANEL_DIR = Path("output/panels")

# Phase 8 reads the beat number from the FILENAME, never from the footage
# itself (PROJECT.md non-goal: "Inferring beat number from footage"). Accepts
# `s2b5.mp4` and `s2b5-take3.mp4` so a human can label their own takes.
_FOOTAGE_RE = re.compile(r"^(s\d+b\d+)(?:[-_].*)?$", re.I)

_VIDEO_SUFFIXES = (".mp4", ".mov", ".m4v", ".webm")
_STILL_SUFFIXES = (".jpg", ".jpeg", ".png")


@dataclass(frozen=True)
class ShotSource:
    """The picture for one beat: what it is, where it is, and why it won."""

    beat_id: str
    kind: str  # "footage" | "motion" | "still"
    path: Path
    reason: str

    @property
    def is_still(self) -> bool:
        return self.kind == "still"

    @property
    def is_real_footage(self) -> bool:
        return self.kind == "footage"


class MissingShotError(Exception):
    """Raised when a beat has no picture at all — not even its panel."""


def resolve_shot(
    beat_id: str,
    footage_dir: Path = FOOTAGE_DIR,
    motion_dir: Path = MOTION_DIR,
    panel_dir: Path = PANEL_DIR,
) -> ShotSource:
    """The highest-priority picture that exists for `beat_id`."""
    footage = _find_footage(beat_id, footage_dir)
    if footage:
        return ShotSource(
            beat_id, "footage", footage,
            f"real footage supplied at {footage} — replaces the animatic shot",
        )

    motion = _find_by_suffix(motion_dir, beat_id, _VIDEO_SUFFIXES)
    if motion:
        return ShotSource(
            beat_id, "motion", motion,
            f"generated motion at {motion} — no real footage for this beat",
        )

    still = _find_by_suffix(panel_dir, beat_id, _STILL_SUFFIXES)
    if still:
        return ShotSource(
            beat_id, "still", still,
            f"held panel at {still} — no footage and no motion for this beat",
        )

    raise MissingShotError(
        f"{beat_id} has no picture: no footage in {footage_dir}, no motion in "
        f"{motion_dir}, and no panel in {panel_dir}"
    )


def footage_beat_ids(footage_dir: Path = FOOTAGE_DIR) -> set[str]:
    """Beat ids that have real footage, read from filenames."""
    if not footage_dir.is_dir():
        return set()
    found = set()
    for path in footage_dir.iterdir():
        if path.suffix.lower() not in _VIDEO_SUFFIXES:
            continue
        match = _FOOTAGE_RE.match(path.stem)
        if match:
            found.add(match.group(1).lower())
    return found


def _find_footage(beat_id: str, footage_dir: Path) -> Path | None:
    """Footage for `beat_id`, matched on the filename's beat tag.

    Looser than the motion/panel lookup because these files come from a human,
    who may well have called it `s2b5-final.mp4`. Ties break on sorted name so
    the same directory always yields the same cut.
    """
    if not footage_dir.is_dir():
        return None
    matches = sorted(
        path
        for path in footage_dir.iterdir()
        if path.suffix.lower() in _VIDEO_SUFFIXES
        and (m := _FOOTAGE_RE.match(path.stem))
        and m.group(1).lower() == beat_id.lower()
    )
    return matches[0] if matches else None


def _find_by_suffix(directory: Path, beat_id: str, suffixes: tuple[str, ...]) -> Path | None:
    """Exact `<beat_id><suffix>` lookup — these files are written by us."""
    if not directory.is_dir():
        return None
    for suffix in suffixes:
        candidate = directory / f"{Path(beat_id).name}{suffix}"
        if candidate.exists():
            return candidate
    return None
