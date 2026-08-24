"""Unit tests for the beat parser pipeline."""

from __future__ import annotations

import json
from itertools import islice
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from animatic.core.beat_extractor import Beat
from animatic.core.pdf_extractor import (
    _extract_full_text,
    _split_by_scene,
    extract_scenes,
)
from animatic.main import app

client = TestClient(app)

PDF_PATH = Path("docs/rocky-1976.pdf")

# ---------------------------------------------------------------------------
# PDF extractor tests
# ---------------------------------------------------------------------------

def test_extract_scenes_returns_8_scenes():
    scenes = extract_scenes(PDF_PATH, first_n=8)
    assert len(scenes) == 8


def test_extract_scenes_all_nonempty():
    """Every scene must have text — but a slug-only scene is legitimate.

    Rocky scene 1 is the bare slug "INT. BLUE DOOR FIGHT CLUB - NIGHT";
    the action it introduces is written as scene 2 (a SUPERIMPOSE). So a
    per-scene length floor is the wrong assertion — require a heading on
    each, and real body text across the demo set as a whole.
    """
    scenes = extract_scenes(PDF_PATH, first_n=8)
    for num, text in scenes.items():
        assert text.strip(), f"Scene {num} is empty"
        assert str(num) in text.split("\n")[0], f"Scene {num} lost its heading"
    total_words = sum(len(t.split()) for t in scenes.values())
    assert total_words > 900, f"demo set too thin: {total_words} words"


def test_extract_scenes_first_is_fight_club():
    scenes = extract_scenes(PDF_PATH, first_n=8)
    first_text = list(scenes.values())[0]
    assert "INT." in first_text or "EXT." in first_text


def test_extract_scenes_returns_scenes_1_to_8():
    """The demo set is scenes 1-8. Contiguous, no gaps, no scene 9.

    Regression guard: an INT/EXT-only heading pattern silently dropped
    scene 2 (a SUPERIMPOSE title card, not a slug line) and shifted the
    range to 1,3-9. Downstream phases key panels, audio, motion and
    footage filenames off these numbers, so pin the exact set.
    """
    scenes = extract_scenes(PDF_PATH, first_n=8)
    assert list(scenes.keys()) == [1, 2, 3, 4, 5, 6, 7, 8]


def test_scene_2_is_present_and_carries_the_fight():
    """Scene 2 is the opening fight — the single biggest scene in the demo.

    It has no INT./EXT. slug, so it is exactly the scene a naive heading
    pattern loses. Its body must contain the fight, not be an empty stub.
    """
    scenes = extract_scenes(PDF_PATH, first_n=8)
    assert 2 in scenes, "scene 2 (SUPERIMPOSE title card) must not be dropped"
    body = scenes[2]
    assert "ROCKY BALBOA" in body
    assert "BLACK FIGHTER" in body
    assert len(body.split()) > 400, "scene 2 should carry the full fight-club scene"


def test_extract_scenes_preserves_appearance_order():
    """Scenes must come back in document order, not re-sorted by number.

    Checks each returned block's real offset in the source text, so a
    regression to numeric sorting would be caught on a script whose
    numbering is out of order.
    """
    scenes = extract_scenes(PDF_PATH, first_n=20)
    assert len(scenes) == 20

    full_text = _extract_full_text(PDF_PATH)
    offsets = [full_text.index(text[:60]) for text in scenes.values()]
    assert offsets == sorted(offsets), "scenes are not in document order"


def test_split_by_scene_takes_first_n_by_appearance_not_number():
    """Directly pin the appearance-order contract with out-of-order input.

    A renumbered insert (scene 5 appearing after 12) must not be pulled
    forward by numeric sorting.
    """
    text = (
        "1 INT. FIRST - DAY 1\nBody one.\n"
        "12 INT. SECOND - DAY 12\nBody two.\n"
        "5 INT. THIRD - DAY 5\nBody three.\n"
    )
    scene_map = _split_by_scene(text)
    assert list(scene_map.keys()) == [1, 12, 5]
    assert list(islice(scene_map.items(), 2)) == [
        (1, scene_map[1]),
        (12, scene_map[12]),
    ]


# ---------------------------------------------------------------------------
# Beat schema validation tests (using mock Gemini response)
# ---------------------------------------------------------------------------

_MOCK_BEATS_JSON = json.dumps([
    {
        "beat": 1,
        "scene_heading": "INT. TEST - NIGHT",
        "type": "establishing",
        "content": "A dark room.",
        "duration_secs": 3.0,
        "motion_candidate": False,
        "reason": "Opening establishing shot sets location.",
        "characters": [],
        "dialogue": [],
    },
    {
        "beat": 2,
        "scene_heading": "INT. TEST - NIGHT",
        "type": "action",
        "content": "A fight breaks out.",
        "duration_secs": 5.0,
        "motion_candidate": True,
        "reason": "High-intensity action beat.",
        "characters": ["ROCKY"],
        "dialogue": [],
    },
    {
        "beat": 3,
        "scene_heading": "INT. TEST - NIGHT",
        "type": "dialogue",
        "content": "Rocky speaks.",
        "duration_secs": 4.0,
        "motion_candidate": False,
        "reason": "Key dialogue exchange.",
        "characters": ["ROCKY", "ADRIAN"],
        "dialogue": [
            {"character": "ROCKY", "line": "Yo, Adrian."},
            {"character": "ADRIAN", "line": "... I was worried."},
        ],
    },
])


def _make_mock_response(text: str) -> MagicMock:
    mock = MagicMock()
    mock.text = text
    return mock


@patch("animatic.core.beat_extractor.genai.Client")
def test_extract_beats_returns_beats(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_BEATS_JSON)

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(1, "INT. TEST - NIGHT\nSome action.")

    assert len(beats) == 3
    assert all(isinstance(b, Beat) for b in beats)


@patch("animatic.core.beat_extractor.genai.Client")
def test_all_beats_have_required_fields(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_BEATS_JSON)

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(1, "INT. TEST - NIGHT\nSome action.")

    for beat in beats:
        assert beat.beat_id, "beat_id must be non-empty"
        assert beat.reason, "reason must be non-empty"
        assert beat.duration_secs > 0, "duration must be positive"
        assert beat.type in {"action", "dialogue", "establishing"}


@patch("animatic.core.beat_extractor.genai.Client")
def test_beat_ids_are_unique(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_BEATS_JSON)

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(1, "INT. TEST - NIGHT\nSome action.")

    ids = [b.beat_id for b in beats]
    assert len(ids) == len(set(ids)), "All beat_ids must be unique"


@patch("animatic.core.beat_extractor.genai.Client")
def test_motion_candidates_flagged_correctly(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_BEATS_JSON)

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(1, "INT. TEST - NIGHT\nA fight.")

    motion = [b for b in beats if b.motion_candidate]
    assert len(motion) == 1
    assert motion[0].type == "action"


# ---------------------------------------------------------------------------
# Dialogue attribution — one speaker per line
# ---------------------------------------------------------------------------

@patch("animatic.core.beat_extractor.genai.Client")
def test_dialogue_lines_keep_their_speaker(mock_client_cls):
    """Each line carries exactly one speaker.

    Regression guard: `dialogue` used to be a single string, so a two-person
    exchange came back merged ("Ya movin' like a bum -- ... Just gimme the
    water.") with both names in `characters`. Phase 5 assigns a voice per
    character and cannot split a blob like that.
    """
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_BEATS_JSON)

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(1, "INT. TEST - NIGHT\nTalk.")

    spoken = [b for b in beats if b.dialogue]
    assert len(spoken) == 1
    lines = spoken[0].dialogue
    assert [(x.character, x.line) for x in lines] == [
        ("ROCKY", "Yo, Adrian."),
        ("ADRIAN", "... I was worried."),
    ]
    for x in lines:
        assert x.character, "every line must name its speaker"


@patch("animatic.core.beat_extractor.genai.Client")
def test_beats_without_speech_have_empty_dialogue(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_BEATS_JSON)

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(1, "INT. TEST - NIGHT\nAction.")

    assert beats[0].dialogue == []
    assert beats[0].spoken_words == 0
    assert beats[0].duration_source == "model"


def test_legacy_string_dialogue_is_coerced_not_crashed():
    """An older cached beat list must load, flagged rather than mis-voiced."""
    from animatic.core.beat_extractor import _parse_lines

    lines = _parse_lines("Ya movin' like a bum -- Just gimme the water.")
    assert len(lines) == 1
    assert lines[0].character == "UNKNOWN"
    assert _parse_lines(None) == []
    assert _parse_lines([]) == []


# ---------------------------------------------------------------------------
# Duration floor — a beat must be long enough to speak its own lines
# ---------------------------------------------------------------------------

def test_duration_is_raised_to_fit_its_dialogue():
    """Phase 7 cuts each shot to duration_secs, so speech must fit inside it."""
    from animatic.core.beat_extractor import Beat, Line, _apply_duration_floor

    beat = Beat(
        beat_id="s3b4", scene=3, beat=4, scene_heading="INT. DRESSING ROOM - NIGHT",
        type="dialogue", content="The promoter itemises the deductions.",
        duration_secs=6.0, motion_candidate=False, reason="Pay transaction.",
        characters=["PROMOTER"],
        dialogue=[Line("PROMOTER", "Twenty bucks for the locker an' cornerman -- "
                                   "Two bucks for the towel an' shower, seven for tax -- "
                                   "The house owes ya, sixty-one dollars.")],
    )
    _apply_duration_floor(beat)

    assert beat.duration_secs > 6.0
    assert beat.duration_secs == beat.min_speakable_secs
    assert beat.duration_source == "dialogue_floor"
    assert "duration raised" in beat.reason, "adjustment must stay machine-readable"


def test_duration_is_left_alone_when_already_long_enough():
    from animatic.core.beat_extractor import Beat, Line, _apply_duration_floor

    beat = Beat(
        beat_id="s4b3", scene=4, beat=3, scene_heading="INT. TROLLEY - NIGHT",
        type="dialogue", content="Rocky explains himself.", duration_secs=8.0,
        motion_candidate=False, reason="Short admission.", characters=["ROCKY"],
        dialogue=[Line("ROCKY", "I'm a fighter.")],
    )
    _apply_duration_floor(beat)

    assert beat.duration_secs == 8.0
    assert beat.duration_source == "model"


def test_every_dialogue_beat_can_speak_its_lines():
    """The invariant Phase 5 and Phase 7 depend on, asserted end to end."""
    from animatic.core.beat_extractor import Beat, Line, _apply_duration_floor

    for words, given in ((26, 6.0), (15, 5.0), (11, 3.5), (3, 20.0)):
        beat = Beat(
            beat_id="x", scene=1, beat=1, scene_heading="H", type="dialogue",
            content="c", duration_secs=given, motion_candidate=False, reason="r",
            characters=["A"], dialogue=[Line("A", " ".join(["word"] * words))],
        )
        _apply_duration_floor(beat)
        assert beat.duration_secs >= beat.min_speakable_secs


# ---------------------------------------------------------------------------
# API endpoint test
# ---------------------------------------------------------------------------

@patch("animatic.api.beats.extract_scenes")
@patch("animatic.api.beats.extract_beats")
@patch("animatic.api.beats.assemble_and_write")
def test_post_beats_parse_returns_200(mock_assemble, mock_extract_beats, mock_extract_scenes):
    mock_extract_scenes.return_value = {1: "INT. TEST - NIGHT\nSome action."}
    mock_extract_beats.return_value = [
        Beat(
            beat_id="s1b1", scene=1, beat=1,
            scene_heading="INT. TEST - NIGHT",
            type="action", content="Fight.", duration_secs=4.0,
            motion_candidate=True, reason="Action beat.", characters=["ROCKY"],
        )
    ]
    mock_assemble.return_value = "s3://animatic-media-628818/beats/latest.json"

    response = client.post("/beats/parse")
    assert response.status_code == 200
    data = response.json()
    assert data["total_beats"] == 1
    assert data["s3_uri"].startswith("s3://")
    assert len(data["scenes"]) == 1
