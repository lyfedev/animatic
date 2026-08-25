"""Pytest fixtures over the real Rocky corpus. Paths live in `corpus.py`.

The README runs the suite as `PYTHONPATH=src pytest tests/`, which puts `src`
on the path but not `tests`, so a test module cannot import a sibling helper.
conftest.py is imported before any test module, which makes it the right place
to fix that — the same `sys.path` insert every script in `scripts/` already
does for `src`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from corpus import (  # noqa: E402
    FIXTURE_BEATS,
    FIXTURE_MANIFEST,
    LIVE_BEATS,
    LIVE_MANIFEST,
    beats_path,
    manifest_path,
)


@pytest.fixture(scope="session")
def beats_doc() -> dict:
    return json.loads(beats_path().read_text())


@pytest.fixture(scope="session")
def assets_manifest() -> dict:
    return json.loads(manifest_path().read_text())


def test_fixtures_match_the_live_artifacts():
    """The fixture is a copy, and a copy that drifts is worse than none.

    Skips when there is nothing to compare against (CI). Fails on the machine
    that regenerated the corpus, which is exactly where the refresh belongs:
    `cp output/beats.json tests/fixtures/beats.json`.
    """
    checked = 0
    for live, fixture in ((LIVE_BEATS, FIXTURE_BEATS), (LIVE_MANIFEST, FIXTURE_MANIFEST)):
        if not (live.exists() and fixture.exists()):
            continue
        checked += 1
        live_doc = json.loads(live.read_text())
        fixture_doc = json.loads(fixture.read_text())
        # `generated_at` and S3 status change on every run without changing
        # anything a test asserts on; comparing them would fail constantly.
        volatile = {"generated_at", "s3_ok", "s3_reason", "stale_beat_ids",
                    "stale_beat_reason", "beats_generated_at"}
        live_stable = {k: v for k, v in live_doc.items() if k not in volatile}
        fixture_stable = {k: v for k, v in fixture_doc.items() if k not in volatile}
        assert live_stable == fixture_stable, (
            f"{fixture} has drifted from {live} — refresh it with "
            f"`cp {live} {fixture}`"
        )

    if not checked:
        pytest.skip("no live artifacts to compare the fixtures against")
