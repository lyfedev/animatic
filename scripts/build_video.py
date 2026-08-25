#!/usr/bin/env python3
"""CLI: assemble panels, motion and audio into the animatic cut.

Usage:
    python scripts/build_video.py
    python scripts/build_video.py --scene 2
    python scripts/build_video.py --dry-run
    python scripts/build_video.py --out output/video/animatic.mp4 --no-s3
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from animatic.core.cut_manifest import (  # noqa: E402
    LOCAL_VIDEO_DIR,
    build_index,
    write_cut,
    write_index,
)
from animatic.core.shot_sources import MissingShotError  # noqa: E402
from animatic.core.video_assembler import (  # noqa: E402
    CUT_TEMPLATE_VERSION,
    build_shot,
    concat_shots,
    plan_shots,
    probe_duration,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assemble panels, motion and audio into the animatic cut"
    )
    parser.add_argument("--beats", default="output/beats.json")
    parser.add_argument("--audio", default="output/audio/index.json")
    parser.add_argument("--panels", default="output/panels/index.json")
    parser.add_argument("--scene", type=int, default=None, help="Assemble one scene only")
    parser.add_argument("--out", default=None, help="Output MP4 path")
    parser.add_argument("--no-s3", action="store_true", help="Skip the S3 upload")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the shot list and cut length without encoding",
    )
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH — required to assemble the cut")

    beats_doc = json.loads(Path(args.beats).read_text())
    audio_index = _load_optional(args.audio, "audio")
    panel_index = _load_optional(args.panels, "panel")

    try:
        shots = plan_shots(beats_doc, audio_index, scene=args.scene)
    except MissingShotError as exc:
        sys.exit(str(exc))

    if not shots:
        sys.exit("no shots selected")

    if args.dry_run:
        _dry_run(shots)
        return

    out_path = Path(args.out) if args.out else _default_out(args.scene)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    started = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        segments = []
        for position, shot in enumerate(shots):
            segment = build_shot(shot, tmp_dir / f"{position:03d}.mp4")
            segments.append(segment)
            print(
                f"  [{time.time() - started:6.1f}s] {shot.beat_id:>6}  "
                f"{shot.secs:5.2f}s  {shot.source.kind}"
            )
        concat_shots(segments, out_path)

    measured = probe_duration(out_path)
    index = build_index(
        [s.to_entry() for s in shots],
        beats_doc,
        audio_index,
        panel_index,
        out_path,
        measured,
        CUT_TEMPLATE_VERSION,
    )

    if not args.no_s3:
        s3_uri, s3_ok, s3_reason = write_cut(out_path)
        index["cut_s3_uri"] = s3_uri
        index["cut_s3_ok"] = s3_ok
        index["cut_s3_reason"] = s3_reason

    write_index(index)
    _report(index, out_path, time.time() - started)


def _load_optional(path: str, label: str) -> dict:
    """An index the cut can be built without, but is worse without."""
    if not Path(path).exists():
        print(f"  !! no {label} index at {path} — continuing without it")
        return {}
    return json.loads(Path(path).read_text())


def _default_out(scene: int | None) -> Path:
    name = f"animatic-scene{scene}.mp4" if scene is not None else "animatic.mp4"
    return LOCAL_VIDEO_DIR / name


def _dry_run(shots: list) -> None:
    total = sum(s.secs for s in shots)
    print(f"{len(shots)} shot(s), {total:.1f}s ({total / 60:.1f} min)\n")

    by_source: dict[str, int] = {}
    fallbacks = []
    for shot in shots:
        by_source[shot.source.kind] = by_source.get(shot.source.kind, 0) + 1
        if shot.secs_source == "beat_duration":
            fallbacks.append(shot.beat_id)
        silent = "" if shot.audio_path else "   (no audio)"
        music = "  + music" if shot.music_path else ""
        print(
            f"  {shot.beat_id:>6}  {shot.secs:5.2f}s  {shot.source.kind:<8}"
            f"{music}{silent}"
        )

    print(f"\nsources: {by_source}")
    widened = [s for s in shots if s.secs_source == "audio_floor"]
    if widened:
        print(f"shots widened to fit their audio: {[s.beat_id for s in widened]}")
    if fallbacks:
        print(f"!! no audio entry, using the beat's planned duration: {fallbacks}")


def _report(index: dict, out_path: Path, elapsed: float) -> None:
    print(f"\n{index['total_shots']} shot(s) assembled in {elapsed:.1f}s")
    print(f"  {out_path}  ({out_path.stat().st_size / 1_000_000:.1f} MB)")
    print(f"  planned {index['planned_secs']}s, measured {index['measured_secs']}s")
    print(f"  sources: {index['shots_by_source']}")
    print(
        f"  real footage: {index['real_footage_pct']}% "
        f"({index['real_footage_secs']}s of {index['planned_secs']}s)"
    )

    drift = abs((index["measured_secs"] or 0) - index["planned_secs"])
    if drift > 0.5:
        print(f"  !! cut is {drift:.2f}s off its plan")

    stale = index.get("stale_audio_beat_ids") or []
    mismatch = index.get("text_mismatch_beat_ids") or []
    if stale:
        print(f"  {len(stale)} shot(s) carry audio behind the current template")
    if mismatch:
        print(f"  {len(mismatch)} shot(s) carry audio that predates its recorded text")

    if "cut_s3_ok" in index:
        print(f"  cut s3: {'ok' if index['cut_s3_ok'] else index['cut_s3_reason']}")
    print(f"  index s3: {'ok' if index['s3_ok'] else index['s3_reason']}")


if __name__ == "__main__":
    main()
