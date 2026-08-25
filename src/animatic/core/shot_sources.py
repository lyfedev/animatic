"""Which picture plays for a beat, and why.

This is the seam the rest of the project hangs off. Five phases want to put
something different on screen for the same beat:

- Phase 4 generated a still panel for every beat. That always exists.
- Phase 6 generates motion for a handful of high-value beats.
- Phase 8 accepts real footage tagged with a beat number in its filename.
- A human hand-edits a panel — paints out a turtle, adds a sign.
- A **daily** covers a RANGE of beats with one continuous take.

Rather than each of those teaching the assembler a new rule, they all write a
file into a known directory and this module picks the highest-priority one that
exists. Adding footage is a copy, not a code change — which is precisely what
Phase 8's criterion asks for, and removing the file restores the animatic shot
on the next run for free.

**Priority, most-real first:** daily, footage, motion, edited panel, generated
panel. An edited panel outranks the generated one because it is the only
artifact here a person made by hand; a `--force` regeneration must not silently
destroy it.

**A daily is the one that is not shaped like the others.** The rest are one
file for one beat, and the beat's duration is fixed by the cut. A daily is one
file for N beats, and it plays its own full length carrying its own production
sound — so the beats it covers contribute neither their picture nor their
audio, and the cut's runtime moves. `daily_span` is how the assembler learns
that a beat is the START of such a span, a continuation of one, or neither.

Every shot records which source it got and why, so the cut can report what
fraction of itself is real (FR-08) and how much a person corrected by hand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DAILIES_DIR = Path("assets/dailies")
FOOTAGE_DIR = Path("assets/footage")
MOTION_DIR = Path("output/motion")
EDITED_PANEL_DIR = Path("assets/edited-panels")
PANEL_DIR = Path("output/panels")

# Phase 8 reads the beat number from the FILENAME, never from the footage
# itself (PROJECT.md non-goal: "Inferring beat number from footage"). Accepts
# `s2b5.mp4` and `s2b5-take3.mp4` so a human can label their own takes.
_FOOTAGE_RE = re.compile(r"^(s\d+b\d+)(?:[-_].*)?$", re.I)

# A daily names the range it covers: `s2b5-s2b9.mp4`, or `s2b5-s2b9-take2.mp4`.
# The same rule applies — the range comes from the filename, not the footage.
_DAILY_RE = re.compile(r"^(s\d+b\d+)-(s\d+b\d+)(?:[-_].*)?$", re.I)

_VIDEO_SUFFIXES = (".mp4", ".mov", ".m4v", ".webm")
_STILL_SUFFIXES = (".jpg", ".jpeg", ".png")


class MissingShotError(Exception):
    """Raised when a beat has no picture at all — not even its panel."""


class OverlappingDailiesError(Exception):
    """Raised when two dailies claim the same beat.

    Refused rather than resolved. Two takes covering `s2b5-s2b9` and
    `s2b8-s2b12` is a mistake to report, not a precedence puzzle to guess at —
    whichever the code picked would be arbitrary and the cut would quietly be
    wrong in a way nobody could see.
    """


@dataclass(frozen=True)
class DailySpan:
    """One continuous take covering a range of beats."""

    path: Path
    start_beat_id: str
    end_beat_id: str
    beat_ids: tuple[str, ...]

    @property
    def span_id(self) -> str:
        return f"{self.start_beat_id}-{self.end_beat_id}"

    def is_start(self, beat_id: str) -> bool:
        return bool(self.beat_ids) and beat_id == self.beat_ids[0]


@dataclass(frozen=True)
class ShotSource:
    """The picture for one beat: what it is, where it is, and why it won."""

    beat_id: str
    kind: str  # "daily" | "footage" | "motion" | "edited" | "still"
    path: Path
    reason: str
    daily_span: DailySpan | None = None

    @property
    def is_still(self) -> bool:
        return self.kind in ("still", "edited")

    @property
    def is_real_footage(self) -> bool:
        return self.kind in ("footage", "daily")

    @property
    def is_hand_made(self) -> bool:
        """A person drew or corrected this frame."""
        return self.kind == "edited"

    @property
    def carries_own_audio(self) -> bool:
        """A daily brings production sound; everything else takes the bed."""
        return self.kind == "daily"


def resolve_shot(
    beat_id: str,
    footage_dir: Path | None = None,
    motion_dir: Path | None = None,
    panel_dir: Path | None = None,
    edited_dir: Path | None = None,
    dailies: dict[str, DailySpan] | None = None,
) -> ShotSource:
    """The highest-priority picture that exists for `beat_id`.

    Directories default to None and resolve to the module constants at CALL
    time, not at definition time. Binding them as default arguments captured
    the values once at import, so patching `PANEL_DIR` did nothing — a test
    doing exactly that passed locally purely because the real `output/panels/`
    happened to exist, and failed in CI where it does not.
    """
    footage_dir = FOOTAGE_DIR if footage_dir is None else footage_dir
    motion_dir = MOTION_DIR if motion_dir is None else motion_dir
    panel_dir = PANEL_DIR if panel_dir is None else panel_dir
    edited_dir = EDITED_PANEL_DIR if edited_dir is None else edited_dir

    if dailies and beat_id in dailies:
        span = dailies[beat_id]
        position = "opens" if span.is_start(beat_id) else "is covered by"
        return ShotSource(
            beat_id, "daily", span.path,
            f"this beat {position} the daily at {span.path}, one take over "
            f"{len(span.beat_ids)} beat(s) ({span.span_id}) playing its own "
            f"length with its own sound",
            daily_span=span,
        )

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

    edited = _find_by_suffix(edited_dir, beat_id, _STILL_SUFFIXES)
    if edited:
        return ShotSource(
            beat_id, "edited", edited,
            f"hand-edited panel at {edited} — outranks the generated panel and "
            f"is never overwritten by a regeneration",
        )

    still = _find_by_suffix(panel_dir, beat_id, _STILL_SUFFIXES)
    if still:
        return ShotSource(
            beat_id, "still", still,
            f"held panel at {still} — no footage, motion or hand edit for this beat",
        )

    raise MissingShotError(
        f"{beat_id} has no picture: nothing in {dailies and 'dailies, ' or ''}"
        f"{footage_dir}, {motion_dir}, {edited_dir} or {panel_dir}"
    )


def find_dailies(
    beat_order: list[str], dailies_dir: Path | None = None
) -> dict[str, DailySpan]:
    """Map every beat covered by a daily to the span covering it.

    `beat_order` is the cut's beat order, which is what makes a RANGE
    meaningful: `s2b5-s2b9` means every beat from s2b5 to s2b9 as the cut runs
    them, not every beat whose id sorts between those two strings.

    Raises OverlappingDailiesError rather than choosing between two takes that
    claim the same beat.
    """
    dailies_dir = DAILIES_DIR if dailies_dir is None else dailies_dir
    if not dailies_dir.is_dir():
        return {}

    position = {beat_id: i for i, beat_id in enumerate(beat_order)}
    covered: dict[str, DailySpan] = {}

    for path in sorted(dailies_dir.iterdir()):
        if path.suffix.lower() not in _VIDEO_SUFFIXES:
            continue
        match = _DAILY_RE.match(path.stem)
        if not match:
            continue

        start, end = match.group(1).lower(), match.group(2).lower()
        if start not in position or end not in position:
            continue
        if position[start] > position[end]:
            start, end = end, start

        span_beats = tuple(beat_order[position[start] : position[end] + 1])
        span = DailySpan(path, start, end, span_beats)

        clash = next((b for b in span_beats if b in covered), None)
        if clash is not None:
            raise OverlappingDailiesError(
                f"{path.name} and {covered[clash].path.name} both cover "
                f"{clash} — remove one; the cut cannot choose between two takes"
            )
        for beat_id in span_beats:
            covered[beat_id] = span

    return covered


def footage_beat_ids(footage_dir: Path | None = None) -> set[str]:
    """Beat ids that have real footage, read from filenames."""
    footage_dir = FOOTAGE_DIR if footage_dir is None else footage_dir
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
        # A daily's filename also starts with a beat id; it is not footage.
        and not _DAILY_RE.match(path.stem)
    )
    return matches[0] if matches else None


def _find_by_suffix(
    directory: Path, beat_id: str, suffixes: tuple[str, ...]
) -> Path | None:
    """Exact `<beat_id><suffix>` lookup — these files are written by us."""
    if not directory.is_dir():
        return None
    for suffix in suffixes:
        candidate = directory / f"{Path(beat_id).name}{suffix}"
        if candidate.exists():
            return candidate
    return None
