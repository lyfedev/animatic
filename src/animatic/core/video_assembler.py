"""Video assembly — panels, motion and audio into one timed cut.

The first phase that produces something a person can watch. Everything before
it produced folders.

Three rules it does not get to choose:

**Cut on `shot_secs`, not `duration_secs`.** Phase 2 planned a duration per
beat from page geometry; Phase 5 measured what the audio actually is and
widened the shots that could not hold their own speech. The audio index's
`shot_secs` is the reconciled number and the only one that keeps criterion 3
("audio stays in sync with its shot and is never clipped") true. Using the
beat's own duration would clip five shots in the current corpus.

**Never re-time a shot to fit the picture.** A motion clip that runs shorter
than its shot holds its last frame; one that runs longer is trimmed. The
*audio* sets the length, because the audio is what a viewer notices being cut.

**Every shot records its source and its length reason.** A cut that cannot say
why a shot is 12.98 seconds long is not traceable (NFR-04), and Phase 8 needs
to report what fraction of the cut is real footage (FR-08).

ffmpeg is invoked per shot and then once to concatenate. Per-shot rather than
one enormous filtergraph so a single bad input names itself, and so a rebuild
after one footage swap only re-encodes the shots that changed.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from animatic.core.beat_overrides import apply as apply_override
from animatic.core.beat_overrides import load_overrides
from animatic.core.shot_sources import ShotSource, find_dailies, resolve_shot

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, float], None]

CUT_TEMPLATE_VERSION = "v1"

# Panels generate at 1376x768. Encoding at that size avoids a rescale, but
# 1376 is not a size players expect, so the cut normalises to 720p and pads.
# The pad is WHITE: the house style is black line art on white, and black bars
# either side of a white frame read as a rendering fault rather than a letterbox.
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
PAD_COLOUR = "white"
FPS = 24
AUDIO_RATE = 48000

# The cue plays under the scene, not over it — dialogue and narration have to
# stay intelligible on top. Same value the audio preview uses.
MUSIC_GAIN = 0.22


class AssemblyError(Exception):
    """Raised when ffmpeg cannot build a shot or the final cut."""


@dataclass
class Shot:
    """One shot of the cut, fully resolved before a frame is encoded."""

    beat_id: str
    scene: int
    beat: int
    secs: float
    secs_source: str
    secs_reason: str
    source: ShotSource
    audio_path: Path | None
    music_path: Path | None
    # Non-empty only for a daily: the beats this one shot stands in for. The
    # cut has fewer shots than beats when a daily is spliced, and a manifest
    # that did not say which beats vanished would be lying by omission.
    covers_beat_ids: tuple[str, ...] = ()

    def to_entry(self) -> dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "scene": self.scene,
            "beat": self.beat,
            "shot_secs": round(self.secs, 2),
            "shot_secs_source": self.secs_source,
            "shot_secs_reason": self.secs_reason,
            "shot_source": self.source.kind,
            "shot_source_path": str(self.source.path),
            "shot_source_reason": self.source.reason,
            "audio_path": str(self.audio_path) if self.audio_path else None,
            "music_path": str(self.music_path) if self.music_path else None,
            "covers_beat_ids": list(self.covers_beat_ids),
            "uses_own_audio": self.source.carries_own_audio,
            "hand_made": self.source.is_hand_made,
        }


def plan_shots(
    beats_doc: dict[str, Any],
    audio_index: dict[str, Any],
    scene: int | None = None,
    ignore_footage: bool = False,
    ignore_motion: bool = False,
    ignore_dailies: bool = False,
    ignore_edits: bool = False,
) -> list[Shot]:
    """Resolve every beat into a Shot without encoding anything.

    Separated from encoding so `--dry-run` can report the whole cut — its
    length, its sources, which beats are real footage — for free.

    `ignore_footage` and `ignore_motion` force the cut down the priority
    ladder without touching the filesystem. DR-04 requires the SAME scene to
    render at three states (all panels / partial footage / all footage), and
    moving files around to achieve that would race with anything else reading
    the tree — including a second visitor on the hosted demo.
    """
    clips = {c["beat_id"]: c for c in audio_index.get("clips", [])}
    music = _music_by_beat(audio_index)
    overrides = load_overrides()

    ordered_beats = sorted(beats_doc["beats"], key=lambda b: (b["scene"], b["beat"]))
    dailies = (
        {} if ignore_dailies
        else find_dailies([b["beat_id"] for b in ordered_beats])
    )

    shots: list[Shot] = []
    for beat in ordered_beats:
        if scene is not None and beat["scene"] != scene:
            continue

        beat_id = beat["beat_id"]
        source = _resolve(
            beat_id, ignore_footage, ignore_motion, ignore_edits, dailies
        )

        # A daily covers several beats with one take. Only its FIRST beat
        # becomes a shot; the rest are represented by that shot and would
        # otherwise be encoded twice. The take also plays its own length and
        # brings its own sound, so neither the beats' planned durations nor
        # their synthesised clips apply to it.
        if source.daily_span is not None:
            if not source.daily_span.is_start(beat_id):
                continue
            shots.append(_daily_shot(beat, source, ordered_beats, clips))
            continue

        clip = clips.get(beat_id)
        secs, secs_source, secs_reason = _shot_length(beat, clip)
        secs, secs_source, secs_reason = apply_override(
            beat_id, secs, secs_source, secs_reason, overrides
        )

        shots.append(
            Shot(
                beat_id=beat_id,
                scene=beat["scene"],
                beat=beat["beat"],
                secs=secs,
                secs_source=secs_source,
                secs_reason=secs_reason,
                source=source,
                audio_path=_playable(clip),
                music_path=music.get(beat_id),
            )
        )

    return sorted(shots, key=lambda s: (s.scene, s.beat))


def _daily_shot(
    beat: dict[str, Any],
    source: ShotSource,
    ordered_beats: list[dict[str, Any]],
    clips: dict[str, dict[str, Any]],
) -> Shot:
    """One shot for a whole daily span, at the take's own length.

    The developer chose "the daily plays whole; the cut gets shorter or
    longer" together with "the daily carries its own production sound", and
    those two answers are what make each other safe. A take that plays its own
    length no longer matches the runtime of the beats it replaces — but its
    sound arrives with its picture, so there is nothing left to desync.
    """
    span = source.daily_span
    measured = probe_duration(span.path)
    planned = round(
        sum(
            _shot_length(b, clips.get(b["beat_id"]))[0]
            for b in ordered_beats
            if b["beat_id"] in span.beat_ids
        ),
        2,
    )
    delta = round(measured - planned, 2)
    direction = "shorter" if delta < 0 else "longer"
    silent = not has_audio_stream(span.path)
    if silent:
        logger.warning(
            "%s carries no audio stream; %d beat(s) of narration are replaced "
            "by silence",
            span.path,
            len(span.beat_ids),
        )

    return Shot(
        beat_id=span.start_beat_id,
        scene=beat["scene"],
        beat=beat["beat"],
        secs=round(measured, 2),
        secs_source="daily",
        secs_reason=(
            f"the daily at {span.path} runs {measured:.2f}s and plays whole; "
            f"the {len(span.beat_ids)} beat(s) it covers ({span.span_id}) "
            f"planned {planned:.2f}s, so the cut is {abs(delta):.2f}s "
            f"{direction} than the beat list"
            + (
                ". IT CARRIES NO AUDIO STREAM, so this span is silent — the "
                "synthesised narration for those beats is not used and nothing "
                "replaces it"
                if silent else ""
            )
        ),
        source=source,
        # None: the take's own audio stream is used instead, so no synthesised
        # clip and no music cue is laid over it.
        audio_path=None,
        music_path=None,
        covers_beat_ids=tuple(span.beat_ids),
    )


def _resolve(
    beat_id: str,
    ignore_footage: bool,
    ignore_motion: bool,
    ignore_edits: bool = False,
    dailies: dict[str, Any] | None = None,
) -> ShotSource:
    """Resolve a shot's picture, optionally skipping levels of the ladder.

    Implemented by pointing the ignored level at a directory that cannot
    exist, so the ONE priority rule in `shot_sources` stays the only place
    that decides — a second copy of the ladder here would be a second thing to
    keep correct.
    """
    nowhere = Path("/nonexistent-animatic-render-mode")
    return resolve_shot(
        beat_id,
        footage_dir=nowhere if ignore_footage else None,
        motion_dir=nowhere if ignore_motion else None,
        edited_dir=nowhere if ignore_edits else None,
        dailies=dailies,
    )


def _shot_length(beat: dict[str, Any], clip: dict[str, Any] | None) -> tuple[float, str, str]:
    """How long this shot runs, and why.

    `shot_secs` from the audio index wins whenever it exists: it is the
    reconciled figure that guarantees the clip is never cut off. A beat with no
    audio entry falls back to its planned duration and says so, rather than
    silently borrowing a number that means something else.
    """
    if clip and clip.get("shot_secs"):
        return (
            float(clip["shot_secs"]),
            clip.get("shot_secs_source", "audio_index"),
            clip.get("shot_secs_reason", "taken from the audio index"),
        )
    return (
        float(beat["duration_secs"]),
        "beat_duration",
        (
            f"no audio entry for {beat['beat_id']}; fell back to the beat's "
            f"planned {beat['duration_secs']}s from page geometry"
        ),
    )


def _playable(clip: dict[str, Any] | None) -> Path | None:
    """The clip's audio file, if there is one on disk."""
    if not clip or not clip.get("local_path"):
        return None
    path = Path(clip["local_path"])
    return path if path.exists() else None


def _music_by_beat(audio_index: dict[str, Any]) -> dict[str, Path]:
    """Beat id -> music file, for the beats a script cue plays under."""
    out: dict[str, Path] = {}
    for cue in audio_index.get("music_cues", []):
        path = cue.get("local_path")
        if not path or not Path(path).exists():
            continue
        for beat_id in cue.get("beat_ids", []):
            out[beat_id] = Path(path)
    return out


def build_shot(shot: Shot, out_path: Path) -> Path:
    """Encode one shot to `out_path`. Returns the path written."""
    cmd = ["ffmpeg", "-v", "error", "-y"]
    cmd += _video_input(shot)
    audio_inputs, audio_filter, audio_label = _audio_graph(shot, len(cmd))

    cmd += audio_inputs
    filters = [f"[0:v]{_video_filter(shot)}[v]"]
    if audio_filter:
        filters.append(audio_filter)

    cmd += ["-filter_complex", ";".join(filters), "-map", "[v]"]
    cmd += ["-map", audio_label] if audio_label else []
    cmd += [
        "-t", f"{shot.secs:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k", "-ar", str(AUDIO_RATE), "-ac", "2",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssemblyError(
            f"ffmpeg failed on {shot.beat_id}: {result.stderr.strip()[:400]}"
        )
    return out_path


def _video_input(shot: Shot) -> list[str]:
    """Input flags for the picture.

    A still is looped for the shot's length. A clip is read normally and either
    trimmed or frozen on its last frame by the filter below — never sped up or
    slowed down, which would misrepresent the motion that was generated.
    """
    if shot.source.is_still:
        return ["-loop", "1", "-t", f"{shot.secs:.3f}", "-i", str(shot.source.path)]
    return ["-i", str(shot.source.path)]


def has_audio_stream(path: Path) -> bool:
    """Whether a media file actually carries sound.

    A daily is assumed to bring production sound, but a silent export is an
    easy mistake and the failure is silent in the worst way — a stretch of cut
    with no audio at all where five beats of narration used to be.
    """
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def _video_filter(shot: Shot) -> str:
    scale = (
        f"scale={FRAME_WIDTH}:{FRAME_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={FRAME_WIDTH}:{FRAME_HEIGHT}:(ow-iw)/2:(oh-ih)/2:{PAD_COLOUR}"
    )
    if shot.source.is_still:
        return f"{scale},fps={FPS},format=yuv420p"
    # `tpad=stop_mode=clone` holds the last frame if the clip is shorter than
    # the shot; the -t on the output trims it if it is longer.
    return f"{scale},fps={FPS},tpad=stop_mode=clone:stop_duration={shot.secs:.3f},format=yuv420p"


def _audio_graph(shot: Shot, video_arg_count: int) -> tuple[list[str], str, str | None]:
    """Input flags and filter for the shot's audio.

    Returns (extra inputs, filter string, output label). A shot with no audio
    at all gets silence rather than no track — a concat of segments where some
    have audio and some do not desynchronises.
    """
    # A daily brings production sound. Mapping the video input's own audio is
    # the whole implementation — no filter, no mix, no pad, because the sound
    # is exactly as long as the picture it came with.
    if shot.source.carries_own_audio:
        if has_audio_stream(shot.source.path):
            return [], f"[0:a]aresample={AUDIO_RATE}[a]", "[a]"
        # A daily exported without sound. Silence rather than a failed encode,
        # and `_daily_shot` has already said so in the shot's reason — a
        # stretch of cut that is silent where five beats of narration used to
        # be is exactly the kind of thing that reads as "the audio broke".
        return (
            ["-f", "lavfi", "-t", f"{shot.secs:.3f}",
             "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo"],
            f"[1:a]aresample={AUDIO_RATE}[a]",
            "[a]",
        )

    inputs: list[str] = []
    next_index = 1  # 0 is the video

    speech_label = None
    if shot.audio_path:
        inputs += ["-i", str(shot.audio_path)]
        speech_label = next_index
        next_index += 1

    music_label = None
    if shot.music_path:
        inputs += ["-i", str(shot.music_path)]
        music_label = next_index
        next_index += 1

    pad = f"apad=whole_dur={shot.secs:.3f},atrim=0:{shot.secs:.3f}"

    if speech_label is None and music_label is None:
        inputs += [
            "-f", "lavfi", "-t", f"{shot.secs:.3f}",
            "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo",
        ]
        return inputs, f"[{next_index}:a]aresample={AUDIO_RATE}[a]", "[a]"

    parts = []
    if speech_label is not None:
        parts.append(f"[{speech_label}:a]aresample={AUDIO_RATE},{pad}[sp]")
    if music_label is not None:
        parts.append(
            f"[{music_label}:a]aresample={AUDIO_RATE},volume={MUSIC_GAIN},{pad}[mu]"
        )

    if speech_label is not None and music_label is not None:
        parts.append("[sp][mu]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        parts.append(f"[{'sp' if speech_label is not None else 'mu'}]anull[a]")

    return inputs, ";".join(parts), "[a]"


def concat_shots(segments: list[Path], out_path: Path) -> Path:
    """Join encoded shots into the final cut, without re-encoding."""
    if not segments:
        raise AssemblyError("no shots to concatenate")

    listing = out_path.parent / "segments.txt"
    listing.write_text("\n".join(f"file '{p.resolve()}'" for p in segments))

    result = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-c", "copy", "-movflags", "+faststart",
            str(out_path),
        ],
        capture_output=True,
        text=True,
    )
    listing.unlink(missing_ok=True)
    if result.returncode != 0:
        raise AssemblyError(f"concat failed: {result.stderr.strip()[:400]}")
    return out_path


def probe_duration(path: Path) -> float:
    """Real duration of a media file, read from the file itself."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise AssemblyError(f"could not probe {path}: {result.stderr.strip()[:200]}")
    return float(result.stdout.strip())
