"""Asset manifest assembler — collects resolved slots, writes generated and
reference art and the manifest itself to local disk and S3.

Follows `beat_assembler.py`'s local-then-S3 dual-write precedent, with one
correction inherited from Task 1: every S3 write goes through the shared
`s3_writer.put_bytes`, which never reports a failure as success
(`.planning/phases/phase-2/2-VERIFICATION.md` — the known open bug in
`beat_assembler._write_s3`'s original form). `write_manifest` records an
honest `s3_ok`/`s3_reason` in the manifest body itself (T-03-05).

Write paths are built from `Path(name).name` plus a slot_id that is already
`[a-z0-9_]` by construction from the resolver's own normalisation, never
from a raw external filename (T-03-01).

Change detection (ROADMAP criterion 4) lives in `build_manifest`: it reads
the previous manifest's slots (by slot_id) and compares each new slot's
`content_hash`/`source` against it. `content_hash` was chosen over mtime
because it is re-runnable and does not depend on filesystem timestamps.
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from animatic.config import settings
from animatic.core.s3_writer import put_bytes
from animatic.core.slot_resolver import Slot
from animatic.core.script_source import script_id

logger = logging.getLogger(__name__)

_LOCAL_MANIFEST = Path("output/assets/manifest.json")
_LOCAL_GENERATED_DIR = Path("output/assets/generated")
_S3_MANIFEST_KEY = "assets/manifest.json"
_S3_ART_PREFIX = "assets/art"


def build_manifest(
    slots: list[Slot],
    beats: dict[str, Any],
    beats_source: str = "output/beats.json",
    unmatched_reference_files: list[dict[str, str]] | None = None,
    previous_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the manifest dict, shaped like `beat_assembler._build_beat_list`.

    Top level carries `total_slots`/`character_slots`/`location_slots`,
    `art_slots` (distinct art_slot_id count), `reference_backed`,
    `generated`, `beats_source` and `beats_generated_at` (the beat list's
    own `generated_at`, so a manifest can be tied to the beat list it came
    from), `unmatched_reference_files` (NFR-04 — a mis-named reference file
    is visible rather than silently dropped), `stale_beat_ids` and its
    `stale_beat_reason`, and `s3_ok`/`s3_reason` — set here to `None`/"not
    yet written" and filled honestly by `write_manifest`.

    Each slot entry carries the full `Slot` field set from 03-01/03-02:
    ROADMAP criterion 5 is satisfied per entry by slot_id/display_name plus
    priority_rank plus source plus the reason fields, and NFR-04 by
    `merge_reason`, `priority_reason` and `source_reason` all being
    non-empty for the cases they apply to.
    """
    location_slots = [s for s in slots if s.slot_type == "location"]
    character_slots = [s for s in slots if s.slot_type == "character"]
    art_slot_ids = {s.art_slot_id or s.slot_id for s in slots}
    reference_backed = [s for s in slots if s.source == "reference"]
    generated_backed = [s for s in slots if s.source == "generated"]

    stale_beat_ids, stale_beat_reason = _detect_changes(slots, previous_manifest)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script": script_id(),
        "beats_source": beats_source,
        "beats_generated_at": beats.get("generated_at", ""),
        "total_slots": len(slots),
        "character_slots": len(character_slots),
        "location_slots": len(location_slots),
        "art_slots": len(art_slot_ids),
        "reference_backed": len(reference_backed),
        "generated": len(generated_backed),
        "unmatched_reference_files": unmatched_reference_files or [],
        "stale_beat_ids": stale_beat_ids,
        "stale_beat_reason": stale_beat_reason,
        "s3_ok": None,
        "s3_reason": "not yet written",
        "slots": [s.to_dict() for s in slots],
    }


def _detect_changes(
    slots: list[Slot], previous_manifest: dict[str, Any] | None
) -> tuple[list[str], str]:
    """Set `art_changed` on every slot and return the union of changed
    slots' beat_ids (ROADMAP criterion 4).

    A slot's art is changed when it is newly appearing (no previous entry
    with the same slot_id and a non-empty content_hash), when its
    content_hash differs from the previous run's, or when its `source`
    flipped (e.g. a reference file appeared for a previously generated
    slot). The reason line names which slots changed and why, so the
    signal is checkable rather than asserted (NFR-04) — this is precisely
    the set of panels Phase 4 must redraw.
    """
    previous_by_id: dict[str, dict[str, Any]] = {}
    if previous_manifest:
        previous_by_id = {
            s["slot_id"]: s for s in previous_manifest.get("slots", [])
        }

    stale: set[str] = set()
    notes: list[str] = []
    for slot in slots:
        prev = previous_by_id.get(slot.slot_id)
        if prev is None:
            slot.art_changed = bool(slot.content_hash)
            if slot.art_changed:
                notes.append(f"{slot.slot_id}: newly appeared")
        else:
            hash_changed = slot.content_hash != prev.get("content_hash", "")
            source_flipped = slot.source != prev.get("source", "")
            slot.art_changed = hash_changed or source_flipped
            if slot.art_changed:
                reasons = []
                if hash_changed:
                    reasons.append("content_hash changed")
                if source_flipped:
                    reasons.append(
                        f"source changed {prev.get('source') or '(none)'!r} "
                        f"-> {slot.source!r}"
                    )
                notes.append(f"{slot.slot_id}: {', '.join(reasons)}")
        if slot.art_changed:
            stale.update(slot.beat_ids)

    reason = (
        "; ".join(notes)
        if notes
        else "no slot's art changed since the previous manifest"
    )
    return sorted(stale), reason


def write_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Write `manifest` to local disk and S3, local-then-S3 (as `beat_assembler`).

    The first local write happens before the S3 attempt (matching
    `beat_assembler.assemble_and_write`'s order); once the S3 outcome is
    known, `manifest`'s `s3_ok`/`s3_reason` fields are updated and the local
    copy is rewritten so the artifact on disk is never stale about whether
    it reached the bucket.

    Returns:
        A result dict: `local_path`, `s3_uri`, `s3_ok` (bool), `s3_reason`.
    """
    _write_local(manifest)

    result = put_bytes(
        _S3_MANIFEST_KEY,
        json.dumps(manifest, indent=2).encode("utf-8"),
        content_type="application/json",
    )
    manifest["s3_ok"] = result.ok
    manifest["s3_reason"] = result.error or "put_object succeeded"

    _write_local(manifest)

    return {
        "local_path": str(_LOCAL_MANIFEST),
        "s3_uri": result.uri,
        "s3_ok": result.ok,
        "s3_reason": manifest["s3_reason"],
    }


def write_slot_art(slot: Slot, image_bytes: bytes, mime_type: str) -> None:
    """Write freshly generated art for `slot` to local disk, mirror to S3.

    Sets `slot.art_uri`, `slot.art_s3_uri`, `slot.content_hash`,
    `slot.source` ("generated") and `slot.source_reason` in place.
    """
    content_hash, local_path, uri, ok, reason = _write_art_bytes(
        slot, image_bytes, mime_type
    )
    slot.art_uri = str(local_path)
    slot.art_s3_uri = uri if ok else ""
    slot.content_hash = content_hash
    slot.source = "generated"
    slot.source_reason = (
        f"generated via {settings.gemini_image_model}; "
        f"sha256={content_hash[:12]}; s3_ok={ok} ({reason})"
    )


def write_reference_art(slot: Slot, source_path: Path) -> None:
    """Copy a resolved reference file's bytes into the shared output tree
    and S3, so Phase 4 gets one consistent art_uri/art_s3_uri regardless of
    source.

    Leaves `source`/`source_reason`/`source_files`/`match_rule` untouched —
    `reference_art.resolve_reference_art` already set those to describe how
    the file was matched (D-01); this only handles the mechanical copy,
    hash and upload so a reference-backed slot's art is reachable the same
    way a generated slot's is.
    """
    mime_type = mimetypes.guess_type(str(source_path))[0] or "application/octet-stream"
    image_bytes = source_path.read_bytes()
    content_hash, local_path, uri, ok, _reason = _write_art_bytes(
        slot, image_bytes, mime_type
    )
    slot.art_uri = str(local_path)
    slot.art_s3_uri = uri if ok else ""
    slot.content_hash = content_hash


def _write_art_bytes(
    slot: Slot, image_bytes: bytes, mime_type: str
) -> tuple[str, Path, str, bool, str]:
    """Write `image_bytes` to the shared local+S3 output tree for `slot`.

    Returns (content_hash, local_path, s3_uri, s3_ok, s3_reason). Filename
    is built from `Path(name).name` plus the resolver's own normalised
    slot_id — never from a raw external filename (T-03-01). Falls back to
    `slot_id` when `art_slot_id` is unset (safe: the two are always equal
    for a location or a bespoke character).
    """
    ext = _ext_for_mime(mime_type)
    art_slot_id = slot.art_slot_id or slot.slot_id
    filename = f"{Path(art_slot_id).name}.{ext}"

    local_path = _LOCAL_GENERATED_DIR / filename
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(image_bytes)

    content_hash = hashlib.sha256(image_bytes).hexdigest()

    s3_key = f"{_S3_ART_PREFIX}/{filename}"
    result = put_bytes(s3_key, image_bytes, content_type=mime_type)
    reason = result.error or "put_object succeeded"

    return content_hash, local_path, result.uri, result.ok, reason


def _write_local(manifest: dict[str, Any]) -> None:
    _LOCAL_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCAL_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info("Manifest written locally to %s", _LOCAL_MANIFEST)


def _ext_for_mime(mime_type: str) -> str:
    ext = mimetypes.guess_extension(mime_type or "")
    if not ext:
        return "bin"
    return ext.lstrip(".")
