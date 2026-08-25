"""Tests for motion selection, prompts and the motion index.

No Veo call is made here — a clip costs a minute of wall clock and counts
against a per-model daily cap. What is tested is everything around it, which
is where ROADMAP criteria 1-4 actually live.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from animatic.core.motion_generator import (
    EmptyVeoResponse,
    MotionGenerationError,
    motion_cache_key,
    panel_for,
    write_motion,
)
from animatic.core.motion_manifest import build_index
from animatic.core.motion_prompt import (
    MOTION_PROMPT_VERSION,
    build_motion_prompt,
    motion_description,
)
from animatic.core.motion_selector import (
    DEFAULT_BUDGET,
    select_for_motion,
)
from corpus import beats_path

BEATS = [
    {"beat_id": "s1b1", "scene": 1, "beat": 1, "type": "establishing",
     "duration_secs": 2.2, "content": "A dark club.", "motion_candidate": False},
    {"beat_id": "s2b2", "scene": 2, "beat": 2, "type": "action",
     "duration_secs": 8.8, "content": "Rocky trades blows.", "motion_candidate": True},
    {"beat_id": "s2b5", "scene": 2, "beat": 5, "type": "dialogue",
     "duration_secs": 5.4, "content": "He sneers.", "motion_candidate": False},
    {"beat_id": "s2b9", "scene": 2, "beat": 9, "type": "action",
     "duration_secs": 9.9, "content": "The crowd surges.", "motion_candidate": False},
    {"beat_id": "s8b6", "scene": 8, "beat": 6, "type": "action",
     "duration_secs": 3.5, "content": "He throws a right cross.", "motion_candidate": True},
]


class TestSelection:
    def test_every_beat_gets_a_decision(self):
        """ROADMAP criterion 2 — not just the winners."""
        choices = select_for_motion(BEATS, budget=2)
        assert len(choices) == len(BEATS)
        assert all(c.reason.strip() for c in choices)

    def test_the_budget_is_respected(self):
        """ROADMAP criterion 1."""
        for budget in (0, 1, 3, 99):
            picked = [c for c in select_for_motion(BEATS, budget=budget) if c.motion]
            assert len(picked) <= budget

    def test_a_flagged_beat_outranks_a_longer_unflagged_one(self):
        # s2b9 is 9.9s and unflagged; s8b6 is 3.5s and flagged. The parser read
        # the scene, so its judgement about movement beats raw length.
        picked = [c.beat_id for c in select_for_motion(BEATS, budget=2) if c.motion]
        assert "s8b6" in picked
        assert "s2b9" not in picked

    def test_action_outranks_dialogue_and_establishing(self):
        """ROADMAP criterion 3."""
        unflagged = [{**b, "motion_candidate": False} for b in BEATS]
        picked = [c.beat_id for c in select_for_motion(unflagged, budget=2) if c.motion]
        types = {b["beat_id"]: b["type"] for b in BEATS}
        assert all(types[bid] == "action" for bid in picked)

    def test_a_longer_beat_wins_within_the_same_type(self):
        unflagged = [{**b, "motion_candidate": False} for b in BEATS]
        picked = [c.beat_id for c in select_for_motion(unflagged, budget=1) if c.motion]
        assert picked == ["s2b9"]  # 9.9s beats 8.8s beats 3.5s

    def test_selection_is_stable_across_runs(self):
        runs = {
            tuple(c.beat_id for c in select_for_motion(BEATS, budget=3) if c.motion)
            for _ in range(5)
        }
        assert len(runs) == 1

    def test_choices_come_back_in_beat_order(self):
        choices = select_for_motion(list(reversed(BEATS)), budget=2)
        assert [(c.scene, c.beat) for c in choices] == [
            (1, 1), (2, 2), (2, 5), (2, 9), (8, 6)
        ]

    def test_only_overrides_the_ranking(self):
        choices = select_for_motion(BEATS, budget=2, only="s1b1")
        picked = [c.beat_id for c in choices if c.motion]
        assert picked == ["s1b1"]

    def test_only_still_explains_every_other_beat(self):
        choices = select_for_motion(BEATS, budget=2, only="s1b1")
        for choice in choices:
            if not choice.motion:
                assert "not requested" in choice.reason

    def test_a_still_reason_says_where_it_ranked(self):
        choices = {c.beat_id: c for c in select_for_motion(BEATS, budget=1)}
        assert "ranked" in choices["s1b1"].reason
        assert "outside the budget" in choices["s1b1"].reason

    def test_an_unknown_beat_type_does_not_crash_the_ranking(self):
        odd = BEATS + [{"beat_id": "s9b9", "scene": 9, "beat": 9, "type": "montage",
                        "duration_secs": 4.0, "content": "x"}]
        choices = select_for_motion(odd, budget=2)
        assert len(choices) == len(odd)


class TestMotionPrompt:
    def _beat(self, **over):
        return {**BEATS[1], **over}

    def test_the_prompt_says_animate_not_redraw(self):
        prompt = build_motion_prompt(self._beat())
        assert "brought to life as it already stands" in prompt

    def test_the_facial_rule_lands_last(self):
        """D-06's lesson: a rule stated mid-prompt loses to what follows it."""
        prompt = build_motion_prompt(self._beat())
        assert prompt.rstrip().endswith(
            "no matter how strong the reaction or how hard the moment of impact."
        )

    def test_a_close_up_gets_the_three_line_clause(self):
        close_up = self._beat(type="dialogue")
        assert "exactly three lines" in build_motion_prompt(close_up)

    def test_a_medium_gets_the_blank_plane_clause(self):
        assert "one continuous blank plane" in build_motion_prompt(self._beat())

    def test_the_no_invention_rule_is_stated_positively(self):
        # The first live clip grew a crowd that was not in the panel. The rule
        # says what the frame HOLDS, never what it must not add (D-07).
        prompt = build_motion_prompt(self._beat())
        assert "stays exactly as populated as the drawing shows it" in prompt

    def test_the_camera_is_held(self):
        assert "no push in, no pan, no cut" in build_motion_prompt(self._beat())

    def test_what_moves_comes_from_the_beat_itself(self):
        # Nothing here knows about boxing; a different script gets a different
        # description because the description IS the beat content.
        assert "Rocky trades blows" in motion_description(self._beat())
        other = self._beat(content="A trolley rattles past a shuttered storefront")
        assert "trolley rattles past" in build_motion_prompt(other)

    def test_the_prompt_never_names_an_absent_feature(self):
        # D-07: naming a thing draws it, present or absent. The clauses
        # describe the lines that ARE drawn.
        prompt = build_motion_prompt(self._beat())
        for banned in ("do not draw", "without any", "avoid", "no crowd"):
            assert banned not in prompt.lower()


class TestCacheKey:
    def _key(self, **over):
        base = {"beat": BEATS[1], "prompt": "p", "panel_hash": "abc"}
        return motion_cache_key(**{**base, **over})

    def test_it_is_stable(self):
        assert self._key() == self._key()

    def test_a_regenerated_panel_invalidates_the_motion(self):
        # The panel is the seed image, so new panel means stale clip even
        # though the beat text never changed.
        assert self._key(panel_hash="different") != self._key()

    def test_a_changed_prompt_invalidates(self):
        assert self._key(prompt="other") != self._key()


class TestPanelLookup:
    def test_it_finds_the_panel(self, tmp_path):
        (tmp_path / "s2b2.jpg").write_bytes(b"JPEG")
        assert panel_for("s2b2", tmp_path).name == "s2b2.jpg"

    def test_a_missing_panel_names_the_command_that_fixes_it(self, tmp_path):
        with pytest.raises(MotionGenerationError, match="build_panels"):
            panel_for("s2b2", tmp_path)


class TestWriteMotion:
    def test_the_filename_is_what_the_assembler_looks_for(self, tmp_path):
        path, _ = write_motion("s2b2", b"MP4", tmp_path)
        assert path.name == "s2b2.mp4"

    def test_a_content_derived_name_is_refused(self, tmp_path):
        with pytest.raises(AssertionError):
            write_motion("../../etc/passwd", b"MP4", tmp_path)

    def test_the_hash_is_of_the_bytes_written(self, tmp_path):
        import hashlib

        path, digest = write_motion("s2b2", b"MP4", tmp_path)
        assert digest == hashlib.sha256(path.read_bytes()).hexdigest()


class TestMotionIndex:
    def _entries(self):
        return [
            {"beat_id": "s2b2", "scene": 2, "beat": 2, "type": "action",
             "motion": True, "source": "generated"},
            {"beat_id": "s8b6", "scene": 8, "beat": 6, "type": "action",
             "motion": True, "source": "generation_failed"},
            {"beat_id": "s1b1", "scene": 1, "beat": 1, "type": "establishing",
             "motion": False, "source": "still"},
        ]

    def test_selected_is_not_confused_with_delivered(self):
        """A refused beat was selected and cost a call, but has no clip.

        Reporting the first as though it were the second is how a run with a
        refusal reads as complete.
        """
        index = build_index(self._entries(), {}, "b.json", 4, MOTION_PROMPT_VERSION)
        assert index["selected_count"] == 2
        assert index["motion_count"] == 1
        assert index["fell_back_to_still_beat_ids"] == ["s8b6"]

    def test_the_budget_check_counts_what_was_spent(self):
        index = build_index(self._entries(), {}, "b.json", 2, MOTION_PROMPT_VERSION)
        assert index["within_budget"] is True
        tight = build_index(self._entries(), {}, "b.json", 1, MOTION_PROMPT_VERSION)
        assert tight["within_budget"] is False

    def test_every_beat_is_in_the_index(self):
        """ROADMAP criterion 2."""
        index = build_index(self._entries(), {}, "b.json", 4, MOTION_PROMPT_VERSION)
        assert index["total_beats"] == 3

    def test_beats_come_out_in_order(self):
        index = build_index(self._entries(), {}, "b.json", 4, MOTION_PROMPT_VERSION)
        assert [b["beat_id"] for b in index["beats"]] == ["s1b1", "s2b2", "s8b6"]

    def test_failures_are_listed(self):
        index = build_index(self._entries(), {}, "b.json", 4, MOTION_PROMPT_VERSION)
        assert index["failed_beat_ids"] == ["s8b6"]

    def test_the_index_never_claims_an_unwritten_s3_state(self):
        index = build_index(self._entries(), {}, "b.json", 4, MOTION_PROMPT_VERSION)
        assert index["s3_ok"] is None


class TestTheRealSelection:
    """Against the actual beat list."""

    def test_the_default_budget_selects_action_beats_only(self):
        beats = json.loads(beats_path().read_text())["beats"]
        picked = [c for c in select_for_motion(beats, budget=DEFAULT_BUDGET) if c.motion]
        types = {b["beat_id"]: b["type"] for b in beats}
        assert all(types[c.beat_id] == "action" for c in picked)

    def test_most_beats_are_stills(self):
        """PROJECT.md: motion is cost-constrained, most beats are stills."""
        beats = json.loads(beats_path().read_text())["beats"]
        choices = select_for_motion(beats, budget=DEFAULT_BUDGET)
        stills = [c for c in choices if not c.motion]
        assert len(stills) / len(choices) > 0.8


class TestTheRealMotionIndex:
    INDEX = Path("output/motion/index.json")

    def test_the_cut_never_claims_a_clip_that_is_not_there(self):
        if not self.INDEX.exists():
            pytest.skip("no motion index yet — run scripts/build_motion.py")
        index = json.loads(self.INDEX.read_text())
        for beat in index["beats"]:
            if beat["beat_id"] in index["motion_beat_ids"]:
                assert Path(beat["local_path"]).exists(), beat["beat_id"]
