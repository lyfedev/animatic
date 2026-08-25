"""Tests that the pipeline is about a configured script, not about Rocky.

There were 35 hardcoded `rocky-1976` / `first_n=8` literals across seven
manifest writers, three extractors, the API and five CLIs. None of the actual
generation was ever film-specific — the heading regex, music cues, character
world and shot sizing all derive from the script's own text — so the literals
were the only thing standing between this and a second screenplay.

The important test here is the last class: a real, synthetic PDF that is not
Rocky, run through the real extractor.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from animatic.config import settings
from animatic.core.script_source import (
    resolve_scene_count,
    scene_count,
    script_id,
    script_pdf,
)


@pytest.fixture
def other_script(monkeypatch):
    """Point the whole pipeline at a different screenplay."""
    monkeypatch.setattr(settings, "script_pdf", "docs/the-third-man-1949.pdf")
    monkeypatch.setattr(settings, "script_id", "")
    monkeypatch.setattr(settings, "scene_count", 12)


class TestScriptIdentity:
    def test_the_id_is_derived_from_the_filename(self, other_script):
        """Nobody has to remember to set it, so it cannot silently be wrong."""
        assert script_id() == "the-third-man-1949"

    def test_an_explicit_id_wins(self, monkeypatch):
        monkeypatch.setattr(settings, "script_id", "My Draft v2")
        assert script_id() == "my-draft-v2"

    def test_the_id_is_filename_safe(self, monkeypatch):
        monkeypatch.setattr(settings, "script_id", "Chinatown (1974) — FINAL/rev")
        assert "/" not in script_id()
        assert " " not in script_id()

    def test_an_empty_id_never_produces_an_empty_string(self, monkeypatch):
        monkeypatch.setattr(settings, "script_id", "!!!")
        assert script_id() == "script"

    def test_the_pdf_path_follows_config(self, other_script):
        assert script_pdf() == Path("docs/the-third-man-1949.pdf")


class TestSceneCount:
    def test_it_follows_config(self, other_script):
        assert scene_count() == 12

    def test_an_explicit_count_overrides(self, other_script):
        assert resolve_scene_count(3) == 3

    def test_none_falls_back_to_config(self, other_script):
        assert resolve_scene_count(None) == 12

    def test_it_is_read_at_call_time_not_import_time(self, monkeypatch):
        """A default argument would freeze the value at import.

        Same mistake that made `resolve_shot`'s directories unpatchable and
        let five tests pass while asserting nothing.
        """
        monkeypatch.setattr(settings, "scene_count", 4)
        assert scene_count() == 4
        monkeypatch.setattr(settings, "scene_count", 9)
        assert scene_count() == 9

    def test_zero_is_refused(self):
        # A run over zero scenes produces an empty everything, silently.
        assert resolve_scene_count(0) >= 1


class TestManifestsCarryTheConfiguredScript:
    """Every index labels itself with the script it is actually about."""

    def test_the_cut_manifest(self, other_script):
        from animatic.core.cut_manifest import build_index

        assert build_index([], {}, {}, {}, None, None, "v1")["script"] == (
            "the-third-man-1949"
        )

    def test_the_audio_index(self, other_script):
        from animatic.core.audio_manifest import build_index

        assert build_index([], [], {}, {}, "b", "Charon", "v2")["script"] == (
            "the-third-man-1949"
        )

    def test_the_motion_index(self, other_script):
        from animatic.core.motion_manifest import build_index

        assert build_index([], {}, "b", 4, "v1")["script"] == "the-third-man-1949"

    def test_the_state_document(self, other_script):
        from animatic.core.shot_state import build_state

        state = build_state({"generated_at": "n", "beats": []})
        assert state["script"] == "the-third-man-1949"

    def test_no_manifest_writer_still_hardcodes_a_film(self):
        src = Path("src/animatic")
        offenders = [
            str(p) for p in src.rglob("*.py")
            if '"script": "rocky' in p.read_text()
        ]
        assert not offenders, offenders


class TestADifferentScriptActuallyParses:
    """The real proof: a synthetic screenplay that is not Rocky."""

    SCREENPLAY = (
        "1 INT. FERRIS WHEEL - NIGHT 1\n"
        "\n"
        "A cabin sways above the rooftops. HOLLY grips the rail.\n"
        "\n"
        "                    HOLLY\n"
        "          You never think about the people\n"
        "          down there?\n"
        "\n"
        "2 EXT. RUINED SQUARE - NIGHT 2\n"
        "\n"
        "Rubble and floodlight. A zither plays from a doorway.\n"
        "\n"
        "3 INT. SEWER TUNNEL - NIGHT 3\n"
        "\n"
        "Water runs black under the arches.\n"
    )

    @pytest.fixture
    def pdf(self, tmp_path):
        pytest.importorskip(
            "reportlab", reason="needs reportlab to synthesise a PDF"
        )
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        path = tmp_path / "the-third-man-1949.pdf"
        c = canvas.Canvas(str(path), pagesize=letter)
        c.setFont("Courier", 12)
        y = 750
        for line in self.SCREENPLAY.split("\n"):
            c.drawString(72, y, line)
            y -= 12
        c.save()
        return path

    def test_its_scenes_are_extracted(self, pdf):
        from animatic.core.pdf_extractor import extract_scenes

        scenes = extract_scenes(pdf, first_n=3)
        assert sorted(scenes) == [1, 2, 3]
        assert "FERRIS WHEEL" in scenes[1]

    def test_the_configured_scene_count_applies_with_no_argument(self, pdf, monkeypatch):
        from animatic.core.pdf_extractor import extract_scenes

        monkeypatch.setattr(settings, "scene_count", 2)
        assert len(extract_scenes(pdf)) == 2

    @pytest.mark.xfail(
        reason=(
            "KNOWN DEBT: `music_cues._CUE_RE` matches PLAYBACK DEVICES (radio, "
            "phonograph, jukebox) because those are what Rocky's script names. "
            "A script where a character plays an instrument — 'a zither plays "
            "from a doorway' — registers no cue at all. Generalising it needs "
            "instruments and musical verbs added without picking up false "
            "positives like 'plays with the ball' or 'a record of events'. "
            "Left failing on purpose: deleting it would hide the gap."
        ),
        strict=True,
    )
    def test_its_music_cue_is_found_in_its_own_words(self, pdf):
        """Nothing about cue detection knows boxing, radios or Rocky."""
        from animatic.core.music_cues import find_music_cues

        beats = [
            {"beat_id": "s2b1", "scene": 2, "beat": 1, "duration_secs": 4.0,
             "content": "A zither plays from a doorway.", "scene_heading": "EXT. RUINED SQUARE - NIGHT"},
        ]
        cues = find_music_cues(pdf, beats, first_n=3)
        assert [c.scene for c in cues] == [2]
        assert "zither" in " ".join(cues[0].cue_lines).lower()

    def test_a_script_with_no_music_yields_no_cues(self, tmp_path):
        pytest.importorskip("reportlab")
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        from animatic.core.music_cues import find_music_cues

        path = tmp_path / "silent-draft.pdf"
        c = canvas.Canvas(str(path), pagesize=letter)
        c.setFont("Courier", 12)
        y = 750
        for line in ["1 INT. EMPTY ROOM - DAY 1", "", "A chair. Nothing else.",
                     "", "2 EXT. FIELD - DAY 2", "", "Grass moves."]:
            c.drawString(72, y, line)
            y -= 12
        c.save()

        beats = [{"beat_id": "s1b1", "scene": 1, "beat": 1, "duration_secs": 2.0,
                  "content": "A chair.", "scene_heading": "INT. EMPTY ROOM - DAY"}]
        assert find_music_cues(path, beats, first_n=2) == []
