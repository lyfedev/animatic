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
guards this at the value level.

This module builds out across two plans. Plan 04-01 wired the shot size
mapping table and all three facial branches through a single tracer beat
(s2b7). Its first live call drew the eyes fully rendered anyway (iris,
pupil, eyelid crease) and separately let a character panel close on its
facial clause with no lettering rule present at all ("TRAIN" painted onto
a wall sign) — both fixed before 04-02 began (PROMPT_TEMPLATE_VERSION
"v1"): the close-up clause stopped naming eyes in either direction, and
the room rule was made to close every prompt, not only the no-character
ones. 04-02's scene-2 batch (19 beats) then ran the plan's full two-pass
revision budget. "v2" made both rules apply to every figure/surface in the
frame rather than an implicit singular one — real but partial improvement.
"v3", the last pass the plan allows, named the two contexts that still
failed directly rather than trusting a broader rule to cover them by
implication: a packed crowd and the moment of impact for the blank-face
rule, and a familiar/iconic garment the model already "knows" the
lettering for, for the room rule. Any defect still open past "v3" is
carried in `.planning/WINDOWS.md`, not chased further (D-09's ceiling).
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
#
# v2 (04-02's scene-2 review pass): two defects found judging live scene-2
# output against the six review points. (1) The blank-face clause held for
# a single figure but not reliably for two figures trading blows in the
# same medium shot (s2b2, s2b16) or a crowd (s2b3) — full brows, eyes and
# mouths were drawn on some figures while others in the same frame stayed
# blank, as if the rule bound only to "the" (singular) face. (2) The room
# rule's noun list never named garments, and a robe came back lettered
# "ROCKY" (s2b17) — the same class of leak the room rule was written to
# close for walls and signs, just on a surface the list didn't cover.
#
# v3 (04-02, second and LAST revision pass — the plan's two-pass ceiling):
# regenerating scene 2 under v2 showed real but partial improvement (a
# background boxer and a referee that were fully-featured under v1 came
# back blank), but two failure modes survived clause-list wording: (1) a
# whole crowd shouting (s2b3) and the figure absorbing a punch (s2b16)
# still carried full faces — the v2 wording named "several trading blows"
# but not a crowd, and named no exception for the moment of impact, where
# the pull toward an expressive face is strongest. (2) "ROCKY" was still
# lettered on the robe in s2b17 even with "garment" added to the room
# rule's noun list — `output/beats.json` s2b17 literally quotes the robe's
# real lettering ('The Italian Stallion'), which `_strip_on_screen_text`
# does strip from the subject clause, but the model supplied "ROCKY" from
# its own knowledge of the source film rather than from the prompt text,
# so a same-sentence noun addition wasn't emphatic enough to override it.
# Both clauses gained a dedicated, explicit exception naming the specific
# context that was failing — a crowd, an impact, a familiar/iconic
# garment — rather than trusting a longer noun list to cover it by
# implication.
PROMPT_TEMPLATE_VERSION = "v3"

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

# Started as asset_generator._subject_note's minor-character wording
# (03-ART-REVIEW.md's second pass, D-06 of Phase 3), proven there for one
# figure at a time. Scene 2's medium shots put two figures trading blows in
# the same frame, and the singular "the face" read as binding to one of
# them — the other came back with a full brow, eyes and mouth (s2b2, s2b16;
# s2b3's crowd showed the same split). Reworded at v2 to state the rule
# holds for every head in the frame, not just one — real but partial
# improvement (a background figure went blank that hadn't before), but a
# packed crowd (s2b3) and the figure taking the punch at the story's most
# dramatic beat (s2b16) still came back fully featured. v3 names those two
# contexts directly rather than trusting "several trading blows" to cover
# them by implication — the same lesson D-06 already taught once: a rule
# that has to be inferred loses to a rule that is stated.
_BLANK_FACE_CLAUSE = (
    "Where each figure's face sits in the frame — every head present, "
    "whether the scene holds one figure alone, two trading blows, or a "
    "whole crowd packed shoulder to shoulder — the outline traces one "
    "continuous blank plane bounded only by the hairline and jaw contour, "
    "as bare and unmarked as the open background itself, with no eyebrow, "
    "eye, nose or mouth line interrupting that plane on any of them, no "
    "matter how strong the reaction or how hard the moment of impact."
)

# The new piece this phase adds — three lines shown, the eyes left blank,
# without naming the eye's own anatomy as the thing being left out
# (see the eye-anatomy guard note in the module docstring).
# First live attempt drew a fully rendered eye — iris, pupil, eyelid crease —
# while getting the three lines right. The clause named "the eyes" twice
# ("a brow line above the eyes", "The eyes themselves"), and D-07's lesson is
# that naming a thing draws it, whether it is named as present or as absent.
# This wording never refers to them at all: it states the three lines that ARE
# drawn and describes the rest of the face as one uninterrupted plane.
_CLOSEUP_FACE_CLAUSE = (
    "Where the face sits, the outline draws exactly three lines and no "
    "others: one brow line across the upper face, one mouth line, and one "
    "short nose line down the centre. Every other part of that face is one "
    "continuous blank plane, unbroken from hairline to jaw and as bare and "
    "unmarked as the open background itself."
)

# Applies to EVERY panel, not only the ones with no characters. The first
# live panel came back with the word "TRAIN" lettered on a wall sign, because
# a character panel closed on its facial clause and this rule was never in the
# prompt at all. Panels render rooms whether or not a person is standing in
# them, so the room rule is appended to every prompt and lands last (D-06).
#
# v2 added "garment" to the noun list — a robe still came back lettered
# "ROCKY" (s2b17). The beat itself quotes the robe's real lettering
# ('The Italian Stallion'), which _strip_on_screen_text does remove from
# the subject clause, so the model was not reading the word from the
# prompt at all — it supplied "ROCKY" from its own knowledge of the source
# film. A same-sentence noun addition wasn't emphatic enough to override
# that outside knowledge, so v3 gives the garment rule its own sentence and
# names the failure mode directly: stay blank even when the garment is a
# familiar or iconic one the model already "knows" the lettering for.
_BLANK_ROOM_CLAUSE = (
    "Every wall, prop, door, plaque, sign and background surface in the "
    "room stays a plain, blank outline shape, carrying no lettering of its "
    "own anywhere in the frame. Every garment a figure wears or puts on "
    "follows the same rule, its outline staying just as plain and blank — "
    "no name, initial or number sewn, printed or painted into it — even "
    "when it is a familiar or iconic garment whose real lettering is well "
    "known."
)


# Appended ONLY when a panel is generated from reference plates. A seed image
# can overrule a prompt — the S-03 spike returned a plate-conditioned panel
# with facial features despite the clause being present — so when plates are
# supplied the rule is restated after them and the plates are demoted to what
# they are: a source for build, clothing and fittings, not for the face.
_PLATE_CONDITIONING_CLAUSE = (
    "The supplied drawings are the source for each figure's build and "
    "clothing and for the room's fittings, and for nothing else. Where a face "
    "sits in this new frame, follow the face rule stated above exactly as it "
    "is written, whatever the supplied drawings happen to show."
)


def build_conditioned_prompt(base_prompt: str) -> str:
    """The prompt for a plate-seeded panel: the base, then the plate rule.

    Lands last for the reason D-06 established — a rule stated before another
    rule loses to it — and this is the one place where the thing it has to beat
    is not text at all but an image.
    """
    return f"{base_prompt}\n\n{_PLATE_CONDITIONING_CLAUSE}"


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
            "the eyes stay part of the blank face plane (D-05; validated "
            "against 9 of 10 sampled live scene-2 close-ups, 04-02)",
        )
    return (
        _BLANK_FACE_CLAUSE,
        "none",
        f"{shot_size} shot size carries no facial features (D-05) — "
        f"wording started from Phase 3's asset_generator._subject_note "
        f"clause and was reworded in 04-02 to bind explicitly to every "
        f"figure in the frame, not one implicit face",
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

    # The room rule closes EVERY prompt. A character panel used to end on its
    # facial clause with no lettering rule anywhere, and came back with "TRAIN"
    # lettered on a wall. When a facial clause applies it sits second-to-last,
    # so the two rules that actually govern the picture are the last things
    # said (D-06).
    parts = [STYLE_BLOCK, framing, f"Subject: {subject}"]
    if facial_clause and facial_clause != _BLANK_ROOM_CLAUSE:
        parts.append(facial_clause)
    parts.append(_BLANK_ROOM_CLAUSE)
    prompt = "\n\n".join(parts)
    return prompt, facial_features, facial_features_reason
