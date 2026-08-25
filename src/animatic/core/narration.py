"""Narration for beats with no dialogue — written to the clock, not to the page.

The measurement that shapes this module: a beat's action prose read verbatim
takes about three times the beat. `s1b1` is 2.2 seconds long and its content
line — "Establishing shot of the dark, tense interior of the Blue Door Fight
Club at night" — measured 6.04 seconds spoken. Narrating action lines verbatim
would overrun 31 of the 49 beats, most of them badly.

So narration is not a reading of the action line; it is a line *written to fit*
the beat, from the action line. `audio_timing.narration_budget_words` sets the
budget from the beat's own duration, and the whole run is written in one call
so the narrator's register stays consistent and consecutive beats do not repeat
each other's nouns.

The budget is planning only. Every clip is measured after generation, and
`shorten` re-writes any line whose audio still overran.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from animatic.config import settings
from animatic.core.audio_timing import narration_budget_words

logger = logging.getLogger(__name__)

_NARRATION_SCHEMA = {
    "type": "object",
    "properties": {
        "narration": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "beat_id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["beat_id", "text"],
            },
        }
    },
    "required": ["narration"],
}

_RULES = (
    "Write each line as a narrator describing what is on screen, in the "
    "present tense. Keep the concrete nouns from the action — the place, the "
    "objects, the people — and drop the camera language, the adjectives and "
    "anything a viewer can already see is a mood. Never name a shot type. "
    "Consecutive lines describe consecutive moments of the same scene, so do "
    "not restate what the line before it already established.\n\n"
    "The word budget on each beat is the number of words that beat's running "
    "time can physically carry. Stay at or under it."
)


class NarrationError(Exception):
    """Raised when the narration call returns nothing usable."""


def narration_beats(beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The beats that need narration: every beat with no dialogue."""
    return [b for b in beats if not b.get("dialogue")]


def build_narration_prompt(beats: list[dict[str, Any]]) -> str:
    """One prompt covering the whole run, grouped by scene.

    Grouped so the model can see what the previous beat already said — the
    only way to stop 31 independently-written lines all opening with the same
    establishing noun.
    """
    blocks: list[str] = []
    current_scene: int | None = None
    for beat in beats:
        if beat["scene"] != current_scene:
            current_scene = beat["scene"]
            blocks.append(f"\nScene {current_scene} — {beat.get('scene_heading', '')}")
        budget = narration_budget_words(beat["duration_secs"])
        blocks.append(
            f"  {beat['beat_id']} ({beat['duration_secs']}s, at most {budget} words)\n"
            f"    action: {beat['content']}"
        )

    return (
        "Write one narration line for each beat below.\n\n"
        f"{_RULES}\n\n"
        "Return every beat_id exactly as given.\n"
        + "\n".join(blocks)
    )


def write_narration(beats: list[dict[str, Any]]) -> dict[str, str]:
    """Narration text for every beat with no dialogue.

    Returns:
        dict mapping beat_id -> narration text. A beat the model omitted falls
        back to its own action line truncated to budget — worse prose than the
        model would write, but never a silent beat.
    """
    targets = narration_beats(beats)
    if not targets:
        return {}

    written = _call_narration(targets)

    out: dict[str, str] = {}
    for beat in targets:
        text = (written.get(beat["beat_id"]) or "").strip()
        if not text:
            text = _truncate_to_budget(
                beat["content"], narration_budget_words(beat["duration_secs"])
            )
            logger.warning(
                "no narration returned for %s; falling back to a truncated "
                "action line",
                beat["beat_id"],
            )
        out[beat["beat_id"]] = text
    return out


def shorten(text: str, target_words: int) -> str:
    """Cut a narration line that overran, keeping it a readable phrase.

    Used only after a clip has been measured over its beat. Deliberately
    deterministic — a second model call to shorten a line that is already
    short buys nothing and can come back longer.
    """
    return _truncate_to_budget(text, max(2, target_words))


def _truncate_to_budget(text: str, budget: int) -> str:
    words = text.split()
    if len(words) <= budget:
        return text.strip()
    kept = " ".join(words[:budget]).rstrip(",;:- ")
    return kept if kept.endswith(".") else f"{kept}."


def _call_narration(beats: list[dict[str, Any]]) -> dict[str, str]:
    """Returns {} on failure — `write_narration` falls back per beat."""
    try:
        client = genai.Client(api_key=settings.google_api_key)
        response = client.models.generate_content(
            model=f"models/{settings.gemini_model}",
            contents=build_narration_prompt(beats),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_NARRATION_SCHEMA,
            ),
        )
        payload = json.loads(response.text)
    except Exception as exc:  # noqa: BLE001 — narration degrades, never blocks
        logger.warning("narration call failed (%s); falling back per beat", exc)
        return {}

    return {
        entry["beat_id"]: entry["text"]
        for entry in payload.get("narration", [])
        if entry.get("beat_id")
    }
