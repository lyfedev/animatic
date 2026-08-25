"""Audio generation — one TTS call per beat, one Lyria call per music cue.

Follows the call shape `asset_generator` and `panel_generator` already proved
live on this backend: `generate_content` on the `GOOGLE_API_KEY` (MLDev)
client, no `system_instruction`, mime type read from the response rather than
assumed. `google-genai` stays the only AI SDK imported (NFR-03).

The loop is the same shape as `generate_missing_panels` — per-beat cache key,
one retry on a transient failure, entries written as each beat resolves, and a
beat outside a `--only` selection carried forward from the previous index
rather than dropped (Phase 3's `--only` regression; Phase 4's whole-index
rule).

What is new here is the **measured fit**. An image either exists or it does
not; a clip has a length, and ROADMAP criterion 5 is a statement about that
length. So every clip is measured after generation:

- silence is trimmed first, which reclaims a consistent ~0.6s
- a narration line still over its beat is rewritten shorter and generated once
  more — narration text is ours to write, so it yields
- a dialogue line is never shortened; the script's words are not ours to cut,
  so the *shot* widens instead and records why, exactly as Phase 2's dialogue
  floor did

Generation stays sequential, as in Phase 4 (D-10), and paced: this backend
caps the TTS model at 10 requests per minute AND 100 per day per project, both
found the hard way. Concurrency would buy nothing against either.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import wave
from pathlib import Path
from typing import Any, Callable

from google import genai
from google.genai import types

from animatic.config import settings
from animatic.core import narration as narration_mod
from animatic.core.audio_manifest import (
    LOCAL_AUDIO_DIR,
    build_index,
    load_previous_index,
    write_clip,
    write_index,
)
from animatic.core.audio_timing import (
    TTS_SAMPLE_RATE,
    fit_shot_secs,
    narration_budget_words,
    pcm_duration_secs,
    pcm_to_wav,
    trim_silence,
)
from animatic.core.music_cues import MusicCue, build_music_prompt, find_music_cues
from animatic.core.voice_casting import NARRATOR_VOICE, cast_voices, character_profiles

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any], str, float], None]

# v1 -> v2: narration planning recalibrated from 2.2 to 1.8 words/sec against
# the first full run's 31 measured clips, the overrun repair changed from a
# word-boundary truncation to a model rewrite (v1 produced 8 fragment lines),
# and on-screen-text directives are now stripped before the narrator sees them
# (v1 read a SUPERIMPOSE directive aloud as the word "Text").
AUDIO_TEMPLATE_VERSION = "v2"

_RETRY_DELAY_SECS = 2

# Per-minute cap, found on the first full run: 10 requests/minute per project,
# while the run was issuing them every ~4s. Beat 44 of 49 came back 429 with
# `retryDelay: 54s` — a quota, not a network blip, so the flat 2s retry that
# works for panels could never clear it.
#
# Pacing keeps the run under the cap so the error mostly does not happen; the
# 429-aware retry waits the interval the server names when it happens anyway.
# 6.5s (9.2 req/min) still tripped it — the limiter measures a rolling window,
# and a narration beat that overruns spends TWO calls inside one beat's
# interval. 7.5s is 8 req/min.
_TTS_MIN_INTERVAL_SECS = 7.5
_RETRY_DELAY_CAP_SECS = 120

# A per-minute quota error is worth more than one retry — the window it waits
# for is guaranteed to open shortly, unlike a network fault which may not clear
# at all. A per-DAY quota is a different animal entirely; see below.
_QUOTA_RETRIES = 2

# The v2 run found the limit that actually matters, and it is not the
# per-minute one: this backend also caps the TTS model at **100 requests per
# day per project**, and answered `retryDelay: 43424s` — twelve hours. No
# amount of pacing reaches that, and no retry should wait it out inside a run.
#
# Two consequences. A wait longer than this threshold is a daily cap, not a
# blip, so the run stops rather than marching the remaining beats into the same
# wall (the v2 run failed ten in a row before it ran out of beats). And
# `_RETRY_DELAY_CAP_SECS` stays well under it so no retry can ever sleep for
# half a day.
_DAILY_QUOTA_THRESHOLD_SECS = 900


class DailyQuotaExhausted(Exception):
    """Raised when the per-day request cap is hit — the run cannot continue."""


_last_tts_call_at: float = 0.0


def _pace_tts() -> None:
    """Hold the run under the model's per-minute request cap."""
    global _last_tts_call_at
    wait = _TTS_MIN_INTERVAL_SECS - (time.time() - _last_tts_call_at)
    if wait > 0:
        time.sleep(wait)
    _last_tts_call_at = time.time()


def _retry_after_secs(exc: Exception, cap: bool = True) -> float | None:
    """The delay a 429 asks for, if it asked for one.

    Read from the server's own `RetryInfo` rather than guessed. With
    `cap=False` the raw value is returned, which is how the caller tells a
    per-minute quota (tens of seconds) from a per-day one (tens of thousands);
    capping first would make the two indistinguishable.
    """
    text = str(exc)
    if "RESOURCE_EXHAUSTED" not in text and "429" not in text:
        return None
    match = re.search(r"'retryDelay':\s*'(\d+(?:\.\d+)?)s'", text)
    if not match:
        match = re.search(r"retry in (\d+(?:\.\d+)?)s", text)
    if not match:
        return float(_RETRY_DELAY_CAP_SECS)
    delay = float(match.group(1)) + 1.0
    return min(delay, float(_RETRY_DELAY_CAP_SECS)) if cap else delay


# `lyria-3-clip-preview` returned a 30.8s stereo MP3 for a one-paragraph
# prompt; `lyria-3-pro-preview` returned 175s. A cue in this cut is 5.9s and
# 11.3s long, so the clip model is both sufficient and the cheaper call.
#
# Read through functions rather than bound at import so a `--tts-model`
# override reaches code that has already imported this module.
def music_model() -> str:
    return f"models/{settings.gemini_music_model}"


def tts_model() -> str:
    return f"models/{settings.gemini_tts_model}"


class AudioGenerationError(Exception):
    """Raised when a generation response carries no inline audio data."""


def speech_prompt(text: str, direction: str) -> str:
    """The text handed to TTS, with its delivery direction in front.

    The direction is prose, not a tag: this backend reads "Say this as ..."
    as instruction and everything after the colon as the line to speak.
    """
    return f"{direction}: {text}"


def dialogue_direction(beat: dict[str, Any], character: str) -> str:
    """Delivery direction for a spoken line, drawn from the beat itself.

    Built from the beat's own content and location rather than from a table
    of characters, so a different script gets directions that fit it.
    """
    return (
        f"Say this as {character.title()}, in this moment — "
        f"{beat['content'].rstrip('.')} — at a natural, unhurried pace"
    )


NARRATION_DIRECTION = (
    "Read this as a film narrator describing the picture, level and "
    "unhurried, with no dramatisation"
)


def synthesize_speech(text: str, voice: str, direction: str) -> tuple[bytes, float]:
    """One TTS call. Returns (trimmed PCM, duration in seconds).

    Silence is trimmed here rather than by the caller because an untrimmed
    duration is not a fact anyone downstream wants: every consumer cares how
    long the *speech* is.
    """
    client = genai.Client(api_key=settings.google_api_key)

    _pace_tts()
    response = client.models.generate_content(
        model=tts_model(),
        contents=speech_prompt(text, direction),
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            pcm = trim_silence(part.inline_data.data)
            return pcm, pcm_duration_secs(pcm)

    raise AudioGenerationError(
        f"No inline audio data in TTS response for voice {voice!r}"
    )


def generate_music(cue: MusicCue) -> tuple[bytes, str]:
    """One Lyria call for a music cue. Returns (audio bytes, mime type)."""
    client = genai.Client(api_key=settings.google_api_key)

    logger.info("Generating music for cue %s", cue.cue_id)

    response = client.models.generate_content(
        model=music_model(),
        contents=build_music_prompt(cue),
        config=types.GenerateContentConfig(response_modalities=["AUDIO"]),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data, part.inline_data.mime_type

    raise AudioGenerationError(
        f"No inline audio data in Lyria response for cue {cue.cue_id!r}"
    )


def audio_cache_key(
    beat: dict[str, Any],
    kind: str,
    text: str,
    voice: str,
    template_version: str,
) -> str:
    """sha256 over the fields that determine the sound.

    `duration_secs` is deliberately in the payload, unlike the panel cache
    key: a beat whose duration changed needs its narration re-planned to the
    new budget, so the clip really is stale. Dialogue clips are unaffected in
    practice because their text and voice pin them anyway.
    """
    payload = {
        "beat_id": beat["beat_id"],
        "kind": kind,
        "text": text,
        "voice": voice,
        "duration_secs": beat["duration_secs"],
        "audio_template_version": template_version,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def resolve_beat_audio(
    beat: dict[str, Any],
    cast: dict[str, dict[str, str]],
    narration_text: dict[str, str],
    narrator_voice: str,
) -> tuple[str, str, str, str, str]:
    """What this beat says, who says it, and why.

    Returns (kind, text, voice, voice_reason, direction). `kind` is
    `dialogue` when the beat has a spoken line and `narration` otherwise —
    the two arms of ROADMAP criteria 2 and 3.
    """
    lines = beat.get("dialogue") or []
    if lines:
        character = lines[0]["character"]
        entry = cast.get(character, {})
        voice = entry.get("voice") or narrator_voice
        reason = entry.get("reason") or (
            f"{character} was not in the cast list; fell back to the narrator voice"
        )
        text = " ".join(ln["line"] for ln in lines)
        return "dialogue", text, voice, reason, dialogue_direction(beat, character)

    # Falls back to the beat's own action line with title-card directives
    # already stripped — never the raw content, or the narrator reads a
    # SUPERIMPOSE instruction aloud.
    text = narration_text.get(beat["beat_id"]) or narration_mod.action_line(beat)
    return (
        "narration",
        text,
        narrator_voice,
        "beat has no dialogue, so its action is narrated in the reserved "
        "narrator voice",
        NARRATION_DIRECTION,
    )


def synthesize_fitted(
    beat: dict[str, Any],
    kind: str,
    text: str,
    voice: str,
    direction: str,
) -> tuple[bytes, float, str, str]:
    """Generate a clip and make it fit, or record honestly that it did not.

    Returns (wav bytes, audio_secs, final text, fit_reason).

    Narration that overruns is rewritten to the budget the overrun proves is
    real — the measured words-per-second of the clip just generated, not the
    planning constant — and generated once more. Dialogue is never rewritten.
    """
    pcm, secs = _call_with_retry(text, voice, direction, beat["beat_id"])
    budget = beat["duration_secs"]

    if secs <= budget or kind != "narration":
        return pcm_to_wav(pcm), secs, text, "generated at first pass"

    measured_wps = len(text.split()) / secs if secs else narration_budget_words(1.0)
    target = max(2, int((budget - 0.15) * measured_wps))
    shorter = narration_mod.shorten(text, target)

    if shorter == text:
        return (
            pcm_to_wav(pcm),
            secs,
            text,
            f"overran its {budget:.2f}s beat at {secs:.2f}s and was already at "
            f"minimum length; shot widened instead",
        )

    logger.info(
        "%s narration overran (%.2fs > %.2fs); retrying at %d words",
        beat["beat_id"],
        secs,
        budget,
        target,
    )
    pcm2, secs2 = _call_with_retry(shorter, voice, direction, beat["beat_id"])
    return (
        pcm_to_wav(pcm2),
        secs2,
        shorter,
        f"first pass ran {secs:.2f}s against a {budget:.2f}s beat "
        f"({measured_wps:.2f} words/sec measured); rewritten to {target} words "
        f"and regenerated at {secs2:.2f}s",
    )


def _call_with_retry(
    text: str, voice: str, direction: str, beat_id: str
) -> tuple[bytes, float]:
    """One retry, waiting as long as the failure says it needs.

    A transient network error clears in a couple of seconds, as it does for
    panels. A quota error does not — it clears when the quota window rolls,
    and the server says when that is. Retrying a 429 after 2 seconds just
    spends a second call to fail the same way.
    """
    attempt = 0
    while True:
        try:
            return synthesize_speech(text, voice, direction)
        except Exception as exc:  # noqa: BLE001 — retried, then raised
            delay = _retry_after_secs(exc, cap=False)
            if delay is not None and delay >= _DAILY_QUOTA_THRESHOLD_SECS:
                raise DailyQuotaExhausted(
                    f"per-day request cap reached on {tts_model()}: the server "
                    f"asks for {delay / 3600:.1f}h. Stopping rather than "
                    f"failing every remaining beat against the same wall."
                ) from exc
            delay = None if delay is None else min(delay, _RETRY_DELAY_CAP_SECS)
            attempt += 1
            budget = _QUOTA_RETRIES if delay is not None else 1
            if attempt > budget:
                raise
            if delay is None:
                logger.warning("TTS failed for %s (%s); retrying once", beat_id, exc)
                delay = _RETRY_DELAY_SECS
            else:
                logger.warning(
                    "TTS rate-limited on %s (attempt %d of %d); waiting %.0fs as "
                    "the server asked",
                    beat_id,
                    attempt,
                    budget,
                    delay,
                )
            time.sleep(delay)


def build_beat_entry(
    beat: dict[str, Any],
    kind: str,
    text: str,
    voice: str,
    voice_reason: str,
    audio_secs: float,
    fit_reason: str,
    cache_key: str,
) -> dict[str, Any]:
    """One audio index entry — every field a later phase or a human needs."""
    shot_secs, shot_source, shot_reason = fit_shot_secs(beat["duration_secs"], audio_secs)
    return {
        "beat_id": beat["beat_id"],
        "scene": beat["scene"],
        "beat": beat["beat"],
        "kind": kind,
        "text": text,
        "voice": voice,
        "voice_reason": voice_reason,
        "beat_duration_secs": beat["duration_secs"],
        "audio_secs": round(audio_secs, 2),
        "shot_secs": shot_secs,
        "shot_secs_source": shot_source,
        "shot_secs_reason": shot_reason,
        "fit_reason": fit_reason,
        "sample_rate": TTS_SAMPLE_RATE,
        # Which model spoke this line. The daily cap is per model, so a long
        # run can legitimately finish on the fallback — and a corpus voiced by
        # two models is a consistency risk worth being able to SEE rather than
        # discover by ear. `index["tts_models"]` counts them.
        "tts_model": tts_model(),
        "cache_key": cache_key,
        "audio_template_version": AUDIO_TEMPLATE_VERSION,
    }


def generate_missing_audio(
    beats_doc: dict[str, Any],
    pdf_path: str,
    beats_source: str,
    only: str | None = None,
    scene: int | None = None,
    force: bool = False,
    skip_music: bool = False,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Build the audio index: one clip per beat, plus one clip per music cue.

    Narrowing with `only`/`scene` narrows GENERATION, never the index — every
    beat outside the selection is carried forward from the previous index
    unchanged. This is the rule Phase 3's `--only` broke (it truncated a
    16-slot manifest to 1) and Phase 4 made explicit.

    Returns the assembled index dict, already written to disk and S3.
    """
    beats = beats_doc["beats"]
    previous = load_previous_index()
    previous_by_id = {c["beat_id"]: c for c in previous.get("clips", [])}

    selected = _select(beats, only=only, scene=scene)
    selected_ids = {b["beat_id"] for b in selected}

    cast = _resolve_cast(beats, previous, force=force)
    narrator_voice = previous.get("narrator_voice") or NARRATOR_VOICE

    # A narration line is stale when the template that planned it is stale,
    # not only when the beat is new. Without this, changing the words-per-second
    # constant or the overrun repair silently regenerates 49 clips of the OLD
    # text — the cache key moves, the prose does not.
    template_changed = previous.get("audio_template_version") != AUDIO_TEMPLATE_VERSION
    needs_narration = [
        b for b in selected
        if not b.get("dialogue")
        and (force or template_changed or b["beat_id"] not in previous_by_id)
    ]
    narration_text = _resolve_narration(beats, needs_narration, previous_by_id)

    music = _resolve_music(
        pdf_path, beats, previous, force=force, skip_music=skip_music
    )

    entries: list[dict[str, Any]] = [
        dict(previous_by_id[b["beat_id"]])
        for b in beats
        if b["beat_id"] not in selected_ids and b["beat_id"] in previous_by_id
    ]
    for entry in entries:
        entry["source"] = "reused"
        entry["source_reason"] = "outside this run's selection; carried forward"

    started = time.time()
    halted: str | None = None
    for index_pos, beat in enumerate(selected, start=1):
        try:
            entry = _resolve_one(
                beat,
                cast=cast,
                narration_text=narration_text,
                narrator_voice=narrator_voice,
                previous=previous_by_id.get(beat["beat_id"]),
                force=force,
            )
        except DailyQuotaExhausted as exc:
            # Stop, and carry every remaining beat forward from the previous
            # index. Marching on would fail each of them identically and turn
            # a complete index into a mostly-failed one — which is exactly what
            # the v2 run did before this existed.
            halted = str(exc)
            logger.error("%s — halted at %s", halted, beat["beat_id"])
            for remaining in selected[index_pos - 1:]:
                prior = previous_by_id.get(remaining["beat_id"])
                if not prior:
                    continue
                # Route through the same recovery a per-beat failure uses, so
                # a beat whose previous entry is ITSELF a failure record still
                # gets its on-disk clip back. Carrying the record forward
                # verbatim would leave a hole in the cut.
                kind, text, voice, voice_reason, _ = resolve_beat_audio(
                    remaining, cast, narration_text, narrator_voice
                )
                key = audio_cache_key(
                    remaining, kind, text, voice, AUDIO_TEMPLATE_VERSION
                )
                entries.append(
                    _entry_after_failure(
                        remaining, kind, text, voice, voice_reason, key, prior, exc
                    )
                )
            break
        entries.append(entry)

        index = build_index(
            entries,
            music,
            cast,
            beats_doc,
            beats_source,
            narrator_voice,
            AUDIO_TEMPLATE_VERSION,
        )
        write_index(index)

        if progress:
            progress(beat, entry["source"], time.time() - started)
        logger.info(
            "%d/%d %s: %s (%s, %.2fs)",
            index_pos,
            len(selected),
            beat["beat_id"],
            entry["source"],
            entry["kind"],
            entry["audio_secs"],
        )

    # The per-beat writes above each wrote a partial index. Write once more so
    # the index that is returned (and reported) is the one on disk and in S3 —
    # otherwise the run's own summary reports `s3_reason: not yet written`
    # about an index that had in fact been written 49 times.
    final = build_index(
        entries, music, cast, beats_doc, beats_source, narrator_voice,
        AUDIO_TEMPLATE_VERSION,
    )
    final["halted_reason"] = halted
    write_index(final)
    return final


def _select(
    beats: list[dict[str, Any]], only: str | None, scene: int | None
) -> list[dict[str, Any]]:
    if only:
        return [b for b in beats if b["beat_id"] == only]
    if scene is not None:
        return [b for b in beats if b["scene"] == scene]
    return list(beats)


def _resolve_cast(
    beats: list[dict[str, Any]], previous: dict[str, Any], force: bool
) -> dict[str, dict[str, str]]:
    """Reuse the previous cast unless forced or a speaking part is uncast.

    Re-casting on every run would give a character a different voice between
    runs, which is precisely what ROADMAP criterion 2 forbids.
    """
    previous_cast = previous.get("cast") or {}
    speakers = {p["character"] for p in character_profiles(beats)}
    if not force and speakers and speakers <= set(previous_cast):
        logger.info("reusing cast for %d speaking part(s)", len(previous_cast))
        return previous_cast
    return cast_voices(beats)


def _resolve_narration(
    beats: list[dict[str, Any]],
    needs: list[dict[str, Any]],
    previous_by_id: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """Narration text for the beats that need new lines, reused for the rest.

    Written in one call across the whole run (see `narration.py`) but only
    when at least one beat actually needs it — a re-run that reuses every clip
    should spend nothing.
    """
    stale = {b["beat_id"] for b in needs}
    text = {
        beat_id: entry["text"]
        for beat_id, entry in previous_by_id.items()
        # A beat being re-planned must not keep its old line as a seed: if the
        # new call omits it, falling back to the text the re-plan exists to
        # replace is worse than falling back to the action line.
        if entry.get("kind") == "narration" and beat_id not in stale
    }
    if needs:
        text.update(narration_mod.write_narration(beats))
    return text


def _resolve_music(
    pdf_path: str,
    beats: list[dict[str, Any]],
    previous: dict[str, Any],
    force: bool,
    skip_music: bool,
) -> list[dict[str, Any]]:
    """One clip per music cue the script specifies (ROADMAP criterion 4)."""
    cues = find_music_cues(pdf_path, beats)
    if skip_music:
        return [
            {
                "cue_id": c.cue_id, "scene": c.scene, "beat_ids": c.beat_ids,
                "total_secs": c.total_secs, "reason": c.reason,
                "source": "skipped", "source_reason": "--skip-music",
            }
            for c in cues
        ]

    previous_music = {m["cue_id"]: m for m in previous.get("music_cues", [])}
    out: list[dict[str, Any]] = []

    for cue in cues:
        prior = previous_music.get(cue.cue_id)
        prompt = build_music_prompt(cue)
        if (
            not force
            and prior
            and prior.get("prompt") == prompt
            and prior.get("local_path")
            and Path(prior["local_path"]).exists()
        ):
            out.append({**prior, "source": "reused",
                        "source_reason": "prompt unchanged since the previous run"})
            continue

        record: dict[str, Any] = {
            "cue_id": cue.cue_id,
            "scene": cue.scene,
            "beat_ids": cue.beat_ids,
            "total_secs": cue.total_secs,
            "reason": cue.reason,
            "prompt": prompt,
        }
        try:
            audio_bytes, mime = generate_music(cue)
        except Exception as exc:  # noqa: BLE001 — one cue failing is not the run
            logger.error("music generation failed for %s: %s", cue.cue_id, exc)
            out.append({**record, "source": "generation_failed",
                        "source_reason": f"{type(exc).__name__}: {exc}"})
            continue

        content_hash, local_path, s3_uri, s3_ok, s3_reason = write_clip(
            cue.cue_id, audio_bytes, mime, prefix="music_"
        )
        out.append({
            **record,
            "mime_type": mime,
            "content_hash": content_hash,
            "local_path": str(local_path),
            "s3_uri": s3_uri,
            "s3_ok": s3_ok,
            "s3_reason": s3_reason,
            "source": "generated",
            "source_reason": "original instrumental generated from the script's "
                             "own staging of the cue; no named work in the prompt",
        })

    return out


def _resolve_one(
    beat: dict[str, Any],
    cast: dict[str, dict[str, str]],
    narration_text: dict[str, str],
    narrator_voice: str,
    previous: dict[str, Any] | None,
    force: bool,
) -> dict[str, Any]:
    """Generate, reuse or fail one beat's clip."""
    kind, text, voice, voice_reason, direction = resolve_beat_audio(
        beat, cast, narration_text, narrator_voice
    )
    key = audio_cache_key(beat, kind, text, voice, AUDIO_TEMPLATE_VERSION)

    # A stale entry is playable but behind, and behind means regenerate as soon
    # as it is possible to. Without this the recovery path defeats itself: a
    # clip rescued from disk carries the cache key of the text it FAILED to
    # generate, so the next run reads a hit and never fixes it.
    if (
        not force
        and previous
        and not previous.get("stale")
        and previous.get("cache_key") == key
        and previous.get("local_path")
        and Path(previous["local_path"]).exists()
    ):
        return {
            **previous,
            "source": "reused",
            "source_reason": "cache key unchanged and the clip is still on disk",
        }

    try:
        wav, secs, final_text, fit_reason = synthesize_fitted(
            beat, kind, text, voice, direction
        )
    except DailyQuotaExhausted:
        raise
    except Exception as exc:  # noqa: BLE001 — one beat failing is not the run
        logger.error("audio generation failed for %s: %s", beat["beat_id"], exc)
        return _entry_after_failure(
            beat, kind, text, voice, voice_reason, key, previous, exc
        )

    # A rewritten narration line changes the cache key it should be stored
    # under, or the next run regenerates it every time.
    final_key = audio_cache_key(beat, kind, final_text, voice, AUDIO_TEMPLATE_VERSION)
    content_hash, local_path, s3_uri, s3_ok, s3_reason = write_clip(
        beat["beat_id"], wav, "audio/wav"
    )

    entry = build_beat_entry(
        beat, kind, final_text, voice, voice_reason, secs, fit_reason, final_key
    )
    entry.update({
        "mime_type": "audio/wav",
        "content_hash": content_hash,
        "local_path": str(local_path),
        "s3_uri": s3_uri,
        "s3_ok": s3_ok,
        "s3_reason": s3_reason,
        "source": "generated",
        "source_reason": fit_reason,
    })
    return entry


def _entry_after_failure(
    beat: dict[str, Any],
    kind: str,
    text: str,
    voice: str,
    voice_reason: str,
    key: str,
    previous: dict[str, Any] | None,
    exc: Exception,
) -> dict[str, Any]:
    """Record a failure without throwing away a clip that already works.

    The v2 run turned a complete 49-clip index into 39 good entries and 10
    failures, even though all ten beats still had a perfectly playable v1 clip
    sitting on disk. A regeneration that cannot complete is a reason to keep
    what you have, not to discard it — the same judgement Phase 4 reached when
    a paid call went unavailable mid-run.

    So a beat whose regeneration failed keeps its previous entry, and the entry
    says exactly what it is: an older template's clip, retained, with the
    failure that stopped it being replaced. `stale` marks it for the next run;
    nothing downstream has to guess.
    """
    failure = f"{type(exc).__name__}: {exc}"

    # A previous entry that is ITSELF a failure record has no clip to keep —
    # but the beat may still have a playable file from an earlier run, because
    # clip paths are conventional (`output/audio/<beat_id>.wav`) and a failed
    # generation never deletes what is there. Recovering it is the difference
    # between a cut that is behind and a cut with holes in it. Provenance is
    # unknown in that case and the entry says so.
    if previous and not previous.get("local_path"):
        previous = _previous_from_disk(beat, previous) or previous

    if previous and previous.get("local_path") and Path(previous["local_path"]).exists():
        logger.warning(
            "%s kept its %s clip: regeneration failed (%s)",
            beat["beat_id"],
            previous.get("audio_template_version", "previous"),
            type(exc).__name__,
        )
        # The audio matches the index's `text` only if it was generated FOR
        # that text. A clip whose provenance is unknown, or whose entry was
        # itself a failure record (its text was planned, never spoken), fails
        # that test — and the flag has to key off provenance rather than off
        # which recovery path happened to run, or a second pass through here
        # silently drops it.
        text_matches = not (
            previous.get("audio_template_version") == "unknown"
            or previous.get("source") == "generation_failed"
            or previous.get("text_matches_audio") is False
        )
        return {
            **previous,
            "text_matches_audio": text_matches,
            "source": "reused_after_failure",
            "source_reason": (
                f"regeneration to {AUDIO_TEMPLATE_VERSION} failed, so the "
                f"existing {previous.get('audio_template_version', 'previous')} "
                f"clip was kept rather than discarded — {failure[:200]}"
            ),
            "stale": True,
            "stale_reason": (
                f"generated under {previous.get('audio_template_version', 'an '
                'earlier template')}; re-run to bring it to "
                f"{AUDIO_TEMPLATE_VERSION}"
            ),
        }

    entry = build_beat_entry(
        beat, kind, text, voice, voice_reason, 0.0, failure, key
    )
    entry["source"] = "generation_failed"
    entry["source_reason"] = failure
    return entry


def _previous_from_disk(
    beat: dict[str, Any], previous: dict[str, Any]
) -> dict[str, Any] | None:
    """Recover a playable clip for a beat whose index entry has none.

    Clip paths are conventional, and a failed generation never deletes what is
    already there — so a beat recorded as `generation_failed` on one run can
    still have a real clip on disk from an earlier one. Its duration is
    measured from the file rather than taken from the stale entry, so the shot
    is fitted to the audio that actually exists.

    Returns None when nothing is on disk. Provenance is unknowable this way,
    which the caller records.
    """
    path = LOCAL_AUDIO_DIR / f"{Path(beat['beat_id']).name}.wav"
    if not path.exists():
        return None

    try:
        with wave.open(str(path), "rb") as w:
            secs = w.getnframes() / w.getframerate()
    except (wave.Error, OSError) as exc:
        logger.warning("clip at %s is unreadable (%s)", path, exc)
        return None

    shot_secs, shot_source, shot_reason = fit_shot_secs(beat["duration_secs"], secs)
    return {
        **previous,
        "audio_secs": round(secs, 2),
        "shot_secs": shot_secs,
        "shot_secs_source": shot_source,
        "shot_secs_reason": shot_reason,
        "mime_type": "audio/wav",
        "local_path": str(path),
        "content_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
        "audio_template_version": "unknown",
        # The entry's `text` is what this run WANTED spoken; the file predates
        # it and says something else. Anything that shows the text alongside
        # the audio — subtitles in Phase 7, the UI in Phase 9 — has to know
        # they disagree, so the disagreement is a field rather than a footnote.
        "text_matches_audio": False,
    }
