#!/usr/bin/env python3
"""CLI: derive shot sizes, build prompts, generate one panel per beat, and
write output/panels/index.json.

Usage:
    python scripts/build_panels.py --only s2b7
    python scripts/build_panels.py --scene 2
    python scripts/build_panels.py --force
    python scripts/build_panels.py --dry-run
    python scripts/build_panels.py --beats output/beats.json --pdf docs/rocky-1976.pdf --manifest output/assets/manifest.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure src/ is on the path when run from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from animatic.core.panel_generator import generate_missing_panels
from animatic.core.slot_resolver import resolve_slots
from animatic.core.script_source import script_pdf  # noqa: E402

_DEFAULT_INDEX_PATH = Path("output/panels/index.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive shot sizes, build prompts, generate one panel per beat, write the panel index"
    )
    parser.add_argument(
        "--beats",
        default="output/beats.json",
        help="Path to the beat list (default: output/beats.json)",
    )
    parser.add_argument(
        "--pdf",
        default=None,
        help="Path to the screenplay PDF (default: settings.script_pdf)",
    )
    parser.add_argument(
        "--manifest",
        default="output/assets/manifest.json",
        help="Path to the asset manifest (default: output/assets/manifest.json)",
    )
    parser.add_argument(
        "--scene",
        type=int,
        default=None,
        help="Regenerate only this scene's beats",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Regenerate exactly one beat_id (the tracer path, e.g. s2b7)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate every selected beat's panel even if its cache key is unchanged",
    )
    parser.add_argument(
        "--from-plates",
        action="store_true",
        help=(
            "Compose each panel FROM its slot art rather than from a text "
            "description of it (lifts D-08). This is what makes a character "
            "model sheet visible in the cut. Re-verify the facial rule after "
            "using it — a seed image can overrule a prompt clause."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve beats and slots without calling the image API",
    )
    args = parser.parse_args()
    if getattr(args, "pdf", None) is None:
        args.pdf = str(script_pdf())

    beats_path = Path(args.beats)
    pdf_path = Path(args.pdf)
    manifest_path = Path(args.manifest)
    if not beats_path.exists():
        print(f"Error: beat list not found at {beats_path}", file=sys.stderr)
        sys.exit(1)
    if not pdf_path.exists():
        print(f"Error: PDF not found at {pdf_path}", file=sys.stderr)
        sys.exit(1)
    if not manifest_path.exists():
        print(
            f"Error: asset manifest not found at {manifest_path} — "
            f"run scripts/build_assets.py first",
            file=sys.stderr,
        )
        sys.exit(1)

    start = time.time()
    beats_doc = json.loads(beats_path.read_text())
    manifest = json.loads(manifest_path.read_text())

    if manifest.get("total_slots", 0) < 1 or not manifest.get("slots"):
        print(
            f"Error: asset manifest at {manifest_path} has no slots — "
            f"run scripts/build_assets.py (no --only) first",
            file=sys.stderr,
        )
        sys.exit(1)

    previous_index = None
    if _DEFAULT_INDEX_PATH.exists():
        try:
            previous_index = json.loads(_DEFAULT_INDEX_PATH.read_text())
        except json.JSONDecodeError:
            previous_index = None

    print(f"\nBuilding panel index from {beats_path} + {manifest_path}\n")

    print("Step 1/3  Resolving beats and slots...")
    slots = resolve_slots(beats_doc, pdf_path)
    total_beats = len(beats_doc.get("beats", []))
    print(f"          {total_beats} beat(s), {len(slots)} slot(s)")

    only: set[str] | None = {args.only} if args.only else None
    if only is not None:
        beat_ids = {b["beat_id"] for b in beats_doc["beats"]}
        if not only <= beat_ids:
            print(
                f"Error: no beat named {args.only!r} among {sorted(beat_ids)}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"          --only {args.only!r}: generating 1 beat")
    if args.scene is not None:
        print(f"          --scene {args.scene}: generating that scene's beats")

    print("\nStep 2/3  Generating panels...")
    if args.dry_run:
        print("          --dry-run: skipping every API call")
        return

    def _progress(beat, outcome, elapsed):
        print(
            f"          {beat['beat_id']:8s} scene {beat['scene']:>2} "
            f"({beat['type']}) -> {outcome}  ({elapsed:.1f}s)"
        )

    index = generate_missing_panels(
        beats_doc,
        slots,
        manifest,
        previous_index=previous_index,
        force=args.force,
        only=only,
        scene=args.scene,
        on_progress=_progress,
        condition_on_plates=args.from_plates,
    )

    print("\nStep 3/3  Index written")
    elapsed_total = time.time() - start
    print(f"\n✓ Done in {elapsed_total:.1f}s")
    print(
        f"  Panels      : {index['total_panels']} "
        f"(generated {index['generated_count']}, reused {index['reused_count']}, "
        f"failed {index['failed_count']})"
    )
    print(f"  Local       : {_DEFAULT_INDEX_PATH}")
    if not index["s3_ok"]:
        print(f"  WARNING: S3 write failed — {index['s3_reason']}")
    print(f"  S3          : panels/index.json (s3_ok={index['s3_ok']}: {index['s3_reason']})\n")


if __name__ == "__main__":
    main()
