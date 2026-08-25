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
from animatic.core.slot_resolver import Slot, resolve_slots
from corpus import beats_path, manifest_path

PDF_PATH = Path("docs/rocky-1976.pdf")
BEATS_PATH = beats_path()
MANIFEST_PATH = manifest_path()


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


# ---------------------------------------------------------------------------
# generate_missing_panels — cache reuse, failure isolation, the whole-index
# rule (Task 3, ROADMAP criteria 4 and 5, NFR-04)
# ---------------------------------------------------------------------------

def _synthetic_fixture():
    """Two beats, two locations, two characters — small enough to make
    targeted cache-invalidation assertions without the real 49-beat corpus."""
    beat_a = {
        "beat_id": "s1b1", "scene": 1, "beat": 1, "type": "dialogue",
        "content": "Alice speaks her line.", "duration_secs": 3.0,
        "characters": ["ALICE"], "dialogue": [],
    }
    beat_b = {
        "beat_id": "s2b1", "scene": 2, "beat": 1, "type": "dialogue",
        "content": "Bob speaks his line.", "duration_secs": 3.0,
        "characters": ["BOB"], "dialogue": [],
    }
    beats_doc = {"generated_at": "2026-08-24T00:00:00Z", "beats": [beat_a, beat_b]}

    loc1 = Slot(slot_id="loc1", slot_type="location", display_name="LOC1")
    loc1.source_scenes = [1]
    loc2 = Slot(slot_id="loc2", slot_type="location", display_name="LOC2")
    loc2.source_scenes = [2]
    alice = Slot(slot_id="alice", slot_type="character", display_name="ALICE")
    bob = Slot(slot_id="bob", slot_type="character", display_name="BOB")
    slots = [loc1, loc2, alice, bob]

    manifest = {
        "generated_at": "2026-08-25T00:00:00Z",
        "slots": [
            {"slot_id": "loc1", "content_hash": "hash_loc1"},
            {"slot_id": "loc2", "content_hash": "hash_loc2"},
            {"slot_id": "alice", "content_hash": "hash_alice"},
            {"slot_id": "bob", "content_hash": "hash_bob"},
        ],
    }
    return beats_doc, slots, manifest


@patch("animatic.core.s3_writer.boto3.Session")
@patch("animatic.core.panel_generator.genai.Client")
def test_unchanged_rerun_makes_zero_calls_and_marks_every_panel_reused(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    beats_doc, slots, manifest = _synthetic_fixture()

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    first_index = generate_missing_panels(beats_doc, slots, manifest)
    assert mock_client.models.generate_content.call_count == 2

    second_index = generate_missing_panels(beats_doc, slots, manifest, previous_index=first_index)

    assert mock_client.models.generate_content.call_count == 2, "no new calls on an unchanged rerun"
    assert all(p["source"] == "reused" for p in second_index["panels"])
    assert second_index["reused_count"] == 2
    assert second_index["generated_count"] == 0


@patch("animatic.core.s3_writer.boto3.Session")
@patch("animatic.core.panel_generator.genai.Client")
def test_slot_content_hash_change_invalidates_only_dependent_beats(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    beats_doc, slots, manifest = _synthetic_fixture()

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    first_index = generate_missing_panels(beats_doc, slots, manifest)
    assert mock_client.models.generate_content.call_count == 2

    manifest2 = json.loads(json.dumps(manifest))
    for s in manifest2["slots"]:
        if s["slot_id"] == "bob":
            s["content_hash"] = "hash_bob_changed"

    second_index = generate_missing_panels(beats_doc, slots, manifest2, previous_index=first_index)

    assert mock_client.models.generate_content.call_count == 3, "only bob's dependent beat regenerates"
    by_id = {p["beat_id"]: p for p in second_index["panels"]}
    assert by_id["s2b1"]["source"] == "generated"
    assert by_id["s1b1"]["source"] == "reused"


@patch("animatic.core.s3_writer.boto3.Session")
@patch("animatic.core.panel_generator.genai.Client")
def test_prompt_template_version_bump_invalidates_every_panel(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    beats_doc, slots, manifest = _synthetic_fixture()

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    first_index = generate_missing_panels(beats_doc, slots, manifest)
    assert mock_client.models.generate_content.call_count == 2

    # Prove caching is actually engaged before defeating it with a version bump.
    unchanged_index = generate_missing_panels(beats_doc, slots, manifest, previous_index=first_index)
    assert mock_client.models.generate_content.call_count == 2

    monkeypatch.setattr("animatic.core.panel_generator.PROMPT_TEMPLATE_VERSION", "v2-test")
    bumped_index = generate_missing_panels(beats_doc, slots, manifest, previous_index=unchanged_index)

    assert mock_client.models.generate_content.call_count == 4, "a template version bump redraws everything"
    assert all(p["source"] == "generated" for p in bumped_index["panels"])


@patch("animatic.core.s3_writer.boto3.Session")
@patch("animatic.core.panel_generator.genai.Client")
def test_editing_a_beat_content_invalidates_only_that_beat(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    beats_doc, slots, manifest = _synthetic_fixture()

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    first_index = generate_missing_panels(beats_doc, slots, manifest)
    assert mock_client.models.generate_content.call_count == 2

    beats_doc2 = json.loads(json.dumps(beats_doc))
    beats_doc2["beats"][0]["content"] = "Alice says something completely different now."

    second_index = generate_missing_panels(beats_doc2, slots, manifest, previous_index=first_index)

    assert mock_client.models.generate_content.call_count == 3, "only the edited beat regenerates"
    by_id = {p["beat_id"]: p for p in second_index["panels"]}
    assert by_id["s1b1"]["source"] == "generated"
    assert by_id["s2b1"]["source"] == "reused"


@patch("animatic.core.s3_writer.boto3.Session")
@patch("animatic.core.panel_generator.genai.Client")
@patch("animatic.core.panel_generator.time.sleep")
def test_a_call_that_fails_twice_records_generation_failed_and_the_loop_continues(
    mock_sleep, mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    beats_doc, slots, manifest = _synthetic_fixture()

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] <= 2:
            raise RuntimeError("simulated API failure")
        return _mock_image_response()

    mock_client.models.generate_content.side_effect = side_effect
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    index = generate_missing_panels(beats_doc, slots, manifest)

    # s1b1 is processed first and fails on both attempts (calls 1, 2);
    # s2b1 is processed next and succeeds on its first attempt (call 3).
    by_id = {p["beat_id"]: p for p in index["panels"]}
    assert by_id["s1b1"]["source"] == "generation_failed"
    assert "RuntimeError" in by_id["s1b1"]["source_reason"]
    assert "simulated API failure" in by_id["s1b1"]["source_reason"]
    assert by_id["s2b1"]["source"] == "generated"
    assert mock_sleep.called


@patch("animatic.core.s3_writer.boto3.Session")
@patch("animatic.core.panel_generator.genai.Client")
@patch("animatic.core.panel_generator.time.sleep")
def test_a_call_that_fails_once_then_succeeds_on_retry_produces_a_panel(
    mock_sleep, mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    beats_doc, slots, manifest = _synthetic_fixture()
    # Only test the first beat to keep the retry count unambiguous.
    beats_doc = {**beats_doc, "beats": [beats_doc["beats"][0]]}

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("transient failure")
        return _mock_image_response()

    mock_client.models.generate_content.side_effect = side_effect
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    index = generate_missing_panels(beats_doc, slots, manifest)

    entry = index["panels"][0]
    assert entry["source"] == "generated", "the retry succeeded, this must not be a failure record"
    assert entry["beat_id"] == "s1b1"
    assert Path(entry["panel_uri"]).exists()


@patch("animatic.core.s3_writer.boto3.Session")
@patch("animatic.core.panel_generator.genai.Client")
def test_only_restricted_run_still_writes_an_entry_for_every_beat(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    """--only narrows what is GENERATED, never what is written to the index
    — the whole-index rule (mirrors asset_generator's --only regression)."""
    beats_doc, slots, manifest = _synthetic_fixture()

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    first_index = generate_missing_panels(beats_doc, slots, manifest)
    assert len(first_index["panels"]) == 2

    second_index = generate_missing_panels(
        beats_doc, slots, manifest, previous_index=first_index,
        only={"s1b1"}, force=True,
    )

    assert len(second_index["panels"]) == 2, "s2b1 must still be in the index, carried forward"
    by_id = {p["beat_id"]: p for p in second_index["panels"]}
    assert by_id["s1b1"]["source"] == "generated"
    assert by_id["s2b1"] == {
        k: v for k, v in first_index["panels"][
            [p["beat_id"] for p in first_index["panels"]].index("s2b1")
        ].items()
    }


@patch("animatic.core.s3_writer.boto3.Session")
@patch("animatic.core.panel_generator.genai.Client")
def test_full_run_every_index_entry_has_required_reason_fields(
    mock_client_cls, mock_session_cls, tmp_path, monkeypatch
):
    """Runs the full real 49-beat corpus (mocked calls) and asserts every
    entry carries a non-empty prompt, source_reason, asset_slots_used,
    shot_size_reason and cache_key (NFR-04)."""
    beats_doc = json.loads(BEATS_PATH.read_text())
    manifest = json.loads(MANIFEST_PATH.read_text())
    slots = resolve_slots(beats_doc, PDF_PATH)

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_image_response()
    mock_session = MagicMock()
    mock_session.client.return_value = MagicMock()
    mock_session_cls.return_value = mock_session
    _patch_local_dirs(monkeypatch, tmp_path)

    index = generate_missing_panels(beats_doc, slots, manifest)

    assert index["total_panels"] == 49
    for entry in index["panels"]:
        assert entry["prompt"]
        assert entry["source_reason"]
        assert entry["asset_slots_used"]
        assert entry["shot_size_reason"]
        assert entry["cache_key"]
