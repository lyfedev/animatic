"""Beat list assembler — collects beats from all scenes, writes to S3 and local."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from animatic.config import settings
from animatic.core.beat_extractor import Beat

logger = logging.getLogger(__name__)

_LOCAL_OUTPUT = Path("output/beats.json")
_S3_KEY = "beats/latest.json"


def assemble_and_write(scenes_beats: dict[int, list[Beat]]) -> str:
    """Assemble beat list from all scenes and write to S3 and local.

    Args:
        scenes_beats: dict mapping scene_number → list of Beat objects.

    Returns:
        S3 URI of the written beat list (e.g. s3://bucket/beats/latest.json).
    """
    beat_list = _build_beat_list(scenes_beats)
    _write_local(beat_list)
    s3_uri = _write_s3(beat_list)
    return s3_uri


def _build_beat_list(scenes_beats: dict[int, list[Beat]]) -> dict[str, Any]:
    """Build the full beat list manifest."""
    all_beats = []
    for scene_num in sorted(scenes_beats.keys()):
        all_beats.extend(b.to_dict() for b in scenes_beats[scene_num])

    total_duration = sum(b["duration_secs"] for b in all_beats)
    motion_count = sum(1 for b in all_beats if b["motion_candidate"])
    pct_motion = round(motion_count / len(all_beats) * 100, 1) if all_beats else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script": "rocky-1976",
        "scenes": sorted(scenes_beats.keys()),
        "total_beats": len(all_beats),
        "total_duration_secs": round(total_duration, 1),
        "pct_motion_candidates": pct_motion,
        "beats": all_beats,
    }


def _write_local(beat_list: dict[str, Any]) -> None:
    """Write beat list to local output file."""
    _LOCAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCAL_OUTPUT, "w") as f:
        json.dump(beat_list, f, indent=2)
    logger.info("Beat list written locally to %s", _LOCAL_OUTPUT)


def _write_s3(beat_list: dict[str, Any]) -> str:
    """Write beat list to S3, return S3 URI."""
    bucket = settings.media_bucket
    try:
        # Use named profile locally; in ECS the task role is used automatically
        profile = os.environ.get("AWS_PROFILE", "newaccount") if settings.environment == "development" else None
        session = boto3.Session(profile_name=profile)
        s3 = session.client("s3", region_name=settings.aws_region)
        body = json.dumps(beat_list, indent=2).encode("utf-8")
        s3.put_object(
            Bucket=bucket,
            Key=_S3_KEY,
            Body=body,
            ContentType="application/json",
        )
        uri = f"s3://{bucket}/{_S3_KEY}"
        logger.info("Beat list written to %s", uri)
        return uri
    except ClientError as e:
        logger.warning("S3 write failed (%s) — local output only", e)
        return f"local://{_LOCAL_OUTPUT}"
