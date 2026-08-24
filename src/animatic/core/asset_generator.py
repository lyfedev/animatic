"""Generated slot art — one image-generation call per slot lacking reference art.

Uses exactly the call shape D-12 records as known-good: `generate_content`
with `response_modalities=["IMAGE"]` on the `GOOGLE_API_KEY` (MLDev) backend,
following how `beat_extractor.py` already constructs its client. Deliberately
does NOT pass `system_instruction` — RESEARCH Pitfall 1: `system_instruction`
combined with an image-output model raises `ClientError` on this backend.
The shared style block goes in the prompt text instead (`style.build_slot_prompt`).
"""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

from animatic.config import settings

logger = logging.getLogger(__name__)


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
