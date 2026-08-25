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
import re
from typing import Any

from google import genai
from google.genai import types

from animatic.config import settings
from animatic.core.audio_timing import narration_budget_words
from animatic.core.style import _strip_on_screen_text

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


def action_line(beat: dict[str, Any]) -> str:
    """A beat's action, with on-screen-text directives removed.

    A screenplay's title-card instructions are directions to the production,
    not events in the room. Phase 3 learned this when "SUPERIMPOSE ... 'NOVEMBER
    12, 1975 - PHILADELPHIA'" was painted into a panel as literal lettering;
    the same line reached the narrator here and came back as the word "Text."
    read aloud. `style._strip_on_screen_text` already removes exactly this
    class of directive and is already tested, so it is reused rather than
    reimplemented.

    Falls back to the raw content when stripping leaves nothing — a beat whose
    entire action is a title card still needs something to narrate.
    """
    stripped = re.sub(r"\s{2,}", " ", _strip_on_screen_text(beat["content"])).strip()
    return stripped.lstrip(".:;, ") or beat["content"]


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
            f"    action: {action_line(beat)}"
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
                action_line(beat), narration_budget_words(beat["duration_secs"])
            )
            logger.warning(
                "no narration returned for %s; falling back to a truncated "
                "action line",
                beat["beat_id"],
            )
        out[beat["beat_id"]] = text
    return out


def shorten(text: str, target_words: int) -> str:
    """Rewrite a narration line that overran, to `target_words` or fewer.

    The first implementation of this was deterministic truncation, on the
    reasoning that a second model call to shorten an already-short line buys
    nothing. That reasoning was wrong, and the first full run showed how:
    8 of 31 narration lines came back as fragments — "Rocky closes his.",
    "and spit on the.", "Rocky looks up. The." A word-boundary cut is not a
    sentence, and a narrator reading one sounds broken.

    So the line is rewritten by the model, which can drop a clause and keep a
    sentence. `_truncate_to_budget` remains as the fallback for when that call
    fails, but it is now clause-aware rather than a raw slice.
    """
    target = max(2, target_words)
    words = text.split()
    if len(words) <= target:
        return text.strip()

    rewritten = _call_rewrite(text, target)
    if rewritten and len(rewritten.split()) <= target:
        return rewritten
    if rewritten:
        logger.warning(
            "rewrite came back at %d words against a %d-word target; trimming",
            len(rewritten.split()),
            target,
        )
        return _truncate_to_budget(rewritten, target)
    return _truncate_to_budget(text, target)


def _call_rewrite(text: str, target: int) -> str | None:
    """One short call to say the same thing in fewer words. None on failure."""
    try:
        client = genai.Client(api_key=settings.google_api_key)
        response = client.models.generate_content(
            model=f"models/{settings.gemini_model}",
            contents=(
                f"Rewrite this narration line in {target} words or fewer. Keep "
                f"the most important thing that happens and drop the rest. "
                f"Return one complete sentence and nothing else.\n\n{text}"
            ),
        )
        out = (response.text or "").strip().strip('"')
    except Exception as exc:  # noqa: BLE001 — falls back to the trim
        logger.warning("narration rewrite failed (%s); trimming instead", exc)
        return None
    return out or None


# A line that ends on one of these is a fragment, not a sentence. Used to walk
# a deterministic trim back to somewhere it can legitimately stop.
_DANGLING = frozenset(
    """a an the and or but so of to in on at by for with from into onto upon as
    his her its their our your my this that these those is are was were be been
    being had has have will would could should may might must than then while
    when where who whom which what whose""".split()
)


def _truncate_to_budget(text: str, budget: int) -> str:
    """Trim to `budget` words without ending mid-thought.

    Prefers to drop whole trailing sentences, then a trailing clause at a
    comma, and only then walks back word by word off anything that cannot end
    a sentence.
    """
    if len(text.split()) <= budget:
        return text.strip()

    # Whole sentences first — the cleanest cut there is.
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if len(sentences) > 1:
        kept: list[str] = []
        for sentence in sentences:
            candidate = kept + [sentence]
            if len(" ".join(candidate).split()) > budget and kept:
                break
            kept = candidate
        if kept and len(" ".join(kept).split()) <= budget:
            return " ".join(kept).strip()
        text = sentences[0]

    # Then a trailing clause.
    words = text.split()
    if len(words) > budget:
        head = " ".join(words[:budget])
        if "," in head:
            clause = head.rsplit(",", 1)[0].strip()
            if len(clause.split()) >= 2:
                return _finish(clause)
        words = words[:budget]

    # Then back off anything that cannot end a sentence.
    while len(words) > 2 and words[-1].strip(".,;:-").lower() in _DANGLING:
        words = words[:-1]
    return _finish(" ".join(words))


def _finish(text: str) -> str:
    text = text.rstrip(",;:- ").strip()
    return text if text.endswith((".", "!", "?")) else f"{text}."


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
