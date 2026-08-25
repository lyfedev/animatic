#!/usr/bin/env python3
"""CLI: report per-shot state — animatic, motion or real footage.

Reads what is on disk right now. Spends nothing, encodes nothing, runs in
milliseconds, so it is safe to poll.

Usage:
    python scripts/build_state.py
    python scripts/build_state.py --no-s3
    python scripts/build_state.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from animatic.core.shot_state import build_state, write_state  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Report per-shot state")
    parser.add_argument("--beats", default="output/beats.json")
    parser.add_argument("--audio", default="output/audio/index.json")
    parser.add_argument("--motion", default="output/motion/index.json")
    parser.add_argument("--cut", default="output/video/index.json")
    parser.add_argument("--no-s3", action="store_true", help="Write locally only")
    parser.add_argument("--json", action="store_true", help="Print the state document")
    args = parser.parse_args()

    state = build_state(
        json.loads(Path(args.beats).read_text()),
        _load(args.audio),
        _load(args.motion),
        _load(args.cut),
    )

    if args.no_s3:
        Path("output").mkdir(exist_ok=True)
        Path("output/state.json").write_text(json.dumps(state, indent=2))
        state["s3_reason"] = "skipped (--no-s3)"
    else:
        write_state(state)

    if args.json:
        print(json.dumps(state, indent=2))
        return

    _report(state)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text()) if Path(path).exists() else {}


def _report(state: dict) -> None:
    print(f"{state['total_shots']} shot(s), {state['total_secs']}s")
    for name, count in sorted(state["shots_by_state"].items()):
        print(f"  {name:<18} {count}")
    print(
        f"\n  real footage: {state['real_footage_pct']}% "
        f"({state['real_footage_secs']}s of {state['total_secs']}s)"
    )
    if state["real_footage_beat_ids"]:
        print(f"    {', '.join(state['real_footage_beat_ids'])}")
    if state["motion_beat_ids"]:
        print(f"  motion: {', '.join(state['motion_beat_ids'])}")
    if state["missing_beat_ids"]:
        print(f"  !! no picture at all: {', '.join(state['missing_beat_ids'])}")
    if state["shots_without_audio"]:
        print(f"  !! no audio: {', '.join(state['shots_without_audio'])}")

    current = state["cut_is_current"]
    if current is None:
        print("\n  no cut rendered yet — run scripts/build_video.py")
    elif current:
        print(f"\n  cut is current: {state['cut_path']}")
    else:
        print(
            f"\n  ** cut is STALE ** {state['cut_path']} was rendered from a "
            f"different set of shots — re-run scripts/build_video.py"
        )
    print(f"  state s3: {'ok' if state['s3_ok'] else state['s3_reason']}")


if __name__ == "__main__":
    main()
