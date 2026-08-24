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

from animatic.core.slot_resolver import Slot

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


def build_slot_prompt(slot: Slot, note: str) -> str:
    """Build the full generation prompt for one slot.

    Returns the shared style block, a blank line, then the slot's subject
    clause — never a per-slot restatement of the style rules, so every
    generated asset draws from the same wording (D-08).
    """
    return f"{STYLE_BLOCK}\n\nSubject: {note}"
