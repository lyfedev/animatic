"""Scene timing derived from screenplay page geometry.

One script page is one minute of screen time — the standard industry
heuristic. A page is a fixed grid of single-spaced 12pt lines, so a scene's
share of that minute is just its share of the page, measured top to bottom
and counting blank lines.

Blank lines matter: they are the script's own pacing notation. But
`extract_text()` collapses them, so this module works from character
positions instead, converting each line's vertical offset into a slot on the
page's line grid. A scene runs from its own heading to the next scene's
heading, so scenes tile the page exactly and every line is claimed once.

This needs nothing but the PDF, which is what the pipeline will have for any
script. Nothing here is calibrated against a particular film.
"""

from __future__ import annotations

import logging
import re
import statistics
from pathlib import Path
from typing import Any

import pdfplumber
from animatic.core.script_source import resolve_scene_count

logger = logging.getLogger(__name__)

# One page of screenplay is one minute of screen time.
LINES_PER_PAGE = 54
PAGE_SECS = 60.0

# Fallbacks if a PDF is too irregular to measure. 12pt single-spaced Courier
# on US Letter is the screenplay standard.
_DEFAULT_PITCH = 12.0
_DEFAULT_SLOTS_PER_PAGE = 57

_HEADING_RE = re.compile(r"^(\d+)\s+(\S.*?)\s+\1\s*$")


def secs_for_lines(lines: int) -> float:
    """Screen time for a span of script lines, at one page per minute."""
    return round(lines / LINES_PER_PAGE * PAGE_SECS, 1)


def scene_line_counts(
    pdf_path: str | Path, first_n: int | None = None
) -> dict[int, int]:
    """Line count per scene, blanks included, for the first N scenes.

    A scene spans from its heading line to the next scene's heading, so it
    owns the blank separator that follows it and the counts tile the page.

    Returns:
        dict mapping scene_number → line count (heading and blanks included).
    """
    first_n = resolve_scene_count(first_n)
    with pdfplumber.open(Path(pdf_path)) as pdf:
        pages = [page.extract_text_lines() for page in pdf.pages]

    pitch, page_top, slots = _measure_grid(pages)
    logger.info(
        "page grid: pitch=%.1fpt top=%.1fpt slots=%d", pitch, page_top, slots
    )

    headings: list[tuple[int, int]] = []
    for page_index, lines in enumerate(pages):
        for line in lines:
            match = _HEADING_RE.match(line["text"].strip())
            if match:
                slot = _global_slot(page_index, line["top"], pitch, page_top, slots)
                headings.append((int(match.group(1)), slot))
    headings.sort(key=lambda h: h[1])

    counts: dict[int, int] = {}
    for (scene, slot), (_, next_slot) in zip(headings, headings[1:]):
        counts[scene] = max(1, next_slot - slot)
        if len(counts) == first_n:
            break
    return counts


def scene_targets(
    pdf_path: str | Path, first_n: int | None = None
) -> dict[int, float]:
    """Target screen time in seconds per scene, from page geometry."""
    return {
        scene: secs_for_lines(lines)
        for scene, lines in scene_line_counts(pdf_path, first_n).items()
    }


def _measure_grid(pages: list[list[dict[str, Any]]]) -> tuple[float, float, int]:
    """Recover the page's line grid: pitch, top margin, slots per page.

    Measured rather than assumed so a script set in a different point size
    still times correctly. Front matter (title page, cast list) is skipped —
    it is sparse and would skew the top margin.
    """
    tops_per_page = [
        sorted({round(line["top"], 1) for line in lines}) for lines in pages if lines
    ]
    body = [tops for tops in tops_per_page if len(tops) >= 20]
    if not body:
        return _DEFAULT_PITCH, 0.0, _DEFAULT_SLOTS_PER_PAGE

    deltas = [
        round(b - a, 1)
        for tops in body
        for a, b in zip(tops, tops[1:])
        # Ignore sub-line jitter and multi-line gaps; the pitch is the mode of
        # adjacent-line deltas.
        if 4.0 < (b - a) < 20.0
    ]
    pitch = statistics.mode(deltas) if deltas else _DEFAULT_PITCH

    page_top = min(tops[0] for tops in body)
    span = max(tops[-1] for tops in body) - page_top
    slots = int(round(span / pitch)) + 1
    return pitch, page_top, slots


def _global_slot(
    page_index: int, top: float, pitch: float, page_top: float, slots: int
) -> int:
    """Absolute line-slot index, so spans across a page break stay correct."""
    return page_index * slots + int(round((top - page_top) / pitch))
