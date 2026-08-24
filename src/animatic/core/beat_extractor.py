"""Beat dataclass and Gemini-powered beat extractor."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, replace
from typing import Any

from google import genai
from google.genai import types

from animatic.config import settings
from animatic.core.scene_timing import LINES_PER_PAGE, PAGE_SECS

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
- ONE BEAT PER SPEAKER TURN. When a character starts speaking, that is a new beat.
  Film cuts on speaker turns — a four-line back-and-forth is FOUR beats
  (shot / reverse shot / shot / reverse shot), never one long held shot.
  So `dialogue` normally holds exactly ONE entry. Use more than one only when
  the same character speaks several lines without interruption.
- Because each dialogue beat is one speaker, `content` should describe THAT
  speaker's shot — who we are on and what they are doing as they say it.
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
# No shot is shorter than this, however small its share of the page.
_MIN_SHOT_SECS = 0.8


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


def extract_beats(
    scene_num: int, scene_text: str, target_secs: float | None = None
) -> list[Beat]:
    """Extract beats from a single scene using Gemini.

    Args:
        scene_num: The screenplay scene number.
        scene_text: Raw scene text (heading + body).
        target_secs: Screen time this scene should occupy, from its script
            page geometry. When given, beat durations are scaled to sum to it.

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

    for raw in raw_beats:
        beats.append(
            Beat(
                beat_id="",  # assigned after splitting, below
                scene=scene_num,
                beat=0,
                scene_heading=raw.get("scene_heading", ""),
                type=raw.get("type", "action"),
                content=raw.get("content", ""),
                duration_secs=float(raw.get("duration_secs", 3.0)),
                motion_candidate=bool(raw.get("motion_candidate", False)),
                reason=raw.get("reason", ""),
                characters=raw.get("characters", []),
                dialogue=_parse_lines(raw.get("dialogue")),
            )
        )

    beats = _split_speaker_turns(beats)

    for i, beat in enumerate(beats, start=1):
        beat.beat_id = f"s{scene_num}b{i}"
        beat.beat = i
        _apply_duration_floor(beat)

    if target_secs:
        fit_scene_to_budget(beats, target_secs)

    logger.info("Scene %d: extracted %d beats", scene_num, len(beats))
    return beats


def _split_speaker_turns(beats: list[Beat]) -> list[Beat]:
    """Guarantee one speaker turn per beat.

    Film cuts on speaker turns: a four-line exchange is four shots, not one
    held frame. The prompt asks for this directly, so normally nothing here
    fires — this is the deterministic backstop for when the model returns a
    multi-turn beat anyway. Without it a beat can hold 4 lines, and the
    duration floor then stretches it to ~12s of static panel, which is the
    pacing bug this exists to prevent.

    Consecutive lines by the same character stay together — that is one turn.
    """
    out: list[Beat] = []
    for beat in beats:
        turns = _group_consecutive_turns(beat.dialogue)
        if len(turns) <= 1:
            out.append(beat)
            continue
        for n, turn in enumerate(turns, start=1):
            speaker = turn[0].character
            spoken = " ".join(line.line for line in turn)
            out.append(
                replace(
                    beat,
                    beat_id="",
                    beat=0,
                    type="dialogue",
                    content=f"{speaker}: {spoken}",
                    # Recomputed from this turn's own words by the duration floor.
                    duration_secs=0.0,
                    # A single speaker turn is never worth animating.
                    motion_candidate=False,
                    reason=(
                        f"{beat.reason} [split: turn {n} of {len(turns)} in this "
                        f"exchange — film cuts on speaker turns, so each turn is "
                        f"its own shot]"
                    ).strip(),
                    characters=[speaker],
                    dialogue=list(turn),
                    duration_source="model",
                )
            )
    return out


def fit_scene_to_budget(beats: list[Beat], target_secs: float) -> None:
    """Scale a scene's beats to the screen time its page geometry implies.

    One script page is one minute, so a scene's line count sets its runtime.
    The model's per-beat estimates are only a *shape* — this makes them sum
    to a target measured from the script rather than guessed from a range.

    Speech is the one incompressible part: a beat can never fall below the
    time its lines take to say. Those beats are pinned at their floor and the
    remaining budget is re-spread over the rest, repeatedly, until nothing
    else would be pushed under its floor.
    """
    if not beats or target_secs <= 0:
        return

    floors = {id(b): b.min_speakable_secs for b in beats}
    free = list(beats)
    pinned_secs = 0.0

    while free:
        pool = target_secs - pinned_secs
        free_total = sum(b.duration_secs for b in free)
        if free_total <= 0:
            break
        scale = pool / free_total
        under = [b for b in free if b.duration_secs * scale < floors[id(b)]]
        if not under:
            for b in free:
                b.duration_secs = max(_MIN_SHOT_SECS, round(b.duration_secs * scale, 1))
            break
        for b in under:
            b.duration_secs = max(_MIN_SHOT_SECS, floors[id(b)])
            pinned_secs += b.duration_secs
            free.remove(b)

    for b in beats:
        b.duration_source = "page_budget"
        b.reason = (
            f"{b.reason} [scene fitted to {target_secs}s from script page "
            f"geometry at {LINES_PER_PAGE} lines/{PAGE_SECS:.0f}s]"
        ).strip()

    overrun = sum(b.duration_secs for b in beats) - target_secs
    if overrun > 0.5:
        logger.warning(
            "Scene %d overruns its page budget by %.1fs — speech alone needs "
            "more time than the script's line count allows",
            beats[0].scene,
            overrun,
        )


def _group_consecutive_turns(lines: list[Line]) -> list[list[Line]]:
    """Group a beat's lines into speaker turns, preserving order."""
    turns: list[list[Line]] = []
    for line in lines:
        if turns and turns[-1][0].character == line.character:
            turns[-1].append(line)
        else:
            turns.append([line])
    return turns


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
    if floor <= beat.duration_secs:
        return

    if beat.duration_secs <= 0.0:
        # A beat produced by _split_speaker_turns carries no estimate of its
        # own; its duration is derived from the words it actually holds.
        note = (
            f"[duration {floor}s derived from {beat.spoken_words} spoken words "
            f"at {_WORDS_PER_SEC} words/sec plus {_PAUSE_PER_LINE}s per line]"
        )
    else:
        note = (
            f"[duration raised {beat.duration_secs}s → {floor}s: "
            f"{beat.spoken_words} spoken words across {len(beat.dialogue)} line(s) "
            f"cannot be delivered in less at {_WORDS_PER_SEC} words/sec]"
        )

    beat.reason = f"{beat.reason} {note}".strip()
    beat.duration_secs = floor
    beat.duration_source = "dialogue_floor"
