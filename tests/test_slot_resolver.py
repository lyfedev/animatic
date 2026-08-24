"""Unit tests for slot resolution — locations, characters, and the derived
priority/art/voice axes.

Pins exact expected slot_id sets, in the style of
test_extract_scenes_returns_scenes_1_to_8 — a wrong merge or a dropped
character names itself in the failure output rather than hiding behind a
bare count.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from animatic.core.slot_resolver import Slot, assert_no_voice_collisions, resolve_slots

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


# ---------------------------------------------------------------------------
# Task 3 — priority ranking, generic art slots, voice registry
# ---------------------------------------------------------------------------

def test_priority_ranks_are_unique_1_to_16(slots):
    ranks = sorted(s.priority_rank for s in slots)
    assert ranks == list(range(1, 17))


def test_rocky_is_rank_1_and_fight_club_is_rank_2(slots):
    rocky = next(s for s in slots if s.slot_id == "rocky")
    fight_club = next(s for s in slots if s.slot_id == "int_blue_door_fight_club")

    assert rocky.priority_rank == 1
    assert rocky.beats == 31
    assert rocky.duration_secs == pytest.approx(152.3, abs=0.1)
    assert rocky.share_pct == pytest.approx(59.6, abs=0.1)

    assert fight_club.priority_rank == 2
    assert fight_club.beats == 20
    assert fight_club.duration_secs == pytest.approx(117.8, abs=0.1)
    assert fight_club.share_pct == pytest.approx(46.1, abs=0.1)


def test_every_priority_reason_restates_beats_secs_and_share(slots):
    for slot in slots:
        reason = slot.priority_reason
        assert str(slot.beats) in reason, slot.slot_id
        assert str(slot.duration_secs) in reason, slot.slot_id
        assert str(slot.share_pct) in reason, slot.slot_id


def test_minor_characters_are_exactly_the_four_low_beat_roles(slots):
    minor_ids = sorted(
        s.slot_id for s in slots if s.slot_type == "character" and s.is_minor
    )
    assert minor_ids == sorted(["fighter_1", "fighter_2", "fan", "announcer"])

    bespoke_ids = sorted(
        s.slot_id
        for s in slots
        if s.slot_type == "character" and s.is_minor is False
    )
    assert bespoke_ids == sorted(
        ["rocky", "black_fighter", "promoter", "cornerman", "woman"]
    )

    for s in slots:
        if s.slot_type == "location":
            assert s.is_minor is None


def test_minor_characters_share_one_generic_art_slot(slots):
    minor = [s for s in slots if s.slot_type == "character" and s.is_minor]
    assert len(minor) == 4
    for s in minor:
        assert s.art_slot_id == "generic_minor_character"
        expected_shared = sorted(x.slot_id for x in minor if x.slot_id != s.slot_id)
        assert s.art_shared_with == expected_shared


def test_bespoke_characters_and_locations_use_their_own_slot_id_as_art_slot(slots):
    for s in slots:
        is_bespoke_character = s.slot_type == "character" and s.is_minor is False
        if s.slot_type == "location" or is_bespoke_character:
            assert s.art_slot_id == s.slot_id
            assert s.art_shared_with == []


def test_all_characters_have_distinct_voice_ids_locations_have_none(slots):
    character_slots = [s for s in slots if s.slot_type == "character"]
    voice_ids = [s.voice_id for s in character_slots]

    assert all(v is not None for v in voice_ids)
    assert len(voice_ids) == len(set(voice_ids)) == 9

    for s in slots:
        if s.slot_type == "location":
            assert s.voice_id is None


def test_fighter_1_and_fighter_2_share_art_but_not_voice(slots):
    f1 = next(s for s in slots if s.slot_id == "fighter_1")
    f2 = next(s for s in slots if s.slot_id == "fighter_2")

    assert f1.art_slot_id == f2.art_slot_id == "generic_minor_character"
    assert f1.voice_id != f2.voice_id


def test_assert_no_voice_collisions_passes_for_the_real_beat_list(beats, slots):
    assert_no_voice_collisions(beats, slots)  # must not raise


def test_assert_no_voice_collisions_raises_on_a_deliberate_collision(beats, slots):
    """FIGHTER #1 and FIGHTER #2 both speak in scene 3 (D-06) — forcing their
    voice_ids to collide must raise, in both directions of the guard."""
    colliding = copy.deepcopy(slots)
    f1 = next(s for s in colliding if s.slot_id == "fighter_1")
    f2 = next(s for s in colliding if s.slot_id == "fighter_2")
    f2.voice_id = f1.voice_id

    with pytest.raises(ValueError):
        assert_no_voice_collisions(beats, colliding)
