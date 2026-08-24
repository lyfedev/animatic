"""PDF text extractor — splits Rocky screenplay into scenes by INT/EXT headings."""

from __future__ import annotations

import re
from itertools import islice
from pathlib import Path

import pdfplumber

# Matches a numbered screenplay scene heading. The scene number appears at
# BOTH ends of the line, which is what makes this safe to match loosely:
#   1 INT. BLUE DOOR FIGHT CLUB - NIGHT 1
#   5 EXT. STREET - NIGHT 5
#   2 SUPERIMPOSE OVER ACTION... "NOVEMBER 12, 1975 - 2
#
# Deliberately NOT restricted to INT./EXT. Scene 2 of Rocky is a SUPERIMPOSE
# title card, and an INT/EXT-only pattern silently swallowed it into scene 1 —
# which shifted the whole demo range to 1,3-9 and dropped scene 2 entirely.
_HEADING_RE = re.compile(
    r"^(\d+)\s+(\S.*?)\s+\1\s*$",
    re.MULTILINE,
)


def extract_scenes(
    pdf_path: str | Path,
    first_n: int = 8,
) -> dict[int, str]:
    """Extract raw text for the first N scenes from a screenplay PDF.

    For the demo this returns Rocky scenes 1-8, which is the fixed content
    set. Scene 2 is a SUPERIMPOSE title card rather than an INT/EXT slug —
    it is a real scene and must be present.

    Scenes are taken in order of appearance in the document, not by scene
    number value, so a renumbered insert cannot be pulled forward.

    Args:
        pdf_path: Path to the PDF file.
        first_n: Number of scenes to extract from the start (default: 8).

    Returns:
        dict mapping scene_number → raw scene text (heading included),
        in order of appearance.
    """
    pdf_path = Path(pdf_path)
    full_text = _extract_full_text(pdf_path)
    scene_map = _split_by_scene(full_text)

    # _split_by_scene builds the dict in match order, so insertion order
    # is already appearance order — slice it without re-sorting.
    return dict(islice(scene_map.items(), first_n))


def _extract_full_text(pdf_path: Path) -> str:
    """Extract all text from PDF, joining pages with newlines."""
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n".join(pages)


def _split_by_scene(text: str) -> dict[int, str]:
    """Split full screenplay text into scenes by INT/EXT heading.

    Returns dict of scene_number → text block (heading + body).
    """
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return {}

    scene_map: dict[int, str] = {}
    for i, match in enumerate(matches):
        scene_num = int(match.group(1))
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        scene_map[scene_num] = text[start:end].strip()

    return scene_map
