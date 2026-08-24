"""Asset manifest assembler — collects resolved slots, writes generated art
and the manifest itself to local disk and S3.

Follows `beat_assembler.py`'s local-then-S3 dual-write precedent, with one
correction: `beat_assembler._write_s3` swallows `ClientError` and returns a
`local://` URI as if the write had succeeded, which is a known open bug
(`.planning/phases/phase-2/2-VERIFICATION.md`). `write_manifest` here never
does that — it returns and records an honest `s3_ok`/`s3_reason` (T-03-05).

Write paths are built from `Path(name).name` plus a slot_id that is already
`[a-z0-9_]` by construction from the resolver's own normalisation, never
from a raw external filename (T-03-01).
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from animatic.config import settings
from animatic.core.slot_resolver import Slot

logger = logging.getLogger(__name__)

_LOCAL_MANIFEST = Path("output/assets/manifest.json")
_LOCAL_GENERATED_DIR = Path("output/assets/generated")
_S3_MANIFEST_KEY = "assets/manifest.json"
_S3_ART_PREFIX = "assets/art"


def build_manifest(slots: list[Slot]) -> dict[str, Any]:
    """Assemble the manifest dict, shaped like `beat_assembler._build_beat_list`.

    `s3_ok`/`s3_reason` start unset — `write_manifest` fills them with the
    real outcome of its own S3 attempt before the final local write, so the
    persisted artifact says honestly whether it reached the bucket (NFR-04).
    """
    location_slots = [s for s in slots if s.slot_type == "location"]
    character_slots = [s for s in slots if s.slot_type == "character"]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script": "rocky-1976",
        "total_slots": len(slots),
        "location_slots": len(location_slots),
        "character_slots": len(character_slots),
        "s3_ok": None,
        "s3_reason": "not yet written",
        "slots": [s.to_dict() for s in slots],
    }


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

    s3_ok, s3_reason, s3_uri = _write_bytes_to_s3(
        json.dumps(manifest, indent=2).encode("utf-8"),
        _S3_MANIFEST_KEY,
        content_type="application/json",
    )
    manifest["s3_ok"] = s3_ok
    manifest["s3_reason"] = s3_reason

    _write_local(manifest)

    return {
        "local_path": str(_LOCAL_MANIFEST),
        "s3_uri": s3_uri,
        "s3_ok": s3_ok,
        "s3_reason": s3_reason,
    }


def write_slot_art(slot: Slot, image_bytes: bytes, mime_type: str) -> None:
    """Write generated art for `slot` to local disk, mirror to S3.

    Sets `slot.art_uri`, `slot.art_s3_uri`, `slot.content_hash`, `slot.source`
    and `slot.source_reason` in place. The art bytes are already fully in
    memory (the API response), so the hash is computed directly — the
    chunked-read guard (T-03-03) applies to hashing *reference* art loaded
    from disk, which 03-02 adds.
    """
    ext = _ext_for_mime(mime_type)
    # T-03-01: filename built from Path(name).name plus the resolver's own
    # normalised slot_id — never from a raw external filename. Falls back to
    # slot_id when art_slot_id has not been populated yet (Task 3 fills it;
    # for a location or a bespoke character the two are always equal anyway).
    art_slot_id = slot.art_slot_id or slot.slot_id
    filename = f"{Path(art_slot_id).name}.{ext}"

    local_path = _LOCAL_GENERATED_DIR / filename
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(image_bytes)

    content_hash = hashlib.sha256(image_bytes).hexdigest()

    s3_key = f"{_S3_ART_PREFIX}/{filename}"
    s3_ok, s3_reason, s3_uri = _write_bytes_to_s3(
        image_bytes, s3_key, content_type=mime_type
    )

    slot.art_uri = str(local_path)
    slot.art_s3_uri = s3_uri if s3_ok else ""
    slot.content_hash = content_hash
    slot.source = "generated"
    slot.art_changed = True
    slot.source_reason = (
        f"generated via {settings.gemini_image_model}; sha256={content_hash[:12]}; "
        f"s3_ok={s3_ok} ({s3_reason})"
    )


def _write_local(manifest: dict[str, Any]) -> None:
    _LOCAL_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCAL_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info("Manifest written locally to %s", _LOCAL_MANIFEST)


def _write_bytes_to_s3(
    body: bytes, key: str, content_type: str
) -> tuple[bool, str, str]:
    """Write `body` to `key` in `settings.media_bucket`.

    Never reports a failure as success (T-03-05, fixing the
    `beat_assembler._write_s3` precedent): returns `(s3_ok, s3_reason, uri)`
    with `s3_ok=False` on any error, `uri` still populated with the intended
    location so callers can log what *would* have been written.
    """
    bucket = settings.media_bucket
    uri = f"s3://{bucket}/{key}"
    try:
        # Named profile locally; in ECS the task role is used automatically.
        profile = (
            os.environ.get("AWS_PROFILE", "newaccount")
            if settings.environment == "development"
            else None
        )
        session = boto3.Session(profile_name=profile)
        s3 = session.client("s3", region_name=settings.aws_region)
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
        logger.info("Wrote %s", uri)
        return True, "put_object succeeded", uri
    except ClientError as e:
        logger.warning("S3 write to %s failed: %s", uri, e)
        return False, f"ClientError: {e}", uri
    except Exception as e:  # e.g. ProfileNotFound — beat_assembler leaves this
        # uncaught (open bug per STATE.md); catch broadly here so a missing
        # local AWS profile degrades to an honest s3_ok=False instead of a
        # crash that loses the local write already on disk.
        logger.warning("S3 write to %s failed: %s", uri, e)
        return False, f"{type(e).__name__}: {e}", uri


def _ext_for_mime(mime_type: str) -> str:
    ext = mimetypes.guess_extension(mime_type or "")
    if not ext:
        return "bin"
    return ext.lstrip(".")
