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
