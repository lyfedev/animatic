#!/usr/bin/env python3
"""CLI: select high-value beats, animate their panels with Veo, write the index.

Usage:
    python scripts/build_motion.py --dry-run
    python scripts/build_motion.py
    python scripts/build_motion.py --budget 6
    python scripts/build_motion.py --only s2b16 --force
    python scripts/build_motion.py --veo-model veo-3.1-lite-generate-preview
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from animatic.config import settings  # noqa: E402
from animatic.core.motion_generator import (  # noqa: E402
    MotionQuotaExhausted,
    resolve_one,
    veo_model,
)
from animatic.core.motion_manifest import (  # noqa: E402
    build_index,
    load_previous_index,
    write_clip,
    write_index,
)
from animatic.core.motion_prompt import MOTION_PROMPT_VERSION, build_motion_prompt  # noqa: E402
from animatic.core.motion_selector import DEFAULT_BUDGET, select_for_motion  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select beats for motion, animate their panels, write the index"
    )
    parser.add_argument("--beats", default="output/beats.json")
    parser.add_argument(
        "--budget",
        type=int,
        default=DEFAULT_BUDGET,
        help=f"Maximum beats to animate (default: {DEFAULT_BUDGET})",
    )
    parser.add_argument("--only", default=None, help="Animate exactly this beat_id")
    parser.add_argument("--force", action="store_true", help="Regenerate despite the cache")
    parser.add_argument("--no-s3", action="store_true", help="Skip the S3 upload")
    parser.add_argument(
        "--veo-model",
        default=None,
        help=(
            "Override the Veo model. The daily cap is per model, so this is "
            "the escape hatch when the default is spent."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the selection and the prompts, spending nothing",
    )
    args = parser.parse_args()

    if args.veo_model:
        settings.gemini_veo_model = args.veo_model

    beats_doc = json.loads(Path(args.beats).read_text())
    beats = {b["beat_id"]: b for b in beats_doc["beats"]}
    choices = select_for_motion(beats_doc["beats"], budget=args.budget, only=args.only)

    if args.dry_run:
        _dry_run(beats, choices, args)
        return

    print(f"  model: {veo_model()}")
    previous = {e["beat_id"]: e for e in load_previous_index().get("beats", [])}

    started = time.time()
    entries: list[dict] = []
    halted: str | None = None

    for choice in choices:
        if halted and choice.motion:
            entries.append({
                "beat_id": choice.beat_id, "scene": choice.scene, "beat": choice.beat,
                "type": beats[choice.beat_id].get("type", "unknown"),
                "duration_secs": beats[choice.beat_id].get("duration_secs"),
                "motion": False,
                "motion_reason": f"{choice.reason} — but the run halted before reaching it",
                "selection_rank": choice.rank,
                "motion_prompt_version": MOTION_PROMPT_VERSION,
                "source": "still",
                "source_reason": "run halted on the per-day request cap; falls back to its panel",
            })
            continue

        try:
            entry = resolve_one(
                beats[choice.beat_id], choice, previous.get(choice.beat_id), args.force
            )
        except MotionQuotaExhausted as exc:
            halted = str(exc)
            print(f"\n  ** HALTED ** {halted}")
            continue

        entries.append(entry)
        if entry["source"] in ("generated", "reused", "reused_after_failure"):
            if entry["source"] == "generated" and not args.no_s3:
                uri, ok, reason = write_clip(entry["beat_id"], Path(entry["local_path"]))
                entry.update({"s3_uri": uri, "s3_ok": ok, "s3_reason": reason})
            print(
                f"  [{time.time() - started:6.1f}s] {entry['beat_id']:>6}  "
                f"{entry['source']}"
            )
        elif entry["source"] == "generation_failed":
            print(f"  [{time.time() - started:6.1f}s] {entry['beat_id']:>6}  FAILED")

    index = build_index(
        entries, beats_doc, args.beats, args.budget, MOTION_PROMPT_VERSION, halted
    )
    write_index(index)
    _report(index, time.time() - started)


def _dry_run(beats: dict, choices: list, args) -> None:
    picked = [c for c in choices if c.motion]
    print(f"{len(choices)} beat(s), {len(picked)} selected for motion (budget {args.budget})\n")
    for choice in picked:
        beat = beats[choice.beat_id]
        print(f"  {choice.beat_id}  rank {choice.rank}  {beat['type']}  {beat['duration_secs']}s")
        print(f"    reason: {choice.reason}")
        print(f"    prompt: {build_motion_prompt(beat)[:220]}...")
        print()
    by_type: dict[str, int] = {}
    for choice in choices:
        if not choice.motion:
            by_type[beats[choice.beat_id]["type"]] = (
                by_type.get(beats[choice.beat_id]["type"], 0) + 1
            )
    print(f"stills by type: {by_type}")


def _report(index: dict, elapsed: float) -> None:
    print(f"\n{index['total_beats']} beat(s) decided in {elapsed:.1f}s")
    print(
        f"  selected {index['selected_count']} (budget {index['budget']}, "
        f"within budget: {index['within_budget']}), "
        f"with motion {index['motion_count']}, stills {index['still_count']}"
    )
    if index["fell_back_to_still_beat_ids"]:
        print(
            f"  selected but fell back to their panel: "
            f"{', '.join(index['fell_back_to_still_beat_ids'])}"
        )
    print(f"  sources: {index['sources']}")
    print(f"  motion by type: {index['motion_by_type']}")
    print(f"  animated: {', '.join(index['motion_beat_ids']) or 'none'}")
    if index["failed_beat_ids"]:
        print(f"  FAILED: {', '.join(index['failed_beat_ids'])}")
    if index["halted_reason"]:
        print(f"  ** HALTED ** {index['halted_reason']}")
    print(f"  index s3: {'ok' if index['s3_ok'] else index['s3_reason']}")


if __name__ == "__main__":
    main()
