"""Tests for music-cue detection and the named-work guard.

The guard test is the important one. The script names a real 1958 recording by
title, and handing that title to a music model asks it to reproduce a
copyrighted work. The rule is asserted on the BUILT PROMPT STRING, not by
reading the source for a strip call — the same discipline Phase 4 settled on
after a rule that existed in the source failed to reach the prompt.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from animatic.core.music_cues import (
    MusicCue,
    _sentences,
    build_music_prompt,
    find_music_cues,
    strip_named_works,
)
from corpus import beats_path

PDF = Path("docs/rocky-1976.pdf")
BEATS_JSON = beats_path()

pytestmark = pytest.mark.skipif(
    not (PDF.exists() and BEATS_JSON.exists()),
    reason="needs the real script PDF and beat list",
)


@pytest.fixture(scope="module")
def beats():
    return json.loads(BEATS_JSON.read_text())["beats"]


@pytest.fixture(scope="module")
def cues(beats):
    return find_music_cues(PDF, beats)


class TestSentences:
    def test_pdf_line_wrapping_is_undone(self):
        wrapped = "As the CRACKLING MUSIC BEGINS, Rocky picks up his\nhairbrush."
        assert _sentences(wrapped) == [
            "As the CRACKLING MUSIC BEGINS, Rocky picks up his hairbrush."
        ]

    def test_sentences_are_split_apart(self):
        text = "He boils water. Then he plays a record. The room is quiet."
        assert len(_sentences(text)) == 3

    def test_an_abbreviation_does_not_split_mid_sentence(self):
        # Screenplay prose is full of "INT." and "EXT."
        assert len(_sentences("He enters the room quietly and sits down.")) == 1


class TestFindCues:
    def test_the_script_yields_its_real_cues(self, cues):
        assert {c.scene for c in cues} == {3, 8}

    def test_a_cue_names_the_beats_that_carry_it(self, cues):
        scene8 = next(c for c in cues if c.scene == 8)
        assert scene8.beat_ids == ["s8b4", "s8b5"]
        assert scene8.total_secs > 0

    def test_a_cue_quotes_the_script_line_that_triggered_it(self, cues):
        scene3 = next(c for c in cues if c.scene == 3)
        joined = " ".join(scene3.cue_lines).lower()
        assert "radio" in joined and "music" in joined

    def test_the_reason_is_machine_readable_and_specific(self, cues):
        # NFR-04.
        for cue in cues:
            assert cue.scene_heading or cue.beat_ids
            assert str(cue.scene) in cue.reason
            assert all(bid in cue.reason for bid in cue.beat_ids)

    def test_a_scene_with_no_music_produces_no_cue(self, cues):
        # Scenes 1, 2, 4-7 have no music cue in the script; if detection fired
        # on every scene the criterion would be met vacuously.
        assert len(cues) < 8


class TestNamedWorkGuard:
    def test_a_quoted_title_is_stripped(self):
        assert "ALL IN THE GAME" not in strip_named_works(
            'The record is a tune, "ALL IN THE GAME."'
        )

    def test_curly_quotes_are_stripped_too(self):
        assert "SOME SONG" not in strip_named_works("He plays “SOME SONG” loudly.")

    def test_surrounding_prose_survives(self):
        out = strip_named_works('He plays "SOME SONG" on the phonograph.')
        assert "phonograph" in out

    def test_no_named_work_reaches_a_built_prompt(self, cues):
        # Asserted on the string that is actually sent, not on the source.
        for cue in cues:
            prompt = build_music_prompt(cue)
            assert '"' not in prompt
            assert "“" not in prompt
            assert "all in the game" not in prompt.lower()

    def test_a_title_planted_in_a_cue_still_never_reaches_the_prompt(self):
        # The real script happens not to put its title on a cue-matching line.
        # This plants one there so the guard is tested, not the luck.
        cue = MusicCue(
            scene=8,
            scene_heading="INT. APARTMENT - NIGHT",
            cue_lines=['He puts on a record of "ALL IN THE GAME" and the music starts.'],
            beat_ids=["s8b4"],
            total_secs=5.9,
        )
        prompt = build_music_prompt(cue)
        assert "ALL IN THE GAME" not in prompt.upper()
        assert "record" in prompt.lower()

    def test_the_prompt_asks_for_original_music_in_positive_terms(self, cues):
        for cue in cues:
            prompt = build_music_prompt(cue)
            assert "original" in prompt.lower()


class TestPromptContent:
    def test_the_prompt_carries_the_room_and_the_source(self, cues):
        scene8 = next(c for c in cues if c.scene == 8)
        prompt = build_music_prompt(scene8).lower()
        assert "apartment" in prompt
        assert "phonograph" in prompt or "record" in prompt

    def test_prompts_differ_between_cues(self, cues):
        prompts = {build_music_prompt(c) for c in cues}
        assert len(prompts) == len(cues)
