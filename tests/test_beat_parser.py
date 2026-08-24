"""Unit tests for the beat parser pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from animatic.core.beat_extractor import Beat
from animatic.core.pdf_extractor import extract_scenes
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
    scenes = extract_scenes(PDF_PATH, first_n=8)
    for num, text in scenes.items():
        assert len(text) > 50, f"Scene {num} text too short: {len(text)} chars"


def test_extract_scenes_first_is_fight_club():
    scenes = extract_scenes(PDF_PATH, first_n=8)
    first_text = list(scenes.values())[0]
    assert "INT." in first_text or "EXT." in first_text


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
        "dialogue": "",
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
        "dialogue": "",
    },
    {
        "beat": 3,
        "scene_heading": "INT. TEST - NIGHT",
        "type": "dialogue",
        "content": "Rocky speaks.",
        "duration_secs": 4.0,
        "motion_candidate": False,
        "reason": "Key dialogue exchange.",
        "characters": ["ROCKY"],
        "dialogue": "Yo, Adrian.",
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
