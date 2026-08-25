"""Endpoints for redirecting a generated cut: model sheets, holds, edits, dailies.

Every one of these costs something, and three of them cost nothing. The
difference matters enough that each endpoint reports its price before it is
called (`GET /api/characters` says how many panels a model sheet swap would
redraw) and the UI shows that price on the button.

**Two audiences, one API.** The developer curates what is available — which
model sheets exist, which dailies are on disk. A demo visitor selects from
what is there. Nothing here accepts an arbitrary reference image from the
public internet, because "upload anything, then redraw 31 panels" is a
quota-exhaustion button with a friendly label.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel, Field

from animatic.config import settings
from animatic.core import beat_overrides, panel_edit, quota
from animatic.core.shot_sources import (
    DAILIES_DIR,
    EDITED_PANEL_DIR,
    PANEL_DIR,
    OverlappingDailiesError,
    find_dailies,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

_BEATS = Path("output/beats.json")
_MANIFEST = Path("output/assets/manifest.json")
REFERENCE_ART_DIR = Path("assets/reference-art")

_BEAT_ID_RE = re.compile(r"^s\d+b\d+$")
_SLOT_ID_RE = re.compile(r"^[a-z0-9_]+$")
_VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm"}
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
_MAX_UPLOAD_BYTES = 200 * 1024 * 1024

_QUOTA_MODELS = {
    "panels": lambda: settings.gemini_image_model,
    "voices": lambda: settings.gemini_tts_model,
    "motion": lambda: settings.gemini_veo_model,
}


class HoldRequest(BaseModel):
    hold_secs: float = Field(gt=0, le=120)
    reason: str = ""


class EditRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=500)


# ------------------------------------------------------------------ budget

@router.get("/budget")
async def get_budget() -> dict[str, Any]:
    """What is left of today's generation budget, as far as this machine knows."""
    return quota.budget({label: model() for label, model in _QUOTA_MODELS.items()})


# -------------------------------------------------------------- characters

@router.get("/characters")
async def list_characters() -> dict[str, Any]:
    """Every character, its current art, and what changing it would cost."""
    manifest = _load(_MANIFEST)
    sheets = _available_model_sheets()

    characters = []
    for slot in manifest.get("slots", []):
        if not slot.get("voice_id"):
            continue
        beat_ids = slot.get("beat_ids", [])
        characters.append({
            "slot_id": slot["slot_id"],
            "display_name": slot.get("display_name", slot["slot_id"]),
            "beat_ids": beat_ids,
            "panel_count": len(beat_ids),
            "art_uri": slot.get("art_uri"),
            "source": slot.get("source"),
            "model_sheet": _current_model_sheet(slot["slot_id"]),
            # The number that should be on the button, not discovered after it.
            "redraw_cost_calls": quota.price(panels=len(beat_ids)),
        })

    return {
        "characters": sorted(characters, key=lambda c: -c["panel_count"]),
        "available_model_sheets": sheets,
        "note": (
            "A model sheet only changes the panels once they are generated "
            "with --from-plates. Without it, panels are drawn from text and "
            "the art file is not read."
        ),
    }


@router.get("/model-sheets")
async def list_model_sheets() -> dict[str, Any]:
    """The reference folders a visitor may choose from. Curated, not uploaded."""
    return {"model_sheets": _available_model_sheets()}


# ------------------------------------------------------------------- holds

@router.get("/holds")
async def list_holds() -> dict[str, Any]:
    return {"holds": beat_overrides.load_overrides()}


@router.put("/beat/{beat_id}/hold")
async def set_hold(beat_id: str, body: HoldRequest) -> dict[str, Any]:
    """Hold a beat longer. Costs nothing — re-assembly only."""
    _assert_beat_id(beat_id)
    record = beat_overrides.set_duration(beat_id, body.hold_secs, body.reason)
    return {
        **record,
        "cost_calls": 0,
        "next": "re-render to see it — no generation is needed",
    }


@router.delete("/beat/{beat_id}/hold")
async def clear_hold(beat_id: str) -> dict[str, Any]:
    _assert_beat_id(beat_id)
    if not beat_overrides.clear_duration(beat_id):
        raise HTTPException(status_code=404, detail=f"No hold set on {beat_id}")
    return {"beat_id": beat_id, "action": "cleared", "cost_calls": 0}


# ------------------------------------------------------------ panel edits

@router.post("/panel/{beat_id}/edit")
async def edit_panel(beat_id: str, body: EditRequest) -> dict[str, Any]:
    """Redraw one panel from a written instruction, in place. One image call.

    The response carries `prompt_sent` and `negations_rewritten` because the
    instruction is not sent as typed: a negation gets rendered, so it is turned
    into a statement about what the frame holds. A rewrite the developer cannot
    see is a rewrite they cannot correct.
    """
    _assert_beat_id(beat_id)
    panel = _current_panel(beat_id)

    try:
        data, mime, prompt, notes = panel_edit.edit_panel(panel, body.instruction)
    except panel_edit.PanelEditError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surfaced, not swallowed
        raise HTTPException(
            status_code=502, detail=f"{type(exc).__name__}: {str(exc)[:300]}"
        ) from exc

    quota.record(settings.gemini_image_model)
    record = panel_edit.save_edit(
        beat_id, data, mime, panel, body.instruction, prompt, notes
    )
    return {**record, "cost_calls": 1}


@router.post("/panel/{beat_id}/upload")
async def upload_edited_panel(beat_id: str, file: UploadFile) -> dict[str, Any]:
    """Accept a hand-edited panel. Costs nothing — the file IS the result."""
    _assert_beat_id(beat_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _IMAGE_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"Expected one of {sorted(_IMAGE_SUFFIXES)}, got {suffix or '(none)'}",
        )

    data = await file.read(_MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")

    record = panel_edit.save_edit(
        beat_id, data, f"image/{suffix.lstrip('.')}", _current_panel(beat_id),
        "hand-edited image supplied", "(no model call — the file is the result)", [],
    )
    return {**record, "cost_calls": 0}


@router.delete("/panel/{beat_id}/edit")
async def revert_panel(beat_id: str) -> dict[str, Any]:
    """Drop the edit and go back to the generated panel. Costs nothing."""
    _assert_beat_id(beat_id)
    if not panel_edit.revert(beat_id):
        raise HTTPException(status_code=404, detail=f"No edit on {beat_id}")
    return {"beat_id": beat_id, "action": "reverted", "cost_calls": 0}


# ----------------------------------------------------------------- dailies

@router.get("/dailies")
async def list_dailies() -> dict[str, Any]:
    """Every daily on disk and the beats it covers."""
    beats = _load(_BEATS, required=True)["beats"]
    order = [b["beat_id"] for b in sorted(beats, key=lambda b: (b["scene"], b["beat"]))]
    try:
        covered = find_dailies(order)
    except OverlappingDailiesError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    spans: dict[str, dict[str, Any]] = {}
    for span in covered.values():
        spans[span.span_id] = {
            "span_id": span.span_id,
            "path": str(span.path),
            "beat_ids": list(span.beat_ids),
            "beat_count": len(span.beat_ids),
        }
    return {"dailies": sorted(spans.values(), key=lambda d: d["span_id"])}


@router.post("/daily/{start_beat_id}/{end_beat_id}")
async def upload_daily(
    start_beat_id: str, end_beat_id: str, file: UploadFile
) -> dict[str, Any]:
    """Splice a take across a beat range. Costs nothing.

    The range comes from the PATH, never from the uploaded filename and never
    from the footage — the same rule single-beat footage follows, unchanged by
    the unit going from one beat to several.
    """
    _assert_beat_id(start_beat_id)
    _assert_beat_id(end_beat_id)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _VIDEO_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"Expected one of {sorted(_VIDEO_SUFFIXES)}, got {suffix or '(none)'}",
        )
    data = await file.read(_MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Clip too large")

    DAILIES_DIR.mkdir(parents=True, exist_ok=True)
    target = DAILIES_DIR / f"{start_beat_id}-{end_beat_id}{suffix}"
    target.write_bytes(data)

    # Reject an overlap by removing what was just written, rather than leaving
    # the tree in a state where every later call 409s.
    beats = _load(_BEATS, required=True)["beats"]
    order = [b["beat_id"] for b in sorted(beats, key=lambda b: (b["scene"], b["beat"]))]
    try:
        covered = find_dailies(order)
    except OverlappingDailiesError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    span = covered.get(start_beat_id)
    return {
        "span_id": f"{start_beat_id}-{end_beat_id}",
        "path": str(target),
        "beat_ids": list(span.beat_ids) if span else [],
        "cost_calls": 0,
        "next": "re-render to see it — the take plays its own length with its own sound",
    }


@router.delete("/daily/{span_id}")
async def delete_daily(span_id: str) -> dict[str, Any]:
    """Remove a daily, restoring the animatic shots underneath it."""
    if not re.match(r"^s\d+b\d+-s\d+b\d+$", span_id):
        raise HTTPException(status_code=400, detail=f"Bad span id {span_id!r}")
    if not DAILIES_DIR.is_dir():
        raise HTTPException(status_code=404, detail="No dailies")

    removed = [
        p.name for p in sorted(DAILIES_DIR.iterdir())
        if p.suffix.lower() in _VIDEO_SUFFIXES and p.stem.lower().startswith(span_id.lower())
    ]
    for name in removed:
        (DAILIES_DIR / name).unlink(missing_ok=True)
    if not removed:
        raise HTTPException(status_code=404, detail=f"No daily for {span_id}")
    return {"span_id": span_id, "action": "removed", "removed": removed, "cost_calls": 0}


# ----------------------------------------------------------------- helpers

def _available_model_sheets() -> list[dict[str, Any]]:
    """Reference folders on disk. Curated by the developer, never uploaded."""
    if not REFERENCE_ART_DIR.is_dir():
        return []
    sheets = []
    for folder in sorted(REFERENCE_ART_DIR.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        images = [
            p.name for p in sorted(folder.iterdir())
            if p.suffix.lower() in _IMAGE_SUFFIXES
        ]
        if images:
            sheets.append({
                "slot_id": folder.name,
                "path": str(folder),
                "image_count": len(images),
                "images": images,
            })
    return sheets


def _current_model_sheet(slot_id: str) -> str | None:
    folder = REFERENCE_ART_DIR / slot_id
    return str(folder) if folder.is_dir() else None


def _current_panel(beat_id: str) -> Path:
    """The panel an edit should be applied to — the edited one if there is one."""
    for directory in (EDITED_PANEL_DIR, PANEL_DIR):
        for suffix in (".jpg", ".jpeg", ".png"):
            path = directory / f"{beat_id}{suffix}"
            if path.exists():
                return path
    raise HTTPException(status_code=404, detail=f"No panel for {beat_id}")


def _assert_beat_id(beat_id: str) -> None:
    if not _BEAT_ID_RE.match(beat_id):
        raise HTTPException(
            status_code=400, detail=f"beat_id {beat_id!r} does not match ^s\\d+b\\d+$"
        )


def _load(path: Path, required: bool = False) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise HTTPException(status_code=503, detail=f"{path} is missing")
        return {}
    return json.loads(path.read_text())
