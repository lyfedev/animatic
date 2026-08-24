"""Slot resolution — collapses beats.json's characters and scene headings into
a deduplicated, priority-ranked registry of character and location slots.

Slot identity is resolved automatically, with no hand-curated alias list
(D-01). Every merge records both the source headings/names and the rule that
produced it, so a wrong guess is visible in the manifest rather than silent.

Locations are resolved from the PDF's raw scene text via
`pdf_extractor.extract_scenes` — the ground truth for "does this scene have a
real INT./EXT. slug" — not from beats.json's `scene_heading` field, which is
Gemini's own invented text and is wrong for scene 2 (D-03a). A scene with no
slug of its own inherits the preceding scene's resolved location (D-02).
Remaining headings are normalised (time-of-day suffix and punctuation
stripped, possessives collapsed) while the leading INT./EXT. token is kept as
part of the key, so an interior and an exterior of the same address stay two
slots (D-03) — dropping the prefix would wrongly merge scene 6's
`EXT. ROCKY'S APARTMENT` with scene 8's `INT. ROCKY'S APARTMENT`, which are
different pictures.

Characters are resolved from the union of each beat's `characters[]` and
every `dialogue[].character` — the display name is copied exactly as the
script writes it, and the slot_id is the same `_slugify` normalisation used
for locations (D-01: no hand-curated alias list either way).

Priority (D-10/D-11) is a single global ranking across every slot by its
share of total screen time — how much of the finished cut depends on it —
not a generation order or a cost band.

Art slots and voice identities are separate axes and do not collapse the
same way (D-04): a minor character (D-05, <= 2 beats) shares a generic art
slot with the other minor characters, but every character keeps a
project-wide-unique `voice_id` (D-06/D-07), so two characters who speak in
the same scene can never be given the same voice — `assert_no_voice_collisions`
is the regression guard for that invariant.

This module builds out incrementally across Phase 3's three plan tasks:
Task 1 resolved locations only, far enough to prove the one tracer slot
(`int_blue_door_fight_club`). Task 2 added character resolution to reach the
full 16-slot registry. Task 3 (this pass) fills the derived priority/art/
voice axes and the voice-collision guard.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from animatic.core import pdf_extractor

# A scene's raw first line has a real INT./EXT. slug, e.g. "1 INT. BLUE DOOR
# FIGHT CLUB - NIGHT 1". Scene 2 of Rocky is a SUPERIMPOSE title card and
# fails this match — that is exactly the case D-02 exists to handle.
_SLUG_RE = re.compile(r"^\d+\s+(INT\.|EXT\.)", re.IGNORECASE)

# Pulls the heading text out of a numbered scene-heading line: the scene
# number appears at both ends (pdf_extractor's own heading contract), e.g.
# "1 INT. BLUE DOOR FIGHT CLUB - NIGHT 1" -> "INT. BLUE DOOR FIGHT CLUB - NIGHT".
_HEADING_LINE_RE = re.compile(r"^(\d+)\s+(\S.*?)\s+\1\s*$")

# Trailing time-of-day suffix, stripped during normalisation (D-03).
_TIME_OF_DAY_RE = re.compile(
    r"\s*-\s*(DAY|NIGHT|DUSK|DAWN|MORNING|EVENING|CONTINUOUS|LATER|"
    r"MOMENTS LATER)\s*$",
    re.IGNORECASE,
)

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# A near-match clustering fallback (RESEARCH §Don't Hand-Roll) — expected to
# fire zero times on this corpus since D-02/D-03's normalisation already
# collapses every real duplicate to an exact key. Kept as insurance; any pair
# it merges is recorded in that slot's merge_reason.
_NEAR_MATCH_RATIO = 0.92

# A character appearing in this many beats or fewer maps to a shared generic
# art slot rather than getting bespoke generated art (D-05). Matches all four
# of D-05's own named examples (FIGHTER #1 at exactly 2 beats is the boundary
# case) and correctly leaves WOMAN (3 beats) bespoke despite the
# function-style name.
MINOR_CHARACTER_MAX_BEATS = 2

GENERIC_MINOR_ART_SLOT_ID = "generic_minor_character"


@dataclass
class Slot:
    """One resolved asset slot — a character or a location.

    Field provenance across this phase's three tasks: Task 1 declares every
    field and populates the tracer's one location slot. Task 2 expands
    resolution to all 16 slots (source_names/source_headings/source_scenes/
    merge_reason/beat_ids). Task 3 fills the derived axes — priority
    (priority_rank/priority_reason/beats/duration_secs/share_pct), art
    (art_slot_id/art_shared_with/is_minor) and voice (voice_id). 03-02 fills
    the source/art-write/hash fields (source/source_files/match_rule/
    source_reason/art_uri/art_s3_uri/content_hash/art_changed/prompt).
    """

    slot_id: str
    slot_type: str  # "character" | "location"
    display_name: str
    art_slot_id: str = ""
    art_shared_with: list[str] = field(default_factory=list)
    voice_id: str | None = None
    is_minor: bool | None = None
    source_names: list[str] = field(default_factory=list)
    source_headings: list[str] = field(default_factory=list)
    source_scenes: list[int] = field(default_factory=list)
    merge_reason: str = ""
    beat_ids: list[str] = field(default_factory=list)
    beats: int = 0
    duration_secs: float = 0.0
    share_pct: float = 0.0
    priority_rank: int = 0
    priority_reason: str = ""
    source: str = ""
    source_files: list[str] = field(default_factory=list)
    match_rule: str = ""
    source_reason: str = ""
    art_uri: str = ""
    art_s3_uri: str = ""
    content_hash: str = ""
    art_changed: bool = False
    prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "slot_type": self.slot_type,
            "display_name": self.display_name,
            "art_slot_id": self.art_slot_id,
            "art_shared_with": self.art_shared_with,
            "voice_id": self.voice_id,
            "is_minor": self.is_minor,
            "source_names": self.source_names,
            "source_headings": self.source_headings,
            "source_scenes": self.source_scenes,
            "merge_reason": self.merge_reason,
            "beat_ids": self.beat_ids,
            "beats": self.beats,
            "duration_secs": self.duration_secs,
            "share_pct": self.share_pct,
            "priority_rank": self.priority_rank,
            "priority_reason": self.priority_reason,
            "source": self.source,
            "source_files": self.source_files,
            "match_rule": self.match_rule,
            "source_reason": self.source_reason,
            "art_uri": self.art_uri,
            "art_s3_uri": self.art_s3_uri,
            "content_hash": self.content_hash,
            "art_changed": self.art_changed,
            "prompt": self.prompt,
        }


def resolve_slots(beats: dict, pdf_path: str | Path) -> list[Slot]:
    """Resolve every character and location referenced in `beats` into slots.

    Args:
        beats: The parsed beats.json dict (as produced by
            `beat_assembler._build_beat_list` — `generated_at`, `script`,
            `scenes`, `total_beats`, `total_duration_secs`,
            `pct_motion_candidates`, `beats`).
        pdf_path: Path to the screenplay PDF — re-read for raw scene headings
            since beats.json's own `scene_heading` field has no provenance
            flag for "was this a real slug" (D-03a).

    Returns:
        All 16 slots, priority-ranked (ranks 1..16, no gaps or ties), with
        the art axis (art_slot_id/art_shared_with/is_minor) and the voice
        axis (voice_id) both resolved. Raises ValueError if two characters
        who speak in the same scene were somehow given the same voice_id
        (assert_no_voice_collisions) — structurally unreachable given every
        character's voice_id is unique project-wide, but checked anyway as
        a regression guard (D-06).
    """
    slots = _resolve_locations(beats, Path(pdf_path)) + _resolve_characters(beats)
    _apply_priority(slots, beats)
    _apply_art_and_voice(slots)
    assert_no_voice_collisions(beats, slots)
    return slots


def _resolve_locations(beats: dict, pdf_path: Path) -> list[Slot]:
    """Resolve every scene's location to a deduplicated set of location slots."""
    all_beats = beats["beats"]
    scene_numbers = sorted({b["scene"] for b in all_beats})
    if not scene_numbers:
        return []

    raw_scenes = pdf_extractor.extract_scenes(pdf_path, first_n=max(scene_numbers))

    scene_first_line = {
        n: text.splitlines()[0].strip() for n, text in raw_scenes.items()
    }
    has_own_slug = {n: bool(_SLUG_RE.match(scene_first_line[n])) for n in scene_numbers}

    # D-02 inheritance + D-03a: resolve each scene's location text, inheriting
    # the preceding scene's resolved heading when this scene has no slug of
    # its own. `heading_source[n]` tracks which scene's raw slug the final
    # text came from, for the merge_reason.
    resolved_heading: dict[int, str] = {}
    heading_source: dict[int, int] = {}
    for n in scene_numbers:
        if has_own_slug[n]:
            match = _HEADING_LINE_RE.match(scene_first_line[n])
            heading_text = match.group(2) if match else scene_first_line[n]
            resolved_heading[n] = heading_text
            heading_source[n] = n
        else:
            prev = n - 1
            if prev not in resolved_heading:
                # No preceding scene to inherit from — keep the raw text
                # rather than crash; this does not occur in the fixed demo
                # corpus (scene 1 always has its own slug).
                resolved_heading[n] = scene_first_line[n]
                heading_source[n] = n
            else:
                resolved_heading[n] = resolved_heading[prev]
                heading_source[n] = heading_source[prev]

    normalized_key = {
        n: _slugify(_TIME_OF_DAY_RE.sub("", resolved_heading[n]))
        for n in scene_numbers
    }

    groups: dict[str, list[int]] = {}
    for n in scene_numbers:
        groups.setdefault(normalized_key[n], []).append(n)

    final_key_for, fuzzy_notes = _cluster_near_matches(list(groups.keys()))

    final_groups: dict[str, list[int]] = {}
    for key, scenes in groups.items():
        final_groups.setdefault(final_key_for[key], []).extend(scenes)

    slots: list[Slot] = []
    for slot_id, scenes in final_groups.items():
        scenes = sorted(set(scenes))
        source_headings = sorted({resolved_heading[n] for n in scenes})
        display_name = _TIME_OF_DAY_RE.sub("", resolved_heading[scenes[0]]).strip()

        reasons: list[str] = []
        for n in scenes:
            if not has_own_slug[n]:
                src = heading_source[n]
                reasons.append(
                    f"scene {n} has no INT./EXT. slug in the PDF and inherits "
                    f"scene {src}'s location (D-02)"
                )
        if len(source_headings) > 1:
            reasons.append(
                f"headings {source_headings} normalised to the same key after "
                f"stripping the time-of-day suffix and punctuation (D-03)"
            )
        for note in fuzzy_notes.get(slot_id, []):
            reasons.append(note)
        if not reasons:
            reasons.append(f"single heading {source_headings[0]!r}, no merge")

        beat_ids = [b["beat_id"] for b in all_beats if b["scene"] in scenes]

        slots.append(
            Slot(
                slot_id=slot_id,
                slot_type="location",
                display_name=display_name,
                source_headings=source_headings,
                source_scenes=scenes,
                merge_reason="; ".join(reasons),
                beat_ids=beat_ids,
            )
        )

    slots.sort(key=lambda s: s.source_scenes[0])
    return slots


def _cluster_near_matches(
    keys: list[str],
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Merge near-duplicate normalised keys, expected to fire zero times.

    Exact-match clustering (the caller's own normalized_key grouping) is
    primary. This is the stdlib `difflib` fallback RESEARCH recommends
    instead of hand-rolling a distance metric — any pair it merges is
    recorded so the merge stays visible rather than silent.
    """
    final_key_for = {k: k for k in keys}
    notes: dict[str, list[str]] = {}
    for i, k1 in enumerate(keys):
        for k2 in keys[i + 1 :]:
            if final_key_for[k1] == final_key_for[k2]:
                continue
            ratio = difflib.SequenceMatcher(None, k1, k2).ratio()
            if ratio > _NEAR_MATCH_RATIO:
                target = final_key_for[k1]
                stale = final_key_for[k2]
                for k in keys:
                    if final_key_for[k] == stale:
                        final_key_for[k] = target
                notes.setdefault(target, []).append(
                    f"near-match merged {k2!r} into {k1!r} "
                    f"(difflib ratio {ratio:.2f} — RESEARCH §Don't Hand-Roll fallback)"
                )
    return final_key_for, notes


def _resolve_characters(beats: dict) -> list[Slot]:
    """Resolve every character referenced in `beats` into one slot each.

    The name set per beat is the union of the beat's `characters[]` and
    every `dialogue[].character` — a beat where a character is present but
    silent still counts. Each character gets exactly one slot; no alias
    list (D-01), so the slot_id is just `_slugify` of the exact display
    name the script uses.
    """
    all_beats = beats["beats"]
    beat_ids_by_name: dict[str, list[str]] = {}

    for b in all_beats:
        names = set(b.get("characters", []))
        for line in b.get("dialogue", []):
            character = line.get("character")
            if character:
                names.add(character)
        for name in names:
            beat_ids_by_name.setdefault(name, []).append(b["beat_id"])

    slots: list[Slot] = []
    for name in sorted(beat_ids_by_name):
        slots.append(
            Slot(
                slot_id=_slugify(name),
                slot_type="character",
                display_name=name,
                source_names=[name],
                merge_reason=f"single character name {name!r}, no merge (D-01)",
                beat_ids=beat_ids_by_name[name],
            )
        )
    return slots


def _slugify(text: str) -> str:
    """Normalize a display name/heading into a slot_id.

    Possessive apostrophes are stripped outright (ROCKY'S -> ROCKYS) rather
    than turned into a separator, matching the canonical spellings this
    phase's interface_contract pins (`ext_rockys_apartment`, not
    `ext_rocky_s_apartment`). Every other run of non-alphanumeric characters
    collapses to a single underscore.
    """
    text = text.lower().replace("'", "")
    text = _NON_ALNUM_RE.sub("_", text)
    return text.strip("_")


def _apply_priority(slots: list[Slot], beats: dict) -> None:
    """Rank every slot by its share of total screen time (D-10/D-11).

    Priority is how much of the finished cut depends on the slot, not a
    generation order or a cost band — a single global ordering across
    characters and locations, ranks 1..16 with no gaps or ties, broken by
    beat count then slot_id when seconds tie exactly.
    """
    beats_by_id = {b["beat_id"]: b for b in beats["beats"]}
    total_secs = beats["total_duration_secs"]

    for slot in slots:
        durations = [beats_by_id[bid]["duration_secs"] for bid in slot.beat_ids]
        slot.beats = len(slot.beat_ids)
        slot.duration_secs = round(sum(durations), 1)
        slot.share_pct = (
            round(slot.duration_secs / total_secs * 100, 1) if total_secs else 0.0
        )

    ranked = sorted(slots, key=lambda s: (-s.duration_secs, -s.beats, s.slot_id))
    for rank, slot in enumerate(ranked, start=1):
        slot.priority_rank = rank
        slot.priority_reason = (
            f"{slot.beats} beat(s), {slot.duration_secs}s, "
            f"{slot.share_pct}% of the {total_secs}s total cut — "
            f"rank {rank} of {len(slots)} by share of screen time (D-10/D-11)"
        )


def _apply_art_and_voice(slots: list[Slot]) -> None:
    """Fill the art axis (D-05) and the voice axis (D-04/D-06/D-07).

    These are separate axes and do not collapse the same way: minor
    characters share one generic art slot but each keeps a distinct
    voice_id, so two minor characters who speak to each other never share a
    voice.
    """
    minor_characters = [
        s
        for s in slots
        if s.slot_type == "character" and s.beats <= MINOR_CHARACTER_MAX_BEATS
    ]
    minor_ids = {s.slot_id for s in minor_characters}

    for slot in slots:
        if slot.slot_type == "location":
            slot.is_minor = None
            slot.art_slot_id = slot.slot_id
            slot.art_shared_with = []
            slot.voice_id = None
            continue

        slot.is_minor = slot.slot_id in minor_ids
        if slot.is_minor:
            slot.art_slot_id = GENERIC_MINOR_ART_SLOT_ID
            slot.art_shared_with = sorted(minor_ids - {slot.slot_id})
        else:
            slot.art_slot_id = slot.slot_id
            slot.art_shared_with = []
        # Globally unique per character — sufficient to make an in-scene
        # voice collision structurally impossible (D-06).
        slot.voice_id = slot.slot_id


def assert_no_voice_collisions(beats: dict, slots: list[Slot]) -> None:
    """Raise if two characters who speak in the same scene share a voice_id.

    A regression guard, not decoration (D-06): FIGHTER #1 and FIGHTER #2
    talk to each other in scene 3, and sharing the generic art slot is fine
    but sharing a voice is not — the exchange would become one person
    talking to themselves. This is what stops a later phase pooling voices
    across characters from silently breaking that scene.
    """
    voice_id_by_name: dict[str, str | None] = {}
    for slot in slots:
        if slot.slot_type == "character":
            for name in slot.source_names:
                voice_id_by_name[name] = slot.voice_id

    speakers_by_scene: dict[int, set[str]] = {}
    for b in beats["beats"]:
        for line in b.get("dialogue", []):
            character = line.get("character")
            if character:
                speakers_by_scene.setdefault(b["scene"], set()).add(character)

    for scene, speakers in speakers_by_scene.items():
        voice_ids = [voice_id_by_name.get(name) for name in speakers]
        if len(voice_ids) != len(set(voice_ids)):
            raise ValueError(
                f"voice collision in scene {scene}: {sorted(speakers)} resolve "
                f"to non-distinct voice_ids {voice_ids}"
            )
