#!/usr/bin/env python3
"""Assemble the audio index into one continuous track for review.

Phase 4 built `output/panels/all_panels.jpg` so the art could be judged by
eye instead of by report. This is the same idea for the ear: every clip laid
end to end at its own shot length, with the script's music cues mixed under
the beats that carry them.

It is a review artifact, not the cut — Phase 7 assembles the real video. But
pacing, voice casting and narration are things you hear, not things a table
tells you, so this exists before Phase 7 does.

Usage:
    python scripts/preview_audio.py
    python scripts/preview_audio.py --scene 2
    python scripts/preview_audio.py --out output/audio/preview.wav
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

_INDEX = Path("output/audio/index.json")
_RATE = 24000

# The cue plays under the scene, not over it — dialogue and narration have to
# stay intelligible on top.
_MUSIC_GAIN = 0.22


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble the audio index into one track")
    parser.add_argument("--index", default=str(_INDEX))
    parser.add_argument("--scene", type=int, default=None, help="Only this scene")
    parser.add_argument("--out", default="output/audio/preview.wav")
    parser.add_argument(
        "--no-music", action="store_true", help="Leave the music cues out"
    )
    args = parser.parse_args()

    index = json.loads(Path(args.index).read_text())
    clips = [c for c in index["clips"] if c["source"] != "generation_failed"]
    if args.scene is not None:
        clips = [c for c in clips if c["scene"] == args.scene]
    if not clips:
        sys.exit("no clips to assemble")

    music_by_beat = {}
    if not args.no_music:
        for cue in index.get("music_cues", []):
            if cue.get("local_path") and Path(cue["local_path"]).exists():
                for beat_id in cue["beat_ids"]:
                    music_by_beat[beat_id] = cue["local_path"]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        segments = [
            _render_segment(clip, tmp_dir, i, music_by_beat.get(clip["beat_id"]))
            for i, clip in enumerate(clips)
        ]
        _concat(segments, tmp_dir, Path(args.out))

    total = sum(c["shot_secs"] for c in clips)
    print(f"{len(clips)} clip(s), {total:.1f}s -> {args.out}")
    # Count what was actually mixed, not what was available: with --scene the
    # cue map still holds every cue in the script.
    used = [c["beat_id"] for c in clips if c["beat_id"] in music_by_beat]
    if used:
        print(f"  music mixed under {len(used)} beat(s) at {_MUSIC_GAIN:.0%}: {', '.join(used)}")


def _render_segment(
    clip: dict, tmp_dir: Path, position: int, music_path: str | None
) -> Path:
    """One clip padded to its full shot length, with music under it if any.

    Padded rather than trimmed: `shot_secs` is always at or above the clip's
    own length by construction, so this only ever adds the silence the cut
    needs, never cuts a word off.
    """
    out = tmp_dir / f"{position:03d}.wav"
    shot = clip["shot_secs"]

    if music_path:
        cmd = [
            "ffmpeg", "-v", "error", "-y",
            "-i", clip["local_path"],
            "-i", music_path,
            "-filter_complex",
            f"[0:a]aresample={_RATE},apad=whole_dur={shot}[v];"
            f"[1:a]aresample={_RATE},atrim=0:{shot},volume={_MUSIC_GAIN},"
            f"apad=whole_dur={shot}[m];"
            f"[v][m]amix=inputs=2:duration=first:normalize=0[a]",
            "-map", "[a]", "-ac", "1", "-ar", str(_RATE), str(out),
        ]
    else:
        cmd = [
            "ffmpeg", "-v", "error", "-y",
            "-i", clip["local_path"],
            "-af", f"aresample={_RATE},apad=whole_dur={shot}",
            "-ac", "1", "-ar", str(_RATE), str(out),
        ]

    subprocess.run(cmd, check=True)
    return out


def _concat(segments: list[Path], tmp_dir: Path, out: Path) -> None:
    listing = tmp_dir / "segments.txt"
    listing.write_text("\n".join(f"file '{p}'" for p in segments))
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-ac", "1", "-ar", str(_RATE), str(out),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
