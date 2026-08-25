"""Tests for shot-source priority — the seam Phases 6 and 8 both hang off.

Real files on a real filesystem throughout. The point of this module is which
file on disk wins, so mocking the filesystem would test nothing.
"""

from __future__ import annotations

import pytest

from animatic.core.shot_sources import (
    MissingShotError,
    footage_beat_ids,
    resolve_shot,
)


@pytest.fixture
def dirs(tmp_path):
    footage = tmp_path / "footage"
    motion = tmp_path / "motion"
    panels = tmp_path / "panels"
    for d in (footage, motion, panels):
        d.mkdir()
    return footage, motion, panels


def _resolve(beat_id, dirs):
    footage, motion, panels = dirs
    return resolve_shot(beat_id, footage_dir=footage, motion_dir=motion, panel_dir=panels)


class TestPriority:
    def test_the_panel_is_used_when_nothing_else_exists(self, dirs):
        _, _, panels = dirs
        (panels / "s2b5.jpg").write_bytes(b"JPEG")
        shot = _resolve("s2b5", dirs)
        assert shot.kind == "still"
        assert shot.is_still

    def test_motion_beats_the_panel(self, dirs):
        _, motion, panels = dirs
        (panels / "s2b5.jpg").write_bytes(b"JPEG")
        (motion / "s2b5.mp4").write_bytes(b"MP4")
        assert _resolve("s2b5", dirs).kind == "motion"

    def test_footage_beats_motion(self, dirs):
        footage, motion, panels = dirs
        (panels / "s2b5.jpg").write_bytes(b"JPEG")
        (motion / "s2b5.mp4").write_bytes(b"MP4")
        (footage / "s2b5.mp4").write_bytes(b"MP4")
        shot = _resolve("s2b5", dirs)
        assert shot.kind == "footage"
        assert shot.is_real_footage

    def test_removing_footage_restores_the_animatic_shot(self, dirs):
        """Phase 8 criterion 4, stated as an invariant of this module."""
        footage, _, panels = dirs
        (panels / "s2b5.jpg").write_bytes(b"JPEG")
        (footage / "s2b5.mp4").write_bytes(b"MP4")
        assert _resolve("s2b5", dirs).kind == "footage"
        (footage / "s2b5.mp4").unlink()
        assert _resolve("s2b5", dirs).kind == "still"

    def test_a_beat_with_no_picture_at_all_raises(self, dirs):
        with pytest.raises(MissingShotError):
            _resolve("s2b5", dirs)

    def test_missing_directories_are_not_an_error(self, tmp_path):
        panels = tmp_path / "panels"
        panels.mkdir()
        (panels / "s2b5.jpg").write_bytes(b"JPEG")
        shot = resolve_shot(
            "s2b5",
            footage_dir=tmp_path / "nope",
            motion_dir=tmp_path / "also-nope",
            panel_dir=panels,
        )
        assert shot.kind == "still"

    def test_every_shot_explains_which_source_won(self, dirs):
        footage, motion, panels = dirs
        (panels / "s2b5.jpg").write_bytes(b"JPEG")
        (motion / "s2b5.mp4").write_bytes(b"MP4")
        (footage / "s2b5.mp4").write_bytes(b"MP4")
        for _ in range(3):
            shot = _resolve("s2b5", dirs)
            assert shot.reason.strip()
            assert str(shot.path) in shot.reason


class TestFootageNaming:
    """Beat number comes from the FILENAME, never from the footage.

    PROJECT.md lists "inferring beat number from footage" as an explicit
    non-goal, so the filename is the whole contract.
    """

    def test_a_bare_beat_id_matches(self, dirs):
        footage, _, panels = dirs
        (panels / "s2b5.jpg").write_bytes(b"JPEG")
        (footage / "s2b5.mp4").write_bytes(b"MP4")
        assert _resolve("s2b5", dirs).kind == "footage"

    @pytest.mark.parametrize("name", ["s2b5-take3.mp4", "s2b5_final.mp4", "s2b5-v2.mov"])
    def test_a_labelled_take_still_matches(self, dirs, name):
        footage, _, panels = dirs
        (panels / "s2b5.jpg").write_bytes(b"JPEG")
        (footage / name).write_bytes(b"MP4")
        assert _resolve("s2b5", dirs).kind == "footage"

    def test_a_different_beats_footage_does_not_match(self, dirs):
        footage, _, panels = dirs
        (panels / "s2b5.jpg").write_bytes(b"JPEG")
        (footage / "s2b50.mp4").write_bytes(b"MP4")
        assert _resolve("s2b5", dirs).kind == "still"

    def test_an_untagged_file_is_ignored(self, dirs):
        footage, _, panels = dirs
        (panels / "s2b5.jpg").write_bytes(b"JPEG")
        (footage / "rocky_fight_final.mp4").write_bytes(b"MP4")
        assert _resolve("s2b5", dirs).kind == "still"

    def test_a_non_video_file_is_ignored(self, dirs):
        footage, _, panels = dirs
        (panels / "s2b5.jpg").write_bytes(b"JPEG")
        (footage / "s2b5.txt").write_text("notes")
        assert _resolve("s2b5", dirs).kind == "still"

    def test_two_takes_resolve_the_same_way_every_run(self, dirs):
        # A cut that changes depending on directory iteration order is not
        # reproducible.
        footage, _, panels = dirs
        (panels / "s2b5.jpg").write_bytes(b"JPEG")
        for name in ("s2b5-take2.mp4", "s2b5-take1.mp4", "s2b5-take3.mp4"):
            (footage / name).write_bytes(b"MP4")
        chosen = {_resolve("s2b5", dirs).path.name for _ in range(5)}
        assert chosen == {"s2b5-take1.mp4"}

    def test_footage_beat_ids_reads_the_directory(self, dirs):
        footage, _, _ = dirs
        (footage / "s2b5.mp4").write_bytes(b"MP4")
        (footage / "s3b9-take2.mov").write_bytes(b"MOV")
        (footage / "notes.txt").write_text("x")
        (footage / "untagged.mp4").write_bytes(b"MP4")
        assert footage_beat_ids(footage) == {"s2b5", "s3b9"}

    def test_footage_beat_ids_on_a_missing_directory_is_empty(self, tmp_path):
        assert footage_beat_ids(tmp_path / "nope") == set()
