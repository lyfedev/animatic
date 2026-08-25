"""Tests for per-shot state — FR-08 and Phase 8's criteria 3 and 4."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from animatic.core.shot_state import build_state

BEATS = {
    "generated_at": "now",
    "beats": [
        {"beat_id": "s1b1", "scene": 1, "beat": 1, "type": "establishing",
         "duration_secs": 2.0},
        {"beat_id": "s2b2", "scene": 2, "beat": 2, "type": "action",
         "duration_secs": 8.0},
        {"beat_id": "s2b5", "scene": 2, "beat": 5, "type": "dialogue",
         "duration_secs": 5.0},
    ],
}


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A footage/motion/panels tree with a panel for every beat."""
    footage, motion, panels = (tmp_path / n for n in ("footage", "motion", "panels"))
    for d in (footage, motion, panels):
        d.mkdir()
    for beat in BEATS["beats"]:
        (panels / f"{beat['beat_id']}.jpg").write_bytes(b"JPEG")
    monkeypatch.setattr("animatic.core.shot_sources.FOOTAGE_DIR", footage)
    monkeypatch.setattr("animatic.core.shot_sources.MOTION_DIR", motion)
    monkeypatch.setattr("animatic.core.shot_sources.PANEL_DIR", panels)
    return footage, motion, panels


def _audio(**over):
    base = {
        "generated_at": "now",
        "clips": [
            {"beat_id": "s1b1", "shot_secs": 2.0, "kind": "narration",
             "voice": "Charon", "local_path": "x.wav"},
            {"beat_id": "s2b2", "shot_secs": 9.5, "kind": "narration",
             "voice": "Charon", "local_path": "x.wav"},
        ],
    }
    base.update(over)
    return base


class TestThreeStates:
    def test_a_bare_panel_is_an_animatic_still(self, tree):
        state = build_state(BEATS)
        assert state["shots_by_state"] == {"animatic_still": 3}

    def test_motion_is_its_own_state_not_a_still(self, tree):
        """FR-07 says animatic or footage, but a moving shot is neither."""
        _, motion, _ = tree
        (motion / "s2b2.mp4").write_bytes(b"MP4")
        state = build_state(BEATS)
        assert state["shots_by_state"]["animatic_motion"] == 1
        motion_shot = next(s for s in state["shots"] if s["beat_id"] == "s2b2")
        assert motion_shot["state"] == "animatic_motion"

    def test_motion_is_not_counted_as_real(self, tree):
        _, motion, _ = tree
        (motion / "s2b2.mp4").write_bytes(b"MP4")
        state = build_state(BEATS)
        assert state["real_footage_pct"] == 0.0
        assert all(not s["is_real"] for s in state["shots"])

    def test_footage_is_real(self, tree):
        footage, _, _ = tree
        (footage / "s2b2.mp4").write_bytes(b"MP4")
        state = build_state(BEATS)
        assert state["real_footage_beat_ids"] == ["s2b2"]
        real = next(s for s in state["shots"] if s["beat_id"] == "s2b2")
        assert real["is_real"] is True

    def test_a_beat_with_no_picture_is_reported_not_hidden(self, tmp_path, monkeypatch):
        empty = tmp_path / "nothing"
        empty.mkdir()
        monkeypatch.setattr("animatic.core.shot_sources.FOOTAGE_DIR", empty)
        monkeypatch.setattr("animatic.core.shot_sources.MOTION_DIR", empty)
        monkeypatch.setattr("animatic.core.shot_sources.PANEL_DIR", empty)
        state = build_state(BEATS)
        assert len(state["missing_beat_ids"]) == 3


class TestRealFootagePct:
    def test_it_is_by_screen_time_not_shot_count(self, tree):
        """One long replaced shot is more of the cut than several short ones."""
        footage, _, _ = tree
        (footage / "s2b2.mp4").write_bytes(b"MP4")  # 8s of 15s
        state = build_state(BEATS)
        assert state["real_footage_pct"] == pytest.approx(53.3, abs=0.1)

    def test_it_uses_the_audio_shot_secs_when_there_is_one(self, tree):
        # s2b2's beat is 8.0s but its audio widened the shot to 9.5s.
        footage, _, _ = tree
        (footage / "s2b2.mp4").write_bytes(b"MP4")
        state = build_state(BEATS, _audio())
        assert state["real_footage_secs"] == 9.5

    def test_an_all_animatic_cut_reports_zero(self, tree):
        assert build_state(BEATS)["real_footage_pct"] == 0.0

    def test_no_shots_does_not_divide_by_zero(self, tree):
        state = build_state({"generated_at": "n", "beats": []})
        assert state["real_footage_pct"] == 0.0


class TestFootageRoundTrip:
    """Phase 8 criteria 1 and 4, as a state-level round trip."""

    def test_adding_footage_changes_the_state(self, tree):
        footage, _, _ = tree
        before = build_state(BEATS)["real_footage_pct"]
        (footage / "s2b2.mp4").write_bytes(b"MP4")
        after = build_state(BEATS)["real_footage_pct"]
        assert after > before

    def test_removing_footage_restores_the_animatic_shot(self, tree):
        footage, _, _ = tree
        clip = footage / "s2b2.mp4"
        clip.write_bytes(b"MP4")
        assert build_state(BEATS)["real_footage_beat_ids"] == ["s2b2"]
        clip.unlink()
        assert build_state(BEATS)["real_footage_beat_ids"] == []

    def test_removing_footage_restores_MOTION_when_there_is_motion(self, tree):
        """Not the still — priority is footage, then motion, then panel."""
        footage, motion, _ = tree
        (motion / "s2b2.mp4").write_bytes(b"MP4")
        clip = footage / "s2b2.mp4"
        clip.write_bytes(b"MP4")
        assert build_state(BEATS)["shots_by_state"]["footage"] == 1
        clip.unlink()
        assert build_state(BEATS)["shots_by_state"]["animatic_motion"] == 1

    def test_a_labelled_take_is_recognised(self, tree):
        footage, _, _ = tree
        (footage / "s2b2-take1.mp4").write_bytes(b"MP4")
        assert build_state(BEATS)["real_footage_beat_ids"] == ["s2b2"]


class TestCutFreshness:
    def test_no_cut_reports_none_not_false(self, tree):
        assert build_state(BEATS)["cut_is_current"] is None

    def test_a_matching_cut_is_current(self, tree):
        cut = {"shots": [{"beat_id": b["beat_id"], "shot_source": "still"}
                         for b in BEATS["beats"]]}
        assert build_state(BEATS, cut_index=cut)["cut_is_current"] is True

    def test_a_footage_drop_makes_the_cut_stale(self, tree):
        footage, _, _ = tree
        (footage / "s2b2.mp4").write_bytes(b"MP4")
        cut = {"shots": [{"beat_id": b["beat_id"], "shot_source": "still"}
                         for b in BEATS["beats"]]}
        assert build_state(BEATS, cut_index=cut)["cut_is_current"] is False

    def test_a_rebuild_that_changed_nothing_is_not_stale(self, tree):
        # Comparing timestamps rather than sources would report stale here.
        cut = {"shots": [{"beat_id": b["beat_id"], "shot_source": "still"}
                         for b in BEATS["beats"]],
               "generated_at": "1999-01-01T00:00:00Z"}
        assert build_state(BEATS, cut_index=cut)["cut_is_current"] is True


class TestPerShotDetail:
    def test_every_shot_carries_a_reason(self, tree):
        for shot in build_state(BEATS)["shots"]:
            assert shot["shot_source_reason"].strip()

    def test_audio_presence_is_reported_per_shot(self, tree):
        shots = {s["beat_id"]: s for s in build_state(BEATS, _audio())["shots"]}
        assert shots["s1b1"]["has_audio"] is True
        assert shots["s2b5"]["has_audio"] is False

    def test_shots_without_audio_are_listed(self, tree):
        assert build_state(BEATS, _audio())["shots_without_audio"] == ["s2b5"]

    def test_a_refused_motion_beat_says_it_was_tried(self, tree):
        # So a UI can say "we tried and it was refused" rather than implying
        # the beat was never a candidate.
        motion_index = {
            "beats": [{"beat_id": "s2b2", "motion": True,
                       "motion_reason": "rank 1", "source": "generation_failed"}]
        }
        shots = {s["beat_id"]: s for s in build_state(BEATS, motion_index=motion_index)["shots"]}
        assert shots["s2b2"]["motion_selected"] is True
        assert shots["s2b2"]["motion_outcome"] == "generation_failed"
        assert shots["s2b2"]["state"] == "animatic_still"

    def test_shots_come_out_in_beat_order(self, tree):
        reversed_beats = {**BEATS, "beats": list(reversed(BEATS["beats"]))}
        order = [s["beat_id"] for s in build_state(reversed_beats)["shots"]]
        assert order == ["s1b1", "s2b2", "s2b5"]

    def test_the_state_never_claims_an_unwritten_s3(self, tree):
        assert build_state(BEATS)["s3_ok"] is None


class TestTheRealState:
    STATE = Path("output/state.json")

    def test_it_agrees_with_the_cut_manifest(self):
        cut_path = Path("output/video/index.json")
        if not (self.STATE.exists() and cut_path.exists()):
            pytest.skip("no state or cut yet")
        state = json.loads(self.STATE.read_text())
        cut = json.loads(cut_path.read_text())
        if not state["cut_is_current"]:
            pytest.skip("cut is stale — the two are expected to disagree")
        assert state["real_footage_pct"] == cut["real_footage_pct"]
