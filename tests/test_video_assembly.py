"""Tests for shot planning, the cut manifest, and the assembled cut itself.

Planning is tested in isolation; the encode is tested against the real
`output/video/animatic.mp4` when one exists, because "the audio is never
clipped" is a claim about a file, not about a function.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from animatic.core.cut_manifest import build_index
from animatic.core.video_assembler import (
    CUT_TEMPLATE_VERSION,
    FRAME_HEIGHT,
    FRAME_WIDTH,
    MUSIC_GAIN,
    PAD_COLOUR,
    Shot,
    _shot_length,
    _video_filter,
    plan_shots,
    probe_duration,
)

BEATS = {
    "generated_at": "now",
    "beats": [
        {"beat_id": "s1b1", "scene": 1, "beat": 1, "duration_secs": 2.2, "dialogue": []},
        {"beat_id": "s2b1", "scene": 2, "beat": 1, "duration_secs": 5.9, "dialogue": []},
        {"beat_id": "s2b2", "scene": 2, "beat": 2, "duration_secs": 7.2, "dialogue": []},
    ],
}


def _audio_index(tmp_path, **over):
    wav = tmp_path / "s1b1.wav"
    wav.write_bytes(b"RIFF")
    music = tmp_path / "music_scene2.mp3"
    music.write_bytes(b"ID3")
    base = {
        "generated_at": "now",
        "clips": [
            {"beat_id": "s1b1", "shot_secs": 2.2, "shot_secs_source": "page_budget",
             "shot_secs_reason": "fits", "audio_secs": 1.9, "local_path": str(wav)},
            {"beat_id": "s2b1", "shot_secs": 6.4, "shot_secs_source": "audio_floor",
             "shot_secs_reason": "widened", "audio_secs": 6.2, "local_path": str(wav)},
        ],
        "music_cues": [
            {"cue_id": "scene2", "beat_ids": ["s2b1"], "local_path": str(music)}
        ],
    }
    base.update(over)
    return base


class TestShotLength:
    def test_the_audio_index_wins_over_the_beat(self):
        """The rule the whole phase turns on."""
        beat = {"beat_id": "s2b1", "duration_secs": 5.9}
        clip = {"shot_secs": 6.4, "shot_secs_source": "audio_floor",
                "shot_secs_reason": "widened to fit speech"}
        secs, source, reason = _shot_length(beat, clip)
        assert secs == 6.4
        assert source == "audio_floor"
        assert "widened" in reason

    def test_a_beat_with_no_audio_falls_back_and_says_so(self):
        beat = {"beat_id": "s9b9", "duration_secs": 3.3}
        secs, source, reason = _shot_length(beat, None)
        assert secs == 3.3
        assert source == "beat_duration"
        assert "no audio entry" in reason
        assert "s9b9" in reason

    def test_a_zero_shot_secs_is_not_trusted(self):
        # A failed clip records shot_secs 0; cutting a shot to nothing would
        # drop the beat out of the cut entirely.
        beat = {"beat_id": "s9b9", "duration_secs": 3.3}
        secs, source, _ = _shot_length(beat, {"shot_secs": 0})
        assert secs == 3.3
        assert source == "beat_duration"


class TestPlanShots:
    def test_every_beat_becomes_a_shot(self, tmp_path, monkeypatch):
        panels = tmp_path / "panels"
        panels.mkdir()
        for b in BEATS["beats"]:
            (panels / f"{b['beat_id']}.jpg").write_bytes(b"JPEG")
        monkeypatch.setattr("animatic.core.shot_sources.PANEL_DIR", panels)
        monkeypatch.setattr("animatic.core.shot_sources.FOOTAGE_DIR", tmp_path / "no-footage")
        monkeypatch.setattr("animatic.core.shot_sources.MOTION_DIR", tmp_path / "no-motion")

        shots = plan_shots(BEATS, _audio_index(tmp_path))
        assert [s.beat_id for s in shots] == ["s1b1", "s2b1", "s2b2"]

    def test_shots_come_out_in_beat_order(self, tmp_path, monkeypatch):
        panels = tmp_path / "panels"
        panels.mkdir()
        for b in BEATS["beats"]:
            (panels / f"{b['beat_id']}.jpg").write_bytes(b"JPEG")
        monkeypatch.setattr("animatic.core.shot_sources.PANEL_DIR", panels)
        monkeypatch.setattr("animatic.core.shot_sources.FOOTAGE_DIR", tmp_path / "nf")
        monkeypatch.setattr("animatic.core.shot_sources.MOTION_DIR", tmp_path / "nm")

        reversed_beats = {**BEATS, "beats": list(reversed(BEATS["beats"]))}
        shots = plan_shots(reversed_beats, _audio_index(tmp_path))
        assert [(s.scene, s.beat) for s in shots] == [(1, 1), (2, 1), (2, 2)]

    def test_music_attaches_only_to_its_carrier_beats(self, tmp_path, monkeypatch):
        panels = tmp_path / "panels"
        panels.mkdir()
        for b in BEATS["beats"]:
            (panels / f"{b['beat_id']}.jpg").write_bytes(b"JPEG")
        monkeypatch.setattr("animatic.core.shot_sources.PANEL_DIR", panels)
        monkeypatch.setattr("animatic.core.shot_sources.FOOTAGE_DIR", tmp_path / "nf")
        monkeypatch.setattr("animatic.core.shot_sources.MOTION_DIR", tmp_path / "nm")

        shots = {s.beat_id: s for s in plan_shots(BEATS, _audio_index(tmp_path))}
        assert shots["s2b1"].music_path is not None
        assert shots["s1b1"].music_path is None

    def test_a_scene_filter_narrows_the_cut(self, tmp_path, monkeypatch):
        panels = tmp_path / "panels"
        panels.mkdir()
        for b in BEATS["beats"]:
            (panels / f"{b['beat_id']}.jpg").write_bytes(b"JPEG")
        monkeypatch.setattr("animatic.core.shot_sources.PANEL_DIR", panels)
        monkeypatch.setattr("animatic.core.shot_sources.FOOTAGE_DIR", tmp_path / "nf")
        monkeypatch.setattr("animatic.core.shot_sources.MOTION_DIR", tmp_path / "nm")

        shots = plan_shots(BEATS, _audio_index(tmp_path), scene=2)
        assert {s.scene for s in shots} == {2}

    def test_a_clip_whose_file_is_gone_yields_a_silent_shot_not_a_crash(
        self, tmp_path, monkeypatch
    ):
        panels = tmp_path / "panels"
        panels.mkdir()
        for b in BEATS["beats"]:
            (panels / f"{b['beat_id']}.jpg").write_bytes(b"JPEG")
        monkeypatch.setattr("animatic.core.shot_sources.PANEL_DIR", panels)
        monkeypatch.setattr("animatic.core.shot_sources.FOOTAGE_DIR", tmp_path / "nf")
        monkeypatch.setattr("animatic.core.shot_sources.MOTION_DIR", tmp_path / "nm")

        audio = _audio_index(tmp_path)
        audio["clips"][0]["local_path"] = "/nonexistent/gone.wav"
        shots = {s.beat_id: s for s in plan_shots(BEATS, audio)}
        assert shots["s1b1"].audio_path is None
        assert shots["s1b1"].secs == 2.2


class TestVideoFilter:
    def _shot(self, kind):
        from animatic.core.shot_sources import ShotSource

        return Shot(
            beat_id="s1b1", scene=1, beat=1, secs=4.0,
            secs_source="page_budget", secs_reason="r",
            source=ShotSource("s1b1", kind, Path("x"), "r"),
            audio_path=None, music_path=None,
        )

    def test_the_pad_is_white_not_black(self):
        # Black bars around black-line-art-on-white read as a rendering fault.
        assert PAD_COLOUR == "white"
        assert f":{PAD_COLOUR}" in _video_filter(self._shot("still"))

    def test_the_frame_is_normalised_without_distorting_the_panel(self):
        f = _video_filter(self._shot("still"))
        assert f"scale={FRAME_WIDTH}:{FRAME_HEIGHT}" in f
        assert "force_original_aspect_ratio=decrease" in f

    def test_a_short_clip_holds_its_last_frame_rather_than_being_slowed(self):
        f = _video_filter(self._shot("motion"))
        assert "tpad=stop_mode=clone" in f
        assert "setpts" not in f  # never re-time the motion

    def test_a_still_is_not_padded_with_clone_frames(self):
        assert "tpad" not in _video_filter(self._shot("still"))


_CUT = Path("output/video/animatic.mp4")
_CUT_INDEX = Path("output/video/index.json")


@pytest.fixture(scope="module")
def cut():
    """The real cut manifest, once a build has produced one."""
    if not (_CUT.exists() and _CUT_INDEX.exists()):
        pytest.skip("no cut yet — run scripts/build_video.py")
    if not shutil.which("ffprobe"):
        pytest.skip("ffprobe not on PATH")
    return json.loads(_CUT_INDEX.read_text())


class TestCutManifest:
    def _entries(self):
        return [
            {"beat_id": "s1b1", "scene": 1, "beat": 1, "shot_secs": 2.0,
             "shot_source": "still", "shot_secs_reason": "r", "shot_source_reason": "r"},
            {"beat_id": "s2b1", "scene": 2, "beat": 1, "shot_secs": 8.0,
             "shot_source": "footage", "shot_secs_reason": "r", "shot_source_reason": "r"},
        ]

    def test_real_footage_pct_is_by_screen_time_not_shot_count(self):
        """One long replaced shot is more of the cut than several short ones."""
        index = build_index(self._entries(), {}, {}, {}, None, None, CUT_TEMPLATE_VERSION)
        assert index["real_footage_pct"] == 80.0  # 8s of 10s, not 50% of 2 shots
        assert index["real_footage_secs"] == 8.0

    def test_an_all_animatic_cut_reports_zero(self):
        stills = [{**e, "shot_source": "still"} for e in self._entries()]
        index = build_index(stills, {}, {}, {}, None, None, CUT_TEMPLATE_VERSION)
        assert index["real_footage_pct"] == 0.0

    def test_sources_are_counted(self):
        index = build_index(self._entries(), {}, {}, {}, None, None, CUT_TEMPLATE_VERSION)
        assert index["shots_by_source"] == {"still": 1, "footage": 1}

    def test_shots_are_written_in_beat_order(self):
        index = build_index(
            list(reversed(self._entries())), {}, {}, {}, None, None, CUT_TEMPLATE_VERSION
        )
        assert [s["beat_id"] for s in index["shots"]] == ["s1b1", "s2b1"]

    def test_audio_warnings_are_carried_onto_the_cut(self):
        # So a reader of the cut manifest need not open the audio index to
        # learn the cut contains stale or mislabelled audio.
        audio = {"stale_beat_ids": ["s5b2"], "text_mismatch_beat_ids": ["s5b2"]}
        index = build_index(self._entries(), {}, audio, {}, None, None, CUT_TEMPLATE_VERSION)
        assert index["stale_audio_beat_ids"] == ["s5b2"]
        assert index["text_mismatch_beat_ids"] == ["s5b2"]

    def test_the_index_never_claims_an_unwritten_s3_state(self):
        index = build_index(self._entries(), {}, {}, {}, None, None, CUT_TEMPLATE_VERSION)
        assert index["s3_ok"] is None

    def test_an_empty_cut_does_not_divide_by_zero(self):
        index = build_index([], {}, {}, {}, None, None, CUT_TEMPLATE_VERSION)
        assert index["real_footage_pct"] == 0.0


class TestTheRealCut:
    """Asserted against `output/video/animatic.mp4` once one has been built."""

    def test_the_cut_covers_the_demo_scenes(self, cut):
        """ROADMAP criterion 1."""
        assert sorted({s["scene"] for s in cut["shots"]}) == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_the_file_is_as_long_as_the_shots_it_claims(self, cut):
        """ROADMAP criterion 2, measured from the file, not the plan."""
        measured = probe_duration(_CUT)
        planned = sum(s["shot_secs"] for s in cut["shots"])
        per_shot_drift = abs(measured - planned) / len(cut["shots"])
        # One frame at 24fps is ~42ms; sub-frame rounding per shot is expected.
        assert per_shot_drift < 0.042, f"{per_shot_drift * 1000:.1f}ms per shot"

    def test_no_shot_is_shorter_than_its_own_audio(self, cut):
        """ROADMAP criterion 3 — the one that would clip speech."""
        audio = json.loads(Path("output/audio/index.json").read_text())
        clips = {c["beat_id"]: c for c in audio["clips"]}
        clipped = [
            s["beat_id"] for s in cut["shots"]
            if (c := clips.get(s["beat_id"])) and c["audio_secs"] > s["shot_secs"] + 1e-6
        ]
        assert not clipped, clipped

    def test_every_shot_carries_a_reason(self, cut):
        """ROADMAP criterion 4 / NFR-04."""
        for shot in cut["shots"]:
            assert shot["shot_secs_reason"].strip(), shot["beat_id"]
            assert shot["shot_source_reason"].strip(), shot["beat_id"]

    def test_every_shot_names_a_source_that_exists(self, cut):
        missing = [
            s["beat_id"] for s in cut["shots"] if not Path(s["shot_source_path"]).exists()
        ]
        assert not missing, missing

    def test_the_cut_records_its_own_hash(self, cut):
        assert cut["cut_sha256"]
