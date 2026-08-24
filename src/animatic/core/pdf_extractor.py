"""PDF text extractor — splits Rocky screenplay into scenes by INT/EXT headings."""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

# Matches screenplay scene headings like:
#   1 INT. BLUE DOOR FIGHT CLUB - NIGHT 1
#   5 EXT. STREET - NIGHT 5
# Scene number appears at both start and end of the line.
_HEADING_RE = re.compile(
    r"^(\d+)\s+((?:INT|EXT)\..*?)\s+\1\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_scenes(
    pdf_path: str | Path,
    first_n: int = 8,
) -> dict[int, str]:
    """Extract raw text for the first N scenes from a screenplay PDF.

    Scene numbers in screenplays are not always contiguous (e.g. Rocky
    skips scene 2). This function takes the first N scenes by order of
    appearance, not by scene number value.

    Args:
        pdf_path: Path to the PDF file.
        first_n: Number of scenes to extract from the start (default: 8).

    Returns:
        dict mapping scene_number → raw scene text (heading included).
    """
    pdf_path = Path(pdf_path)
    full_text = _extract_full_text(pdf_path)
    scene_map = _split_by_scene(full_text)

    # Take first N scenes in order of appearance
    sorted_scenes = sorted(scene_map.items())
    return dict(sorted_scenes[:first_n])


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
