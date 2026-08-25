"""Tests for the measured-timing arithmetic Phase 5 depends on."""

from __future__ import annotations

import array
import io
import wave

import pytest

from animatic.core.audio_timing import (
    SAFE_WORDS_PER_SEC,
    TAIL_PAD_SECS,
    TTS_SAMPLE_RATE,
    fit_shot_secs,
    narration_budget_words,
    pcm_duration_secs,
    pcm_to_wav,
    trim_silence,
)


def _pcm(*segments: tuple[float, int]) -> bytes:
    """Build PCM from (seconds, amplitude) segments."""
    samples = array.array("h")
    for secs, amp in segments:
        samples.extend([amp] * int(secs * TTS_SAMPLE_RATE))
    return samples.tobytes()


class TestNarrationBudget:
    def test_budget_scales_with_the_beat(self):
        assert narration_budget_words(10.0) > narration_budget_words(3.0)

    def test_budget_reserves_a_tail(self):
        # A 10s beat must not be budgeted the full 10s of speech.
        assert narration_budget_words(10.0) < int(10.0 * SAFE_WORDS_PER_SEC)

    def test_shortest_beats_still_get_a_phrase(self):
        # 2.2s is the shortest beat in the real cut; 0.1s is pathological.
        assert narration_budget_words(2.2) >= 2
        assert narration_budget_words(0.1) == 2

    def test_budget_is_speakable_at_the_measured_rate(self):
        # The whole point: the budget must be deliverable inside the beat at
        # the slowest rate actually measured from the model.
        for secs in (2.2, 3.5, 5.9, 8.8, 12.9):
            words = narration_budget_words(secs)
            assert words / SAFE_WORDS_PER_SEC + TAIL_PAD_SECS <= secs + 0.5


class TestTrimSilence:
    def test_leading_and_trailing_silence_are_dropped(self):
        pcm = _pcm((0.3, 0), (1.0, 8000), (0.5, 0))
        trimmed = trim_silence(pcm)
        assert 0.9 < pcm_duration_secs(trimmed) < 1.1
        assert pcm_duration_secs(pcm) > 1.7

    def test_interior_pauses_survive(self):
        # A pause between two words is part of the delivery, not padding.
        pcm = _pcm((0.2, 0), (0.4, 8000), (0.5, 0), (0.4, 8000), (0.2, 0))
        trimmed = trim_silence(pcm)
        assert 1.2 < pcm_duration_secs(trimmed) < 1.4

    def test_an_all_silent_clip_reports_its_real_length(self):
        # Returning empty would tell the caller a failed clip is zero seconds.
        pcm = _pcm((0.8, 0))
        assert trim_silence(pcm) == pcm

    def test_empty_input_does_not_raise(self):
        assert trim_silence(b"") == b""

    def test_room_tone_is_not_mistaken_for_speech(self):
        pcm = _pcm((0.3, 50), (1.0, 9000), (0.3, 50))
        assert pcm_duration_secs(trim_silence(pcm)) < 1.2


class TestPcmToWav:
    def test_wav_is_readable_and_preserves_the_samples(self):
        pcm = _pcm((0.5, 6000))
        wav = pcm_to_wav(pcm)
        with wave.open(io.BytesIO(wav), "rb") as w:
            assert w.getframerate() == TTS_SAMPLE_RATE
            assert w.getnchannels() == 1
            assert w.getsampwidth() == 2
            assert w.readframes(w.getnframes()) == pcm


class TestFitShot:
    def test_audio_inside_the_beat_keeps_the_page_budget(self):
        shot, source, reason = fit_shot_secs(5.4, 3.22)
        assert shot == 5.4
        assert source == "page_budget"
        assert "3.22" in reason and "5.40" in reason

    def test_audio_over_the_beat_widens_the_shot(self):
        shot, source, reason = fit_shot_secs(2.2, 3.0)
        assert source == "audio_floor"
        assert shot == pytest.approx(3.0 + TAIL_PAD_SECS)
        assert "widened" in reason

    def test_the_shot_always_covers_its_audio(self):
        # This is ROADMAP criterion 5 stated as an invariant.
        for beat, audio in [(5.4, 3.2), (2.2, 3.0), (8.8, 8.8), (1.0, 12.0)]:
            shot, _, _ = fit_shot_secs(beat, audio)
            assert shot >= audio

    def test_audio_exactly_filling_the_beat_still_gets_a_tail(self):
        shot, source, _ = fit_shot_secs(3.0, 3.0)
        assert source == "audio_floor"
        assert shot > 3.0
