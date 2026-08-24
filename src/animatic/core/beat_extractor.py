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
    * Dialogue scenes: fewer beats (group coherent exchanges into one beat each)
    * Establishing scenes: typically 1-2 beats
- Each beat must have a type: "action", "dialogue", or "establishing"
- duration_secs: estimate screen time in seconds (action beats: 2–8s, dialogue: 3–10s, establishing: 2–5s)
- motion_candidate: true only for high-intensity action beats worth animating (fights, chases)
- reason: explain why this beat boundary falls here and why it has this duration
- characters: list character names who appear or speak (empty list if none)
- dialogue: the key line of dialogue if type is "dialogue", else empty string

Return ONLY a valid JSON array of beat objects with fields:
beat (int), scene_heading (str), type (str), content (str), duration_secs (float),
motion_candidate (bool), reason (str), characters (array of str), dialogue (str).
No explanation, no markdown fences, just the raw JSON array.
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
            "dialogue": {"type": "string"},
        },
        "required": ["beat", "scene_heading", "type", "content", "duration_secs",
                     "motion_candidate", "reason", "characters", "dialogue"],
    },
}


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
    dialogue: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "scene": self.scene,
            "beat": self.beat,
            "scene_heading": self.scene_heading,
            "type": self.type,
            "content": self.content,
            "duration_secs": self.duration_secs,
            "motion_candidate": self.motion_candidate,
            "reason": self.reason,
            "characters": self.characters,
            "dialogue": self.dialogue,
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
            dialogue=raw.get("dialogue") or None,
        )
        beats.append(beat)

    logger.info("Scene %d: extracted %d beats", scene_num, len(beats))
    return beats
