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
"the hairline, hat brim and jaw contour" (D-07). `tests/test_panel_prompt.py`
guards this at the value level; a live tracer run against `gemini-3.1-
flash-image` on s2b7 (04-01 Task 1) drew the eyes fully rendered anyway —
this wording is [ASSUMED] and expected to be revised by 04-02 after the
scene-2 tracer batch (D-09).

This module builds out across Plan 04-01's tasks: Task 1 wired the shot
size mapping table and the close-up branch through the tracer beat (s2b7,
a dialogue beat, scene 2). Task 2 (this pass) fills in the wide/medium
framing and facial clauses, the no-character path, and the
unrecognised-type fallback.
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

_DEFAULT_SHOT_SIZE = "medium"


def shot_size_for(beat: dict[str, Any]) -> tuple[str, str]:
    """Derive the shot size for `beat` from its type alone (D-01).

    Returns (shot_size, reason) — the reason names the beat type and the
    mapping rule, following `duration_source`'s precedent of carrying the
    rule that produced the value (D-04). An unrecognised beat type falls
    back to medium rather than raising, and says so in its reason — this
    corpus's three known types never miss, but a fifth-scene rewrite adding
    a new beat type must not crash the whole run over a naming choice.
    """
    beat_type = beat.get("type", "")
    size = SHOT_SIZE_BY_BEAT_TYPE.get(beat_type)
    if size is None:
        return (
            _DEFAULT_SHOT_SIZE,
            f"beat type {beat_type!r} is not one of "
            f"{sorted(SHOT_SIZE_BY_BEAT_TYPE)} — falling back to shot size "
            f"{_DEFAULT_SHOT_SIZE!r} (D-01 default)",
        )
    return size, f"beat type {beat_type!r} maps to shot size {size!r} (D-01)"


_FRAMING_SENTENCE = {
    "wide": (
        "This is a wide shot: the whole room is visible and the figures in "
        "it read small and distant, the space itself filling most of the "
        "frame."
    ),
    "medium": (
        "This is a medium shot: the figures are held from roughly the "
        "waist up, with enough room behind them to place the action."
    ),
    "close-up": (
        "This is a close-up: one head and shoulders fills most of the "
        "frame, and the room behind is reduced to a few plain lines."
    ),
}

# The proven wording from asset_generator._subject_note's minor-character
# branch (03-ART-REVIEW.md's second pass, D-06 of Phase 3) — carried
# forward unchanged for wide/medium panels, never paraphrased.
_BLANK_FACE_CLAUSE = (
    "Where the face sits, the outline traces one continuous blank plane "
    "bounded only by the hairline and jaw contour — as bare and unmarked "
    "as the open background itself, with no eyebrow, eye, nose or mouth "
    "line interrupting that plane anywhere."
)

# The new piece this phase adds — three lines shown, the eyes left blank,
# without naming the eye's own anatomy as the thing being left out
# (see the eye-anatomy guard note in the module docstring).
_CLOSEUP_FACE_CLAUSE = (
    "Where the face sits, the outline draws three simple lines: a brow "
    "line above the eyes, a single mouth line, and a short nose line down "
    "the center of the face. The eyes themselves stay part of the same "
    "blank, undrawn plane as the rest of the face, carrying no "
    "interrupting line of their own anywhere in that space."
)

# For a beat naming no characters — the last rule in the prompt should be
# one that applies, so this closes the prompt instead of a facial clause.
_BLANK_ROOM_CLAUSE = (
    "Every wall, prop, door, plaque, sign and background surface in the "
    "room stays a plain, blank outline shape, carrying no lettering of "
    "its own anywhere in the frame."
)


def facial_clause_for(shot_size: str, has_characters: bool) -> tuple[str, str, str]:
    """Return (clause, facial_features, facial_features_reason).

    `facial_features` records what the clause shows: "none" for wide/
    medium, "brow_mouth_nose" for close-up, "not_applicable" when the beat
    names no character — the rule that lands last in the prompt (D-06)
    must be one that actually applies to the picture.
    """
    if not has_characters:
        return (
            _BLANK_ROOM_CLAUSE,
            "not_applicable",
            "beat names no characters — no facial clause emitted, the "
            "blank-surface room clause closes the prompt instead",
        )
    if shot_size == "close-up":
        return (
            _CLOSEUP_FACE_CLAUSE,
            "brow_mouth_nose",
            "close-up shot size shows brow, mouth and nose lines only; "
            "the eyes stay part of the blank face plane (D-05, [ASSUMED] "
            "— pending validation on scene 2's tracer batch, 04-02)",
        )
    return (
        _BLANK_FACE_CLAUSE,
        "none",
        f"{shot_size} shot size carries no facial features (D-05) — "
        f"wording is Phase 3's proven asset_generator._subject_note "
        f"clause, carried forward unchanged",
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
    has_characters = bool(beat.get("characters"))

    framing = _FRAMING_SENTENCE[shot_size]
    facial_clause, facial_features, facial_features_reason = facial_clause_for(
        shot_size, has_characters
    )

    prompt = "\n\n".join([STYLE_BLOCK, framing, f"Subject: {subject}", facial_clause])
    return prompt, facial_features, facial_features_reason
