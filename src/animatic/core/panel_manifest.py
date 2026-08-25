"""Panel index assembler — writes each generated panel to local disk and
S3, and the running `output/panels/index.json` that names every panel's
shot size, prompt, dependent asset slots and a machine-readable reason.

Follows `asset_manifest.py`'s local-then-S3 dual-write and honest
`s3_ok`/`s3_reason` precedent (T-03-05), with one structural difference:
`write_index` is called after EACH panel is resolved — generated, reused
or failed — by `panel_generator.generate_missing_panels`, not once at the
end of the run. A run interrupted at panel 40 of 49 must keep 40 entries on
disk and in S3; batching the write to the end of the loop would lose all of
them (T-04-03).

Panel filenames are `Path(beat_id).name`, with `beat_id` asserted against
`^s\\d+b\\d+$` before it is ever used to build a path — never built from
beat content (T-04-02, mirrors `asset_manifest._write_art_bytes`'s rule).
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from animatic.core.s3_writer import put_bytes

logger = logging.getLogger(__name__)

_LOCAL_PANELS_DIR = Path("output/panels")
_LOCAL_INDEX = Path("output/panels/index.json")
_S3_INDEX_KEY = "panels/index.json"
_S3_PANEL_PREFIX = "panels"

_BEAT_ID_RE = re.compile(r"^s\d+b\d+$")


def write_panel(beat_id: str, image_bytes: bytes, mime_type: str) -> tuple[str, Path, str, bool, str]:
    """Write one panel's bytes to local disk and S3.

    Returns (content_hash, local_path, s3_uri, s3_ok, s3_reason). `beat_id`
    is asserted against `^s\\d+b\\d+$` before it is used to build a path —
    no path segment is ever built from beat content (T-04-02).
    """
    assert _BEAT_ID_RE.match(beat_id), f"beat_id {beat_id!r} does not match ^s\\d+b\\d+$"
    ext = _ext_for_mime(mime_type)
    filename = f"{Path(beat_id).name}.{ext}"

    local_path = _LOCAL_PANELS_DIR / filename
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(image_bytes)

    content_hash = hashlib.sha256(image_bytes).hexdigest()

    s3_key = f"{_S3_PANEL_PREFIX}/{filename}"
    result = put_bytes(s3_key, image_bytes, content_type=mime_type)
    reason = result.error or "put_object succeeded"

    return content_hash, local_path, result.uri, result.ok, reason


def build_index(
    entries: list[dict[str, Any]],
    beats_doc: dict[str, Any],
    manifest: dict[str, Any],
    beats_source: str,
    manifest_source: str,
    prompt_template_version: str,
) -> dict[str, Any]:
    """Assemble the index dict from every entry resolved so far.

    Entries are sorted into beat order (scene, then beat) before writing,
    so `output/panels/index.json` is always in the order Phase 7 assembles
    from, regardless of the order beats were processed or regenerated in.
    """
    ordered = sorted(entries, key=lambda e: (e["scene"], e["beat"]))
    generated_count = sum(1 for e in ordered if e["source"] == "generated")
    reused_count = sum(1 for e in ordered if e["source"] == "reused")
    failed_count = sum(1 for e in ordered if e["source"] == "generation_failed")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script": "rocky-1976",
        "beats_source": beats_source,
        "beats_generated_at": beats_doc.get("generated_at", ""),
        "assets_manifest_source": manifest_source,
        "assets_manifest_generated_at": manifest.get("generated_at", ""),
        "prompt_template_version": prompt_template_version,
        "total_panels": len(ordered),
        "generated_count": generated_count,
        "reused_count": reused_count,
        "failed_count": failed_count,
        "s3_ok": None,
        "s3_reason": "not yet written",
        "panels": ordered,
    }


def write_index(index: dict[str, Any]) -> dict[str, Any]:
    """Write `index` to local disk and S3, local-then-S3 (as `write_manifest`).

    Returns a result dict: `local_path`, `s3_uri`, `s3_ok` (bool),
    `s3_reason`. Mutates `index["s3_ok"]`/`index["s3_reason"]` in place so
    the returned index dict (and the on-disk copy) is never stale about
    whether it reached the bucket.
    """
    _write_local(index)

    result = put_bytes(
        _S3_INDEX_KEY,
        json.dumps(index, indent=2).encode("utf-8"),
        content_type="application/json",
    )
    index["s3_ok"] = result.ok
    index["s3_reason"] = result.error or "put_object succeeded"

    _write_local(index)

    return {
        "local_path": str(_LOCAL_INDEX),
        "s3_uri": result.uri,
        "s3_ok": result.ok,
        "s3_reason": index["s3_reason"],
    }


def _write_local(index: dict[str, Any]) -> None:
    _LOCAL_INDEX.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCAL_INDEX, "w") as f:
        json.dump(index, f, indent=2)
    logger.info("Panel index written locally to %s", _LOCAL_INDEX)


def _ext_for_mime(mime_type: str) -> str:
    ext = mimetypes.guess_extension(mime_type or "")
    if not ext:
        return "bin"
    return ext.lstrip(".")
