"""Endpoints for the cut: state, media, footage swap, and a live render.

DR-02 is the demanding one — "progress indicators must reflect real work".
The honest way to satisfy that is not to report progress about work; it is to
stream events FROM the work as it happens. `GET /api/render` is a
Server-Sent Events stream that runs the assembly inside the response and emits
one event per shot as ffmpeg finishes it. There is no percentage counter
ticking on a timer anywhere in this file, because there is nothing to tick:
the client learns a shot is done when the shot is done.

DR-03 is served by telling the truth about where each shot came from. The
per-shot events carry `source` (`still`/`motion`/`footage`) and the render
summary carries which media was pre-computed, so the UI can disclose it
without inferring anything.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from animatic.core.cut_manifest import build_index as build_cut_index
from animatic.core.cut_manifest import write_index as write_cut_index
from animatic.core.shot_sources import FOOTAGE_DIR, PANEL_DIR
from animatic.core.shot_state import build_state, write_state
from animatic.core.video_assembler import (
    CUT_TEMPLATE_VERSION,
    build_shot,
    concat_shots,
    plan_shots,
    probe_duration,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

_BEATS = Path("output/beats.json")
_AUDIO_INDEX = Path("output/audio/index.json")
_MOTION_INDEX = Path("output/motion/index.json")
_CUT_INDEX = Path("output/video/index.json")
_VIDEO_DIR = Path("output/video")

_BEAT_ID_RE = re.compile(r"^s\d+b\d+$")
_ALLOWED_UPLOAD_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm"}
_MAX_UPLOAD_BYTES = 200 * 1024 * 1024

# DR-04's three states, as render modes. Named rather than expressed as two
# booleans at the call site so the UI and the API agree on what they mean.
RENDER_MODES = {
    "panels": {"ignore_footage": True, "ignore_motion": True},
    "animatic": {"ignore_footage": True, "ignore_motion": False},
    "partial": {"ignore_footage": False, "ignore_motion": False},
}

# One render at a time. Two concurrent ffmpeg passes over the same 49 shots
# would fight for CPU and race on the output file, and the demo is a single
# hosted box.
_render_lock = asyncio.Lock()


class FootageResponse(BaseModel):
    beat_id: str
    action: str
    detail: str
    real_footage_pct: float


@router.get("/state")
async def get_state() -> dict[str, Any]:
    """Per-shot state, computed from what is on disk right now."""
    return build_state(
        _load(_BEATS, required=True),
        _load(_AUDIO_INDEX),
        _load(_MOTION_INDEX),
        _load(_CUT_INDEX),
    )


@router.get("/cut")
async def get_cut(mode: str = "partial", scene: int | None = None) -> FileResponse:
    """Serve a rendered cut. 404 rather than a stale file from another mode.

    `scene` has to be here because a scene-scoped render writes to its own
    file. Without it the URL returned by a `scene=1` render pointed at the
    whole-cut filename and 404'd — the mode was carried through and the scene
    silently was not.
    """
    path = _cut_path(mode, scene)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No cut rendered for mode {mode!r} — POST /api/render first",
        )
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@router.get("/panel/{beat_id}")
async def get_panel(beat_id: str) -> FileResponse:
    """Serve one beat's panel, for the shot strip in the UI."""
    _assert_beat_id(beat_id)
    for suffix in (".jpg", ".jpeg", ".png"):
        path = PANEL_DIR / f"{beat_id}{suffix}"
        if path.exists():
            return FileResponse(path, media_type=f"image/{suffix.lstrip('.')}")
    raise HTTPException(status_code=404, detail=f"No panel for {beat_id}")


@router.post("/footage/{beat_id}", response_model=FootageResponse)
async def upload_footage(beat_id: str, file: UploadFile) -> FootageResponse:
    """Accept a footage clip for one beat (FR-07).

    The beat number comes from the PATH, not from the uploaded filename and
    certainly not from the footage — a visitor's file can be called anything.
    """
    _assert_beat_id(beat_id)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported type {suffix or '(none)'} — "
                   f"expected one of {sorted(_ALLOWED_UPLOAD_SUFFIXES)}",
        )

    data = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Clip is larger than {_MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")

    FOOTAGE_DIR.mkdir(parents=True, exist_ok=True)
    _clear_footage(beat_id)
    target = FOOTAGE_DIR / f"{beat_id}{suffix}"
    target.write_bytes(data)

    state = build_state(_load(_BEATS, required=True), _load(_AUDIO_INDEX),
                        _load(_MOTION_INDEX), _load(_CUT_INDEX))
    return FootageResponse(
        beat_id=beat_id,
        action="added",
        detail=f"{len(data)} bytes written to {target}",
        real_footage_pct=state["real_footage_pct"],
    )


@router.delete("/footage/{beat_id}", response_model=FootageResponse)
async def delete_footage(beat_id: str) -> FootageResponse:
    """Remove a beat's footage, restoring its animatic shot (criterion 4)."""
    _assert_beat_id(beat_id)
    removed = _clear_footage(beat_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"No footage for {beat_id}")

    state = build_state(_load(_BEATS, required=True), _load(_AUDIO_INDEX),
                        _load(_MOTION_INDEX), _load(_CUT_INDEX))
    return FootageResponse(
        beat_id=beat_id,
        action="removed",
        detail=f"removed {', '.join(removed)}",
        real_footage_pct=state["real_footage_pct"],
    )


@router.get("/render")
async def render(mode: str = "partial", scene: int | None = None) -> StreamingResponse:
    """Assemble the cut, streaming one event per shot as it is encoded.

    Server-Sent Events rather than a job id and a polling loop: the work is
    already sequential and already knows when each shot lands, so the honest
    thing is to emit that. Nothing here is on a timer.
    """
    if mode not in RENDER_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown mode {mode!r} — expected one of {sorted(RENDER_MODES)}",
        )

    return StreamingResponse(
        _render_events(mode, scene),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _render_events(mode: str, scene: int | None) -> AsyncIterator[str]:
    if _render_lock.locked():
        yield _event("error", {"detail": "A render is already running"})
        return

    async with _render_lock:
        try:
            beats_doc = _load(_BEATS, required=True)
            audio_index = _load(_AUDIO_INDEX)
            shots = plan_shots(beats_doc, audio_index, scene=scene, **RENDER_MODES[mode])
        except Exception as exc:  # noqa: BLE001 — reported to the client
            yield _event("error", {"detail": str(exc)})
            return

        if not shots:
            yield _event("error", {"detail": "No shots to assemble"})
            return

        yield _event("start", {
            "mode": mode,
            "total_shots": len(shots),
            "planned_secs": round(sum(s.secs for s in shots), 2),
            "sources": _count_sources(shots),
        })

        out_path = _cut_path(mode, scene)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            segments = []
            for position, shot in enumerate(shots):
                try:
                    # ffmpeg is blocking; a thread keeps the event loop free so
                    # the stream actually flushes between shots rather than
                    # arriving in one burst at the end.
                    segment = await asyncio.to_thread(
                        build_shot, shot, tmp_dir / f"{position:03d}.mp4"
                    )
                except Exception as exc:  # noqa: BLE001 — reported, run stops
                    yield _event("error", {
                        "beat_id": shot.beat_id, "detail": str(exc)[:400]
                    })
                    return

                segments.append(segment)
                yield _event("shot", {
                    "index": position + 1,
                    "total": len(shots),
                    "beat_id": shot.beat_id,
                    "scene": shot.scene,
                    "secs": round(shot.secs, 2),
                    "source": shot.source.kind,
                    "source_reason": shot.source.reason,
                })

            try:
                await asyncio.to_thread(concat_shots, segments, out_path)
            except Exception as exc:  # noqa: BLE001
                yield _event("error", {"detail": str(exc)[:400]})
                return

        index = build_cut_index(
            [s.to_entry() for s in shots], beats_doc, audio_index,
            _load(Path("output/panels/index.json")), out_path,
            probe_duration(out_path), CUT_TEMPLATE_VERSION,
        )

        # A scene-scoped render is a preview, not the cut of record. Writing
        # its index would replace a 49-shot manifest with a 1-shot one and
        # leave `state.json` describing a cut nobody asked for — which is
        # exactly what a run of the API tests did to the working tree.
        if scene is None:
            await asyncio.to_thread(write_cut_index, index)
            state = build_state(beats_doc, audio_index, _load(_MOTION_INDEX), index)
            await asyncio.to_thread(write_state, state)

        yield _event("done", {
            "mode": mode,
            "cut_url": (
                f"/api/cut?mode={mode}"
                + (f"&scene={scene}" if scene is not None else "")
            ),
            "measured_secs": index["measured_secs"],
            "sources": index["shots_by_source"],
            "real_footage_pct": index["real_footage_pct"],
            # DR-03: the render itself generated nothing — every panel, clip
            # and motion file it assembled was pre-computed. Say so.
            "media_precomputed": True,
            "cache_note": (
                "Panels, voices and motion were generated ahead of time and "
                "reused. This render assembled them; it did not regenerate them."
            ),
        })


def _event(name: str, payload: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload)}\n\n"


def _count_sources(shots: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for shot in shots:
        counts[shot.source.kind] = counts.get(shot.source.kind, 0) + 1
    return counts


def _cut_path(mode: str, scene: int | None = None) -> Path:
    stem = f"animatic-{mode}" if scene is None else f"animatic-{mode}-scene{scene}"
    return _VIDEO_DIR / f"{stem}.mp4"


def _clear_footage(beat_id: str) -> list[str]:
    """Remove every footage file tagged with this beat. Returns their names."""
    if not FOOTAGE_DIR.is_dir():
        return []
    removed = []
    for path in sorted(FOOTAGE_DIR.iterdir()):
        if path.suffix.lower() not in _ALLOWED_UPLOAD_SUFFIXES:
            continue
        stem = path.stem.lower()
        if stem == beat_id.lower() or stem.startswith(f"{beat_id.lower()}-") or \
                stem.startswith(f"{beat_id.lower()}_"):
            path.unlink()
            removed.append(path.name)
    return removed


def _assert_beat_id(beat_id: str) -> None:
    """A path segment is never built from client input without this check."""
    if not _BEAT_ID_RE.match(beat_id):
        raise HTTPException(
            status_code=400,
            detail=f"beat_id {beat_id!r} does not match ^s\\d+b\\d+$",
        )


def _load(path: Path, required: bool = False) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise HTTPException(
                status_code=503,
                detail=f"{path} is missing — the pipeline has not run yet",
            )
        return {}
    return json.loads(path.read_text())
