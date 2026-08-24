"""Beat dataclass and Gemini-powered beat extractor."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from animatic.config import settings

logger = logging.getLogger(__name__)

BEAT_TYPES = {"action", "dialogue", "establishing"}

_SYSTEM_PROMPT = """\
You are a screenplay analyst. Break a screenplay scene into beats.

Rules:
- A beat is the smallest unit of dramatic action or exchange.
- IMPORTANT: Generate MULTIPLE beats per scene. A typical action scene has 5-15 beats.
- Beat density varies with content:
    * Action scenes: more beats (one per distinct physical action or moment)
    * Dialogue scenes: one beat per exchange, but see the dialogue rule below
    * Establishing scenes: typically 1-2 beats
- Each beat must have a type: "action", "dialogue", or "establishing"
- duration_secs: estimate screen time in seconds (action beats: 2–8s, dialogue: 3–10s, establishing: 2–5s)
- motion_candidate: true only for high-intensity action beats worth animating (fights, chases)
- reason: explain why this beat boundary falls here and why it has this duration
- characters: list character names who appear or speak (empty list if none)

DIALOGUE — the most important rule:
- `dialogue` is an ARRAY of {character, line} objects, one entry per spoken line.
- Reproduce EVERY spoken line in the scene, verbatim, in script order.
- NEVER merge two characters' lines into one entry. Each entry has exactly one speaker.
- NEVER drop a line for being short. "Hey --" and "Absolutely." are lines.
- Keep the screenplay's own punctuation, including leading ellipses ("... Yo' iz an
  accident."). Do not clean it up, paraphrase it, or summarise it.
- Copy the speaker name exactly as the script writes it (ROCKY, CORNERMAN, FIGHTER #1).
- If a beat has no speech, `dialogue` is an empty array.
- Across all the beats you return, every spoken line in the scene must appear exactly
  once. If an exchange is long, split it across several dialogue beats rather than
  dropping lines.
- duration_secs for a dialogue beat must be long enough to actually speak its lines:
  at least (total words / 2.5) seconds, plus about 0.5s per line for pauses.

Return ONLY a valid JSON array of beat objects. No markdown fences, no explanation.
"""

_BEAT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "beat": {"type": "integer"},
            "scene_heading": {"type": "string"},
            "type": {"type": "string", "enum": ["action", "dialogue", "establishing"]},
            "content": {"type": "string"},
            "duration_secs": {"type": "number"},
            "motion_candidate": {"type": "boolean"},
            "reason": {"type": "string"},
            "characters": {"type": "array", "items": {"type": "string"}},
            "dialogue": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "character": {"type": "string"},
                        "line": {"type": "string"},
                    },
                    "required": ["character", "line"],
                },
            },
        },
        "required": ["beat", "scene_heading", "type", "content", "duration_secs",
                     "motion_candidate", "reason", "characters", "dialogue"],
    },
}

# Speaking rate used to floor a dialogue beat's duration. 150 wpm is a normal
# delivery pace; expressed per-second that is 2.5 words/sec.
_WORDS_PER_SEC = 2.5
# Extra seconds allowed per line for the pause between speakers.
_PAUSE_PER_LINE = 0.5


@dataclass
class Line:
    """One spoken line, attributed to exactly one character.

    Phase 5 synthesises audio per line so each character keeps a consistent
    voice — which is only possible if speakers are never merged into a single
    string. `line` holds the screenplay's wording verbatim, ellipses included.
    """

    character: str
    line: str

    def to_dict(self) -> dict[str, Any]:
        return {"character": self.character, "line": self.line}

    @property
    def word_count(self) -> int:
        return len(self.line.split())


@dataclass
class Beat:
    beat_id: str
    scene: int
    beat: int
    scene_heading: str
    type: str
    content: str
    duration_secs: float
    motion_candidate: bool
    reason: str
    characters: list[str] = field(default_factory=list)
    dialogue: list[Line] = field(default_factory=list)
    duration_source: str = "model"

    @property
    def spoken_words(self) -> int:
        return sum(line.word_count for line in self.dialogue)

    @property
    def min_speakable_secs(self) -> float:
        """Shortest duration in which this beat's lines can actually be spoken."""
        if not self.dialogue:
            return 0.0
        return round(
            self.spoken_words / _WORDS_PER_SEC + _PAUSE_PER_LINE * len(self.dialogue), 1
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "scene": self.scene,
            "beat": self.beat,
            "scene_heading": self.scene_heading,
            "type": self.type,
            "content": self.content,
            "duration_secs": self.duration_secs,
            "duration_source": self.duration_source,
            "motion_candidate": self.motion_candidate,
            "reason": self.reason,
            "characters": self.characters,
            "dialogue": [line.to_dict() for line in self.dialogue],
            "spoken_words": self.spoken_words,
            "min_speakable_secs": self.min_speakable_secs,
        }


def extract_beats(scene_num: int, scene_text: str) -> list[Beat]:
    """Extract beats from a single scene using Gemini.

    Args:
        scene_num: The screenplay scene number.
        scene_text: Raw scene text (heading + body).

    Returns:
        List of Beat objects with all required fields populated.
    """
    client = genai.Client(api_key=settings.google_api_key)

    prompt = f"Scene {scene_num}:\n\n{scene_text}"

    response = client.models.generate_content(
        model=f"models/{settings.gemini_model}",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=_BEAT_SCHEMA,
            temperature=0.2,
        ),
    )

    raw_beats: list[dict] = json.loads(response.text)
    beats: list[Beat] = []

    for i, raw in enumerate(raw_beats, start=1):
        beat = Beat(
            beat_id=f"s{scene_num}b{i}",
            scene=scene_num,
            beat=i,
            scene_heading=raw.get("scene_heading", ""),
            type=raw.get("type", "action"),
            content=raw.get("content", ""),
            duration_secs=float(raw.get("duration_secs", 3.0)),
            motion_candidate=bool(raw.get("motion_candidate", False)),
            reason=raw.get("reason", ""),
            characters=raw.get("characters", []),
            dialogue=_parse_lines(raw.get("dialogue")),
        )
        _apply_duration_floor(beat)
        beats.append(beat)

    logger.info("Scene %d: extracted %d beats", scene_num, len(beats))
    return beats


def _parse_lines(raw: Any) -> list[Line]:
    """Coerce the model's dialogue field into a list of attributed lines.

    Tolerates the legacy single-string shape so an older cached beat list does
    not crash the loader; such a line is attributed to UNKNOWN so it is visibly
    wrong rather than silently mis-voiced in Phase 5.
    """
    if not raw:
        return []
    if isinstance(raw, str):
        return [Line(character="UNKNOWN", line=raw)]
    lines: list[Line] = []
    for item in raw:
        if isinstance(item, str):
            lines.append(Line(character="UNKNOWN", line=item))
        elif isinstance(item, dict):
            text = (item.get("line") or "").strip()
            if text:
                lines.append(
                    Line(character=(item.get("character") or "UNKNOWN").strip(), line=text)
                )
    return lines


def _apply_duration_floor(beat: Beat) -> None:
    """Widen a beat that is too short to speak its own lines.

    Phase 5 synthesises audio per beat and Phase 7 cuts each shot to
    duration_secs, so a beat shorter than its speech yields clipped audio or
    A/V drift. Record which source won so the shot duration keeps a
    machine-readable reason, as PROJECT.md requires.
    """
    floor = beat.min_speakable_secs
    if floor > beat.duration_secs:
        beat.reason = (
            f"{beat.reason} [duration raised {beat.duration_secs}s → {floor}s: "
            f"{beat.spoken_words} spoken words across {len(beat.dialogue)} line(s) "
            f"cannot be delivered in less at {_WORDS_PER_SEC} words/sec]"
        ).strip()
        beat.duration_secs = floor
        beat.duration_source = "dialogue_floor"
