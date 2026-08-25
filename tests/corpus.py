"""Where the tests get their real data.

Most of this suite asserts against the actual Rocky corpus rather than
invented fixtures — 16 slots, 49 beats, no voice collisions in scene 3. That
is deliberate and worth keeping: a test built from a fixture that says what
the code says proves nothing.

But those artifacts live under `output/`, which is gitignored, so CI had none
of them and 36 tests failed on every push from Phase 3 onward. The fix is a
committed copy under `tests/fixtures/`, used when the live artifact is absent.

Local runs still prefer the LIVE file, so a regeneration that breaks an
invariant is caught on the machine that regenerated it. CI runs against the
fixture. `test_fixtures_match_the_live_artifacts` fails when the two diverge,
so the fixture cannot go quietly stale.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

LIVE_BEATS = Path("output/beats.json")
LIVE_MANIFEST = Path("output/assets/manifest.json")

FIXTURE_BEATS = FIXTURES / "beats.json"
FIXTURE_MANIFEST = FIXTURES / "assets-manifest.json"


def beats_path() -> Path:
    """The beat list: live if it exists, else the committed fixture."""
    return LIVE_BEATS if LIVE_BEATS.exists() else FIXTURE_BEATS


def manifest_path() -> Path:
    """The asset manifest: live if it exists, else the committed fixture."""
    return LIVE_MANIFEST if LIVE_MANIFEST.exists() else FIXTURE_MANIFEST
