"""FastAPI endpoint for live beat parsing."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from animatic.core.beat_assembler import assemble_and_write
from animatic.core.beat_extractor import extract_beats
from animatic.core.pdf_extractor import extract_scenes

logger = logging.getLogger(__name__)
router = APIRouter()

_PDF_PATH = Path("docs/rocky-1976.pdf")


class SceneSummary(BaseModel):
    scene: int
    beat_count: int
    action: int
    dialogue: int
    establishing: int
    motion_candidates: int
    duration_secs: float


class BeatsParseResponse(BaseModel):
    total_beats: int
    total_duration_secs: float
    pct_motion_candidates: float
    s3_uri: str
    scenes: list[SceneSummary]


@router.post("/beats/parse", response_model=BeatsParseResponse)
async def parse_beats() -> BeatsParseResponse:
    """Parse Rocky screenplay into a beat list.

    Executes live — beat parsing runs on every call (not cached).
    """
    if not _PDF_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Screenplay PDF not found: {_PDF_PATH}")

    logger.info("Starting beat parsing pipeline")

    scenes = extract_scenes(_PDF_PATH, first_n=8)
    scenes_beats: dict[int, list] = {}
    scene_summaries: list[SceneSummary] = []

    for scene_num, scene_text in sorted(scenes.items()):
        beats = extract_beats(scene_num, scene_text)
        scenes_beats[scene_num] = beats
        scene_summaries.append(SceneSummary(
            scene=scene_num,
            beat_count=len(beats),
            action=sum(1 for b in beats if b.type == "action"),
            dialogue=sum(1 for b in beats if b.type == "dialogue"),
            establishing=sum(1 for b in beats if b.type == "establishing"),
            motion_candidates=sum(1 for b in beats if b.motion_candidate),
            duration_secs=round(sum(b.duration_secs for b in beats), 1),
        ))

    s3_uri = assemble_and_write(scenes_beats)

    total_beats = sum(s.beat_count for s in scene_summaries)
    total_duration = sum(s.duration_secs for s in scene_summaries)
    motion_total = sum(s.motion_candidates for s in scene_summaries)
    pct_motion = round(motion_total / total_beats * 100, 1) if total_beats else 0.0

    return BeatsParseResponse(
        total_beats=total_beats,
        total_duration_secs=round(total_duration, 1),
        pct_motion_candidates=pct_motion,
        s3_uri=s3_uri,
        scenes=scene_summaries,
    )
