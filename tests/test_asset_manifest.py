"""Unit tests for the asset manifest pipeline — slot resolution through a
generated image to a written manifest.

Follows tests/test_beat_parser.py's `@patch("animatic.core.<module>.genai.Client")`
pattern for the image call, and patches `boto3.Session` for the S3 write.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from animatic.core.asset_generator import AssetGenerationError, generate_slot_art
from animatic.core.asset_manifest import build_manifest, write_manifest, write_slot_art
from animatic.core.slot_resolver import Slot, resolve_slots
from animatic.core.style import build_slot_prompt

PDF_PATH = Path("docs/rocky-1976.pdf")
BEATS_PATH = Path("output/beats.json")


def _mock_image_response(data: bytes = b"fake-image-bytes", mime_type: str = "image/png"):
    mock_part = MagicMock()
    mock_part.inline_data.data = data
    mock_part.inline_data.mime_type = mime_type
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
    return mock_response


# ---------------------------------------------------------------------------
# End-to-end tracer test — one slot, resolver -> generator -> manifest
# ---------------------------------------------------------------------------

@patch("animatic.core.asset_manifest.boto3.Session")
@patch("animatic.core.asset_generator.genai.Client")
def test_tracer_slot_resolves_generates_and_writes_manifest(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    """The full Phase 3 slice: real beats.json + real PDF resolve the one
    tracer slot; a mocked image call and a mocked S3 write prove every other
    layer without spending a real API call in the test suite (the real call
    is made once, live, by `scripts/build_assets.py --only ...`)."""
    beats = json.loads(BEATS_PATH.read_text())
    slots = resolve_slots(beats, PDF_PATH)
    tracer_matches = [s for s in slots if s.slot_id == "int_blue_door_fight_club"]
    assert len(tracer_matches) == 1
    slot = tracer_matches[0]
    assert slot.source_scenes == [1, 2]
    assert slot.merge_reason

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()

    mock_s3 = MagicMock()
    mock_session = MagicMock()
    mock_session.client.return_value = mock_s3
    mock_session_cls.return_value = mock_session

    import animatic.core.asset_manifest as asset_manifest_mod

    monkeypatch.setattr(asset_manifest_mod, "_LOCAL_MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(asset_manifest_mod, "_LOCAL_GENERATED_DIR", tmp_path / "generated")

    prompt = build_slot_prompt(slot, f"{slot.display_name} ({slot.slot_type})")
    slot.prompt = prompt
    image_bytes, mime_type = generate_slot_art(slot, prompt)
    write_slot_art(slot, image_bytes, mime_type)

    assert slot.content_hash
    assert Path(slot.art_uri).exists()
    assert slot.source == "generated"

    manifest = build_manifest([slot])
    result = write_manifest(manifest)

    assert result["s3_ok"] is True
    assert Path(result["local_path"]).exists()

    written = json.loads(Path(result["local_path"]).read_text())
    assert written["s3_ok"] is True
    assert written["total_slots"] == 1
    assert written["slots"][0]["slot_id"] == "int_blue_door_fight_club"
    assert written["slots"][0]["source_scenes"] == [1, 2]
    assert written["slots"][0]["merge_reason"]
    assert written["slots"][0]["content_hash"]


# ---------------------------------------------------------------------------
# asset_generator
# ---------------------------------------------------------------------------

@patch("animatic.core.asset_generator.genai.Client")
def test_generate_slot_art_returns_bytes_and_mime_type(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response(
        data=b"\x89PNG-fake", mime_type="image/png"
    )

    slot = Slot(slot_id="rocky", slot_type="character", display_name="ROCKY")
    image_bytes, mime_type = generate_slot_art(slot, "a prompt")

    assert image_bytes == b"\x89PNG-fake"
    assert mime_type == "image/png"


@patch("animatic.core.asset_generator.genai.Client")
def test_generate_slot_art_trusts_returned_mime_type_not_png(mock_client_cls):
    """RESEARCH Pitfall 3: don't assume PNG — trust the response's own mime type."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response(
        mime_type="image/jpeg"
    )

    slot = Slot(slot_id="rocky", slot_type="character", display_name="ROCKY")
    _, mime_type = generate_slot_art(slot, "a prompt")

    assert mime_type == "image/jpeg"


@patch("animatic.core.asset_generator.genai.Client")
def test_generate_slot_art_never_passes_system_instruction(mock_client_cls):
    """D-12 / RESEARCH Pitfall 1: system_instruction + image model raises on
    the API-key backend — the style block must travel in the prompt text."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()

    slot = Slot(slot_id="rocky", slot_type="character", display_name="ROCKY")
    generate_slot_art(slot, "a prompt")

    _, kwargs = mock_client.models.generate_content.call_args
    assert kwargs["config"].system_instruction is None


@patch("animatic.core.asset_generator.genai.Client")
def test_generate_slot_art_raises_when_no_inline_data(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_part = MagicMock()
    mock_part.inline_data = None
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
    mock_client.models.generate_content.return_value = mock_response

    slot = Slot(slot_id="rocky", slot_type="character", display_name="ROCKY")
    with pytest.raises(AssetGenerationError):
        generate_slot_art(slot, "a prompt")


# ---------------------------------------------------------------------------
# asset_manifest — honest S3 reporting (T-03-05)
# ---------------------------------------------------------------------------

@patch("animatic.core.asset_manifest.boto3.Session")
def test_write_manifest_reports_s3_failure_honestly(mock_session_cls, tmp_path, monkeypatch):
    """Unlike beat_assembler._write_s3, a failed S3 write must never be
    reported as success — no `local://` URI masquerading as a real one."""
    from botocore.exceptions import ClientError

    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "PutObject"
    )
    mock_session = MagicMock()
    mock_session.client.return_value = mock_s3
    mock_session_cls.return_value = mock_session

    import animatic.core.asset_manifest as asset_manifest_mod

    monkeypatch.setattr(asset_manifest_mod, "_LOCAL_MANIFEST", tmp_path / "manifest.json")

    slot = Slot(slot_id="rocky", slot_type="character", display_name="ROCKY")
    manifest = build_manifest([slot])
    result = write_manifest(manifest)

    assert result["s3_ok"] is False
    assert result["s3_reason"]
    assert not result["s3_uri"].startswith("local://"), (
        "a failed write must never masquerade as a local:// success URI"
    )
    written = json.loads((tmp_path / "manifest.json").read_text())
    assert written["s3_ok"] is False
    assert written["s3_reason"]


def test_build_manifest_shape(tmp_path):
    loc = Slot(slot_id="int_dressing_room", slot_type="location", display_name="INT. DRESSING ROOM")
    char = Slot(slot_id="rocky", slot_type="character", display_name="ROCKY")
    manifest = build_manifest([loc, char])

    assert manifest["total_slots"] == 2
    assert manifest["location_slots"] == 1
    assert manifest["character_slots"] == 1
    assert manifest["generated_at"]
    assert manifest["script"] == "rocky-1976"
    assert len(manifest["slots"]) == 2
