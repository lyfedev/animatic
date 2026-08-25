"""Generated slot art — one image-generation call per slot lacking reference art.

Uses exactly the call shape D-12 records as known-good: `generate_content`
with `response_modalities=["IMAGE"]` on the `GOOGLE_API_KEY` (MLDev) backend,
following how `beat_extractor.py` already constructs its client. Deliberately
does NOT pass `system_instruction` — RESEARCH Pitfall 1: `system_instruction`
combined with an image-output model raises `ClientError` on this backend.
The shared style block goes in the prompt text instead (`style.build_slot_prompt`).
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Callable

from google import genai
from google.genai import types

from animatic.config import settings
from animatic.core.slot_resolver import Slot
from animatic.core.style import build_slot_prompt, character_context, describe_slot

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[Slot, str, float], None]


class AssetGenerationError(Exception):
    """Raised when a generation response carries no inline image data."""


def generate_slot_art(slot, prompt: str) -> tuple[bytes, str]:
    """Generate one image for `slot` from `prompt`.

    Args:
        slot: The `Slot` this art is for — used only for logging (never for
            constructing a write path, and never logged itself as config;
            T-03-02 disposition: log prompts, not client config).
        prompt: Full prompt text, already including the shared style block
            (see `style.build_slot_prompt`) — no `system_instruction` is used.

    Returns:
        (image_bytes, mime_type) — mime type is read from the response
        rather than assumed (RESEARCH Pitfall 3: don't assume PNG).

    Raises:
        AssetGenerationError: no part of the response carried inline image
            data.
    """
    client = genai.Client(api_key=settings.google_api_key)

    logger.info("Generating art for slot %s", getattr(slot, "slot_id", "?"))

    response = client.models.generate_content(
        model=f"models/{settings.gemini_image_model}",
        contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )

    parts = response.candidates[0].content.parts
    for part in parts:
        if part.inline_data is not None:
            return part.inline_data.data, part.inline_data.mime_type

    raise AssetGenerationError(
        f"No inline image data in generate_content response for slot "
        f"{getattr(slot, 'slot_id', '?')!r}"
    )


def generate_missing_art(
    slots: list[Slot],
    beats: dict[str, Any],
    previous_manifest: dict[str, Any] | None = None,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Generate art for every slot not already resolved to reference art.

    Groups slots by `art_slot_id` (minor characters share one) and iterates
    the distinct groups in `priority_rank` order (D-10/D-11), so budget and
    attention go to the highest-share slots first. A slot whose `source` is
    already "reference" (Task 1 ran first) is skipped outright — it is
    never passed to the image model.

    A generated file already on disk whose prompt in `previous_manifest`
    matches the prompt about to be sent is reused rather than regenerated,
    unless `force` is True — image calls cost money and regenerating
    unchanged art on every run is waste.

    A failure on one group's call is caught, recorded as
    `source="generation_failed"` with the error in `source_reason` on every
    slot in that group, and the run continues — FR-02 says the system never
    blocks on a missing input, and one bad slot must not cost the others.
    The resolved art (uri, S3 uri, hash, source, reason, prompt) is copied
    onto every slot sharing an `art_slot_id`, so all four minor characters
    end up carrying the same art_uri and content_hash.
    """
    from animatic.core.asset_manifest import write_slot_art

    previous_by_id: dict[str, dict[str, Any]] = {}
    if previous_manifest:
        previous_by_id = {
            s["slot_id"]: s for s in previous_manifest.get("slots", [])
        }

    groups: dict[str, list[Slot]] = {}
    for slot in slots:
        if slot.source == "reference":
            continue
        art_id = slot.art_slot_id or slot.slot_id
        groups.setdefault(art_id, []).append(slot)

    ordered_art_ids = sorted(
        groups.keys(), key=lambda aid: min(s.priority_rank for s in groups[aid])
    )

    for art_id in ordered_art_ids:
        members = groups[art_id]
        primary = min(members, key=lambda s: s.priority_rank)
        prompt = build_slot_prompt(primary, _subject_note(primary, beats, slots))

        prev = previous_by_id.get(primary.slot_id)
        reuse_path: Path | None = None
        if not force and prev and prev.get("prompt") == prompt:
            candidate = Path(prev.get("art_uri", ""))
            if candidate.is_file():
                reuse_path = candidate

        if reuse_path is not None:
            _reuse_art(members, prompt, reuse_path, prev)
            if on_progress:
                on_progress(primary, "reused", 0.0)
            continue

        t0 = time.time()
        try:
            image_bytes, mime_type = generate_slot_art(primary, prompt)
        except Exception as e:  # noqa: BLE001 — one bad slot must not abort the run
            reason = f"generation failed: {type(e).__name__}: {e}"
            for member in members:
                member.prompt = prompt
                member.source = "generation_failed"
                member.source_reason = reason
            logger.warning(
                "Generation failed for art_slot_id %s: %s", art_id, reason
            )
            if on_progress:
                on_progress(primary, "failed", time.time() - t0)
            continue

        write_slot_art(primary, image_bytes, mime_type)
        elapsed = time.time() - t0
        for member in members:
            member.prompt = prompt
            if member is primary:
                continue
            member.art_uri = primary.art_uri
            member.art_s3_uri = primary.art_s3_uri
            member.content_hash = primary.content_hash
            member.source = primary.source
            member.source_reason = primary.source_reason
        if on_progress:
            on_progress(primary, "generated", elapsed)


def _reuse_art(
    members: list[Slot], prompt: str, reuse_path: Path, prev: dict[str, Any]
) -> None:
    image_bytes = reuse_path.read_bytes()
    content_hash = hashlib.sha256(image_bytes).hexdigest()
    art_s3_uri = prev.get("art_s3_uri", "")
    for member in members:
        member.prompt = prompt
        member.art_uri = str(reuse_path)
        member.art_s3_uri = art_s3_uri
        member.content_hash = content_hash
        member.source = "generated"
        member.source_reason = (
            f"reused existing art at {reuse_path} — prompt unchanged since "
            f"the previous manifest (pass --force to regenerate)"
        )


def _subject_note(
    slot: Slot, beats: dict[str, Any], slots: list[Slot] | None = None
) -> str:
    """Build the subject clause for one slot's generation prompt.

    Locations ask for an empty establishing view grounded in the beats that
    use the slot (`style.describe_slot` — script-derived, D-09-safe). A
    bare `"<name> (location)"` note leaves the model free to invent a
    populated action scene, which is exactly the "words drawn into the
    frame" and detailed-face failure modes D-09 and PROJECT.md's
    visual-style rule both rule out.

    The blank-face wording names no headwear. It used to bound the face
    plane by "the hairline, hat brim and jaw contour" — naming a hat twice
    while describing the head, which put a hat on every character including
    a boxer in trunks and the man reaching into his locker *for* his hat.
    A prompt that mentions an object is a prompt that draws it.

    Characters are deliberately NOT described from their beats — a beat's
    content describes the action, not the person, so every character
    sharing a scene would inherit the same sentence and be drawn the same
    way (`rocky` and `black_fighter` came back byte-identical when this was
    tried). The name is the subject; PROJECT.md's "no facial features"
    rule is stated positively as a blank head rather than a negation.
    """
    if slot.slot_type == "location":
        description = describe_slot(slot, beats)
        return (
            f"An empty establishing view of the physical space itself — "
            f"the architecture, fixtures and props implied by "
            f"{description} — with no people present anywhere in the "
            f"shot. Every door, wall, poster board and nameplate in the "
            f"room is left a plain blank shape, exactly as bare as the "
            f"rest of the linework, carrying no lettering of its own — "
            f"nothing in the picture is captioned, labeled or "
            f"hand-painted with this location's own name or any other "
            f"word."
        )
    # A bare name is ambiguous about the film rather than the word: "BLACK
    # FIGHTER" drew a soldier in a beret and tactical vest. character_context
    # supplies the world from the locations of the character's own scenes.
    # It goes AFTER the figure description and is closed by a restatement of
    # the isolation rule, because the location description is a scene — left
    # open-ended the model stages the figure inside the room.
    context = character_context(slot, list(slots or []), beats)
    belongs = (
        f" This person spends their time somewhere like this: {context}. "
        f"Read that only to decide what they wear and carry. The drawing "
        f"itself remains one lone figure on a blank white page, the "
        f"surroundings left out of the frame entirely."
        if context else ""
    )
    if slot.is_minor:
        return (
            "One unnamed background figure of the same period and world "
            "as the story, a single full-length figure in a neutral "
            "three-quarter standing pose, alone against an open white "
            "background. Where the face sits, the outline traces one "
            "continuous blank plane bounded only by the hairline and jaw "
            "contour — as bare and unmarked as the open "
            "background itself, with no eyebrow, eye, nose or mouth line "
            "interrupting that plane anywhere. Hair and jaw are "
            "described by the same outline work as the rest of the "
            "figure, carrying no lettering anywhere in the picture."
            + belongs
        )
    return (
        f"{slot.display_name.title()}, a single full-length figure in a "
        f"neutral three-quarter standing pose, alone against an open "
        f"white background. Where the face sits, the outline traces one "
        f"continuous blank plane bounded only by the hairline and jaw "
        f"contour — as bare and unmarked as the open background "
        f"itself, with no eyebrow, eye, nose or mouth line interrupting "
        f"that plane anywhere. Hair and jaw are described by the "
        f"same outline work as the rest of the figure, carrying no "
        f"lettering anywhere in the picture.{belongs}"
    )
