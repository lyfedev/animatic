#!/usr/bin/env python3
"""Pull generated media from S3 into `output/`, for a fresh container.

The pipeline writes every artifact to both local disk and the media bucket.
Local disk is the developer's working copy; the bucket is the durable one. A
container starts with neither, so this fetches what the demo needs to serve:
the beat list, the panels, the audio, the motion clips and their indexes.

Rendered cuts ARE fetched, but only the three mode-named ones
(`animatic-panels`, `animatic-animatic`, `animatic-partial`). Those are
rendered footage-free, which is exactly the state a fresh container is in, so
what a visitor plays matches what `state.json` says. Without them the demo
serves a shot strip and a 404 until someone waits thirty seconds for a render.

The dated deliverable renders (`01-no-footage.mp4` and friends) and the
whole-cut `animatic.mp4` are NOT fetched: they can describe a footage state the
container does not have, and a video that contradicts the state beside it is
worse than no video.

Safe to run repeatedly: a file already present with the right size is skipped,
so a restart is fast and a partially-populated volume repairs itself.

Usage:
    python scripts/fetch_media.py
    python scripts/fetch_media.py --prefix panels/ --prefix audio/
    python scripts/fetch_media.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3  # noqa: E402
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError  # noqa: E402

from animatic.config import settings  # noqa: E402

# Everything the demo reads at request time. `video/` is absent on purpose.
DEFAULT_PREFIXES = ("beats/", "assets/", "panels/", "audio/", "motion/", "video/")

# Under `video/`, only these. See the module docstring for why the rest are not
# safe to serve on a container whose footage state may differ from the machine
# that rendered them.
_VIDEO_ALLOWED = {
    # Published deliberately, NOT a side effect of the last local render.
    # `video/index.json` is overwritten by every `build_video.py` run, so a
    # developer rendering with footage on their own machine would silently
    # tell every container that its footage-free cut is stale.
    "video/container-index.json",
    "video/animatic-panels.mp4",
    "video/animatic-animatic.mp4",
    "video/animatic-partial.mp4",
}

# Where each S3 prefix lands locally. The bucket layout and the local layout
# are not identical — `beats/latest.json` is `output/beats.json` on disk —
# so the mapping is explicit rather than inferred from the key.
_LOCAL_FOR_KEY = {
    "beats/latest.json": Path("output/beats.json"),
    "assets/manifest.json": Path("output/assets/manifest.json"),
    "video/container-index.json": Path("output/video/index.json"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch generated media from S3")
    parser.add_argument("--bucket", default=settings.media_bucket)
    parser.add_argument(
        "--prefix", action="append", default=None,
        help=f"S3 prefix to fetch; repeatable (default: {' '.join(DEFAULT_PREFIXES)})",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit 0 even if nothing was found — for a first boot before any run",
    )
    args = parser.parse_args()

    prefixes = tuple(args.prefix) if args.prefix else DEFAULT_PREFIXES
    client = _client(args.bucket)
    if client is None:
        # The container tolerates this (`|| true` in CMD) and degrades to an
        # honest 503; a developer running it by hand should see a failure.
        sys.exit(f"cannot fetch media from s3://{args.bucket}")

    fetched = skipped = 0
    for prefix in prefixes:
        for key, size in _list(client, args.bucket, prefix):
            local = _local_for(key)
            if local.exists() and local.stat().st_size == size:
                skipped += 1
                continue
            if args.dry_run:
                print(f"  would fetch {key} -> {local} ({size} bytes)")
                fetched += 1
                continue
            local.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(args.bucket, key, str(local))
            print(f"  {key} -> {local}")
            fetched += 1

    print(f"\n{fetched} fetched, {skipped} already current")
    if fetched == 0 and skipped == 0 and not args.allow_empty:
        sys.exit(
            f"nothing found under {prefixes} in {args.bucket} — has the "
            f"pipeline run?"
        )


def _client(bucket: str):
    """An S3 client, checked against THIS bucket rather than the account.

    The first version probed with `list_buckets()`, which needs account-wide
    `s3:ListAllMyBuckets`. The ECS task role is scoped to one bucket — exactly
    as it should be — so the probe failed, the script reported "no credentials",
    and the container served a demo with no media behind it. A permission check
    must ask for the permission the code actually needs.
    """
    try:
        session = boto3.Session(profile_name="newaccount")
    except Exception:  # noqa: BLE001 — no named profile in a container
        session = boto3.Session()

    client = session.client("s3", region_name=settings.aws_region)
    try:
        client.head_bucket(Bucket=bucket)
        return client
    except (NoCredentialsError, ClientError, BotoCoreError) as exc:
        print(f"cannot reach s3://{bucket}: {exc}", file=sys.stderr)
        return None


def _list(client, bucket: str, prefix: str):
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            if key.startswith("video/") and key not in _VIDEO_ALLOWED:
                continue
            yield key, obj["Size"]


def _local_for(key: str) -> Path:
    """Where an S3 key lands on disk."""
    if key in _LOCAL_FOR_KEY:
        return _LOCAL_FOR_KEY[key]
    if key.startswith("assets/art/"):
        return Path("output/assets/generated") / Path(key).name
    return Path("output") / key


if __name__ == "__main__":
    main()
