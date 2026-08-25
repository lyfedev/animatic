"""Pin D-09 at the value level.

Asserts on the imported STYLE_BLOCK constant's value, not by grepping
style.py's source — an explanatory comment in style.py naming the banned
word must not fail its own test.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from animatic.core.style import STYLE_BLOCK, build_slot_prompt

# A bare negation or all-caps imperative fragment reads to the model like a
# caption to render — that phrasing is what got the literal words
# "NO FACIALS" painted into output/smoke/panel_test_0.png.
_BARE_NEGATION_STARTS = ("no ", "never ", "don't ", "do not ", "avoid ", "without ")


def test_style_block_never_says_the_chrome_triggering_word():
    """The word itself produced the spiral-notebook binding and panel caption
    in output/smoke/panel_test_0.png — never used anywhere in the prompt."""
    assert "storyboard" not in STYLE_BLOCK.lower()


def test_style_block_avoids_bare_negations_and_allcaps_imperatives():
    sentences = [s.strip() for s in STYLE_BLOCK.split(".") if s.strip()]
    assert sentences, "STYLE_BLOCK must have content"
    for sentence in sentences:
        lowered = sentence.lower()
        assert not lowered.startswith(_BARE_NEGATION_STARTS), (
            f"bare negation reads as a caption to render: {sentence!r}"
        )
        words = sentence.split()
        first_word = words[0] if words else ""
        assert not (len(first_word) > 1 and first_word.isupper()), (
            f"all-caps imperative fragment reads as a caption to render: {sentence!r}"
        )


def test_style_block_is_nonempty():
    assert STYLE_BLOCK.strip()


def test_build_slot_prompt_puts_style_block_first_then_subject():
    from animatic.core.slot_resolver import Slot

    slot = Slot(slot_id="rocky", slot_type="character", display_name="ROCKY")
    prompt = build_slot_prompt(slot, "a lone boxer")

    assert prompt.startswith(STYLE_BLOCK)
    assert "a lone boxer" in prompt


@patch("animatic.core.asset_generator.genai.Client")
def test_style_block_is_referenced_by_asset_generator(mock_client_cls):
    """The style block actually reaches the generate_content call.

    A regression guard against `asset_generator` accepting a prompt that
    never had the shared style block folded in (D-08) — not a grep of
    source, an assertion on the real call's `contents` argument.
    """
    from animatic.core.asset_generator import generate_slot_art
    from animatic.core.slot_resolver import Slot

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_part = MagicMock()
    mock_part.inline_data.data = b"fake-image-bytes"
    mock_part.inline_data.mime_type = "image/png"
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
    mock_client.models.generate_content.return_value = mock_response

    slot = Slot(slot_id="rocky", slot_type="character", display_name="ROCKY")
    prompt = build_slot_prompt(slot, "a lone boxer")
    generate_slot_art(slot, prompt)

    _, kwargs = mock_client.models.generate_content.call_args
    assert STYLE_BLOCK in kwargs["contents"]


# ---------------------------------------------------------------------------
# Slot descriptions come from beat content, and carry no on-screen text
# ---------------------------------------------------------------------------

def test_describe_slot_uses_beat_content_not_the_slot_name():
    """A slot name is a poor subject; the beats already describe the room.

    Regression guard: with only the name to go on, colour-stripping
    "BLUE DOOR FIGHT CLUB" left "DOOR FIGHT CLUB" and the model drew a door.
    """
    from animatic.core.slot_resolver import Slot
    from animatic.core.style import describe_slot

    slot = Slot(slot_id="int_gym", slot_type="location", display_name="BLUE DOOR GYM")
    slot.beat_ids = ["s1b1"]
    beats = {"beats": [
        {"beat_id": "s1b1", "content": "A tiny ring under dim overhead lights."},
    ]}
    out = describe_slot(slot, beats)
    assert "tiny ring" in out
    assert "overhead lights" in out


def test_describe_slot_strips_superimpose_directives():
    """Title-card text must never reach an image model.

    The beat "SUPERIMPOSE OVER ACTION: 'NOVEMBER 12, 1975 - PHILADELPHIA'"
    was rendered as that literal sentence across the frame in 60pt type.
    """
    from animatic.core.slot_resolver import Slot
    from animatic.core.style import describe_slot

    slot = Slot(slot_id="int_gym", slot_type="location", display_name="GYM")
    slot.beat_ids = ["s1b1"]
    beats = {"beats": [{
        "beat_id": "s1b1",
        "content": ("SUPERIMPOSE OVER ACTION: 'NOVEMBER 12, 1975 - PHILADELPHIA'. "
                    "The club has a tiny ring."),
    }]}
    out = describe_slot(slot, beats)
    assert "november" not in out
    assert "philadelphia" not in out
    assert "superimpose" not in out
    assert "tiny ring" in out


def test_describe_slot_strips_quoted_lettering():
    """A script quotes the lettering it wants on screen; the model paints it."""
    from animatic.core.slot_resolver import Slot
    from animatic.core.style import describe_slot

    slot = Slot(slot_id="ext_shop", slot_type="location", display_name="PET SHOP")
    slot.beat_ids = ["s5b4"]
    beats = {"beats": [{
        "beat_id": "s5b4",
        "content": 'He pauses at the "ANIMAL TOWN PET SHOP" and peers inside.',
    }]}
    out = describe_slot(slot, beats)
    assert "animal town" not in out
    assert "peers inside" in out


def test_describe_slot_falls_back_to_name_when_no_beats_match():
    from animatic.core.slot_resolver import Slot
    from animatic.core.style import describe_slot

    slot = Slot(slot_id="int_hall", slot_type="location", display_name="HALLWAY")
    slot.beat_ids = ["missing"]
    assert describe_slot(slot, {"beats": []}) == "hallway"


# ---------------------------------------------------------------------------
# Character world context — derived from the scenes a character appears in
# ---------------------------------------------------------------------------

def test_character_context_comes_from_the_locations_of_their_scenes():
    """A character's world is the location of the scenes they appear in.

    A bare name is ambiguous about the film: "BLACK FIGHTER" generated a
    soldier in a beret and tactical vest. Nothing here names a genre or a
    character — the same code yields a different world for a different script.
    """
    from animatic.core.slot_resolver import Slot
    from animatic.core.style import character_context

    char = Slot(slot_id="black_fighter", slot_type="character",
                display_name="BLACK FIGHTER")
    char.beat_ids = ["s2b2"]
    loc = Slot(slot_id="int_club", slot_type="location", display_name="INT. CLUB")
    loc.source_scenes = [2]
    loc.beat_ids = ["s2b2"]
    beats = {"beats": [
        {"beat_id": "s2b2", "scene": 2,
         "content": "A tiny boxing ring under dim overhead lights."},
    ]}
    out = character_context(char, [char, loc], beats)
    assert "boxing ring" in out


def test_character_context_never_carries_the_location_name():
    """Passing the location's proper name hand-lettered it onto a sign."""
    from animatic.core.slot_resolver import Slot
    from animatic.core.style import character_context

    char = Slot(slot_id="fighter", slot_type="character", display_name="FIGHTER")
    char.beat_ids = ["s2b1"]
    loc = Slot(slot_id="int_blue_door_fight_club", slot_type="location",
               display_name="INT. BLUE DOOR FIGHT CLUB - NIGHT")
    loc.source_scenes = [2]
    loc.beat_ids = ["s2b1"]
    beats = {"beats": [
        {"beat_id": "s2b1", "scene": 2, "content": "A ring under dim lights."},
    ]}
    out = character_context(char, [char, loc], beats)
    assert "blue door" not in out.lower()


def test_character_context_is_empty_when_no_location_matches():
    from animatic.core.slot_resolver import Slot
    from animatic.core.style import character_context

    char = Slot(slot_id="ghost", slot_type="character", display_name="GHOST")
    char.beat_ids = ["nope"]
    assert character_context(char, [char], {"beats": []}) == ""
