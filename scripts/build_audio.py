#!/usr/bin/env python3
"""CLI: cast voices, write narration, synthesise one clip per beat, generate
the script's music cues, and write output/audio/index.json.

Usage:
    python scripts/build_audio.py --only s2b7
    python scripts/build_audio.py --scene 2
    python scripts/build_audio.py --force
    python scripts/build_audio.py --skip-music
    python scripts/build_audio.py --dry-run
    python scripts/build_audio.py --beats output/beats.json --pdf docs/rocky-1976.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure src/ is on the path when run from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from animatic.core.audio_generator import generate_missing_audio  # noqa: E402
from animatic.core.audio_timing import narration_budget_words  # noqa: E402
from animatic.core.music_cues import build_music_prompt, find_music_cues  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Cast voices, write narration, synthesise per-beat audio, generate "
            "music cues, write the audio index"
        )
    )
    parser.add_argument(
        "--beats",
        default="output/beats.json",
        help="Path to the beat list (default: output/beats.json)",
    )
    parser.add_argument(
        "--pdf",
        default="docs/rocky-1976.pdf",
        help="Path to the screenplay PDF, read for music cues",
    )
    parser.add_argument("--scene", type=int, default=None, help="Only this scene's beats")
    parser.add_argument("--only", default=None, help="Only this beat_id, e.g. s2b7")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even when the cache key is unchanged (also re-casts voices)",
    )
    parser.add_argument(
        "--skip-music",
        action="store_true",
        help="Detect and record music cues without spending a Lyria call on them",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be generated, spending nothing",
    )
    args = parser.parse_args()

    beats_doc = json.loads(Path(args.beats).read_text())

    if args.dry_run:
        _dry_run(beats_doc, args)
        return

    started = time.time()

    def progress(beat, source: str, elapsed: float) -> None:
        print(f"  [{elapsed:6.1f}s] {beat['beat_id']:>6}  {source}")

    index = generate_missing_audio(
        beats_doc,
        pdf_path=args.pdf,
        beats_source=args.beats,
        only=args.only,
        scene=args.scene,
        force=args.force,
        skip_music=args.skip_music,
        progress=progress,
    )

    _report(index, time.time() - started)


def _dry_run(beats_doc: dict, args: argparse.Namespace) -> None:
    beats = beats_doc["beats"]
    if args.only:
        beats = [b for b in beats if b["beat_id"] == args.only]
    elif args.scene is not None:
        beats = [b for b in beats if b["scene"] == args.scene]

    dialogue = [b for b in beats if b.get("dialogue")]
    silent = [b for b in beats if not b.get("dialogue")]

    print(f"{len(beats)} beat(s) selected")
    print(f"  {len(dialogue)} dialogue  ->  1 TTS call each, script text unchanged")
    print(f"  {len(silent)} narration ->  1 narration call for the run, then 1 TTS each")
    print("\nnarration word budgets:")
    for b in silent[:10]:
        print(
            f"  {b['beat_id']:>6}  {b['duration_secs']:>5.1f}s  "
            f"-> at most {narration_budget_words(b['duration_secs'])} words"
        )
    if len(silent) > 10:
        print(f"  ... and {len(silent) - 10} more")

    cues = find_music_cues(args.pdf, beats_doc["beats"])
    print(f"\n{len(cues)} music cue(s) found in the script:")
    for cue in cues:
        print(f"  {cue.cue_id}: beats {', '.join(cue.beat_ids)} ({cue.total_secs}s)")
        for line in cue.cue_lines:
            print(f"      script: {line}")
        print(f"      prompt: {build_music_prompt(cue)}")


def _report(index: dict, elapsed: float) -> None:
    print(f"\n{index['total_clips']} clip(s) in {elapsed:.1f}s")
    print(
        f"  generated {index['generated_count']}, reused {index['reused_count']}, "
        f"failed {index['failed_count']}"
    )
    print(
        f"  {index['dialogue_count']} dialogue, {index['narration_count']} narration"
    )
    print(f"  narrator voice: {index['narrator_voice']}")
    print(f"  cast: {len(index['cast'])} speaking part(s)")
    for name, entry in index["cast"].items():
        print(f"      {name:>14}  {entry['voice']}")

    if index["shots_widened_count"]:
        print(
            f"  {index['shots_widened_count']} shot(s) widened to fit their audio, "
            f"+{index['shots_widened_secs']}s total"
        )
    else:
        print("  no shot needed widening — every clip fits its beat")
    print(f"  total shot time: {index['total_shot_secs']}s")

    for cue in index["music_cues"]:
        print(f"  music {cue['cue_id']}: {cue['source']} ({cue.get('source_reason', '')})")

    print(f"  index s3: {'ok' if index['s3_ok'] else index['s3_reason']}")

    failed = [c for c in index["clips"] if c["source"] == "generation_failed"]
    if failed:
        print(f"\n{len(failed)} FAILED:")
        for c in failed:
            print(f"  {c['beat_id']}: {c['source_reason']}")


if __name__ == "__main__":
    main()
