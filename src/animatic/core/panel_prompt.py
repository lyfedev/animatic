"""Panel prompt composition — shot size derivation (D-01) and the prompt a
panel is generated from.

Shot size is a pure lookup from `beat["type"]`, never a model call and
never written back into `output/beats.json` (D-02): `shot_size_for` takes a
beat dict, returns a value, and mutates nothing, and no function in this
module opens the beat list for writing.

The facial rule is keyed off shot size, stated as positive prose, and
placed LAST in the assembled prompt (D-06) — the hardest-won lesson of
Phase 3: negations get rendered as literal text ("NO FACIALS" was painted
into a frame), and a rule stated mid-prompt loses to whatever follows it.
The close-up clause is this phase's one genuinely novel piece — Phase 3
never had to show three of four facial features while suppressing the
fourth, only ever full suppression. It deliberately does NOT name the
suppressed eye's anatomy (no "iris", "pupil", "eyelid", "eyebrow-arch") —
naming an object as absent is still naming it, the same mistake that put a
hat on every character when the blank-face wording bounded the face by
"the hairline, hat brim and jaw contour" (D-07).

This module builds out across Plan 04-01's tasks: Task 1 wires the shot
size mapping table and the close-up branch through the tracer beat (s2b7,
a dialogue beat, scene 2). Task 2 fills in the wide/medium framing and
facial clauses, the no-character path, and the unrecognised-type fallback.
"""

from __future__ import annotations

from typing import Any

from animatic.core.style import STYLE_BLOCK, _strip_on_screen_text

# Bumped by hand whenever a clause in this module changes. Part of the
# panel cache key (panel_generator.panel_cache_key) so a wording fix
# redraws every panel on the next ordinary run instead of requiring a
# manual --force — Phase 3's own regression history is the reason: the
# same beat and the same slot art produced a passing and then a failing
# image purely because the subject clause was reworded.
PROMPT_TEMPLATE_VERSION = "v1"

# Free, deterministic and defensible grammar across all 49 beats: the
# fight plays in wides and mediums, the exchanges play close (D-01).
SHOT_SIZE_BY_BEAT_TYPE = {
    "establishing": "wide",
    "action": "medium",
    "dialogue": "close-up",
}


def shot_size_for(beat: dict[str, Any]) -> tuple[str, str]:
    """Derive the shot size for `beat` from its type alone (D-01).

    Returns (shot_size, reason) — the reason names the beat type and the
    mapping rule, following `duration_source`'s precedent of carrying the
    rule that produced the value (D-04).
    """
    beat_type = beat.get("type", "")
    size = SHOT_SIZE_BY_BEAT_TYPE[beat_type]
    return size, f"beat type {beat_type!r} maps to shot size {size!r} (D-01)"


_CLOSEUP_FRAMING = (
    "This is a close-up: one head and shoulders fills most of the frame, "
    "and the room behind is reduced to a few plain lines."
)

# The new piece this phase adds — three lines shown, the eyes left blank,
# without naming the eye's own anatomy as the thing being left out.
_CLOSEUP_FACE_CLAUSE = (
    "Where the face sits, the outline draws three simple lines: a brow "
    "line above the eyes, a single mouth line, and a short nose line down "
    "the center of the face. The eyes themselves stay part of the same "
    "blank, undrawn plane as the rest of the face, carrying no "
    "interrupting line of their own anywhere in that space."
)


def build_panel_prompt(beat: dict[str, Any], shot_size: str) -> tuple[str, str, str]:
    """Assemble the full panel prompt for one beat at one shot size.

    Order: the shared STYLE_BLOCK imported from style.py (never a
    panel-specific variant — Phase 3 D-08), the framing sentence for
    `shot_size`, the subject, then the facial-feature rule LAST (D-06).

    The subject is `beat["content"]` run through `style._strip_on_screen_text`
    first (D-12) — never `beat["dialogue"][*]["line"]` (quoted lettering a
    script wants heard, not drawn) and never `beat["scene_heading"]` (the
    extractor's own invented text, wrong for scene 2).

    Returns (prompt, facial_features, facial_features_reason) so the caller
    can record the rule alongside the value it produced (D-04's
    duration_source precedent).
    """
    subject = _strip_on_screen_text(beat.get("content", "")).strip()

    if shot_size != "close-up":
        raise NotImplementedError(
            f"shot size {shot_size!r} has no framing/facial clause yet — "
            f"Task 2 fills in wide and medium"
        )

    framing = _CLOSEUP_FRAMING
    facial_clause = _CLOSEUP_FACE_CLAUSE
    facial_features = "brow_mouth_nose"
    facial_features_reason = (
        "close-up shot size shows brow, mouth and nose lines only; the "
        "eyes stay part of the blank face plane (D-05)"
    )

    prompt = "\n\n".join([STYLE_BLOCK, framing, f"Subject: {subject}", facial_clause])
    return prompt, facial_features, facial_features_reason
