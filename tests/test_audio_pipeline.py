"""Tests for narration planning, the audio cache key, and the index contract.

No TTS or Lyria call is made here. Everything under test is the deterministic
scaffolding around those calls — which is where this phase's real invariants
live (ROADMAP criteria 1, 3 and 5).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from animatic.core import audio_generator, narration
from animatic.core.audio_generator import (
    AUDIO_TEMPLATE_VERSION,
    audio_cache_key,
    build_beat_entry,
    dialogue_direction,
    generate_missing_audio,
    resolve_beat_audio,
    speech_prompt,
)
from animatic.core.audio_manifest import build_index, write_clip
from animatic.core.audio_timing import narration_budget_words

DIALOGUE_BEAT = {
    "beat_id": "s2b5",
    "scene": 2,
    "beat": 5,
    "scene_heading": "INT. BOXING CLUB - NIGHT",
    "type": "dialogue",
    "content": "The Black Fighter sneers across the ring at Rocky.",
    "duration_secs": 5.4,
    "dialogue": [{"character": "BLACK FIGHTER", "line": "I'm gonna bust his head wide open!"}],
}

SILENT_BEAT = {
    "beat_id": "s1b1",
    "scene": 1,
    "beat": 1,
    "scene_heading": "INT. BLUE DOOR FIGHT CLUB - NIGHT",
    "type": "establishing",
    "content": "Establishing shot of the dark, tense interior of the club at night.",
    "duration_secs": 2.2,
    "dialogue": [],
}

CAST = {"BLACK FIGHTER": {"voice": "Fenrir", "reason": "gravelly"}}

_LIVE_INDEX = Path("output/audio/index.json")


@pytest.fixture(scope="module")
def index():
    """The real audio index, once a build has produced one."""
    if not _LIVE_INDEX.exists():
        pytest.skip("no audio index yet — run scripts/build_audio.py")
    return json.loads(_LIVE_INDEX.read_text())


class TestNarrationPlanning:
    def test_only_beats_without_dialogue_need_narration(self):
        targets = narration.narration_beats([DIALOGUE_BEAT, SILENT_BEAT])
        assert [b["beat_id"] for b in targets] == ["s1b1"]

    def test_the_prompt_states_a_word_budget_for_every_beat(self):
        prompt = narration.build_narration_prompt([SILENT_BEAT])
        assert f"at most {narration_budget_words(2.2)} words" in prompt
        assert "s1b1" in prompt

    def test_the_prompt_groups_by_scene_so_lines_do_not_repeat(self):
        other = {**SILENT_BEAT, "beat_id": "s2b1", "scene": 2, "beat": 1,
                 "scene_heading": "INT. BOXING CLUB - NIGHT"}
        prompt = narration.build_narration_prompt([SILENT_BEAT, other])
        assert prompt.count("Scene ") == 2

    def test_the_prompt_forbids_shot_language_positively(self):
        # Phase 4's lesson: rules land as instructions, not as negations of a
        # thing you have just named.
        prompt = narration.build_narration_prompt([SILENT_BEAT])
        assert "present tense" in prompt

    def test_shorten_cuts_to_the_target(self):
        text = "A dark and tense fight club interior at night with a crowd"
        assert len(narration.shorten(text, 4).split()) == 4

    def test_shorten_never_returns_nothing(self):
        assert narration.shorten("One two three", 0).split()

    def test_shorten_leaves_a_short_line_alone(self):
        assert narration.shorten("A dark club.", 10) == "A dark club."

    def test_a_shortened_line_still_ends_as_a_sentence(self):
        assert narration.shorten("A dark club at night, crowded and loud", 4).endswith(".")

    def test_a_beat_the_model_skipped_still_gets_text(self):
        with patch.object(narration, "_call_narration", return_value={}):
            out = narration.write_narration([SILENT_BEAT])
        assert out["s1b1"]
        assert len(out["s1b1"].split()) <= narration_budget_words(2.2)

    def test_a_failed_api_call_degrades_instead_of_blocking_the_run(self):
        # Exercises _call_narration's own except path, not a patched stand-in:
        # the client itself is made to fail.
        with patch("animatic.core.narration.genai.Client", side_effect=RuntimeError("boom")):
            out = narration.write_narration([SILENT_BEAT])
        assert out["s1b1"]
        assert len(out["s1b1"].split()) <= narration_budget_words(2.2)


class TestResolveBeatAudio:
    def test_a_dialogue_beat_speaks_its_script_line_in_its_cast_voice(self):
        kind, text, voice, reason, _ = resolve_beat_audio(DIALOGUE_BEAT, CAST, {}, "Charon")
        assert kind == "dialogue"
        assert text == "I'm gonna bust his head wide open!"
        assert voice == "Fenrir"
        assert reason == "gravelly"

    def test_a_silent_beat_is_narrated_in_the_narrator_voice(self):
        kind, text, voice, _, _ = resolve_beat_audio(
            SILENT_BEAT, CAST, {"s1b1": "A dark fight club."}, "Charon"
        )
        assert kind == "narration"
        assert text == "A dark fight club."
        assert voice == "Charon"

    def test_a_silent_beat_with_no_written_narration_falls_back_to_its_action(self):
        _, text, _, _, _ = resolve_beat_audio(SILENT_BEAT, CAST, {}, "Charon")
        assert text == SILENT_BEAT["content"]

    def test_an_uncast_speaker_is_reported_not_silently_narrated(self):
        _, _, _, reason, _ = resolve_beat_audio(DIALOGUE_BEAT, {}, {}, "Charon")
        assert "not in the cast list" in reason

    def test_the_direction_is_built_from_the_beat_not_a_character_table(self):
        direction = dialogue_direction(DIALOGUE_BEAT, "BLACK FIGHTER")
        assert "sneers across the ring" in direction

    def test_the_spoken_text_survives_the_direction_prefix(self):
        prompt = speech_prompt("Absolutely.", "Say this plainly")
        assert prompt.endswith("Absolutely.")


class TestRateLimitHandling:
    """Regression: the first full run lost beat s7b1 to a quota error.

    The backend caps this TTS model at 10 requests/minute and answered 429
    with `retryDelay: 54s`. The flat 2s retry inherited from `panel_generator`
    retried into the same closed window and recorded the beat as failed.
    """

    def test_a_quota_error_is_told_apart_from_a_network_blip(self):
        assert audio_generator._retry_after_secs(RuntimeError("Connection reset")) is None

    def test_the_servers_own_retry_delay_is_honoured(self):
        exc = RuntimeError(
            "429 RESOURCE_EXHAUSTED ... {'@type': 'RetryInfo', 'retryDelay': '54s'}"
        )
        delay = audio_generator._retry_after_secs(exc)
        assert delay is not None and delay >= 54

    def test_the_prose_retry_hint_is_read_when_there_is_no_retryinfo(self):
        exc = RuntimeError("429 RESOURCE_EXHAUSTED. Please retry in 31.5s.")
        assert audio_generator._retry_after_secs(exc) == pytest.approx(32.5)

    def test_a_quota_error_with_no_stated_delay_still_waits(self):
        delay = audio_generator._retry_after_secs(RuntimeError("429 RESOURCE_EXHAUSTED"))
        assert delay is not None and delay > 0

    def test_an_absurd_delay_cannot_stall_the_run(self):
        exc = RuntimeError("429 RESOURCE_EXHAUSTED 'retryDelay': '999999s'")
        assert audio_generator._retry_after_secs(exc) <= audio_generator._RETRY_DELAY_CAP_SECS

    def test_pacing_keeps_the_run_under_the_per_minute_cap(self):
        assert 60.0 / audio_generator._TTS_MIN_INTERVAL_SECS <= 10

    def test_pacing_waits_between_back_to_back_calls(self, monkeypatch):
        slept: list[float] = []
        monkeypatch.setattr(audio_generator.time, "sleep", slept.append)
        audio_generator._last_tts_call_at = audio_generator.time.time()
        audio_generator._pace_tts()
        assert slept and slept[0] > 0

    def test_pacing_does_not_wait_when_the_interval_has_passed(self, monkeypatch):
        slept: list[float] = []
        monkeypatch.setattr(audio_generator.time, "sleep", slept.append)
        audio_generator._last_tts_call_at = 0.0
        audio_generator._pace_tts()
        assert not slept


class TestCacheKey:
    def _key(self, **over):
        base = dict(beat=DIALOGUE_BEAT, kind="dialogue", text="hello",
                    voice="Fenrir", template_version=AUDIO_TEMPLATE_VERSION)
        return audio_cache_key(**{**base, **over})

    def test_it_is_stable(self):
        assert self._key() == self._key()

    def test_changing_the_text_invalidates(self):
        assert self._key(text="goodbye") != self._key()

    def test_changing_the_voice_invalidates(self):
        assert self._key(voice="Puck") != self._key()

    def test_changing_the_duration_invalidates(self):
        # Unlike the panel key: a new duration means a new narration budget.
        longer = {**DIALOGUE_BEAT, "duration_secs": 9.9}
        assert self._key(beat=longer) != self._key()

    def test_changing_the_template_version_invalidates_everything(self):
        assert self._key(template_version="v2") != self._key()


class TestBeatEntry:
    def _entry(self, audio_secs: float, beat=DIALOGUE_BEAT):
        return build_beat_entry(
            beat, "dialogue", "hello", "Fenrir", "gravelly", audio_secs, "fit", "key"
        )

    def test_every_required_field_is_populated(self):
        entry = self._entry(3.2)
        for field in (
            "beat_id", "scene", "beat", "kind", "text", "voice", "voice_reason",
            "beat_duration_secs", "audio_secs", "shot_secs", "shot_secs_source",
            "shot_secs_reason", "fit_reason", "cache_key",
        ):
            assert entry[field] != "" and entry[field] is not None, field

    def test_a_clip_inside_its_beat_keeps_the_page_budget(self):
        assert self._entry(3.2)["shot_secs_source"] == "page_budget"

    def test_a_clip_over_its_beat_widens_the_shot_and_says_so(self):
        entry = self._entry(7.0)
        assert entry["shot_secs_source"] == "audio_floor"
        assert entry["shot_secs"] >= entry["audio_secs"]
        assert "widened" in entry["shot_secs_reason"]


class TestWriteClip:
    def test_a_beat_id_shaped_name_is_accepted(self, tmp_path, monkeypatch):
        monkeypatch.setattr("animatic.core.audio_manifest._LOCAL_AUDIO_DIR", tmp_path)
        monkeypatch.setattr(
            "animatic.core.audio_manifest.put_bytes",
            lambda *a, **k: type("R", (), {"uri": "s3://x", "ok": True, "error": None})(),
        )
        _, path, _, _, _ = write_clip("s2b5", b"RIFF", "audio/wav")
        assert Path(path).name == "s2b5.wav"

    def test_a_content_derived_name_is_refused(self, tmp_path, monkeypatch):
        # Mirrors panel_manifest: no path segment is ever built from beat text.
        monkeypatch.setattr("animatic.core.audio_manifest._LOCAL_AUDIO_DIR", tmp_path)
        with pytest.raises(AssertionError):
            write_clip("../../etc/passwd", b"RIFF", "audio/wav")

    def test_a_music_cue_id_is_accepted(self, tmp_path, monkeypatch):
        monkeypatch.setattr("animatic.core.audio_manifest._LOCAL_AUDIO_DIR", tmp_path)
        monkeypatch.setattr(
            "animatic.core.audio_manifest.put_bytes",
            lambda *a, **k: type("R", (), {"uri": "s3://x", "ok": True, "error": None})(),
        )
        _, path, _, _, _ = write_clip("scene8", b"ID3", "audio/mpeg", prefix="music_")
        assert Path(path).name == "music_scene8.mp3"


class TestBuildIndex:
    def _entries(self):
        return [
            {**build_beat_entry(SILENT_BEAT, "narration", "a", "Charon", "r", 3.0, "f", "k"),
             "source": "generated"},
            {**build_beat_entry(DIALOGUE_BEAT, "dialogue", "b", "Fenrir", "r", 3.2, "f", "k"),
             "source": "reused"},
        ]

    def test_clips_are_written_in_beat_order(self):
        index = build_index(list(reversed(self._entries())), [], {}, {}, "b.json", "Charon", "v1")
        assert [c["beat_id"] for c in index["clips"]] == ["s1b1", "s2b5"]

    def test_counts_are_derived_not_asserted(self):
        index = build_index(self._entries(), [], {}, {}, "b.json", "Charon", "v1")
        assert index["total_clips"] == 2
        assert index["dialogue_count"] == 1
        assert index["narration_count"] == 1
        assert index["generated_count"] == 1
        assert index["reused_count"] == 1

    def test_widened_shots_are_totalled(self):
        index = build_index(self._entries(), [], {}, {}, "b.json", "Charon", "v1")
        # s1b1 is a 2.2s beat carrying 3.0s of audio.
        assert index["shots_widened_count"] == 1
        assert index["shots_widened_secs"] > 0

    def test_the_index_never_claims_an_unwritten_s3_state(self):
        index = build_index(self._entries(), [], {}, {}, "b.json", "Charon", "v1")
        assert index["s3_ok"] is None
        assert index["s3_reason"] == "not yet written"


class TestWholeIndexRule:
    """Narrowing generation must never narrow the index.

    Phase 3 shipped a `--only` that truncated a 16-slot manifest to 1. Phase 4
    made the rule explicit and tested it. Phase 5 inherits both.
    """

    def test_an_only_run_carries_every_other_beat_forward(self, tmp_path, monkeypatch):
        beats_doc = {"beats": [SILENT_BEAT, DIALOGUE_BEAT], "generated_at": "now"}
        previous = {
            "clips": [
                {**build_beat_entry(SILENT_BEAT, "narration", "kept", "Charon", "r",
                                    1.9, "f", "k1"),
                 "source": "generated", "local_path": "gone.wav"},
                {**build_beat_entry(DIALOGUE_BEAT, "dialogue", "old", "Fenrir", "r",
                                    3.2, "f", "k2"),
                 "source": "generated", "local_path": "gone.wav"},
            ],
            "cast": CAST,
            "narrator_voice": "Charon",
            "music_cues": [],
        }

        written: dict = {}
        with (
            patch("animatic.core.audio_generator.load_previous_index", return_value=previous),
            patch("animatic.core.audio_generator._resolve_music", return_value=[]),
            patch("animatic.core.audio_generator.write_index",
                  side_effect=lambda idx: written.update(idx)),
            patch("animatic.core.audio_generator.synthesize_fitted",
                  return_value=(b"RIFF", 3.2, "new", "regenerated")),
            patch("animatic.core.audio_generator.write_clip",
                  return_value=("hash", tmp_path / "s2b5.wav", "s3://x", True, "ok")),
        ):
            index = generate_missing_audio(
                beats_doc, pdf_path="x.pdf", beats_source="b.json", only="s2b5"
            )

        assert [c["beat_id"] for c in index["clips"]] == ["s1b1", "s2b5"]
        kept = next(c for c in index["clips"] if c["beat_id"] == "s1b1")
        assert kept["text"] == "kept"
        assert kept["source"] == "reused"
        regenerated = next(c for c in index["clips"] if c["beat_id"] == "s2b5")
        assert regenerated["source"] == "generated"

    def test_a_reused_cast_keeps_a_character_on_the_same_voice(self, tmp_path):
        """ROADMAP criterion 2 is about consistency ACROSS runs, not within one."""
        beats_doc = {"beats": [DIALOGUE_BEAT], "generated_at": "now"}
        previous = {"clips": [], "cast": CAST, "narrator_voice": "Charon", "music_cues": []}

        with (
            patch("animatic.core.audio_generator.load_previous_index", return_value=previous),
            patch("animatic.core.audio_generator._resolve_music", return_value=[]),
            patch("animatic.core.audio_generator.write_index"),
            patch("animatic.core.audio_generator.cast_voices") as recast,
            patch("animatic.core.audio_generator.synthesize_fitted",
                  return_value=(b"RIFF", 3.2, "t", "r")),
            patch("animatic.core.audio_generator.write_clip",
                  return_value=("h", tmp_path / "s2b5.wav", "s3://x", True, "ok")),
        ):
            index = generate_missing_audio(beats_doc, pdf_path="x.pdf", beats_source="b.json")

        recast.assert_not_called()
        assert index["cast"]["BLACK FIGHTER"]["voice"] == "Fenrir"


class TestLiveIndexInvariants:
    """Asserted against the real index once a build has run."""

    def test_no_clip_outruns_its_shot(self, index):
        """ROADMAP criterion 5, stated over the real artifact."""
        over = [
            c for c in index["clips"]
            if c["source"] != "generation_failed" and c["audio_secs"] > c["shot_secs"]
        ]
        assert not over, [c["beat_id"] for c in over]

    def test_every_clip_carries_a_reason(self, index):
        for clip in index["clips"]:
            assert clip["shot_secs_reason"].strip()
            assert clip["voice_reason"].strip()
