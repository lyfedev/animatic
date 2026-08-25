"""Panel image generation — one `generate_content` call per beat, driving
the per-beat build loop `scripts/build_panels.py` runs.

Uses the identical call shape `asset_generator.generate_slot_art` already
proved live, with one addition: `image_config=ImageConfig(aspect_ratio=
"16:9")` for a consistent frame Phase 7 assembles from. Deliberately does
NOT pass `system_instruction` — RESEARCH Pitfall 1: `system_instruction`
combined with an image-output model raises `ClientError` on this backend.
Panels generate from text only (D-08 HELD) — no second `contents` part, and
`google-genai` stays the only AI SDK imported anywhere in this phase
(NFR-03).

This module builds out across Plan 04-01's tasks: Task 1 wired one beat
(s2b7) through resolution, prompt, generation and the index. Task 2 filled
out the prompt clauses. Task 3 (this pass) adds the memory and resilience a
49-call run needs:

- a beat's own cache key (`panel_cache_key`) is compared against the
  matching entry in `previous_index`; an unchanged key with the panel file
  still on disk is reused without a call
- a failing call gets one retry after a short delay before it is recorded
  `generation_failed`
- a beat outside `only`/`scene`'s selection is carried forward from
  `previous_index` unchanged rather than dropped — narrowing generation
  must never narrow the index (Phase 3's own `--only` regression, T-04's
  whole-index rule)

Generation stays strictly sequential (D-10): roughly ten seconds per image,
about nine minutes for a full 49-beat run, and this model's real
per-minute rate limits could not be verified (RESEARCH Pitfall 3), so no
concurrency is introduced here.
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
from animatic.core.panel_prompt import PROMPT_TEMPLATE_VERSION, build_panel_prompt, shot_size_for
from animatic.core.slot_resolver import Slot, _slugify

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any], str, float], None]

# A single transient network/5xx error costing one extra ~10s call is cheap
# against a 49-panel, ~9-minute budget (D-10). No retry framework — five
# lines of manual retry is simpler and consistent with this project's
# existing "no new dependency for a small mechanism" pattern.
_RETRY_DELAY_SECS = 2


class PanelGenerationError(Exception):
    """Raised when a generation response carries no inline image data."""


def generate_panel(beat: dict[str, Any], prompt: str) -> tuple[bytes, str]:
    """Generate one image for `beat` from `prompt`.

    Returns (image_bytes, mime_type) — mime type is read from the response
    rather than assumed (RESEARCH Pitfall 3: don't assume PNG).

    Raises:
        PanelGenerationError: no part of the response carried inline image
            data.
    """
    client = genai.Client(api_key=settings.google_api_key)

    logger.info("Generating panel for beat %s", beat.get("beat_id", "?"))

    response = client.models.generate_content(
        model=f"models/{settings.gemini_image_model}",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="16:9"),
        ),
    )

    parts = response.candidates[0].content.parts
    for part in parts:
        if part.inline_data is not None:
            return part.inline_data.data, part.inline_data.mime_type

    raise PanelGenerationError(
        f"No inline image data in generate_content response for beat "
        f"{beat.get('beat_id', '?')!r}"
    )


def resolve_beat_slots(beat: dict[str, Any], slots: list[Slot]) -> tuple[Slot, list[Slot]]:
    """Resolve one beat's location slot and its own character slot(s).

    The location is the one slot whose `source_scenes` contains
    `beat["scene"]`. Characters are looked up by their own slot_id
    (`slot_resolver._slugify` of the name) — not the shared `art_slot_id` —
    so the index records which specific character was in the panel even
    when several minor characters share one art file (D-05 of Phase 3).
    """
    location_matches = [
        s for s in slots
        if s.slot_type == "location" and beat["scene"] in s.source_scenes
    ]
    assert len(location_matches) == 1, (
        f"beat {beat['beat_id']} scene {beat['scene']} matched "
        f"{len(location_matches)} location slots"
    )
    location_slot = location_matches[0]

    character_by_id = {s.slot_id: s for s in slots if s.slot_type == "character"}
    character_slots = [
        character_by_id[_slugify(name)] for name in beat.get("characters", [])
    ]
    return location_slot, character_slots


def panel_cache_key(
    beat: dict[str, Any],
    shot_size: str,
    dependent_slots: list[dict[str, str]],
    prompt_template_version: str,
) -> str:
    """sha256 over the fields that determine the picture.

    Leaves `reason` and `duration_secs` out of the payload — neither
    changes what gets drawn. `dependent_slots` is
    `[{"slot_id": ..., "content_hash": ...}, ...]`, read fresh from the
    current asset manifest at build time rather than trusted from that
    manifest's own `stale_beat_ids` (RESEARCH Pattern 1 — Phase 4 keeps its
    own record of which slot hashes each panel was built from and diffs it
    against the current manifest on every run).
    """
    payload = {
        "beat_id": beat["beat_id"],
        "type": beat["type"],
        "content": beat["content"],
        "characters": sorted(beat.get("characters", [])),
        "scene": beat["scene"],
        "shot_size": shot_size,
        "slot_hashes": sorted(
            (s["slot_id"], s["content_hash"]) for s in dependent_slots
        ),
        "prompt_template_version": prompt_template_version,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _dependent_slot_records(
    location_slot: Slot,
    character_slots: list[Slot],
    manifest_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Read each dependent slot's CURRENT content_hash from the manifest.

    Fresh at build time — never the resolver's own `Slot.content_hash`
    (Phase 4 never populates it; that field belongs to Phase 3's own
    generation pass) and never the manifest's point-in-time
    `stale_beat_ids` (RESEARCH Pattern 1).
    """
    records = []
    for slot in [location_slot, *character_slots]:
        entry = manifest_by_id.get(slot.slot_id, {})
        records.append({
            "slot_id": slot.slot_id,
            "content_hash": entry.get("content_hash", ""),
        })
    return records


def _generate_with_retry(beat: dict[str, Any], prompt: str) -> tuple[bytes, str]:
    """Call `generate_panel`, retrying once after `_RETRY_DELAY_SECS` on
    failure. The second failure propagates to the caller, which records it.
    """
    try:
        return generate_panel(beat, prompt)
    except Exception as first_err:  # noqa: BLE001 — retried once, then re-raised
        logger.warning(
            "Panel generation failed for beat %s (attempt 1): %s — retrying in %ss",
            beat.get("beat_id", "?"), first_err, _RETRY_DELAY_SECS,
        )
        time.sleep(_RETRY_DELAY_SECS)
        return generate_panel(beat, prompt)


def _build_entry(
    beat: dict[str, Any],
    shot_size: str,
    shot_size_reason: str,
    facial_features: str,
    facial_features_reason: str,
    asset_slots_used: list[str],
    dependent: list[dict[str, str]],
    prompt: str,
    cache_key: str,
    *,
    source: str,
    source_reason: str,
    panel_uri: str = "",
    panel_s3_uri: str = "",
    content_hash: str = "",
) -> dict[str, Any]:
    return {
        "beat_id": beat["beat_id"],
        "scene": beat["scene"],
        "beat": beat["beat"],
        "type": beat["type"],
        "duration_secs": beat.get("duration_secs", 0.0),
        "shot_size": shot_size,
        "shot_size_reason": shot_size_reason,
        "facial_features": facial_features,
        "facial_features_reason": facial_features_reason,
        "asset_slots_used": asset_slots_used,
        "slot_hashes": dependent,
        "prompt": prompt,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "cache_key": cache_key,
        "panel_uri": panel_uri,
        "panel_s3_uri": panel_s3_uri,
        "content_hash": content_hash,
        "source": source,
        "source_reason": source_reason,
    }


def generate_missing_panels(
    beats_doc: dict[str, Any],
    slots: list[Slot],
    manifest: dict[str, Any],
    previous_index: dict[str, Any] | None = None,
    force: bool = False,
    only: set[str] | None = None,
    scene: int | None = None,
    on_progress: ProgressCallback | None = None,
    beats_source: str = "output/beats.json",
    manifest_source: str = "output/assets/manifest.json",
) -> dict[str, Any]:
    """Build one index entry per beat, in beat order, writing the index
    after each entry is resolved.

    `only`/`scene` narrow which beats are (re)generated this run. A beat
    outside that selection is carried forward from `previous_index`
    unchanged if it has an entry there — narrowing generation must never
    narrow the index (the whole-index rule). A selected beat whose
    `panel_cache_key` matches its entry in `previous_index`, with that
    entry's panel file still on disk, is reused without a call unless
    `force` is set. Otherwise the API is called, with one retry before a
    failure is recorded `generation_failed` and the loop continues to the
    next beat.

    Returns the final written index dict. `panel_manifest.write_index` is
    called after EACH beat's entry is resolved — never once at the end —
    so a run interrupted partway through leaves every entry built so far on
    disk and in S3.
    """
    from animatic.core.panel_manifest import build_index, write_index, write_panel

    beats = beats_doc.get("beats", [])
    manifest_by_id = {s["slot_id"]: s for s in manifest.get("slots", [])}
    previous_by_id: dict[str, dict[str, Any]] = {}
    if previous_index:
        previous_by_id = {e["beat_id"]: e for e in previous_index.get("panels", [])}

    entries: list[dict[str, Any]] = []

    def _flush() -> dict[str, Any]:
        idx = build_index(entries, beats_doc, manifest, beats_source, manifest_source, PROMPT_TEMPLATE_VERSION)
        write_index(idx)
        return idx

    index: dict[str, Any] = {}

    for beat in beats:
        beat_id = beat["beat_id"]
        is_selected = True
        if only is not None and beat_id not in only:
            is_selected = False
        if scene is not None and beat["scene"] != scene:
            is_selected = False

        if not is_selected:
            prev = previous_by_id.get(beat_id)
            if prev is not None:
                entries.append(prev)
            continue

        shot_size, shot_size_reason = shot_size_for(beat)
        location_slot, character_slots = resolve_beat_slots(beat, slots)
        dependent = _dependent_slot_records(location_slot, character_slots, manifest_by_id)
        prompt, facial_features, facial_features_reason = build_panel_prompt(beat, shot_size)
        cache_key = panel_cache_key(beat, shot_size, dependent, PROMPT_TEMPLATE_VERSION)
        asset_slots_used = [location_slot.slot_id] + [s.slot_id for s in character_slots]

        prev = previous_by_id.get(beat_id)
        if (
            not force
            and prev is not None
            and prev.get("cache_key") == cache_key
            and prev.get("panel_uri")
            and Path(prev["panel_uri"]).is_file()
        ):
            entry = _build_entry(
                beat, shot_size, shot_size_reason, facial_features,
                facial_features_reason, asset_slots_used, dependent, prompt,
                cache_key,
                source="reused",
                source_reason=(
                    f"reused existing panel at {prev['panel_uri']} — cache "
                    f"key unchanged since the previous index (pass --force "
                    f"to regenerate)"
                ),
                panel_uri=prev.get("panel_uri", ""),
                panel_s3_uri=prev.get("panel_s3_uri", ""),
                content_hash=prev.get("content_hash", ""),
            )
            entries.append(entry)
            index = _flush()
            if on_progress:
                on_progress(beat, "reused", 0.0)
            continue

        try:
            image_bytes, mime_type = _generate_with_retry(beat, prompt)
        except Exception as e:  # noqa: BLE001 — one bad beat must not abort the run
            reason = f"{type(e).__name__}: {e}"
            entry = _build_entry(
                beat, shot_size, shot_size_reason, facial_features,
                facial_features_reason, asset_slots_used, dependent, prompt,
                cache_key,
                source="generation_failed",
                source_reason=reason,
            )
            logger.warning("Panel generation failed for beat %s: %s", beat_id, reason)
            entries.append(entry)
            index = _flush()
            if on_progress:
                on_progress(beat, "failed", 0.0)
            continue

        content_hash, local_path, s3_uri, s3_ok, s3_reason = write_panel(
            beat_id, image_bytes, mime_type
        )
        entry = _build_entry(
            beat, shot_size, shot_size_reason, facial_features,
            facial_features_reason, asset_slots_used, dependent, prompt,
            cache_key,
            source="generated",
            source_reason=(
                f"generated via {settings.gemini_image_model}; "
                f"sha256={content_hash[:12]}; s3_ok={s3_ok} ({s3_reason})"
            ),
            panel_uri=str(local_path),
            panel_s3_uri=s3_uri if s3_ok else "",
            content_hash=content_hash,
        )
        entries.append(entry)
        index = _flush()
        if on_progress:
            on_progress(beat, "generated", 0.0)

    # Guarantees the final on-disk/S3 index always reflects the full
    # accumulated entry set even if the run's last beat was a pure
    # carry-forward (no active write triggered by it).
    index = _flush()

    return index
