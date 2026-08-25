#!/usr/bin/env python3
"""Fill `assets/footage/` from the supplied reference video, for the demo.

DoD item 3 asks for three rendered videos of the same content: no footage,
partial footage, all footage. The first two exist as soon as the pipeline has
run. The third needs a clip for every beat, and the project's supplied
material includes the reference film — which is exactly what it is for.

This is demo scaffolding and says so. It does not attempt to match a beat to
the moment in the film that depicts it; it walks the film and takes each
beat's worth of screen time in order. What it demonstrates is the SWAP, and
the swap does not care whether the footage is the right footage — that is the
point of reading the beat number from the filename rather than the frames.

Usage:
    python scripts/demo_footage.py --dry-run
    python scripts/demo_footage.py                 # every beat
    python scripts/demo_footage.py --scene 2       # one scene
    python scripts/demo_footage.py --clear         # remove what this wrote
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from animatic.core.shot_sources import FOOTAGE_DIR  # noqa: E402

REFERENCE = Path("assets/Rocky.mp4")

# Skip the opening titles; start where the film proper does.
START_OFFSET_SECS = 60.0

# A marker in the filename so `--clear` can remove exactly what this wrote and
# leave a human's own footage alone.
_DEMO_TAG = "demo"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cut demo footage from the reference video, one clip per beat"
    )
    parser.add_argument("--beats", default="output/beats.json")
    parser.add_argument("--audio", default="output/audio/index.json")
    parser.add_argument("--reference", default=str(REFERENCE))
    parser.add_argument("--scene", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--clear", action="store_true", help="Remove clips this script wrote"
    )
    args = parser.parse_args()

    if args.clear:
        removed = _clear()
        print(f"removed {removed} demo clip(s)")
        return

    reference = Path(args.reference)
    if not reference.exists():
        sys.exit(f"reference video not found: {reference}")

    beats = json.loads(Path(args.beats).read_text())["beats"]
    if args.scene is not None:
        beats = [b for b in beats if b["scene"] == args.scene]

    clips = {}
    audio_path = Path(args.audio)
    if audio_path.exists():
        clips = {c["beat_id"]: c for c in json.loads(audio_path.read_text())["clips"]}

    cursor = START_OFFSET_SECS
    total = 0.0
    FOOTAGE_DIR.mkdir(parents=True, exist_ok=True)

    for beat in beats:
        clip = clips.get(beat["beat_id"])
        secs = float(clip["shot_secs"]) if clip and clip.get("shot_secs") else beat["duration_secs"]
        target = FOOTAGE_DIR / f"{beat['beat_id']}-{_DEMO_TAG}.mp4"

        if args.dry_run:
            print(f"  {beat['beat_id']:>6}  {cursor:8.1f}s +{secs:5.2f}s -> {target.name}")
        else:
            _extract(reference, cursor, secs, target)
            print(f"  {beat['beat_id']:>6}  {target.name}")

        cursor += secs
        total += secs

    print(f"\n{len(beats)} clip(s), {total:.1f}s taken from {reference}")
    if not args.dry_run:
        print("  re-render with: PYTHONPATH=src python scripts/build_video.py")
        print("  undo with:      PYTHONPATH=src python scripts/demo_footage.py --clear")


def _extract(reference: Path, start: float, secs: float, target: Path) -> None:
    """One clip, video only — the cut keeps its own synthesised audio bed."""
    result = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-ss", f"{start:.3f}", "-t", f"{secs:.3f}",
            "-i", str(reference),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
            "-an", str(target),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"ffmpeg failed on {target.name}: {result.stderr.strip()[:300]}")


def _clear() -> int:
    if not FOOTAGE_DIR.is_dir():
        return 0
    removed = 0
    for path in FOOTAGE_DIR.iterdir():
        if f"-{_DEMO_TAG}" in path.stem:
            path.unlink()
            removed += 1
    return removed


if __name__ == "__main__":
    main()
