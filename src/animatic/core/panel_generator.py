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

This module builds out across Plan 04-01's tasks: Task 1 wires one beat
(s2b7) through resolution, prompt, generation and the index — every
selected beat always calls the API, with no cache-hit reuse, no retry and
no carry-forward of beats this run did not select. Task 3 adds all three:
a beat whose cache key is unchanged from the previous index is reused
without a call; a failing call gets one retry before it is recorded
failed; and a beat outside `only`/`scene`'s selection is carried forward
from the previous index unchanged rather than dropped.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable

from google import genai
from google.genai import types

from animatic.config import settings
from animatic.core.panel_prompt import PROMPT_TEMPLATE_VERSION, build_panel_prompt, shot_size_for
from animatic.core.slot_resolver import Slot, _slugify

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any], str, float], None]


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
    """Build one index entry per selected beat, in beat order, writing the
    index after each entry is resolved.

    `only`/`scene` narrow which beats are (re)generated this run. In this
    Task 1 pass, a beat outside that selection has no entry produced for it
    at all (Task 3 adds carrying it forward unchanged from `previous_index`
    — the whole-index rule). Every selected beat always calls the API in
    this pass; Task 3 adds a cache-key match against `previous_index` that
    skips the call when nothing the panel depends on has changed, and a
    single retry before a failing call is recorded `generation_failed`.

    Returns the final written index dict. `panel_manifest.write_index` is
    called after EACH beat's entry is resolved — never once at the end —
    so a run interrupted partway through leaves every entry built so far on
    disk and in S3.
    """
    from animatic.core.panel_manifest import build_index, write_index, write_panel

    beats = beats_doc.get("beats", [])
    manifest_by_id = {s["slot_id"]: s for s in manifest.get("slots", [])}

    entries: list[dict[str, Any]] = []
    index: dict[str, Any] = {}

    for beat in beats:
        beat_id = beat["beat_id"]
        if only is not None and beat_id not in only:
            continue
        if scene is not None and beat["scene"] != scene:
            continue

        shot_size, shot_size_reason = shot_size_for(beat)
        location_slot, character_slots = resolve_beat_slots(beat, slots)
        dependent = _dependent_slot_records(location_slot, character_slots, manifest_by_id)
        prompt, facial_features, facial_features_reason = build_panel_prompt(beat, shot_size)
        cache_key = panel_cache_key(beat, shot_size, dependent, PROMPT_TEMPLATE_VERSION)
        asset_slots_used = [location_slot.slot_id] + [s.slot_id for s in character_slots]

        try:
            image_bytes, mime_type = generate_panel(beat, prompt)
        except Exception as e:  # noqa: BLE001 — one bad beat must not abort the run
            reason = f"{type(e).__name__}: {e}"
            entry = {
                "beat_id": beat_id,
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
                "panel_uri": "",
                "panel_s3_uri": "",
                "content_hash": "",
                "source": "generation_failed",
                "source_reason": reason,
            }
            logger.warning("Panel generation failed for beat %s: %s", beat_id, reason)
            entries.append(entry)
            index = build_index(entries, beats_doc, manifest, beats_source, manifest_source, PROMPT_TEMPLATE_VERSION)
            write_index(index)
            if on_progress:
                on_progress(beat, "failed", 0.0)
            continue

        content_hash, local_path, s3_uri, s3_ok, s3_reason = write_panel(
            beat_id, image_bytes, mime_type
        )
        entry = {
            "beat_id": beat_id,
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
            "panel_uri": str(local_path),
            "panel_s3_uri": s3_uri if s3_ok else "",
            "content_hash": content_hash,
            "source": "generated",
            "source_reason": (
                f"generated via {settings.gemini_image_model}; "
                f"sha256={content_hash[:12]}; s3_ok={s3_ok} ({s3_reason})"
            ),
        }
        entries.append(entry)
        index = build_index(entries, beats_doc, manifest, beats_source, manifest_source, PROMPT_TEMPLATE_VERSION)
        write_index(index)
        if on_progress:
            on_progress(beat, "generated", 0.0)

    if not entries:
        index = build_index(entries, beats_doc, manifest, beats_source, manifest_source, PROMPT_TEMPLATE_VERSION)
        write_index(index)

    return index
