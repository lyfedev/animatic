"""Tests for the five steering features.

Real files on a real filesystem for the priority and override work, because
what is being tested is which file on disk wins. No image or video call is
made — the model-conditioning tests assert the CALL SHAPE and the prompt,
which is all that can be checked without spending quota and a human's eye.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from animatic.core import beat_overrides, panel_edit
from animatic.core.panel_prompt import build_conditioned_prompt
from animatic.core.shot_sources import (
    DailySpan,
    OverlappingDailiesError,
    find_dailies,
    resolve_shot,
)

BEAT_ORDER = ["s1b1", "s2b1", "s2b2", "s2b3", "s2b4", "s2b5"]


@pytest.fixture
def tree(tmp_path, monkeypatch):
    dirs = {
        name: tmp_path / name
        for name in ("dailies", "footage", "motion", "edited", "panels")
    }
    for d in dirs.values():
        d.mkdir()
    for beat_id in BEAT_ORDER:
        (dirs["panels"] / f"{beat_id}.jpg").write_bytes(b"JPEG")
    monkeypatch.setattr("animatic.core.shot_sources.DAILIES_DIR", dirs["dailies"])
    monkeypatch.setattr("animatic.core.shot_sources.FOOTAGE_DIR", dirs["footage"])
    monkeypatch.setattr("animatic.core.shot_sources.MOTION_DIR", dirs["motion"])
    monkeypatch.setattr("animatic.core.shot_sources.EDITED_PANEL_DIR", dirs["edited"])
    monkeypatch.setattr("animatic.core.shot_sources.PANEL_DIR", dirs["panels"])
    return dirs


# ---------------------------------------------------------------- C: edits

class TestEditedPanels:
    def test_an_edited_panel_outranks_the_generated_one(self, tree):
        (tree["edited"] / "s2b2.png").write_bytes(b"PNG")
        shot = resolve_shot("s2b2")
        assert shot.kind == "edited"
        assert shot.is_hand_made

    def test_it_is_still_a_still(self, tree):
        (tree["edited"] / "s2b2.png").write_bytes(b"PNG")
        assert resolve_shot("s2b2").is_still

    def test_it_is_not_counted_as_real_footage(self, tree):
        """A hand-corrected drawing is still a drawing."""
        (tree["edited"] / "s2b2.png").write_bytes(b"PNG")
        assert not resolve_shot("s2b2").is_real_footage

    def test_motion_and_footage_still_outrank_it(self, tree):
        (tree["edited"] / "s2b2.png").write_bytes(b"PNG")
        (tree["motion"] / "s2b2.mp4").write_bytes(b"MP4")
        assert resolve_shot("s2b2").kind == "motion"
        (tree["footage"] / "s2b2.mp4").write_bytes(b"MP4")
        assert resolve_shot("s2b2").kind == "footage"

    def test_removing_the_edit_restores_the_generated_panel(self, tree):
        edit = tree["edited"] / "s2b2.png"
        edit.write_bytes(b"PNG")
        assert resolve_shot("s2b2").kind == "edited"
        edit.unlink()
        assert resolve_shot("s2b2").kind == "still"

    def test_the_reason_says_it_survives_regeneration(self, tree):
        (tree["edited"] / "s2b2.png").write_bytes(b"PNG")
        assert "never overwritten" in resolve_shot("s2b2").reason


# ------------------------------------------------------------- B: overrides

class TestBeatOverrides:
    def test_a_hold_lengthens_the_shot(self, tmp_path):
        path = tmp_path / "ov.json"
        beat_overrides.set_duration("s2b2", 15.0, path=path)
        secs, source, reason = beat_overrides.apply(
            "s2b2", 8.8, "page_budget", "fits", beat_overrides.load_overrides(path)
        )
        assert secs == 15.0
        assert source == "hold_override"
        assert "8.80s -> 15.00s" in reason

    def test_a_beat_with_no_override_is_untouched(self, tmp_path):
        secs, source, reason = beat_overrides.apply(
            "s2b2", 8.8, "page_budget", "fits", {}
        )
        assert (secs, source, reason) == (8.8, "page_budget", "fits")

    def test_a_hold_shorter_than_the_audio_never_clips_speech(self, tmp_path):
        """The audio floor wins. Clipped dialogue is the one defect a viewer
        cannot miss, so an override is a floor and never a ceiling."""
        path = tmp_path / "ov.json"
        beat_overrides.set_duration("s2b18", 5.0, path=path)
        secs, source, reason = beat_overrides.apply(
            "s2b18", 12.98, "audio_floor", "widened",
            beat_overrides.load_overrides(path),
        )
        assert secs == 12.98
        assert "the longer of the two wins" in reason

    def test_overrides_live_outside_beats_json(self):
        """A re-parse must not discard them, and beats.json must stay a
        faithful record of what the script says."""
        assert beat_overrides.LOCAL_OVERRIDES != Path("output/beats.json")

    def test_they_survive_a_round_trip(self, tmp_path):
        path = tmp_path / "ov.json"
        beat_overrides.set_duration("s2b2", 15.0, reason="let the fight breathe", path=path)
        loaded = beat_overrides.load_overrides(path)
        assert loaded["s2b2"]["hold_secs"] == 15.0
        assert loaded["s2b2"]["reason"] == "let the fight breathe"

    def test_clearing_one_leaves_the_others(self, tmp_path):
        path = tmp_path / "ov.json"
        beat_overrides.set_duration("s2b2", 15.0, path=path)
        beat_overrides.set_duration("s2b3", 9.0, path=path)
        assert beat_overrides.clear_duration("s2b2", path=path) is True
        remaining = beat_overrides.load_overrides(path)
        assert set(remaining) == {"s2b3"}

    def test_clearing_one_that_is_not_there_is_not_an_error(self, tmp_path):
        assert beat_overrides.clear_duration("s9b9", path=tmp_path / "ov.json") is False

    def test_an_unreadable_file_degrades_to_no_overrides(self, tmp_path):
        path = tmp_path / "ov.json"
        path.write_text("{ not json")
        assert beat_overrides.load_overrides(path) == {}

    def test_extending_one_beat_does_not_touch_another(self, tmp_path):
        """Backlog S-02's rule, stated as a test.

        `fit_scene_to_budget` scales a whole scene to hit its page target, so
        lengthening one beat inside that model shortens its neighbours. An
        override sits outside it: the scene simply gets longer.
        """
        path = tmp_path / "ov.json"
        beat_overrides.set_duration("s2b2", 15.0, path=path)
        overrides = beat_overrides.load_overrides(path)
        neighbours = [("s2b1", 5.9), ("s2b3", 5.9), ("s2b4", 5.9)]
        for beat_id, secs in neighbours:
            assert beat_overrides.apply(beat_id, secs, "page_budget", "r", overrides)[0] == secs


# --------------------------------------------------------------- E: dailies

class TestDailies:
    def test_a_daily_covers_its_whole_range(self, tree):
        (tree["dailies"] / "s2b1-s2b3.mp4").write_bytes(b"MP4")
        covered = find_dailies(BEAT_ORDER)
        assert set(covered) == {"s2b1", "s2b2", "s2b3"}

    def test_the_range_is_read_from_the_filename(self, tree):
        """PROJECT.md non-goal: never infer the beat from the footage. That
        does not change because the unit went from one beat to several."""
        (tree["dailies"] / "s2b1-s2b3-take2.mp4").write_bytes(b"MP4")
        assert set(find_dailies(BEAT_ORDER)) == {"s2b1", "s2b2", "s2b3"}

    def test_the_range_follows_the_CUT_order_not_string_order(self, tree):
        # s2b1..s2b3 is three beats in cut order. Sorting the ids as strings
        # would give a different set entirely.
        (tree["dailies"] / "s2b1-s2b3.mp4").write_bytes(b"MP4")
        span = find_dailies(BEAT_ORDER)["s2b2"]
        assert span.beat_ids == ("s2b1", "s2b2", "s2b3")

    def test_a_reversed_range_is_accepted(self, tree):
        (tree["dailies"] / "s2b3-s2b1.mp4").write_bytes(b"MP4")
        assert set(find_dailies(BEAT_ORDER)) == {"s2b1", "s2b2", "s2b3"}

    def test_a_daily_outranks_everything(self, tree):
        (tree["dailies"] / "s2b1-s2b3.mp4").write_bytes(b"MP4")
        (tree["footage"] / "s2b2.mp4").write_bytes(b"MP4")
        (tree["motion"] / "s2b2.mp4").write_bytes(b"MP4")
        (tree["edited"] / "s2b2.png").write_bytes(b"PNG")
        shot = resolve_shot("s2b2", dailies=find_dailies(BEAT_ORDER))
        assert shot.kind == "daily"

    def test_it_carries_its_own_audio(self, tree):
        (tree["dailies"] / "s2b1-s2b3.mp4").write_bytes(b"MP4")
        shot = resolve_shot("s2b2", dailies=find_dailies(BEAT_ORDER))
        assert shot.carries_own_audio is True

    def test_nothing_else_carries_its_own_audio(self, tree):
        (tree["footage"] / "s2b2.mp4").write_bytes(b"MP4")
        assert resolve_shot("s2b2").carries_own_audio is False

    def test_it_counts_as_real_footage(self, tree):
        (tree["dailies"] / "s2b1-s2b3.mp4").write_bytes(b"MP4")
        shot = resolve_shot("s2b2", dailies=find_dailies(BEAT_ORDER))
        assert shot.is_real_footage is True

    def test_only_the_first_beat_opens_the_span(self, tree):
        (tree["dailies"] / "s2b1-s2b3.mp4").write_bytes(b"MP4")
        span = find_dailies(BEAT_ORDER)["s2b1"]
        assert span.is_start("s2b1") is True
        assert span.is_start("s2b2") is False

    def test_overlapping_dailies_are_refused_not_resolved(self, tree):
        """Whichever the code picked would be arbitrary, and the cut would be
        quietly wrong in a way nobody could see."""
        (tree["dailies"] / "s2b1-s2b3.mp4").write_bytes(b"MP4")
        (tree["dailies"] / "s2b3-s2b5.mp4").write_bytes(b"MP4")
        with pytest.raises(OverlappingDailiesError, match="s2b3"):
            find_dailies(BEAT_ORDER)

    def test_removing_a_daily_restores_the_animatic_shots(self, tree):
        clip = tree["dailies"] / "s2b1-s2b3.mp4"
        clip.write_bytes(b"MP4")
        assert find_dailies(BEAT_ORDER)
        clip.unlink()
        assert find_dailies(BEAT_ORDER) == {}
        assert resolve_shot("s2b2").kind == "still"

    def test_a_single_beat_file_is_not_treated_as_a_daily(self, tree):
        (tree["dailies"] / "s2b2.mp4").write_bytes(b"MP4")
        assert find_dailies(BEAT_ORDER) == {}

    def test_a_daily_filename_in_the_footage_folder_is_not_taken_as_footage(self, tree):
        # `s2b1-s2b3.mp4` starts with a beat id, so the footage matcher would
        # otherwise claim it for s2b1 alone and play three beats' worth of take
        # in one beat's slot.
        (tree["footage"] / "s2b1-s2b3.mp4").write_bytes(b"MP4")
        assert resolve_shot("s2b1").kind == "still"

    def test_an_unknown_beat_in_the_range_is_ignored(self, tree):
        (tree["dailies"] / "s9b9-s9b9.mp4").write_bytes(b"MP4")
        assert find_dailies(BEAT_ORDER) == {}

    def test_a_missing_dailies_folder_is_not_an_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("animatic.core.shot_sources.DAILIES_DIR", tmp_path / "nope")
        assert find_dailies(BEAT_ORDER) == {}


# ------------------------------------------------------------ D: text edits

class TestNegationRewriting:
    """The project's most expensive lesson, applied to user input.

    A negation gets RENDERED — "NO FACIALS" was once lettered into a frame,
    and naming the eyes as absent drew a fully rendered eye. The natural way
    to ask for an edit is a negation, so the instruction is rewritten before
    it is sent and the developer is shown what actually went.
    """

    @pytest.mark.parametrize(
        "instruction",
        [
            "no other people",
            "singing into a hairbrush alone in the room",
            "remove the turtles",
            "without the sign",
            "nobody else in shot",
        ],
    )
    def test_the_sent_prompt_carries_no_bare_negation(self, instruction):
        prompt, _ = panel_edit.build_edit_prompt(instruction)
        lowered = prompt.lower()
        for banned in ("no other people", "remove the", "without the", "nobody else"):
            assert banned not in lowered, f"{banned!r} survived into: {prompt}"

    def test_no_other_people_becomes_a_statement_about_what_is_there(self):
        rewritten, _ = panel_edit.rewrite_negations("no other people")
        assert "one lone figure" in rewritten

    def test_remove_x_names_the_space_not_the_thing_twice(self):
        rewritten, _ = panel_edit.rewrite_negations("remove the turtles")
        assert "plain, blank background" in rewritten

    def test_every_rewrite_is_reported_to_the_developer(self):
        """A rewrite they cannot see is a rewrite they cannot correct."""
        _, notes = panel_edit.rewrite_negations("no other people")
        assert notes and "->" in notes[0]

    def test_an_instruction_with_no_negation_is_left_alone(self):
        rewritten, notes = panel_edit.rewrite_negations("add a Gold's Gym sign")
        assert rewritten == "add a Gold's Gym sign"
        assert notes == []

    def test_the_style_block_lands_last(self):
        """D-06: a rule stated before another rule loses to it."""
        prompt, _ = panel_edit.build_edit_prompt("add a sign")
        assert prompt.index("The change:") < prompt.index("black")

    def test_the_prompt_asks_for_one_change_and_no_redraw(self):
        prompt, _ = panel_edit.build_edit_prompt("add a sign")
        assert "leave everything else" in prompt


class TestEditPersistence:
    def _panel(self, tmp_path):
        panel = tmp_path / "s8b5.jpg"
        panel.write_bytes(b"JPEG-original")
        return panel

    def test_an_edit_is_written_where_it_outranks_the_panel(self, tmp_path):
        edited = tmp_path / "edited"
        record = panel_edit.save_edit(
            "s8b5", b"PNGDATA", "image/png", self._panel(tmp_path),
            "alone in the room", "prompt", [], edited_dir=edited,
        )
        assert Path(record["edited_path"]).name == "s8b5.png"
        assert Path(record["edited_path"]).read_bytes() == b"PNGDATA"

    def test_the_original_is_kept_so_a_bad_edit_can_be_undone(self, tmp_path):
        """The failure mode of a one-way edit is that you stop trying them."""
        edited = tmp_path / "edited"
        record = panel_edit.save_edit(
            "s8b5", b"PNGDATA", "image/png", self._panel(tmp_path),
            "x", "p", [], edited_dir=edited,
        )
        assert Path(record["original_kept_at"]).read_bytes() == b"JPEG-original"

    def test_a_second_edit_does_not_overwrite_the_true_original(self, tmp_path):
        edited = tmp_path / "edited"
        panel = self._panel(tmp_path)
        panel_edit.save_edit("s8b5", b"ONE", "image/png", panel, "x", "p", [], edited_dir=edited)
        panel.write_bytes(b"JPEG-not-the-original")
        record = panel_edit.save_edit(
            "s8b5", b"TWO", "image/png", panel, "y", "p", [], edited_dir=edited
        )
        assert Path(record["original_kept_at"]).read_bytes() == b"JPEG-original"

    def test_the_record_says_what_was_actually_sent(self, tmp_path):
        record = panel_edit.save_edit(
            "s8b5", b"D", "image/png", self._panel(tmp_path),
            "no other people", "THE PROMPT", ["'no other people' -> '...'"],
            edited_dir=tmp_path / "edited",
        )
        assert record["instruction"] == "no other people"
        assert record["prompt_sent"] == "THE PROMPT"
        assert record["negations_rewritten"]

    def test_reverting_costs_nothing_and_removes_the_edit(self, tmp_path):
        edited = tmp_path / "edited"
        panel_edit.save_edit(
            "s8b5", b"D", "image/png", self._panel(tmp_path), "x", "p", [],
            edited_dir=edited,
        )
        assert panel_edit.revert("s8b5", edited_dir=edited) is True
        assert panel_edit.revert("s8b5", edited_dir=edited) is False

    def test_a_content_derived_beat_id_is_refused(self, tmp_path):
        with pytest.raises(AssertionError):
            panel_edit.save_edit(
                "../../etc/passwd", b"D", "image/png", self._panel(tmp_path),
                "x", "p", [], edited_dir=tmp_path / "edited",
            )

    def test_the_edit_call_sends_the_panel_and_the_prompt(self, tmp_path):
        panel = self._panel(tmp_path)
        response = MagicMock()
        part = MagicMock()
        part.inline_data.data = b"EDITED"
        part.inline_data.mime_type = "image/png"
        response.candidates = [MagicMock(content=MagicMock(parts=[part]))]

        with patch("animatic.core.panel_edit.genai.Client") as client:
            client.return_value.models.generate_content.return_value = response
            data, mime, prompt, _ = panel_edit.edit_panel(panel, "add a sign")

        assert data == b"EDITED"
        sent = client.return_value.models.generate_content.call_args.kwargs["contents"]
        assert len(sent) == 2, "the panel itself must be sent, not just a prompt"
        assert sent[1] == prompt


# -------------------------------------------------- A: plate conditioning

class TestPlateConditioning:
    def test_the_conditioned_prompt_keeps_the_base(self):
        base = "STYLE\n\nSubject: a room"
        assert base in build_conditioned_prompt(base)

    def test_the_plate_rule_lands_after_the_base(self):
        """A seed image can overrule a prompt, so the rule that has to beat it
        is restated after the plates are described — the same discipline that
        put the facial clause last in Phase 4."""
        prompt = build_conditioned_prompt("BASE")
        assert prompt.index("BASE") < prompt.index("supplied drawings")

    def test_the_plate_rule_demotes_plates_to_build_and_fittings(self):
        prompt = build_conditioned_prompt("BASE")
        assert "build and " in prompt and "clothing" in prompt

    def test_the_face_rule_is_told_to_beat_the_plates(self):
        prompt = build_conditioned_prompt("BASE")
        assert "whatever the supplied drawings happen to show" in prompt

    def test_plates_are_only_sent_when_asked_for(self, tmp_path):
        from animatic.core.panel_generator import generate_panel

        response = MagicMock()
        part = MagicMock()
        part.inline_data.data = b"IMG"
        part.inline_data.mime_type = "image/jpeg"
        response.candidates = [MagicMock(content=MagicMock(parts=[part]))]

        with patch("animatic.core.panel_generator.genai.Client") as client:
            client.return_value.models.generate_content.return_value = response
            generate_panel({"beat_id": "s2b2"}, "PROMPT")
        sent = client.return_value.models.generate_content.call_args.kwargs["contents"]
        assert sent == "PROMPT", "an unconditioned panel must stay text-only"

    def test_plates_are_sent_as_image_parts_ahead_of_the_prompt(self, tmp_path):
        from animatic.core.panel_generator import generate_panel

        plate = tmp_path / "rocky.jpg"
        plate.write_bytes(b"JPEG")
        response = MagicMock()
        part = MagicMock()
        part.inline_data.data = b"IMG"
        part.inline_data.mime_type = "image/jpeg"
        response.candidates = [MagicMock(content=MagicMock(parts=[part]))]

        with patch("animatic.core.panel_generator.genai.Client") as client:
            client.return_value.models.generate_content.return_value = response
            generate_panel({"beat_id": "s2b2"}, "PROMPT", [plate])
        sent = client.return_value.models.generate_content.call_args.kwargs["contents"]
        assert len(sent) == 2
        assert sent[-1] == "PROMPT", "the prompt lands after the plates"

    def test_a_plate_that_is_not_on_disk_is_skipped_not_fatal(self, tmp_path):
        from animatic.core.panel_generator import generate_panel

        response = MagicMock()
        part = MagicMock()
        part.inline_data.data = b"IMG"
        part.inline_data.mime_type = "image/jpeg"
        response.candidates = [MagicMock(content=MagicMock(parts=[part]))]

        with patch("animatic.core.panel_generator.genai.Client") as client:
            client.return_value.models.generate_content.return_value = response
            generate_panel({"beat_id": "s2b2"}, "PROMPT", [tmp_path / "gone.jpg"])
        assert client.return_value.models.generate_content.call_args.kwargs["contents"] == "PROMPT"

    def test_a_shared_plate_is_not_sent_twice(self, tmp_path):
        """Several minor characters share one generic art file (D-05). Sending
        it three times spends tokens without adding information."""
        from animatic.core.panel_generator import _slot_plates
        from animatic.core.slot_resolver import Slot

        plate = tmp_path / "generic.jpg"
        plate.write_bytes(b"JPEG")
        manifest = {
            "int_club": {"art_uri": str(plate)},
            "fighter_1": {"art_uri": str(plate)},
            "fighter_2": {"art_uri": str(plate)},
        }
        location = Slot(slot_id="int_club", slot_type="location", display_name="c")
        chars = [
            Slot(slot_id="fighter_1", slot_type="character", display_name="a"),
            Slot(slot_id="fighter_2", slot_type="character", display_name="b"),
        ]
        assert _slot_plates(location, chars, manifest) == [plate]

    def test_the_location_plate_comes_first(self, tmp_path):
        """The room is established before figures are placed in it — the order
        S-03's successful spike used."""
        from animatic.core.panel_generator import _slot_plates
        from animatic.core.slot_resolver import Slot

        room = tmp_path / "room.jpg"
        who = tmp_path / "who.jpg"
        room.write_bytes(b"J")
        who.write_bytes(b"J")
        manifest = {"int_club": {"art_uri": str(room)}, "rocky": {"art_uri": str(who)}}
        plates = _slot_plates(
            Slot(slot_id="int_club", slot_type="location", display_name="c"),
            [Slot(slot_id="rocky", slot_type="character", display_name="r")],
            manifest,
        )
        assert plates == [room, who]
