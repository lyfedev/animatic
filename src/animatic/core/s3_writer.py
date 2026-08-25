"""Shared, honest S3 writer (T-03-05).

Wraps the session/profile handling previously inlined separately in
`beat_assembler._write_s3` and `asset_manifest._write_bytes_to_s3` — one
place decides how the local AWS profile vs. the ECS task role is chosen,
and one place decides what "the write failed" means.

`put_bytes` never reports a failure as success: it returns an explicit
`S3Result(uri, ok, error)` rather than swallowing `ClientError` and handing
the caller a `local://` URI that looks like it succeeded. That swallow-and-
fake-success pattern was `beat_assembler._write_s3`'s original bug
(`.planning/phases/phase-2/2-VERIFICATION.md`); callers here decide for
themselves what a failed write means for their own artifact (a warning, a
`local://` fallback marker, or a top-level `s3_ok`/`s3_reason` field).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

from animatic.config import settings

logger = logging.getLogger(__name__)


@dataclass
class S3Result:
    """Outcome of one `put_bytes` call — always populated, never fabricated.

    `uri` is the intended `s3://bucket/key` location whether or not the
    write succeeded, so a caller can log what *would* have been written
    even on failure. `error` is empty on success.
    """

    uri: str
    ok: bool
    error: str


def put_bytes(key: str, body: bytes, content_type: str) -> S3Result:
    """Write `body` to `key` in `settings.media_bucket`.

    Named profile locally (`AWS_PROFILE`, default "newaccount"); in ECS the
    task role is used automatically since `settings.environment` is not
    "development". Any failure — `ClientError`, a missing local profile
    (`ProfileNotFound`), or anything else — logs at ERROR and returns
    `ok=False` with the message; it never raises and never fabricates a
    success.
    """
    bucket = settings.media_bucket
    uri = f"s3://{bucket}/{key}"
    try:
        profile = (
            os.environ.get("AWS_PROFILE", "newaccount")
            if settings.environment == "development"
            else None
        )
        session = boto3.Session(profile_name=profile)
        s3 = session.client("s3", region_name=settings.aws_region)
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
        logger.info("Wrote %s", uri)
        return S3Result(uri=uri, ok=True, error="")
    except ClientError as e:
        logger.error("S3 write to %s failed: %s", uri, e)
        return S3Result(uri=uri, ok=False, error=f"ClientError: {e}")
    except Exception as e:  # e.g. ProfileNotFound — degrade honestly rather
        # than crash and lose a local write already on disk.
        logger.error("S3 write to %s failed: %s", uri, e)
        return S3Result(uri=uri, ok=False, error=f"{type(e).__name__}: {e}")
