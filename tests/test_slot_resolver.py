"""Unit tests for slot resolution — locations, characters, and the derived
priority/art/voice axes.

Pins exact expected slot_id sets, in the style of
test_extract_scenes_returns_scenes_1_to_8 — a wrong merge or a dropped
character names itself in the failure output rather than hiding behind a
bare count.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from animatic.core.slot_resolver import Slot, resolve_slots

PDF_PATH = Path("docs/rocky-1976.pdf")
BEATS_PATH = Path("output/beats.json")

EXPECTED_LOCATION_SLOT_IDS = sorted(
    [
        "int_blue_door_fight_club",
        "int_dressing_room",
        "int_trolley",
        "ext_street",
        "ext_rockys_apartment",
        "int_rockys_hallway",
        "int_rockys_apartment",
    ]
)

EXPECTED_CHARACTER_SLOT_IDS = sorted(
    [
        "rocky",
        "black_fighter",
        "promoter",
        "cornerman",
        "woman",
        "fighter_1",
        "fighter_2",
        "fan",
        "announcer",
    ]
)


@pytest.fixture(scope="module")
def beats() -> dict:
    return json.loads(BEATS_PATH.read_text())


@pytest.fixture(scope="module")
def slots(beats) -> list[Slot]:
    return resolve_slots(beats, PDF_PATH)


# ---------------------------------------------------------------------------
# Task 2 — full 16-slot registry
# ---------------------------------------------------------------------------

def test_resolve_slots_returns_16_slots(slots):
    assert len(slots) == 16
    assert sum(1 for s in slots if s.slot_type == "character") == 9
    assert sum(1 for s in slots if s.slot_type == "location") == 7


def test_location_slot_ids_match_exactly(slots):
    location_ids = sorted(s.slot_id for s in slots if s.slot_type == "location")
    assert location_ids == EXPECTED_LOCATION_SLOT_IDS


def test_character_slot_ids_match_exactly(slots):
    character_ids = sorted(s.slot_id for s in slots if s.slot_type == "character")
    assert character_ids == EXPECTED_CHARACTER_SLOT_IDS


def test_fight_club_merges_scene_2_by_inheritance(slots):
    slot = next(s for s in slots if s.slot_id == "int_blue_door_fight_club")
    assert slot.source_scenes == [1, 2]
    assert "scene 2" in slot.merge_reason
    assert "D-02" in slot.merge_reason


def test_rockys_apartment_int_and_ext_stay_separate_slots(slots):
    ext = next(s for s in slots if s.slot_id == "ext_rockys_apartment")
    interior = next(s for s in slots if s.slot_id == "int_rockys_apartment")
    assert ext.source_scenes == [6]
    assert interior.source_scenes == [8]
    assert ext.slot_id != interior.slot_id


def test_every_beat_maps_to_exactly_one_location_slot(beats, slots):
    location_slots = [s for s in slots if s.slot_type == "location"]
    beat_ids = {b["beat_id"] for b in beats["beats"]}
    covered: dict[str, list[str]] = {}
    for slot in location_slots:
        for bid in slot.beat_ids:
            covered.setdefault(bid, []).append(slot.slot_id)

    assert set(covered.keys()) == beat_ids
    for bid, owning_slots in covered.items():
        assert len(owning_slots) == 1, f"{bid} mapped to multiple location slots: {owning_slots}"


def test_every_character_name_maps_to_exactly_one_character_slot(beats, slots):
    character_slots = [s for s in slots if s.slot_type == "character"]
    slot_by_name: dict[str, list[str]] = {}
    for slot in character_slots:
        for name in slot.source_names:
            slot_by_name.setdefault(name, []).append(slot.slot_id)

    all_names: set[str] = set()
    for b in beats["beats"]:
        all_names.update(b.get("characters", []))
        for line in b.get("dialogue", []):
            if line.get("character"):
                all_names.add(line["character"])

    assert set(slot_by_name.keys()) == all_names
    for name, owning_slots in slot_by_name.items():
        assert len(owning_slots) == 1, f"{name!r} mapped to multiple character slots: {owning_slots}"


def test_every_slot_beat_ids_nonempty_and_valid(beats, slots):
    valid_ids = {b["beat_id"] for b in beats["beats"]}
    for slot in slots:
        assert slot.beat_ids, f"{slot.slot_id} has no beat_ids"
        for bid in slot.beat_ids:
            assert bid in valid_ids, f"{slot.slot_id} references unknown beat_id {bid}"
