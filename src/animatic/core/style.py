"""Shared style prompt for generated slot art (D-08).

One style definition drives consistency across every generated slot rather
than per-slot prompt wording.

`STYLE_BLOCK` actively suppresses the failure modes observed in the Google
AI smoke test (2026-08-24, `output/smoke/panel_test_0.png`): the model
returned greyscale with heavy shading instead of black line art on white,
added storyboard chrome (a spiral notebook binding and a panel caption), and
rendered instruction words into the frame as artwork (the literal words
"NO FACIALS"). Two rules produce the wording (D-09):

1. Every constraint is stated as positive prose describing the finished
   picture, never as a negation and never as a short all-caps imperative —
   an imperative fragment reads to the model like a caption to render.
2. The word that triggered the notebook-and-caption chrome in this
   project's own smoke test is never used anywhere in this module. Do not
   add it back in a comment or docstring near the constant either — a test
   pins the constant's *value*, but the failure this guards against is a
   model behavior, not a test technicality, so keep the word out of the
   prompt text entirely.
"""

from __future__ import annotations

import re
from typing import Any

from animatic.core.slot_resolver import Slot

# Colour words are stripped from any text that reaches the prompt. A colour
# in a location's own name reads to the model as an instruction to break the
# monochrome rule — observed on this project's first tracer, where "BLUE DOOR
# FIGHT CLUB" produced a blue-filled door. General defence, not a per-slot fix.
_COLOUR_WORD_RE = re.compile(
    r"\b(black|white|red|blue|green|yellow|orange|purple|pink|brown|"
    r"grey|gray|gold|silver)\b",
    re.IGNORECASE,
)

# Screenplay text that asks for words ON SCREEN. Beat content reproduces these
# faithfully, and handing one to an image model is handing it a caption to
# render: the beat "SUPERIMPOSE OVER ACTION: 'NOVEMBER 12, 1975 - PHILADELPHIA'"
# produced exactly that sentence painted across the frame in 60pt type. Every
# screenplay has these, so strip them rather than special-casing this beat.
_ON_SCREEN_TEXT_RE = re.compile(
    r"\b(superimpose|super|title|caption|subtitle|insert|credits?|"
    r"chyron|legend|card)\b[^.]*\.?",
    re.IGNORECASE,
)
# Quoted spans are the other way words reach the frame — a script quotes the
# lettering it wants to see ("ANIMAL TOWN PET SHOP", "The Italian Stallion").
_QUOTED_RE = re.compile(r"[\"\u201c\u2018']([^\"\u201d\u2019']{2,60})[\"\u201d\u2019']")

# How many of a slot's beats are summarised into its subject clause. Enough to
# characterise the space, few enough to stay a description rather than a plot.
_MAX_DESCRIPTION_BEATS = 3

STYLE_BLOCK = (
    "Style: a single flat illustration drawn in solid black ink outlines on "
    "a plain white background, in the manner of a clean animation "
    "pre-visualisation drawing. Every line is the same confident, even "
    "weight, from the figure's silhouette to the smallest prop. The picture "
    "holds exactly two tones from edge to edge — open white ground and "
    "solid black outline — so every surface, sign and object in the scene "
    "reads as a bare linework shape carrying its own contour and nothing "
    "else. The illustration sits alone on the page and fills the frame "
    "edge to edge as a plain drawing in open white margins. Every wall, "
    "prop, door, plaque, sign and background surface stays a plain, blank "
    "outline shape — the same bare linework whether it is brick, wood, "
    "metal or paper — so the only marks anywhere in the frame are the "
    "drawn contour lines of the subject itself."
)


def describe_slot(slot: Slot, beats: dict[str, Any]) -> str:
    """Describe a slot from the beats that use it, not from its name.

    The slot name alone is a poor subject. Stripping the colour word out of
    "BLUE DOOR FIGHT CLUB" leaves "DOOR FIGHT CLUB", and the model drew a
    door — architecturally reasonable, and nothing like the room the script
    describes. The beat list already carries that room in prose ("the trashy,
    dimly lit fight club environment with a tiny boxing ring", "ringside
    spectators clamor for blood in the thick smoke"), so use it.

    Script-derived, so it scales to any screenplay and needs no per-slot
    wording. Re-running after the beats change re-describes the slot.

    Intended for LOCATION slots. A beat's content describes the action, not
    the people in it, so two characters sharing a scene resolve to the same
    sentence — `rocky` and `black_fighter` came back byte-identical. Callers
    keep using the character's name as its own subject.
    """
    wanted = set(slot.beat_ids or [])
    lines = [
        b.get("content", "").strip()
        for b in beats.get("beats", [])
        if b.get("beat_id") in wanted and b.get("content")
    ]
    if not lines:
        return _strip_colour(slot.display_name).lower()
    joined = " ".join(lines[:_MAX_DESCRIPTION_BEATS])
    return _strip_colour(_strip_on_screen_text(joined)).rstrip(". ").lower()


def _strip_colour(text: str) -> str:
    return re.sub(r"\s+", " ", _COLOUR_WORD_RE.sub("", text)).strip()


def _strip_on_screen_text(text: str) -> str:
    """Remove anything that asks for words to appear in the picture.

    Two sources: title-card directives (SUPERIMPOSE, INSERT, CREDITS) and
    quoted lettering. Both are legitimate screenplay content and both become
    literal painted text when handed to an image model.
    """
    return _QUOTED_RE.sub("", _ON_SCREEN_TEXT_RE.sub("", text))


def build_slot_prompt(slot: Slot, note: str) -> str:
    """Build the full generation prompt for one slot.

    Returns the shared style block, a blank line, then the slot's subject
    clause — never a per-slot restatement of the style rules, so every
    generated asset draws from the same wording (D-08).
    """
    return f"{STYLE_BLOCK}\n\nSubject: {note}"
