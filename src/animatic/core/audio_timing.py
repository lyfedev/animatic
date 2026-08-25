"""Measured facts about synthetic speech, and the arithmetic that depends on them.

Phase 2 sized every dialogue beat with an *assumed* 2.5 words/sec. This module
replaces the assumption with measurement. Four clips generated live on
`gemini-3.1-flash-tts-preview` (2026-08-25):

| clip                       | words | raw    | lead  | speech | trail |
|----------------------------|-------|--------|-------|--------|-------|
| dialogue, plain            |     8 |  2.84s | 0.27s |  2.24s | 0.33s |
| dialogue, with direction   |     8 |  3.16s | 0.25s |  2.63s | 0.28s |
| narration, long prose      |    13 |  6.04s | 0.29s |  5.40s | 0.35s |
| narration, short phrase    |     6 |  2.64s | 0.27s |  1.90s | 0.47s |

Two findings drive the whole phase:

1. **Every clip carries ~0.25s of lead-in and ~0.3-0.5s of trail-out silence**,
   independent of length. On a 2.2s beat that padding is a third of the shot,
   so trimming it is not a nicety — it is what makes the short beats fit at all.

2. **Trimmed speech runs 2.4-3.6 words/sec**, and the rate falls as the line
   gets longer (more internal punctuation, more pauses). Planning against the
   fast end would overrun; `SAFE_WORDS_PER_SEC` takes the slow end so a
   generated narration line is sized to fit before a single byte is spent.

The rates are only used to *plan* text length. Nothing downstream trusts them:
every clip is measured after generation and the shot is fitted to what the
audio actually is.
"""

from __future__ import annotations

import array
import io
import wave

# Gemini TTS returns raw 16-bit signed mono PCM at 24kHz (mime `audio/l16;
# rate=24000; channels=1`). Read from the response in `audio_generator`
# rather than assumed there; these are the values to write a WAV header with.
TTS_SAMPLE_RATE = 24000
TTS_SAMPLE_WIDTH = 2
TTS_CHANNELS = 1

# Recalibrated against all 31 narration clips of the first full run, which is
# a far better sample than the four smoke-test clips above:
#
#   min 1.56 · p10 1.82 · median 2.16 · p90 2.50 · max 2.92
#
# The first pass planned at 2.2 — the median — and 11 of 31 beats overran,
# because planning at the median means roughly half of everything is too long
# by construction. Planning near p10 puts most beats inside their budget on
# the first call and leaves the measured-fit path to handle the tail, which is
# what it is for.
SAFE_WORDS_PER_SEC = 1.8

# A shot needs a breath at the end or the cut lands on the last consonant.
TAIL_PAD_SECS = 0.15

# 16-bit full scale is 32768. Measured room tone in these clips sits under
# 100; speech onset jumps well past 400.
_SILENCE_THRESHOLD = 400
_WINDOW_SAMPLES = 240  # 10ms at 24kHz


def pcm_duration_secs(pcm: bytes) -> float:
    """Duration of raw TTS PCM, in seconds."""
    return len(pcm) / (TTS_SAMPLE_RATE * TTS_SAMPLE_WIDTH * TTS_CHANNELS)


def narration_budget_words(duration_secs: float) -> int:
    """How many words of narration fit inside a beat of `duration_secs`.

    Reserves `TAIL_PAD_SECS` so the line does not end flush against the cut,
    and never returns less than 2 — below that a narration line stops being a
    sentence, and a beat that short is better served by a fragment that
    slightly overruns and gets caught by the measured fit than by one word.
    """
    speakable = max(0.0, duration_secs - TAIL_PAD_SECS)
    return max(2, int(speakable * SAFE_WORDS_PER_SEC))


def trim_silence(pcm: bytes) -> bytes:
    """Drop leading and trailing silence from raw TTS PCM.

    Returns the original bytes unchanged if the clip is silent throughout —
    a caller measuring a silent clip should see the real length, not zero.
    """
    samples = array.array("h")
    samples.frombytes(pcm)
    n = len(samples)
    if n == 0:
        return pcm

    loud_windows = [
        i
        for i in range(0, n, _WINDOW_SAMPLES)
        if max(
            (abs(s) for s in samples[i : i + _WINDOW_SAMPLES]),
            default=0,
        )
        > _SILENCE_THRESHOLD
    ]
    if not loud_windows:
        return pcm

    start = loud_windows[0]
    end = min(n, loud_windows[-1] + _WINDOW_SAMPLES)
    return samples[start:end].tobytes()


def pcm_to_wav(pcm: bytes) -> bytes:
    """Wrap raw TTS PCM in a WAV container.

    The API hands back headerless PCM; every consumer downstream (ffmpeg in
    Phase 7, a browser in Phase 9, a human double-clicking the file) wants a
    container.
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(TTS_CHANNELS)
        w.setsampwidth(TTS_SAMPLE_WIDTH)
        w.setframerate(TTS_SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def fit_shot_secs(beat_duration_secs: float, audio_secs: float) -> tuple[float, str, str]:
    """Reconcile a beat's planned duration with the audio actually produced.

    ROADMAP criterion 5 — no beat's audio is longer than the beat — is made
    true here, and made true the same way Phase 2 made its dialogue floor
    true: by widening the shot and recording why, never by clipping speech.
    Cutting a line off mid-word to honour a planned duration would trade a
    visible defect for an audible one.

    Returns:
        (shot_secs, source, reason) — `source` is `page_budget` when the
        beat's own duration already covers its audio, `audio_floor` when the
        audio forced the shot wider.
    """
    needed = audio_secs + TAIL_PAD_SECS
    if needed <= beat_duration_secs:
        return (
            round(beat_duration_secs, 2),
            "page_budget",
            f"audio runs {audio_secs:.2f}s, inside the beat's {beat_duration_secs:.2f}s",
        )
    return (
        round(needed, 2),
        "audio_floor",
        f"shot widened {beat_duration_secs:.2f}s -> {needed:.2f}s: "
        f"{audio_secs:.2f}s of audio plus a {TAIL_PAD_SECS:.2f}s tail cannot "
        f"be delivered in less",
    )
