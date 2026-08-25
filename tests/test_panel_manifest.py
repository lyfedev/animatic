"""Unit tests for the panel index assembler — writing one panel's bytes,
building the index dict, and writing it local-then-S3 with honest
s3_ok/s3_reason (mirrors tests/test_asset_manifest.py's manifest tests).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from animatic.core.panel_manifest import build_index, write_index, write_panel


def _entry(beat_id, scene, beat, source="generated", **overrides):
    base = {
        "beat_id": beat_id,
        "scene": scene,
        "beat": beat,
        "type": "dialogue",
        "duration_secs": 3.0,
        "shot_size": "close-up",
        "shot_size_reason": "test reason",
        "facial_features": "brow_mouth_nose",
        "facial_features_reason": "test facial reason",
        "asset_slots_used": ["loc1", "char1"],
        "slot_hashes": [{"slot_id": "loc1", "content_hash": "h1"}],
        "prompt": "a test prompt",
        "prompt_template_version": "v1",
        "cache_key": "somekey",
        "panel_uri": f"output/panels/{beat_id}.jpg",
        "panel_s3_uri": f"s3://bucket/panels/{beat_id}.jpg",
        "content_hash": "imagehash",
        "source": source,
        "source_reason": "test source reason",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# write_panel
# ---------------------------------------------------------------------------

@patch("animatic.core.s3_writer.boto3.Session")
def test_write_panel_writes_local_and_mirrors_to_s3(mock_session_cls, tmp_path, monkeypatch):
    mock_s3 = MagicMock()
    mock_session = MagicMock()
    mock_session.client.return_value = mock_s3
    mock_session_cls.return_value = mock_session

    import animatic.core.panel_manifest as panel_manifest_mod

    monkeypatch.setattr(panel_manifest_mod, "_LOCAL_PANELS_DIR", tmp_path / "panels")

    content_hash, local_path, s3_uri, s3_ok, s3_reason = write_panel(
        "s2b7", b"\xff\xd8fake-jpeg", "image/jpeg"
    )

    assert local_path.exists()
    assert local_path.name == "s2b7.jpg"
    assert len(content_hash) == 64
    assert s3_ok is True
    assert s3_uri.endswith("panels/s2b7.jpg")


def test_write_panel_asserts_beat_id_pattern():
    with pytest.raises(AssertionError):
        write_panel("not-a-beat-id", b"data", "image/jpeg")


# ---------------------------------------------------------------------------
# build_index — shape, ordering, reason fields (NFR-04)
# ---------------------------------------------------------------------------

def test_build_index_shape():
    beats_doc = {"generated_at": "2026-08-24T00:00:00Z", "beats": []}
    manifest = {"generated_at": "2026-08-25T00:00:00Z", "slots": []}
    entries = [_entry("s1b1", 1, 1), _entry("s2b1", 2, 1)]

    index = build_index(
        entries, beats_doc, manifest,
        beats_source="output/beats.json",
        manifest_source="output/assets/manifest.json",
        prompt_template_version="v1",
    )

    assert index["beats_source"] == "output/beats.json"
    assert index["beats_generated_at"] == "2026-08-24T00:00:00Z"
    assert index["assets_manifest_source"] == "output/assets/manifest.json"
    assert index["assets_manifest_generated_at"] == "2026-08-25T00:00:00Z"
    assert index["prompt_template_version"] == "v1"
    assert index["total_panels"] == 2
    assert index["generated_count"] == 2
    assert index["reused_count"] == 0
    assert index["failed_count"] == 0
    assert index["s3_ok"] is None
    assert index["s3_reason"]
    assert len(index["panels"]) == 2


def test_build_index_counts_generated_reused_and_failed_separately():
    beats_doc = {"generated_at": "", "beats": []}
    manifest = {"generated_at": "", "slots": []}
    entries = [
        _entry("s1b1", 1, 1, source="generated"),
        _entry("s1b2", 1, 2, source="reused"),
        _entry("s1b3", 1, 3, source="generation_failed"),
    ]

    index = build_index(entries, beats_doc, manifest, "b.json", "m.json", "v1")

    assert index["generated_count"] == 1
    assert index["reused_count"] == 1
    assert index["failed_count"] == 1
    assert index["total_panels"] == 3


def test_build_index_orders_entries_by_scene_then_beat():
    beats_doc = {"generated_at": "", "beats": []}
    manifest = {"generated_at": "", "slots": []}
    entries = [
        _entry("s2b1", 2, 1),
        _entry("s1b2", 1, 2),
        _entry("s1b1", 1, 1),
    ]

    index = build_index(entries, beats_doc, manifest, "b.json", "m.json", "v1")

    assert [p["beat_id"] for p in index["panels"]] == ["s1b1", "s1b2", "s2b1"]


def test_every_entry_carries_nonempty_reason_fields():
    """NFR-04: prompt, source_reason, asset_slots_used, shot_size_reason and
    cache_key are non-empty on every entry."""
    beats_doc = {"generated_at": "", "beats": []}
    manifest = {"generated_at": "", "slots": []}
    entries = [_entry("s1b1", 1, 1), _entry("s2b1", 2, 1, source="reused")]

    index = build_index(entries, beats_doc, manifest, "b.json", "m.json", "v1")

    for entry in index["panels"]:
        assert entry["prompt"]
        assert entry["source_reason"]
        assert entry["asset_slots_used"]
        assert entry["shot_size_reason"]
        assert entry["cache_key"]


# ---------------------------------------------------------------------------
# write_index — local-then-S3, honest s3_ok/s3_reason (T-04-03)
# ---------------------------------------------------------------------------

@patch("animatic.core.s3_writer.boto3.Session")
def test_write_index_writes_local_and_records_s3_success(mock_session_cls, tmp_path, monkeypatch):
    mock_s3 = MagicMock()
    mock_session = MagicMock()
    mock_session.client.return_value = mock_s3
    mock_session_cls.return_value = mock_session

    import animatic.core.panel_manifest as panel_manifest_mod

    monkeypatch.setattr(panel_manifest_mod, "_LOCAL_INDEX", tmp_path / "index.json")

    beats_doc = {"generated_at": "", "beats": []}
    manifest = {"generated_at": "", "slots": []}
    index = build_index([_entry("s1b1", 1, 1)], beats_doc, manifest, "b.json", "m.json", "v1")
    result = write_index(index)

    assert result["s3_ok"] is True
    assert Path(result["local_path"]).exists()
    written = json.loads(Path(result["local_path"]).read_text())
    assert written["s3_ok"] is True


@patch("animatic.core.s3_writer.boto3.Session")
def test_write_index_records_s3_failure_not_hidden(mock_session_cls, tmp_path, monkeypatch):
    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "PutObject"
    )
    mock_session = MagicMock()
    mock_session.client.return_value = mock_s3
    mock_session_cls.return_value = mock_session

    import animatic.core.panel_manifest as panel_manifest_mod

    monkeypatch.setattr(panel_manifest_mod, "_LOCAL_INDEX", tmp_path / "index.json")

    beats_doc = {"generated_at": "", "beats": []}
    manifest = {"generated_at": "", "slots": []}
    index = build_index([_entry("s1b1", 1, 1)], beats_doc, manifest, "b.json", "m.json", "v1")
    result = write_index(index)

    assert result["s3_ok"] is False
    assert result["s3_reason"]
    assert not result["s3_uri"].startswith("local://")
    written = json.loads((tmp_path / "index.json").read_text())
    assert written["s3_ok"] is False
    assert written["s3_reason"]
