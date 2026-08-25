"""Unit tests for the panel generation pipeline — one beat through the
resolver, the prompt builder, a mocked image call, and the index.

Follows tests/test_asset_manifest.py's `@patch("animatic.core.<module>.genai.Client")`
pattern for the image call, and patches `animatic.core.s3_writer.boto3.Session`
for the S3 write (every S3 put routes through the shared s3_writer module).
The real live call is made once, by `scripts/build_panels.py --only s2b7`,
never in this suite.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from animatic.core.panel_generator import (
    PanelGenerationError,
    generate_missing_panels,
    generate_panel,
    panel_cache_key,
    resolve_beat_slots,
)
from animatic.core.slot_resolver import resolve_slots

PDF_PATH = Path("docs/rocky-1976.pdf")
BEATS_PATH = Path("output/beats.json")
MANIFEST_PATH = Path("output/assets/manifest.json")


def _mock_image_response(data: bytes = b"fake-panel-bytes", mime_type: str = "image/png"):
    mock_part = MagicMock()
    mock_part.inline_data.data = data
    mock_part.inline_data.mime_type = mime_type
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
    return mock_response


def _s2b7(beats_doc):
    return next(b for b in beats_doc["beats"] if b["beat_id"] == "s2b7")


def _patch_local_dirs(monkeypatch, tmp_path):
    import animatic.core.panel_manifest as panel_manifest_mod

    monkeypatch.setattr(panel_manifest_mod, "_LOCAL_INDEX", tmp_path / "index.json")
    monkeypatch.setattr(panel_manifest_mod, "_LOCAL_PANELS_DIR", tmp_path / "panels")


# ---------------------------------------------------------------------------
# End-to-end tracer test — one beat, resolver -> prompt -> generator -> index
# ---------------------------------------------------------------------------

@patch("animatic.core.s3_writer.boto3.Session")
@patch("animatic.core.panel_generator.genai.Client")
def test_tracer_beat_resolves_generates_and_writes_index(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    """The full Phase 4 slice for one beat: real beats.json + real asset
    manifest resolve s2b7's location and character slots; a mocked image
    call and a mocked S3 write prove every other layer without spending a
    real API call in the test suite."""
    beats_doc = json.loads(BEATS_PATH.read_text())
    manifest = json.loads(MANIFEST_PATH.read_text())
    slots = resolve_slots(beats_doc, PDF_PATH)

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()

    mock_s3 = MagicMock()
    mock_session = MagicMock()
    mock_session.client.return_value = mock_s3
    mock_session_cls.return_value = mock_session

    _patch_local_dirs(monkeypatch, tmp_path)

    index = generate_missing_panels(beats_doc, slots, manifest, only={"s2b7"})

    assert mock_client.models.generate_content.call_count == 1

    entries = [p for p in index["panels"] if p["beat_id"] == "s2b7"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["shot_size"] == "close-up"
    assert entry["shot_size_reason"]
    assert "cornerman" in entry["asset_slots_used"]
    assert "int_blue_door_fight_club" in entry["asset_slots_used"]
    assert entry["prompt"]
    assert entry["cache_key"]
    assert entry["source_reason"]
    assert entry["source"] == "generated"
    assert Path(entry["panel_uri"]).exists()

    _, kwargs = mock_client.models.generate_content.call_args
    assert kwargs["config"].system_instruction is None
    assert kwargs["config"].image_config.aspect_ratio == "16:9"


# ---------------------------------------------------------------------------
# generate_panel
# ---------------------------------------------------------------------------

@patch("animatic.core.panel_generator.genai.Client")
def test_generate_panel_returns_bytes_and_mime_type(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response(
        data=b"\x89PNG-fake", mime_type="image/png"
    )

    beat = {"beat_id": "s2b7", "type": "dialogue"}
    image_bytes, mime_type = generate_panel(beat, "a prompt")

    assert image_bytes == b"\x89PNG-fake"
    assert mime_type == "image/png"


@patch("animatic.core.panel_generator.genai.Client")
def test_generate_panel_trusts_returned_mime_type_not_png(mock_client_cls):
    """RESEARCH Pitfall 3: don't assume PNG — trust the response's own mime type."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response(
        mime_type="image/jpeg"
    )

    beat = {"beat_id": "s2b7", "type": "dialogue"}
    _, mime_type = generate_panel(beat, "a prompt")

    assert mime_type == "image/jpeg"


@patch("animatic.core.panel_generator.genai.Client")
def test_generate_panel_never_passes_system_instruction(mock_client_cls):
    """D-12 / RESEARCH Pitfall 1: system_instruction + image model raises on
    the API-key backend — every rule must travel in the prompt text."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()

    beat = {"beat_id": "s2b7", "type": "dialogue"}
    generate_panel(beat, "a prompt")

    _, kwargs = mock_client.models.generate_content.call_args
    assert kwargs["config"].system_instruction is None


@patch("animatic.core.panel_generator.genai.Client")
def test_generate_panel_sets_16_9_aspect_ratio(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()

    beat = {"beat_id": "s2b7", "type": "dialogue"}
    generate_panel(beat, "a prompt")

    _, kwargs = mock_client.models.generate_content.call_args
    assert kwargs["config"].image_config.aspect_ratio == "16:9"


@patch("animatic.core.panel_generator.genai.Client")
def test_generate_panel_raises_when_no_inline_data(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_part = MagicMock()
    mock_part.inline_data = None
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
    mock_client.models.generate_content.return_value = mock_response

    beat = {"beat_id": "s2b7", "type": "dialogue"}
    with pytest.raises(PanelGenerationError):
        generate_panel(beat, "a prompt")


# ---------------------------------------------------------------------------
# resolve_beat_slots
# ---------------------------------------------------------------------------

def test_resolve_beat_slots_finds_location_and_characters():
    beats_doc = json.loads(BEATS_PATH.read_text())
    slots = resolve_slots(beats_doc, PDF_PATH)
    beat = _s2b7(beats_doc)

    location_slot, character_slots = resolve_beat_slots(beat, slots)

    assert location_slot.slot_id == "int_blue_door_fight_club"
    assert [s.slot_id for s in character_slots] == ["cornerman"]


def test_resolve_beat_slots_uses_the_character_own_slot_id_not_shared_art_slot():
    """FIGHTER #1 shares generic_minor_character art but keeps its own
    slot_id in the index, so the record says which character was in frame."""
    beats_doc = json.loads(BEATS_PATH.read_text())
    slots = resolve_slots(beats_doc, PDF_PATH)
    beat = next(
        b for b in beats_doc["beats"] if "FIGHTER #1" in b.get("characters", [])
    )

    _, character_slots = resolve_beat_slots(beat, slots)

    assert [s.slot_id for s in character_slots] == ["fighter_1"]
    assert character_slots[0].art_slot_id == "generic_minor_character"


# ---------------------------------------------------------------------------
# panel_cache_key
# ---------------------------------------------------------------------------

def test_panel_cache_key_is_deterministic_and_sensitive_to_inputs():
    beat = {
        "beat_id": "s2b7", "type": "dialogue", "content": "x",
        "characters": ["CORNERMAN"], "scene": 2,
    }
    dependent = [{"slot_id": "cornerman", "content_hash": "abc"}]

    key1 = panel_cache_key(beat, "close-up", dependent, "v1")
    key2 = panel_cache_key(beat, "close-up", dependent, "v1")
    assert key1 == key2

    key_diff_version = panel_cache_key(beat, "close-up", dependent, "v2")
    assert key_diff_version != key1

    dependent_changed = [{"slot_id": "cornerman", "content_hash": "def"}]
    key_diff_hash = panel_cache_key(beat, "close-up", dependent_changed, "v1")
    assert key_diff_hash != key1

    beat_changed = {**beat, "content": "y"}
    key_diff_content = panel_cache_key(beat_changed, "close-up", dependent, "v1")
    assert key_diff_content != key1
