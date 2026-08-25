"""Pin panel_prompt.py's shot-size mapping and facial clauses at the value
level.

Asserts on the imported constants' values and the built prompt/clause
strings, never by grepping panel_prompt.py's source — an explanatory
comment naming the old wording must not fail its own test
(tests/test_style.py's own module docstring states why).
"""

from __future__ import annotations

import re

import pytest

from animatic.core.panel_prompt import (
    PROMPT_TEMPLATE_VERSION,
    SHOT_SIZE_BY_BEAT_TYPE,
    build_panel_prompt,
    facial_clause_for,
    shot_size_for,
)
from animatic.core.style import STYLE_BLOCK

# Same source as test_style.py's list, imported directly rather than
# retyped — built from the bug where bounding the face plane by a piece of
# headwear put one on every character in the film including a boxer in
# trunks.
from tests.test_style import _HEADWEAR_AND_GARMENT_NOUNS

_BARE_NEGATION_STARTS = ("no ", "never ", "don't ", "do not ", "avoid ", "without ")

# The close-up clause must not name the eye's own anatomy even as a thing
# left absent — structurally the same move as bounding the face by "the
# hairline, hat brim and jaw contour," which put a hat on every character.
# Naming an object as absent is still naming it.
_EYE_ANATOMY_NOUNS = ("iris", "pupil", "eyelid", "eyebrow-arch")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in text.split(".") if s.strip()]


def _assert_no_bare_negation_or_allcaps(text: str, label: str) -> None:
    for sentence in _sentences(text):
        lowered = sentence.lower()
        assert not lowered.startswith(_BARE_NEGATION_STARTS), (
            f"{label}: bare negation reads as a caption to render: {sentence!r}"
        )
        words = sentence.split()
        first_word = words[0] if words else ""
        assert not (len(first_word) > 1 and first_word.isupper()), (
            f"{label}: all-caps imperative fragment reads as a caption to render: {sentence!r}"
        )


def _assert_no_forbidden_nouns(text: str, nouns: tuple[str, ...], label: str) -> None:
    lowered = text.lower()
    named = [w for w in nouns if re.search(rf"\b{re.escape(w)}s?\b", lowered)]
    assert not named, f"{label} names {named} — naming an object draws it"


# ---------------------------------------------------------------------------
# shot_size_for — D-01, D-02, D-04
# ---------------------------------------------------------------------------

def test_establishing_maps_to_wide():
    size, reason = shot_size_for({"type": "establishing"})
    assert size == "wide"
    assert reason


def test_action_maps_to_medium():
    size, reason = shot_size_for({"type": "action"})
    assert size == "medium"
    assert reason


def test_dialogue_maps_to_closeup():
    size, reason = shot_size_for({"type": "dialogue"})
    assert size == "close-up"
    assert reason


def test_shot_size_reason_names_beat_type_and_rule():
    for beat_type in ("establishing", "action", "dialogue"):
        _, reason = shot_size_for({"type": beat_type})
        assert beat_type in reason


def test_unrecognised_beat_type_falls_back_to_medium_not_raise():
    size, reason = shot_size_for({"type": "montage"})
    assert size == "medium"
    assert "montage" in reason
    assert reason


def test_shot_size_for_does_not_mutate_the_beat_dict():
    beat = {"type": "dialogue", "beat_id": "s2b7"}
    original = dict(beat)
    shot_size_for(beat)
    assert beat == original


def test_shot_size_by_beat_type_covers_all_three_known_types():
    assert SHOT_SIZE_BY_BEAT_TYPE == {
        "establishing": "wide",
        "action": "medium",
        "dialogue": "close-up",
    }


# ---------------------------------------------------------------------------
# facial_clause_for — D-05, D-06, D-07, and the eye-anatomy guard
# ---------------------------------------------------------------------------

def test_wide_and_medium_facial_clause_names_features_as_absent():
    for shot_size in ("wide", "medium"):
        clause, facial_features, reason = facial_clause_for(shot_size, has_characters=True)
        lowered = clause.lower()
        assert "blank" in lowered
        for feature in ("eyebrow", "eye", "nose", "mouth"):
            assert feature in lowered, f"{shot_size}: {feature} must be named as absent"
        assert facial_features == "none"
        assert reason


def test_closeup_facial_clause_shows_brow_mouth_nose():
    clause, facial_features, reason = facial_clause_for("close-up", has_characters=True)
    lowered = clause.lower()
    assert "brow" in lowered
    assert "mouth" in lowered
    assert "nose" in lowered
    assert facial_features == "brow_mouth_nose"
    assert reason


def test_closeup_facial_clause_keeps_eyes_part_of_the_blank_plane():
    clause, _, _ = facial_clause_for("close-up", has_characters=True)
    lowered = clause.lower()
    assert "blank" in lowered
    assert "eye" in lowered


@pytest.mark.parametrize("shot_size", ["wide", "medium", "close-up"])
def test_facial_clause_names_no_headwear_or_garment(shot_size):
    clause, _, _ = facial_clause_for(shot_size, has_characters=True)
    _assert_no_forbidden_nouns(clause, _HEADWEAR_AND_GARMENT_NOUNS, f"{shot_size} facial clause")


def test_closeup_facial_clause_names_no_eye_anatomy_noun():
    """The eye-anatomy guard: naming iris/pupil/eyelid/eyebrow-arch as
    absent is structurally the same mistake as naming a hat brim as absent
    — a value-level test must catch it, not just a later visual review."""
    clause, _, _ = facial_clause_for("close-up", has_characters=True)
    _assert_no_forbidden_nouns(clause, _EYE_ANATOMY_NOUNS, "close-up facial clause")


@pytest.mark.parametrize("shot_size", ["wide", "medium", "close-up"])
def test_facial_clause_has_no_bare_negation_or_allcaps(shot_size):
    clause, _, _ = facial_clause_for(shot_size, has_characters=True)
    _assert_no_bare_negation_or_allcaps(clause, f"{shot_size} facial clause")


def test_no_characters_emits_no_facial_clause_and_records_not_applicable():
    clause, facial_features, reason = facial_clause_for("wide", has_characters=False)
    assert facial_features == "not_applicable"
    assert reason
    lowered = clause.lower()
    assert "blank" in lowered
    for feature in ("eyebrow", "eyelid", "iris", "pupil"):
        assert feature not in lowered


def test_no_characters_clause_has_no_bare_negation_or_allcaps():
    clause, _, _ = facial_clause_for("medium", has_characters=False)
    _assert_no_bare_negation_or_allcaps(clause, "no-character room clause")


# ---------------------------------------------------------------------------
# build_panel_prompt — ordering, D-06, D-12
# ---------------------------------------------------------------------------

def _beat(**overrides):
    base = {
        "beat_id": "s2b7", "scene": 2, "beat": 7, "type": "dialogue",
        "content": "The Cornerman criticizes Rocky's sluggish performance.",
        "duration_secs": 6.0, "characters": ["CORNERMAN"], "dialogue": [],
    }
    base.update(overrides)
    return base


def test_prompt_starts_with_style_block():
    for shot_size in ("wide", "medium", "close-up"):
        beat = _beat(type={"wide": "establishing", "medium": "action", "close-up": "dialogue"}[shot_size])
        prompt, _, _ = build_panel_prompt(beat, shot_size)
        assert prompt.startswith(STYLE_BLOCK)


def test_facial_clause_is_last_for_a_beat_with_characters():
    beat = _beat(characters=["CORNERMAN"])
    prompt, facial_features, _ = build_panel_prompt(beat, "close-up")
    clause, _, _ = facial_clause_for("close-up", has_characters=True)
    assert prompt.rstrip().endswith(clause.rstrip())
    assert facial_features == "brow_mouth_nose"


def test_no_facial_clause_and_blank_room_clause_last_for_beat_without_characters():
    beat = _beat(characters=[], content="The ring stands empty under the lights.")
    prompt, facial_features, reason = build_panel_prompt(beat, "wide")
    room_clause, _, _ = facial_clause_for("wide", has_characters=False)
    assert prompt.rstrip().endswith(room_clause.rstrip())
    assert facial_features == "not_applicable"
    assert reason


def test_prompt_subject_never_carries_dialogue_lines():
    beat = _beat(
        content="The Cornerman criticizes Rocky's sluggish performance.",
        dialogue=[{"character": "CORNERMAN", "line": "Ya waltzin' -- Give the suckers some action."}],
    )
    prompt, _, _ = build_panel_prompt(beat, "close-up")
    assert "waltzin" not in prompt
    assert "suckers" not in prompt


def test_prompt_subject_never_carries_scene_heading():
    beat = _beat(scene_heading="INT. BOXING CLUB - NIGHT")
    prompt, _, _ = build_panel_prompt(beat, "close-up")
    assert "BOXING CLUB" not in prompt


def test_prompt_strips_on_screen_text_directives_from_content():
    beat = _beat(
        content='SUPERIMPOSE OVER ACTION: "NOVEMBER 12, 1975". The trainer watches Rocky spar.',
        type="action",
    )
    prompt, _, _ = build_panel_prompt(beat, "medium")
    assert "november" not in prompt.lower()
    assert "superimpose" not in prompt.lower()


@pytest.mark.parametrize("shot_size", ["wide", "medium", "close-up"])
def test_prompt_has_no_bare_negation_or_allcaps_sentence(shot_size):
    beat = _beat(type={"wide": "establishing", "medium": "action", "close-up": "dialogue"}[shot_size])
    prompt, _, _ = build_panel_prompt(beat, shot_size)
    _assert_no_bare_negation_or_allcaps(prompt, f"{shot_size} prompt")


def test_prompt_template_version_is_a_nonempty_constant():
    assert PROMPT_TEMPLATE_VERSION
