"""Casting — one prebuilt Gemini voice per speaking character, plus a narrator.

Phase 3 gave every character a project-unique `voice_id` and proved with
`assert_no_voice_collisions` that two characters who speak in the same scene
can never share one. That guarantees *distinctness*. This module decides
*which* voice, which is a different question: WOMAN reading in a bass register
is distinct and wrong.

Casting is a judgement about a character, so a model makes it — from the
character's own name, the scene headings they appear in, and the lines they
actually speak. Nothing here knows anything about Rocky, boxing, or 1976; a
different script cast through this module gets a different cast list.

The model's answer is then put through a deterministic guard that is the real
contract:

- every speaking character is cast (a name the model skipped falls back to
  stable-hash assignment)
- no two characters share a voice
- no character is given the narrator's voice
- the whole cast is reproducible from the returned `reason` strings

The cast is written into the audio index, so a re-run reuses it rather than
re-casting — a character whose voice changed between runs would break the
consistency ROADMAP criterion 2 asks for.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from google import genai
from google.genai import types

from animatic.config import settings

logger = logging.getLogger(__name__)

# Prebuilt voice names available to the Gemini TTS models. Order is fixed so
# the hash fallback is reproducible across runs and machines.
GEMINI_VOICES: tuple[str, ...] = (
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda",
    "Orus", "Aoede", "Callirrhoe", "Autonoe", "Enceladus", "Iapetus",
    "Umbriel", "Algieba", "Despina", "Erinome", "Algenib", "Rasalgethi",
    "Laomedeia", "Achernar", "Alnilam", "Schedar", "Gacrux", "Pulcherrima",
    "Achird", "Zubenelgenubi", "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
)

# The narrator is not a character and is never cast from the pool, so a
# script with 29 speaking parts still leaves the narration sounding like
# narration.
NARRATOR_VOICE = "Charon"
NARRATOR_REASON = (
    "reserved narrator voice — never cast to a character, so action narration "
    "stays audibly distinct from anyone in the scene"
)

_CAST_SCHEMA = {
    "type": "object",
    "properties": {
        "cast": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "character": {"type": "string"},
                    "voice": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["character", "voice", "reason"],
            },
        }
    },
    "required": ["cast"],
}


class VoiceCastingError(Exception):
    """Raised when the casting call returns nothing usable."""


def build_casting_prompt(profiles: list[dict[str, Any]]) -> str:
    """Prompt the casting call from character evidence, never from the title.

    Each profile carries the character's name, the scene headings they appear
    in, and their spoken lines — the same evidence a casting director works
    from. The script's name is deliberately absent so the model casts what is
    on the page rather than what it remembers about the film.
    """
    pool = ", ".join(v for v in GEMINI_VOICES if v != NARRATOR_VOICE)
    blocks = []
    for p in profiles:
        lines = "\n".join(f'    - "{ln}"' for ln in p["lines"]) or "    (none)"
        blocks.append(
            f"  {p['character']}\n"
            f"    appears in: {'; '.join(p['scene_headings'])}\n"
            f"    speaks:\n{lines}"
        )
    return (
        "Cast a synthetic voice for each speaking part below. Judge age, "
        "register and delivery only from the character's name, the places "
        "they appear, and the words they say.\n\n"
        f"Available voices: {pool}\n\n"
        "Assign a different voice to every character. Return the character "
        "name exactly as given. In `reason`, state in one sentence what in "
        "the evidence led to that voice.\n\n"
        "Characters:\n" + "\n\n".join(blocks)
    )


def character_profiles(beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evidence per speaking character, in first-appearance order."""
    profiles: dict[str, dict[str, Any]] = {}
    for beat in beats:
        for line in beat.get("dialogue", []):
            name = line["character"]
            p = profiles.setdefault(
                name, {"character": name, "scene_headings": [], "lines": []}
            )
            heading = beat.get("scene_heading", "")
            if heading and heading not in p["scene_headings"]:
                p["scene_headings"].append(heading)
            p["lines"].append(line["line"])
    return list(profiles.values())


def _hash_voice(name: str, taken: set[str]) -> str:
    """Stable fallback voice for `name`, avoiding anything already `taken`.

    Hashed rather than index-ordered so adding a character to a script does
    not reshuffle everyone else's voice.
    """
    start = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16) % len(
        GEMINI_VOICES
    )
    for offset in range(len(GEMINI_VOICES)):
        candidate = GEMINI_VOICES[(start + offset) % len(GEMINI_VOICES)]
        if candidate != NARRATOR_VOICE and candidate not in taken:
            return candidate
    raise VoiceCastingError(
        f"no free voice for {name!r}: {len(taken)} of {len(GEMINI_VOICES)} taken"
    )


def cast_voices(beats: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Cast every speaking character, guarding the result.

    Returns:
        dict mapping character name -> {"voice": ..., "reason": ...}. The
        reason is the model's when the model cast the part and a stated
        fallback reason when the guard had to step in, so every entry in the
        audio index explains itself (NFR-04).
    """
    profiles = character_profiles(beats)
    if not profiles:
        return {}

    proposed = _propose_cast(profiles)
    return _enforce_distinct(profiles, proposed)


def _propose_cast(profiles: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Ask the model to cast. Returns {} on any failure — the guard fills in."""
    try:
        client = genai.Client(api_key=settings.google_api_key)
        response = client.models.generate_content(
            model=f"models/{settings.gemini_model}",
            contents=build_casting_prompt(profiles),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_CAST_SCHEMA,
            ),
        )
        payload = json.loads(response.text)
    except Exception as exc:  # noqa: BLE001 — casting degrades, never blocks
        logger.warning("voice casting call failed (%s); falling back to hash", exc)
        return {}

    return {
        entry["character"]: {"voice": entry["voice"], "reason": entry["reason"]}
        for entry in payload.get("cast", [])
        if entry.get("character") and entry.get("voice")
    }


def _enforce_distinct(
    profiles: list[dict[str, Any]], proposed: dict[str, dict[str, str]]
) -> dict[str, dict[str, str]]:
    """Make the proposal satisfy the contract, recording every intervention.

    Processes characters in first-appearance order so the outcome does not
    depend on dict iteration order, and so an earlier-appearing character
    keeps the voice it was cast when two characters collide.
    """
    cast: dict[str, dict[str, str]] = {}
    taken: set[str] = set()

    for profile in profiles:
        name = profile["character"]
        entry = proposed.get(name)
        voice = entry["voice"] if entry else None

        if voice not in GEMINI_VOICES:
            reason_prefix = (
                f"model returned no cast for this part"
                if entry is None
                else f"model proposed {voice!r}, which is not an available voice"
            )
            voice = _hash_voice(name, taken)
            reason = f"{reason_prefix}; assigned {voice} by stable name hash"
        elif voice == NARRATOR_VOICE:
            replacement = _hash_voice(name, taken)
            reason = (
                f"model proposed {NARRATOR_VOICE}, which is reserved for narration; "
                f"reassigned to {replacement} by stable name hash"
            )
            voice = replacement
        elif voice in taken:
            clash = next(n for n, c in cast.items() if c["voice"] == voice)
            replacement = _hash_voice(name, taken)
            reason = (
                f"model proposed {voice}, already cast to {clash}; two characters "
                f"cannot share a voice, so reassigned to {replacement} by stable "
                f"name hash"
            )
            voice = replacement
        else:
            reason = entry["reason"]

        cast[name] = {"voice": voice, "reason": reason}
        taken.add(voice)

    assert len({c["voice"] for c in cast.values()}) == len(cast), (
        "voice collision survived the casting guard"
    )
    assert NARRATOR_VOICE not in {c["voice"] for c in cast.values()}, (
        "a character was cast the reserved narrator voice"
    )
    return cast
