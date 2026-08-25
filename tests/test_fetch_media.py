"""Tests for the container's media fetch.

The one that matters is the permission probe. The first version asked for a
permission the deployed task role does not have and should not have, so the
hosted demo came up with no media behind it and answered 503 — while every
local run worked, because a developer's credentials are account-wide.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

_SPEC = importlib.util.spec_from_file_location(
    "fetch_media", Path(__file__).parent.parent / "scripts" / "fetch_media.py"
)
fetch_media = importlib.util.module_from_spec(_SPEC)
sys.modules["fetch_media"] = fetch_media
_SPEC.loader.exec_module(fetch_media)


def _denied(operation: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": "AccessDenied", "Message": f"not authorized for {operation}"}},
        operation,
    )


class TestPermissionProbe:
    """Regression: the probe must ask only for what the code needs."""

    def test_it_probes_the_bucket_not_the_account(self, monkeypatch):
        client = MagicMock()
        session = MagicMock()
        session.client.return_value = client
        monkeypatch.setattr(fetch_media.boto3, "Session", lambda **_: session)

        fetch_media._client("animatic-media-628818")

        client.head_bucket.assert_called_once_with(Bucket="animatic-media-628818")
        client.list_buckets.assert_not_called()

    def test_a_bucket_scoped_role_is_accepted(self, monkeypatch):
        """A role with no ListAllMyBuckets must still be usable.

        This is the deployed task role: `media_bucket.grant_read_write` scopes
        it to one bucket, correctly.
        """
        client = MagicMock()
        client.list_buckets.side_effect = _denied("ListBuckets")
        session = MagicMock()
        session.client.return_value = client
        monkeypatch.setattr(fetch_media.boto3, "Session", lambda **_: session)

        assert fetch_media._client("animatic-media-628818") is client

    def test_a_genuinely_unreachable_bucket_returns_none(self, monkeypatch):
        client = MagicMock()
        client.head_bucket.side_effect = _denied("HeadBucket")
        session = MagicMock()
        session.client.return_value = client
        monkeypatch.setattr(fetch_media.boto3, "Session", lambda **_: session)

        assert fetch_media._client("nope") is None

    def test_a_missing_named_profile_falls_back(self, monkeypatch):
        """Containers have no `newaccount` profile; that is normal."""
        client = MagicMock()

        def session(**kwargs):
            if kwargs.get("profile_name"):
                raise RuntimeError("ProfileNotFound")
            s = MagicMock()
            s.client.return_value = client
            return s

        monkeypatch.setattr(fetch_media.boto3, "Session", session)
        assert fetch_media._client("bucket") is client


class TestKeyMapping:
    def test_the_beat_list_lands_where_the_pipeline_reads_it(self):
        # The bucket calls it beats/latest.json; the code reads output/beats.json.
        assert fetch_media._local_for("beats/latest.json") == Path("output/beats.json")

    def test_slot_art_lands_in_the_generated_directory(self):
        assert fetch_media._local_for("assets/art/rocky.jpg") == Path(
            "output/assets/generated/rocky.jpg"
        )

    def test_the_manifest_lands_beside_its_art(self):
        assert fetch_media._local_for("assets/manifest.json") == Path(
            "output/assets/manifest.json"
        )

    @pytest.mark.parametrize(
        "key,expected",
        [
            ("panels/s2b2.jpg", "output/panels/s2b2.jpg"),
            ("audio/s2b5.wav", "output/audio/s2b5.wav"),
            ("motion/s2b2.mp4", "output/motion/s2b2.mp4"),
            ("panels/index.json", "output/panels/index.json"),
        ],
    )
    def test_everything_else_mirrors_under_output(self, key, expected):
        assert fetch_media._local_for(key) == Path(expected)


class TestWhatIsFetched:
    def test_rendered_cuts_are_not_fetched(self):
        """A stale cut would contradict the state the demo reports."""
        assert not any(p.startswith("video") for p in fetch_media.DEFAULT_PREFIXES)

    def test_everything_the_demo_serves_is_fetched(self):
        for needed in ("beats/", "panels/", "audio/", "motion/", "assets/"):
            assert needed in fetch_media.DEFAULT_PREFIXES
