"""Motion generation — one Veo call per selected beat, seeded from its panel.

Unlike every other generator in this project, Veo is a **long-running
operation**: `generate_videos` returns immediately with an operation handle and
the clip arrives about a minute later. So this module polls rather than blocks
on a response, and a run of four beats takes roughly four minutes.

Seeded from the beat's own panel (`source=GenerateVideosSource(prompt, image)`)
rather than from text alone — see `motion_prompt` for why, and for the two
defects the first live clip exposed.

`google-genai` stays the only AI SDK imported (NFR-03).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable

from google import genai
from google.genai import types

from animatic.config import settings
from animatic.core.motion_prompt import MOTION_PROMPT_VERSION, build_motion_prompt
from animatic.core.motion_selector import MotionChoice
from animatic.core.shot_sources import PANEL_DIR

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, float], None]

MOTION_DIR = Path("output/motion")

_POLL_SECS = 10
_POLL_TIMEOUT_SECS = 600

# The same daily-cap regime the TTS models are under, so the same escape hatch
# applies: `--veo-model` swaps to a model with its own quota.
_DAILY_QUOTA_THRESHOLD_SECS = 900


class MotionGenerationError(Exception):
    """Raised when a Veo operation fails or returns no video."""


class EmptyVeoResponse(MotionGenerationError):
    """A completed operation carrying no video and no filter reason.

    Distinguished from a refusal because it behaves differently: two of four
    beats hit this on the first live run, and re-submitting the identical
    prompt returned a video. A refusal sets `rai_media_filtered_count` and
    will refuse again, so retrying that would just spend a second minute.
    """


class MotionQuotaExhausted(Exception):
    """Raised when the per-day request cap is hit — the run cannot continue."""


def veo_model() -> str:
    return f"models/{settings.gemini_veo_model}"


def motion_cache_key(beat: dict[str, Any], prompt: str, panel_hash: str) -> str:
    """sha256 over what determines the clip.

    Includes the PANEL's content hash: a regenerated panel means a different
    seed image, so the motion built from the old one is stale even though the
    beat text never changed. Same reasoning as the panel cache keying on its
    slot hashes.
    """
    payload = {
        "beat_id": beat["beat_id"],
        "prompt": prompt,
        "panel_content_hash": panel_hash,
        "motion_prompt_version": MOTION_PROMPT_VERSION,
        "veo_model": veo_model(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def panel_for(beat_id: str, panel_dir: Path | None = None) -> Path:
    """The panel this beat's motion is seeded from."""
    panel_dir = PANEL_DIR if panel_dir is None else panel_dir
    for suffix in (".jpg", ".jpeg", ".png"):
        candidate = panel_dir / f"{Path(beat_id).name}{suffix}"
        if candidate.exists():
            return candidate
    raise MotionGenerationError(
        f"{beat_id} has no panel in {panel_dir} to animate — run "
        f"scripts/build_panels.py first"
    )


def generate_motion(beat: dict[str, Any], panel: Path) -> bytes:
    """One Veo call, polled to completion. Returns the MP4 bytes."""
    client = genai.Client(api_key=settings.google_api_key)
    prompt = build_motion_prompt(beat)

    logger.info("Generating motion for beat %s from %s", beat["beat_id"], panel)

    try:
        operation = client.models.generate_videos(
            model=veo_model(),
            source=types.GenerateVideosSource(
                prompt=prompt,
                image=types.Image(
                    image_bytes=panel.read_bytes(),
                    mime_type=_mime_for(panel),
                ),
            ),
            config=types.GenerateVideosConfig(
                number_of_videos=1,
                aspect_ratio="16:9",
            ),
        )
    except Exception as exc:  # noqa: BLE001 — classified, then re-raised
        if _is_daily_quota(exc):
            raise MotionQuotaExhausted(
                f"per-day request cap reached on {veo_model()}"
            ) from exc
        raise

    started = time.time()
    while not operation.done:
        if time.time() - started > _POLL_TIMEOUT_SECS:
            raise MotionGenerationError(
                f"{beat['beat_id']}: Veo operation {operation.name} did not "
                f"finish within {_POLL_TIMEOUT_SECS}s"
            )
        time.sleep(_POLL_SECS)
        operation = client.operations.get(operation)

    if operation.error:
        raise MotionGenerationError(f"{beat['beat_id']}: {operation.error}")

    response = operation.response
    videos = getattr(response, "generated_videos", None) or []
    if not videos:
        # Two very different causes look identical here, so say which.
        # `rai_media_filtered_*` is set when the model refused the content;
        # an empty response with those fields unset is transient, and a
        # re-submission of the same prompt has returned a video.
        filtered = getattr(response, "rai_media_filtered_count", None)
        reasons = getattr(response, "rai_media_filtered_reasons", None)
        if filtered:
            raise MotionGenerationError(
                f"{beat['beat_id']}: Veo filtered {filtered} video(s) — {reasons}"
            )
        raise EmptyVeoResponse(
            f"{beat['beat_id']}: Veo reported done with no video and no filter "
            f"reason — transient"
        )

    video = videos[0].video
    data = video.video_bytes
    if data is None:
        # Larger results come back as a file handle rather than inline bytes.
        # `download` returns the bytes; older versions only populated the
        # object, so take whichever is not None rather than trusting one.
        downloaded = client.files.download(file=video)
        data = downloaded if isinstance(downloaded, (bytes, bytearray)) else video.video_bytes
    if not data:
        raise MotionGenerationError(
            f"{beat['beat_id']}: Veo response carried neither inline bytes nor "
            f"a downloadable file (uri={getattr(video, 'uri', None)})"
        )
    return bytes(data)


def write_motion(beat_id: str, data: bytes, motion_dir: Path | None = None) -> tuple[Path, str]:
    """Write a clip to `output/motion/<beat_id>.mp4`. Returns (path, sha256).

    The filename is what makes the shot-source seam work — the assembler finds
    motion by convention, with no index lookup. Asserted against the beat-id
    shape before it is used to build a path, as every other writer does.
    """
    from animatic.core.audio_manifest import _BEAT_ID_RE

    assert _BEAT_ID_RE.match(beat_id), f"beat_id {beat_id!r} does not match ^s\\d+b\\d+$"
    motion_dir = MOTION_DIR if motion_dir is None else motion_dir
    motion_dir.mkdir(parents=True, exist_ok=True)

    path = motion_dir / f"{Path(beat_id).name}.mp4"
    path.write_bytes(data)
    return path, hashlib.sha256(data).hexdigest()


def resolve_one(
    beat: dict[str, Any],
    choice: MotionChoice,
    previous: dict[str, Any] | None,
    force: bool,
    motion_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate, reuse, skip or fail one beat's motion. Always returns an entry."""
    entry: dict[str, Any] = {
        "beat_id": choice.beat_id,
        "scene": choice.scene,
        "beat": choice.beat,
        "type": beat.get("type", "unknown"),
        "duration_secs": beat.get("duration_secs"),
        "motion": choice.motion,
        "motion_reason": choice.reason,
        "selection_rank": choice.rank,
        "motion_prompt_version": MOTION_PROMPT_VERSION,
    }

    if not choice.motion:
        # ROADMAP criterion 4: a beat without motion falls back to its still,
        # which the assembler already does by resolving the panel. Recorded
        # here so the fallback is a stated outcome, not an absence.
        entry["source"] = "still"
        entry["source_reason"] = (
            f"no motion generated; the cut uses this beat's panel — {choice.reason}"
        )
        return entry

    try:
        panel = panel_for(choice.beat_id)
    except MotionGenerationError as exc:
        entry["source"] = "generation_failed"
        entry["source_reason"] = str(exc)
        return entry

    prompt = build_motion_prompt(beat)
    panel_hash = hashlib.sha256(panel.read_bytes()).hexdigest()
    key = motion_cache_key(beat, prompt, panel_hash)
    entry["prompt"] = prompt
    entry["panel_source"] = str(panel)
    entry["panel_content_hash"] = panel_hash
    entry["cache_key"] = key
    entry["veo_model"] = veo_model()

    if (
        not force
        and previous
        and previous.get("cache_key") == key
        and previous.get("local_path")
        and Path(previous["local_path"]).exists()
    ):
        return {
            **previous,
            **entry,
            "source": "reused",
            "source_reason": "cache key unchanged and the clip is still on disk",
        }

    try:
        data = _generate_with_retry(beat, panel)
    except MotionQuotaExhausted:
        raise
    except Exception as exc:  # noqa: BLE001 — one beat failing is not the run
        logger.error("motion generation failed for %s: %s", choice.beat_id, exc)
        if previous and previous.get("local_path") and Path(previous["local_path"]).exists():
            return {
                **previous,
                **entry,
                "source": "reused_after_failure",
                "source_reason": (
                    f"regeneration failed, existing clip kept — "
                    f"{type(exc).__name__}: {str(exc)[:200]}"
                ),
                "stale": True,
            }
        entry["source"] = "generation_failed"
        entry["source_reason"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        return entry

    path, content_hash = write_motion(choice.beat_id, data, motion_dir)
    entry.update({
        "local_path": str(path),
        "content_hash": content_hash,
        "bytes": len(data),
        "source": "generated",
        "source_reason": (
            f"animated from {panel} at {MOTION_PROMPT_VERSION}"
        ),
    })
    return entry


def _mime_for(panel: Path) -> str:
    return "image/png" if panel.suffix.lower() == ".png" else "image/jpeg"


def _is_daily_quota(exc: Exception) -> bool:
    text = str(exc)
    if "RESOURCE_EXHAUSTED" not in text and "429" not in text:
        return False
    return "per_day" in text or "PerDay" in text


def _generate_with_retry(beat: dict[str, Any], panel: Path) -> bytes:
    """Retry an empty response once; never retry a refusal or a quota error.

    An `EmptyVeoResponse` is transient — the first live run lost s2b15 and
    s8b6 to it, and both returned a video on re-submission of the identical
    prompt. A refusal (`rai_media_filtered_count` set) is a decision about the
    content and will be made again, so retrying it spends a minute to learn
    nothing.
    """
    try:
        return generate_motion(beat, panel)
    except EmptyVeoResponse as exc:
        logger.warning("%s — retrying once", exc)
        return generate_motion(beat, panel)
