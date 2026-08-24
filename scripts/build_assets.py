#!/usr/bin/env python3
"""CLI: resolve asset slots, generate temp art, and write the asset manifest.

Usage:
    python scripts/build_assets.py --dry-run
    python scripts/build_assets.py --only int_blue_door_fight_club
    python scripts/build_assets.py --beats output/beats.json --pdf docs/rocky-1976.pdf
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

# Ensure src/ is on the path when run from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from animatic.core.asset_generator import generate_slot_art
from animatic.core.asset_manifest import build_manifest, write_manifest, write_slot_art
from animatic.core.slot_resolver import resolve_slots
from animatic.core.style import build_slot_prompt


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve asset slots and build the manifest")
    parser.add_argument(
        "--beats",
        default="output/beats.json",
        help="Path to the beat list (default: output/beats.json)",
    )
    parser.add_argument(
        "--pdf",
        default="docs/rocky-1976.pdf",
        help="Path to screenplay PDF (default: docs/rocky-1976.pdf)",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Resolve and generate art for exactly one slot_id (tracer path)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve slots and write the manifest without calling the image API",
    )
    args = parser.parse_args()

    beats_path = Path(args.beats)
    pdf_path = Path(args.pdf)
    if not beats_path.exists():
        print(f"Error: beat list not found at {beats_path}", file=sys.stderr)
        sys.exit(1)
    if not pdf_path.exists():
        print(f"Error: PDF not found at {pdf_path}", file=sys.stderr)
        sys.exit(1)

    start = time.time()
    beats = json.loads(beats_path.read_text())

    print(f"\nBuilding asset manifest from {beats_path} + {pdf_path}\n")

    print("Step 1/3  Resolving slots...")
    slots = resolve_slots(beats, pdf_path)
    print(f"          Resolved {len(slots)} slot(s)")
    for slot in slots:
        print(f"            {slot.priority_rank or '-':>2}  {slot.slot_id:32s} "
              f"({slot.slot_type}, {slot.beats} beats, {slot.duration_secs}s)")

    if args.only:
        matched = [s for s in slots if s.slot_id == args.only]
        if not matched:
            print(f"Error: no slot named {args.only!r} among {[s.slot_id for s in slots]}",
                  file=sys.stderr)
            sys.exit(1)
        slots = matched
        print(f"          --only {args.only!r}: generating 1 slot\n")

    print("\nStep 2/3  Generating art...")
    if args.dry_run:
        print("          --dry-run: skipping every API call; art fields left unresolved")
    else:
        for slot in slots:
            t0 = time.time()
            prompt = build_slot_prompt(slot, _subject_note(slot))
            slot.prompt = prompt
            image_bytes, mime_type = generate_slot_art(slot, prompt)
            write_slot_art(slot, image_bytes, mime_type)
            elapsed = time.time() - t0
            print(f"          {slot.slot_id:32s} -> {slot.art_uri}  ({elapsed:.1f}s)")

    print("\nStep 3/3  Writing manifest...")
    manifest = build_manifest(slots)
    result = write_manifest(manifest)

    elapsed_total = time.time() - start
    print(f"\n✓ Done in {elapsed_total:.1f}s")
    print(f"  Slots       : {len(slots)}")
    print(f"  Local       : {result['local_path']}")
    print(f"  S3          : {result['s3_uri']} (s3_ok={result['s3_ok']}: {result['s3_reason']})\n")


_COLOR_WORD_RE = re.compile(
    r"\b(black|white|red|blue|green|yellow|orange|purple|pink|brown|"
    r"grey|gray|gold|silver)\b",
    re.IGNORECASE,
)


def _location_description(display_name: str) -> str:
    """Strip literal colour words out of a location name before it reaches
    the prompt.

    The output is monochrome by design (STYLE_BLOCK), but a location whose
    own name names a colour — this corpus's "BLUE DOOR FIGHT CLUB" — reads
    to the model as an instruction to paint that colour onto whatever it
    names (a blue door), overriding the style block's two-tone rule. This
    is a general defence (any color word, not a hardcoded per-slot fix).
    """
    stripped = _COLOR_WORD_RE.sub("", display_name).strip()
    return re.sub(r"\s+", " ", stripped)


def _subject_note(slot) -> str:
    """Build the subject clause for one slot's generation prompt.

    Locations ask for an empty establishing view — no people, no in-scene
    signage — since a bare `"<name> (location)"` note leaves the model free
    to invent a populated action scene (a fight in progress, a crowd with
    fully rendered faces, a hand-lettered banner), which is exactly the
    "words drawn into the frame" and detailed-face failure modes D-09 and
    PROJECT.md's visual-style rule both rule out.
    """
    if slot.slot_type == "location":
        # Deliberately lowercase, unquoted and colour-stripped — a quoted
        # proper noun reads to the model as a label to paint onto a sign
        # (RESEARCH Pitfall 2), and a colour word in the name reads as an
        # instruction to break the monochrome style — both observed on
        # this exact slot (a hand-lettered "BLUE DOOR FIGHT CLUB" sign and
        # a blue-filled door) before this prompt was tightened.
        description = _location_description(slot.display_name).lower()
        return (
            f"An empty establishing view of the physical space itself — "
            f"the architecture, fixtures and props implied by "
            f"{description} — with no people present anywhere in the "
            f"shot. Every door, wall, poster board and nameplate in the "
            f"room is left a plain blank shape, exactly as bare as the "
            f"rest of the linework, carrying no lettering of its own — "
            f"nothing in the picture is captioned, labeled or "
            f"hand-painted with this location's own name or any other "
            f"word."
        )
    return f"{slot.display_name.title()}, standing alone against a blank background."


if __name__ == "__main__":
    main()
