"""Redraw one panel from a written instruction, in place.

*"s8b5 is the character singing into a hairbrush alone in the room. No other
people."* — send the existing panel and that sentence to the image model, get
back the same drawing with that one thing changed. The room, the framing and
the line weight survive because they are in the seed image, not in a prompt
that has to re-win them.

The result is written to `assets/edited-panels/`, which outranks the generated
panel and is never overwritten by a regeneration. An edit and a hand edit are
the same kind of thing — a person decided what this frame should be — so they
live in the same place and get the same protection.

**The instruction is rewritten before it is sent, and this is the point of the
module.** The natural way to ask for this is a negation: *"no other people"*,
*"remove the turtles"*, *"without the sign"*. This project's most expensive
lesson is that a negation gets RENDERED — "NO FACIALS" was once lettered into
a frame, and naming the eyes as absent drew a fully rendered eye. So a negation
is turned into a statement about what the frame DOES hold, and the developer is
shown exactly what was sent rather than what they typed.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from animatic.config import settings
from animatic.core.shot_sources import EDITED_PANEL_DIR
from animatic.core.style import STYLE_BLOCK

logger = logging.getLogger(__name__)

ORIGINALS_DIR = Path("assets/edited-panels/.originals")
EDIT_TEMPLATE_VERSION = "v1"

_BEAT_ID_RE = re.compile(r"^s\d+b\d+$")

# Negations, and what each becomes. Ordered longest-first so "no other people"
# is not matched by the bare "no ". Each replacement states what the frame
# HOLDS; none of them names the thing being removed a second time.
_POSITIVE_FOR_NEGATION: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bno other (?:people|figures|characters|persons)\b", re.I),
     "one lone figure occupying the frame"),
    (re.compile(r"\b(?:with )?no one else\b", re.I),
     "one lone figure occupying the frame"),
    (re.compile(r"\bnobody else\b", re.I), "one lone figure occupying the frame"),
    (re.compile(r"\balone\b", re.I), "one lone figure occupying the frame"),
    (re.compile(r"\bempty\b", re.I), "bare and unoccupied"),
    (re.compile(r"\b(?:remove|delete|erase|get rid of|take out)\s+(?:the\s+)?([\w\s'-]{1,40})",
                re.I),
     "the space where {0} was is now plain, blank background"),
    (re.compile(r"\bwithout (?:any |the |a )?([\w\s'-]{1,40})", re.I),
     "the space where {0} was is now plain, blank background"),
    (re.compile(r"\bno more (?:than )?([\w\s'-]{1,40})", re.I),
     "the space where {0} was is now plain, blank background"),
)


class PanelEditError(Exception):
    """Raised when the edit call returns no image."""


def rewrite_negations(instruction: str) -> tuple[str, list[str]]:
    """Turn "no other people" into "one lone figure occupying the frame".

    Returns (rewritten, notes). `notes` records each substitution so the UI can
    show the developer what actually went to the model instead of what they
    typed — a rewrite they cannot see is a rewrite they cannot correct.
    """
    text = instruction
    notes: list[str] = []

    for pattern, replacement in _POSITIVE_FOR_NEGATION:
        match = pattern.search(text)
        if not match:
            continue
        subject = (match.group(1).strip() if match.groups() else "")
        positive = replacement.format(subject) if "{0}" in replacement else replacement
        notes.append(f"{match.group(0)!r} -> {positive!r}")
        text = text[: match.start()] + positive + text[match.end() :]

    return re.sub(r"\s{2,}", " ", text).strip(), notes


def build_edit_prompt(instruction: str) -> tuple[str, list[str]]:
    """The full instruction sent alongside the panel image.

    Closes with the style block for the same reason panel prompts do: the rule
    that matters must land LAST, because a rule stated mid-prompt loses to
    whatever follows it.
    """
    positive, notes = rewrite_negations(instruction)
    prompt = (
        "Change one thing about the supplied drawing and leave everything else "
        "exactly as it is — the same framing, the same line weight, the same "
        f"figures, the same room. The change: {positive.rstrip('.')}.\n\n"
        f"{STYLE_BLOCK}"
    )
    return prompt, notes


def edit_panel(panel: Path, instruction: str) -> tuple[bytes, str, str, list[str]]:
    """One image-edit call. Returns (bytes, mime, prompt sent, rewrite notes)."""
    prompt, notes = build_edit_prompt(instruction)
    client = genai.Client(api_key=settings.google_api_key)

    logger.info("Editing %s: %s", panel.name, prompt[:120])

    response = client.models.generate_content(
        model=f"models/{settings.gemini_image_model}",
        contents=[
            types.Part.from_bytes(
                data=panel.read_bytes(), mime_type=_mime_for(panel)
            ),
            prompt,
        ],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data, part.inline_data.mime_type, prompt, notes

    raise PanelEditError(
        f"No image in the edit response for {panel.name} — the model may have "
        f"refused the instruction"
    )


def save_edit(
    beat_id: str,
    data: bytes,
    mime_type: str,
    original: Path,
    instruction: str,
    prompt: str,
    notes: list[str],
    edited_dir: Path | None = None,
) -> dict[str, Any]:
    """Write an edited panel, keeping the frame it replaced.

    The original is preserved so an edit that comes back worse can be reverted
    without spending another call — the failure mode of a one-way edit is that
    the developer stops trying them.
    """
    assert _BEAT_ID_RE.match(beat_id), f"beat_id {beat_id!r} does not match ^s\\d+b\\d+$"
    edited_dir = EDITED_PANEL_DIR if edited_dir is None else edited_dir
    edited_dir.mkdir(parents=True, exist_ok=True)

    originals = edited_dir / ".originals"
    originals.mkdir(parents=True, exist_ok=True)
    kept = originals / f"{beat_id}{original.suffix}"
    if not kept.exists() and original.exists():
        shutil.copy2(original, kept)

    ext = "png" if "png" in mime_type else "jpg"
    target = edited_dir / f"{beat_id}.{ext}"
    target.write_bytes(data)

    return {
        "beat_id": beat_id,
        "edited_path": str(target),
        "original_kept_at": str(kept) if kept.exists() else None,
        "instruction": instruction,
        "prompt_sent": prompt,
        "negations_rewritten": notes,
        "content_hash": hashlib.sha256(data).hexdigest(),
        "edit_template_version": EDIT_TEMPLATE_VERSION,
        "edited_at": datetime.now(timezone.utc).isoformat(),
    }


def revert(beat_id: str, edited_dir: Path | None = None) -> bool:
    """Drop the edit for `beat_id`. True if there was one. Costs nothing."""
    assert _BEAT_ID_RE.match(beat_id), f"beat_id {beat_id!r} does not match ^s\\d+b\\d+$"
    edited_dir = EDITED_PANEL_DIR if edited_dir is None else edited_dir
    if not edited_dir.is_dir():
        return False
    removed = False
    for suffix in (".jpg", ".jpeg", ".png"):
        path = edited_dir / f"{beat_id}{suffix}"
        if path.exists():
            path.unlink()
            removed = True
    return removed


def _mime_for(panel: Path) -> str:
    return "image/png" if panel.suffix.lower() == ".png" else "image/jpeg"
