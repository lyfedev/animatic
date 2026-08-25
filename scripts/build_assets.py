#!/usr/bin/env python3
"""CLI: resolve asset slots, ingest reference art, generate temp art for the
rest, and write the asset manifest.

Usage:
    python scripts/build_assets.py --dry-run
    python scripts/build_assets.py --only int_blue_door_fight_club
    python scripts/build_assets.py --force
    python scripts/build_assets.py --reference-dir assets/reference-art
    python scripts/build_assets.py --beats output/beats.json --pdf docs/rocky-1976.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure src/ is on the path when run from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from animatic.core.asset_generator import generate_missing_art
from animatic.core.asset_manifest import build_manifest, write_manifest, write_reference_art
from animatic.core.reference_art import resolve_reference_art
from animatic.core.slot_resolver import resolve_slots

_DEFAULT_REFERENCE_DIR = Path("assets/reference-art")
_MANIFEST_PATH = Path("output/assets/manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve asset slots, ingest reference art, generate the rest, write the manifest"
    )
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
        "--reference-dir",
        default=str(_DEFAULT_REFERENCE_DIR),
        help="Path to supplied reference art (default: assets/reference-art)",
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate every slot's art even if an unchanged prompt is already on disk",
    )
    args = parser.parse_args()

    beats_path = Path(args.beats)
    pdf_path = Path(args.pdf)
    reference_dir = Path(args.reference_dir)
    if not beats_path.exists():
        print(f"Error: beat list not found at {beats_path}", file=sys.stderr)
        sys.exit(1)
    if not pdf_path.exists():
        print(f"Error: PDF not found at {pdf_path}", file=sys.stderr)
        sys.exit(1)

    start = time.time()
    beats = json.loads(beats_path.read_text())

    previous_manifest = None
    if _MANIFEST_PATH.exists():
        try:
            previous_manifest = json.loads(_MANIFEST_PATH.read_text())
        except json.JSONDecodeError:
            previous_manifest = None

    print(f"\nBuilding asset manifest from {beats_path} + {pdf_path}\n")

    print("Step 1/4  Resolving slots...")
    slots = resolve_slots(beats, pdf_path)
    print(f"          Resolved {len(slots)} slot(s)")
    for slot in slots:
        print(
            f"            {slot.priority_rank or '-':>2}  {slot.slot_id:32s} "
            f"({slot.slot_type}, {slot.beats} beats, {slot.duration_secs}s, "
            f"{slot.share_pct}% share)"
        )

    # A partial run regenerates ONE slot but must still write a whole
    # manifest. Narrowing `slots` here and letting build_manifest run over the
    # remainder wrote a one-entry manifest over the full sixteen — locally and
    # in S3 — leaving every other slot's art on disk but unreferenced. The
    # untouched slots stay in the list and are simply not regenerated.
    regenerate_only: set[str] | None = None
    if args.only:
        if args.only not in {s.slot_id for s in slots}:
            print(
                f"Error: no slot named {args.only!r} among {[s.slot_id for s in slots]}",
                file=sys.stderr,
            )
            sys.exit(1)
        regenerate_only = {args.only}
        print(
            f"          --only {args.only!r}: regenerating 1 slot, "
            f"carrying the other {len(slots) - 1} through unchanged"
        )

    print("\nStep 2/4  Ingesting reference art...")
    scan = resolve_reference_art(slots, reference_dir)
    if scan.matched_slot_ids:
        for slot_id in scan.matched_slot_ids:
            slot = next(s for s in slots if s.slot_id == slot_id)
            # resolve_reference_art already set slot.art_uri to the active
            # source file's own path; write_reference_art copies those bytes
            # into the shared output tree + S3 and overwrites art_uri/
            # art_s3_uri/content_hash to point at the copy, so Phase 4 gets
            # one consistent location regardless of source.
            write_reference_art(slot, Path(slot.art_uri))
            print(f"          {slot_id:32s} <- reference ({slot.match_rule}, {len(slot.source_files)} file(s)) -> {slot.art_uri}")
    else:
        print(f"          No files in {reference_dir} matched a slot")
    if scan.unmatched:
        for entry in scan.unmatched:
            print(f"          UNMATCHED  {entry['path']} — {entry['reason']}")

    print("\nStep 3/4  Generating art...")
    if args.dry_run:
        print("          --dry-run: skipping every API call; unresolved slots left as-is")
    else:
        def _progress(slot, outcome, elapsed):
            print(
                f"          {slot.slot_id:32s} rank {slot.priority_rank:>2} "
                f"({slot.share_pct}% share) -> {outcome} {slot.art_uri}  ({elapsed:.1f}s)"
            )

        generate_missing_art(
            slots, beats, previous_manifest=previous_manifest,
            force=args.force, on_progress=_progress, only=regenerate_only,
        )

    print("\nStep 4/4  Writing manifest...")
    manifest = build_manifest(
        slots, beats, beats_source=str(beats_path),
        unmatched_reference_files=scan.unmatched,
        previous_manifest=previous_manifest,
    )
    result = write_manifest(manifest)

    elapsed_total = time.time() - start
    print(f"\n✓ Done in {elapsed_total:.1f}s")
    print(f"  Slots       : {len(slots)}")
    print(f"  Local       : {result['local_path']}")
    if not result["s3_ok"]:
        print(f"  WARNING: S3 write failed — {result['s3_reason']}")
    print(f"  S3          : {result['s3_uri']} (s3_ok={result['s3_ok']}: {result['s3_reason']})\n")


if __name__ == "__main__":
    main()
