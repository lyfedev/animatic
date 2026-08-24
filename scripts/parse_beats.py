#!/usr/bin/env python3
"""CLI: parse Rocky screenplay into a beat list.

Usage:
    python scripts/parse_beats.py
    python scripts/parse_beats.py --scenes 8
    python scripts/parse_beats.py --pdf docs/rocky-1976.pdf --scenes 8
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure src/ is on the path when run from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from animatic.core.beat_assembler import assemble_and_write
from animatic.core.beat_extractor import extract_beats
from animatic.core.pdf_extractor import extract_scenes
from animatic.core.scene_timing import scene_targets

logging.basicConfig(level=logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse screenplay into beat list")
    parser.add_argument(
        "--pdf",
        default="docs/rocky-1976.pdf",
        help="Path to screenplay PDF (default: docs/rocky-1976.pdf)",
    )
    parser.add_argument(
        "--scenes",
        type=int,
        default=8,
        help="Number of scenes to parse from start (default: 8)",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF not found at {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\nParsing {pdf_path} — first {args.scenes} scenes\n")
    start = time.time()

    # Step 1: Extract scenes from PDF
    print("Step 1/3  Extracting scenes from PDF...")
    scenes = extract_scenes(pdf_path, first_n=args.scenes)
    targets = scene_targets(pdf_path, first_n=args.scenes)
    budget = sum(targets.values())
    print(f"          Found {len(scenes)} scenes: {sorted(scenes.keys())}")
    print(f"          Page budget: {budget:.1f}s ({budget/60:.2f} min) "
          f"at one page per minute\n")

    # Step 2: Extract beats per scene via Gemini
    print("Step 2/3  Extracting beats via Gemini (this may take a minute)...")
    scenes_beats = {}
    total_beats = 0
    for scene_num, scene_text in sorted(scenes.items()):
        t0 = time.time()
        beats = extract_beats(
            scene_num, scene_text, target_secs=targets.get(scene_num)
        )
        elapsed = time.time() - t0
        action = sum(1 for b in beats if b.type == "action")
        dialogue = sum(1 for b in beats if b.type == "dialogue")
        establishing = sum(1 for b in beats if b.type == "establishing")
        motion = sum(1 for b in beats if b.motion_candidate)
        print(
            f"          Scene {scene_num:2d}: {len(beats):2d} beats  "
            f"[action={action} dialogue={dialogue} establishing={establishing} motion✦={motion}]"
            f"  {sum(b.duration_secs for b in beats):5.1f}s"
            f"/{targets.get(scene_num, 0):5.1f}s target  ({elapsed:.1f}s)"
        )
        scenes_beats[scene_num] = beats
        total_beats += len(beats)

    # Step 3: Assemble and write
    print(f"\nStep 3/3  Assembling {total_beats} beats and writing output...")
    s3_uri = assemble_and_write(scenes_beats)

    elapsed_total = time.time() - start
    print(f"\n✓ Done in {elapsed_total:.1f}s")
    print(f"  Total beats : {total_beats}")
    print(f"  Output      : output/beats.json")
    print(f"  S3          : {s3_uri}\n")


if __name__ == "__main__":
    main()
