"""Music cues, found in the screenplay's own words.

ROADMAP criterion 4 is "music is generated where the script specifies a music
cue" — *the script*, not the beat list. So detection reads the PDF scene text
directly. Screenplays announce sound in caps ("BLASTING MUSIC", "the CRACKLING
MUSIC BEGINS"), which is a convention, not a Rocky fact: any script that names
a radio, a record, a band or a song in a scene produces a cue here, and a
script that names none produces none.

The cue is then attached to the beats of that scene whose content echoes it,
so the music lands on the moment the script put it on rather than under the
whole scene.

**Named works are stripped before the prompt is built.** A screenplay names
real records — this one calls for a specific 1958 single by title. Handing
that title to a music model asks it to reproduce a copyrighted recording. The
title is removed and the cue is described by its *staging* instead: the
instrument or device it plays from, the room, and the action around it. What
comes back is original music that fits the scene, which is what the cut needs
anyway.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from animatic.core.pdf_extractor import extract_scenes

# Sound sources a screenplay names when it wants music. Matched on the scene
# text, so "listens to a portable RADIO that is BLASTING MUSIC" and "places an
# old 45 RPM record on a battered phonograph" both register.
_CUE_RE = re.compile(
    r"\b(music|song|record player|phonograph|jukebox|juke box|radio|45 rpm|"
    r"band plays|orchestra|anthem|hymn)\b",
    re.I,
)

# A screenplay puts the title of a real recording in quotes. Removed before
# any prompt is built — see the module docstring.
_NAMED_WORK_RE = re.compile(r"[\"“]([^\"”]{2,80})[\"”]")

# Words that describe how the music reaches the room. These survive into the
# prompt; the title does not.
_STAGING_TERMS = (
    "radio", "phonograph", "record", "jukebox", "juke box", "portable",
    "battered", "crackling", "blasting", "loud", "old", "45 rpm",
)


@dataclass
class MusicCue:
    """One music cue: where the script asks for it, and which beats carry it."""

    scene: int
    scene_heading: str
    cue_lines: list[str]
    beat_ids: list[str] = field(default_factory=list)
    total_secs: float = 0.0

    @property
    def cue_id(self) -> str:
        return f"scene{self.scene}"

    @property
    def reason(self) -> str:
        quoted = " ".join(self.cue_lines)
        return (
            f"script scene {self.scene} specifies a music cue: "
            f"{quoted[:180]!r}; carried by beats {', '.join(self.beat_ids)} "
            f"({self.total_secs:.1f}s)"
        )


def find_music_cues(
    pdf_path: str | Path,
    beats: list[dict[str, Any]],
    first_n: int = 8,
) -> list[MusicCue]:
    """Music cues in the script, each mapped to the beats that carry it."""
    scenes = extract_scenes(pdf_path, first_n=first_n)

    cues: list[MusicCue] = []
    for scene_num, text in scenes.items():
        cue_lines = [s for s in _sentences(text) if _CUE_RE.search(s)]
        if not cue_lines:
            continue

        scene_beats = [b for b in beats if b["scene"] == scene_num]
        heading = scene_beats[0].get("scene_heading", "") if scene_beats else ""
        cue = MusicCue(scene=scene_num, scene_heading=heading, cue_lines=cue_lines)
        carriers = _beats_carrying(cue_lines, scene_beats)
        cue.beat_ids = [b["beat_id"] for b in carriers]
        cue.total_secs = round(sum(b["duration_secs"] for b in carriers), 2)
        if cue.beat_ids:
            cues.append(cue)

    return cues


def _sentences(scene_text: str) -> list[str]:
    """Whole sentences from PDF scene text.

    A PDF hard-wraps prose mid-sentence, so matching per line yields
    fragments — "as the CRACKLING MUSIC BEGINS, Rocky picks up his" is where
    one line ended, not where the thought did. Unwrapping first means a cue
    reaches the prompt as something a reader would recognise as a sentence.
    """
    unwrapped = re.sub(r"\s*\n\s*", " ", scene_text)
    unwrapped = re.sub(r"\s{2,}", " ", unwrapped)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", unwrapped)
    return [p.strip() for p in parts if p.strip()]


def _beats_carrying(
    cue_lines: list[str], scene_beats: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Beats whose own content echoes the cue.

    Matched on the sound words the cue itself used, so the music sits under
    the moment the script staged it. If nothing in the scene echoes the cue,
    the whole scene carries it — the script said there is music in this room,
    and a cue with no beats would silently drop it.
    """
    cue_terms = {
        t.lower()
        for line in cue_lines
        for t in _CUE_RE.findall(line)
    }
    carriers = [
        b
        for b in scene_beats
        if any(term in b["content"].lower() for term in cue_terms)
    ]
    return carriers or scene_beats


def strip_named_works(text: str) -> str:
    """Remove quoted titles of real recordings from cue text."""
    return re.sub(r"\s{2,}", " ", _NAMED_WORK_RE.sub("", text)).strip()


def build_music_prompt(cue: MusicCue) -> str:
    """Describe the cue by its staging, never by the work it names.

    The prompt carries the room, the device the music plays from, and the
    action it plays under — everything the cut needs to make the music feel
    diegetic — and nothing that asks for a specific existing recording.
    """
    staged = strip_named_works(" ".join(cue.cue_lines)).lower().rstrip(". ")
    devices = sorted({t for t in _STAGING_TERMS if t in staged})

    return (
        "Compose an original instrumental cue for a film scene. "
        f"It is heard inside this location: {cue.scene_heading.lower()}. "
        f"It reaches the room this way: {staged}. "
        + (f"Match the character of that source — {', '.join(devices)}. " if devices else "")
        + "Write original music only: do not imitate, quote or arrange any "
        "existing recording, and use no vocals. Keep it in the background of "
        "a scene, with room for dialogue over the top."
    )
