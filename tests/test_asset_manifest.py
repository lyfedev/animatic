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

from animatic.core.asset_generator import (
    AssetGenerationError,
    generate_missing_art,
    generate_slot_art,
)
from animatic.core.asset_manifest import build_manifest, write_manifest, write_slot_art
from animatic.core.reference_art import content_hash_file, resolve_reference_art
from animatic.core.slot_resolver import Slot, resolve_slots
from animatic.core.style import build_slot_prompt

PDF_PATH = Path("docs/rocky-1976.pdf")
BEATS_PATH = Path("output/beats.json")
REFERENCE_DIR = Path("assets/reference-art")


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


# ---------------------------------------------------------------------------
# reference_art — supplied art wins over generation (Task 1)
# ---------------------------------------------------------------------------

def test_reference_art_takes_priority():
    """With the reference directory as supplied today, rocky resolves to
    source "reference" with its three rocky-named files and never reaches
    the image model; no other slot resolves to source "reference"."""
    beats = json.loads(BEATS_PATH.read_text())
    slots = resolve_slots(beats, PDF_PATH)

    resolve_reference_art(slots, REFERENCE_DIR)

    by_id = {s.slot_id: s for s in slots}
    rocky = by_id["rocky"]
    assert rocky.source == "reference"
    assert rocky.match_rule == "filename_token"
    assert len(rocky.source_files) == 3
    assert all("rocky" in f.lower() for f in rocky.source_files)
    assert rocky.source_reason

    reference_backed = [s.slot_id for s in slots if s.source == "reference"]
    assert reference_backed == ["rocky"]


def test_unmatched_reference_file_is_recorded():
    """boxing_poses.jpeg matches no slot_id and is recorded with a reason
    rather than silently dropped (NFR-04)."""
    beats = json.loads(BEATS_PATH.read_text())
    slots = resolve_slots(beats, PDF_PATH)

    scan = resolve_reference_art(slots, REFERENCE_DIR)

    unmatched_names = [Path(u["path"]).name for u in scan.unmatched]
    assert "boxing_poses.jpeg" in unmatched_names
    matching = next(u for u in scan.unmatched if Path(u["path"]).name == "boxing_poses.jpeg")
    assert matching["reason"]


def test_slot_directory_beats_filename_token(tmp_path):
    """A file under assets/reference-art/<slot_id>/ wins outright over a
    flat file that would otherwise match the same slot on filename tokens."""
    ref_dir = tmp_path / "reference-art"
    (ref_dir / "rocky").mkdir(parents=True)
    dir_file = ref_dir / "rocky" / "primary.jpg"
    dir_file.write_bytes(b"dir-bytes")
    flat_file = ref_dir / "rocky_extra.jpg"
    flat_file.write_bytes(b"flat-bytes")

    slots = [Slot(slot_id="rocky", slot_type="character", display_name="ROCKY")]
    scan = resolve_reference_art(slots, ref_dir)

    rocky = slots[0]
    assert rocky.match_rule == "slot_directory"
    assert rocky.source_files == [str(dir_file)]
    assert scan.matched_slot_ids == ["rocky"]


def test_empty_reference_dir_resolves_nothing(tmp_path):
    """An empty reference directory resolves no slot and raises nothing."""
    empty_dir = tmp_path / "reference-art"
    empty_dir.mkdir()
    slots = [Slot(slot_id="rocky", slot_type="character", display_name="ROCKY")]

    scan = resolve_reference_art(slots, empty_dir)

    assert scan.matched_slot_ids == []
    assert scan.unmatched == []
    assert slots[0].source == ""


def test_content_hash_changes_on_file_replace(tmp_path):
    """content_hash_file is a sha256 hex digest that changes with the
    file's bytes, computed by streaming rather than a whole-file read."""
    path = tmp_path / "art.jpg"
    path.write_bytes(b"original bytes")
    hash1 = content_hash_file(path)
    assert len(hash1) == 64
    assert all(c in "0123456789abcdef" for c in hash1)

    path.write_bytes(b"replaced bytes")
    hash2 = content_hash_file(path)

    assert hash1 != hash2


# ---------------------------------------------------------------------------
# asset_generator.generate_missing_art — Task 2
# ---------------------------------------------------------------------------

def _patch_local_dirs(monkeypatch, tmp_path):
    import animatic.core.asset_manifest as asset_manifest_mod

    monkeypatch.setattr(asset_manifest_mod, "_LOCAL_MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(asset_manifest_mod, "_LOCAL_GENERATED_DIR", tmp_path / "generated")


@patch("animatic.core.asset_manifest.boto3.Session")
@patch("animatic.core.asset_generator.genai.Client")
def test_manifest_complete_with_no_reference_art(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    """With reference art absent, all 16 slots end with a non-empty art_uri
    and source "generated"; the run produces 13 distinct art files (7
    locations, 5 bespoke characters, 1 generic_minor_character)."""
    beats = json.loads(BEATS_PATH.read_text())
    slots = resolve_slots(beats, PDF_PATH)

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    generate_missing_art(slots, beats)

    assert len(slots) == 16
    assert all(s.art_uri for s in slots)
    assert all(s.source == "generated" for s in slots)
    assert all(s.prompt for s in slots)
    assert len({s.art_uri for s in slots}) == 13


@patch("animatic.core.asset_manifest.boto3.Session")
@patch("animatic.core.asset_generator.genai.Client")
def test_minor_characters_share_one_art_file(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    """The four minor characters share one art file and one content_hash."""
    beats = json.loads(BEATS_PATH.read_text())
    slots = resolve_slots(beats, PDF_PATH)

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    generate_missing_art(slots, beats)

    minors = [s for s in slots if s.is_minor]
    assert len(minors) == 4
    assert len({s.art_uri for s in minors}) == 1
    assert len({s.content_hash for s in minors}) == 1


@patch("animatic.core.asset_manifest.boto3.Session")
@patch("animatic.core.asset_generator.genai.Client")
def test_generation_order_follows_priority(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    """Slots are generated in priority_rank order, highest-share first."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    low = Slot(slot_id="ext_alley", slot_type="location", display_name="EXT. ALLEY")
    low.priority_rank, low.art_slot_id, low.beat_ids = 3, "ext_alley", []
    high = Slot(slot_id="int_ring", slot_type="location", display_name="INT. RING")
    high.priority_rank, high.art_slot_id, high.beat_ids = 1, "int_ring", []
    mid = Slot(slot_id="rocky", slot_type="character", display_name="ROCKY")
    mid.priority_rank, mid.art_slot_id, mid.is_minor, mid.beat_ids = 2, "rocky", False, []

    slots = [low, mid, high]
    generate_missing_art(slots, {"beats": []})

    called_prompts = [
        c.kwargs["contents"] for c in mock_client.models.generate_content.call_args_list
    ]
    assert called_prompts == [high.prompt, mid.prompt, low.prompt]


@patch("animatic.core.asset_manifest.boto3.Session")
@patch("animatic.core.asset_generator.genai.Client")
def test_existing_art_is_reused_without_a_second_call(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    """A generated file that already exists on disk with the same prompt is
    reused rather than regenerated, unless --force is passed."""
    beats = json.loads(BEATS_PATH.read_text())
    slots = resolve_slots(beats, PDF_PATH)

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    generate_missing_art(slots, beats)
    first_call_count = mock_client.models.generate_content.call_count
    assert first_call_count == 13

    previous_manifest = {"slots": [s.to_dict() for s in slots]}
    slots2 = resolve_slots(beats, PDF_PATH)
    generate_missing_art(slots2, beats, previous_manifest=previous_manifest)

    assert mock_client.models.generate_content.call_count == first_call_count

    by_id_1 = {s.slot_id: s for s in slots}
    by_id_2 = {s.slot_id: s for s in slots2}
    for slot_id, s1 in by_id_1.items():
        s2 = by_id_2[slot_id]
        assert s2.content_hash == s1.content_hash
        assert s2.source == "generated"


@patch("animatic.core.asset_manifest.boto3.Session")
@patch("animatic.core.asset_generator.genai.Client")
def test_one_slot_failure_does_not_abort_the_run(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    """A failure on one slot records the error in that slot's reason and
    leaves the other slots complete — the run does not abort."""
    beats = json.loads(BEATS_PATH.read_text())
    slots = resolve_slots(beats, PDF_PATH)

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated API failure")
        return _mock_image_response()

    mock_client.models.generate_content.side_effect = side_effect
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    generate_missing_art(slots, beats)

    # rocky is priority_rank 1 and its own art_slot_id, so it is the only
    # slot in the first (failing) group.
    failed = [s for s in slots if s.source == "generation_failed"]
    succeeded = [s for s in slots if s.source == "generated"]
    assert len(failed) == 1
    assert failed[0].slot_id == "rocky"
    assert failed[0].source_reason
    assert "simulated API failure" in failed[0].source_reason
    assert len(succeeded) == 15
