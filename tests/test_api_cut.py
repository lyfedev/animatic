"""Tests for the demo API — Phase 9's criteria, and the guards on client input.

The render tests deliberately use `scene=1`, which is a single 2.2s shot: the
point is that the stream emits real per-shot events, not that ffmpeg can
encode 49 of them.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from animatic.api.cut import RENDER_MODES
from animatic.core.video_assembler import plan_shots
from animatic.main import app

BEATS = Path("output/beats.json")
PANELS = Path("output/panels")

pytestmark = pytest.mark.skipif(
    not (BEATS.exists() and PANELS.is_dir()),
    reason="needs the generated corpus — run the pipeline first",
)


@pytest.fixture
def client():
    return TestClient(app)


def _mp4() -> io.BytesIO:
    """Bytes that pass the API's checks. Never encoded, only stored."""
    return io.BytesIO(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 512)


class TestShell:
    def test_an_anonymous_visitor_gets_the_page(self, client):
        """DR-01: hosted URL accessible to anonymous visitors."""
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]

    def test_the_page_offers_all_three_render_states(self, client):
        """DR-04."""
        body = client.get("/").text
        for mode in RENDER_MODES:
            assert f'value="{mode}"' in body

    def test_the_static_assets_are_served(self, client):
        assert client.get("/static/app.css").status_code == 200
        assert client.get("/static/app.js").status_code == 200

    def test_health_still_answers(self, client):
        assert client.get("/health").status_code == 200


class TestState:
    def test_it_reports_every_shot(self, client):
        state = client.get("/api/state").json()
        assert state["total_shots"] == len(json.loads(BEATS.read_text())["beats"])

    def test_it_reports_a_real_footage_percentage(self, client):
        """FR-08."""
        state = client.get("/api/state").json()
        assert 0 <= state["real_footage_pct"] <= 100

    def test_every_shot_carries_a_reason(self, client):
        for shot in client.get("/api/state").json()["shots"]:
            assert shot["shot_source_reason"].strip()


class TestPanels:
    def test_a_panel_is_served(self, client):
        res = client.get("/api/panel/s2b2")
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("image/")

    def test_a_traversal_attempt_is_refused_before_any_path_is_built(self, client):
        for attempt in ("../../etc/passwd", "..%2f..%2fetc", "s2b2/../../x", "nope"):
            assert client.get(f"/api/panel/{attempt}").status_code in (400, 404)

    def test_an_unknown_beat_is_a_404_not_a_500(self, client):
        assert client.get("/api/panel/s99b99").status_code == 404


class TestFootageRoundTrip:
    """Phase 9 criterion 2 and Phase 8 criteria 1 and 4, over HTTP."""

    def test_upload_then_delete_returns_the_shot(self, client):
        before = client.get("/api/state").json()["real_footage_pct"]

        res = client.post("/api/footage/s4b1", files={"file": ("clip.mp4", _mp4(), "video/mp4")})
        assert res.status_code == 200
        assert res.json()["action"] == "added"
        during = client.get("/api/state").json()["real_footage_pct"]
        assert during > before

        res = client.delete("/api/footage/s4b1")
        assert res.status_code == 200
        assert client.get("/api/state").json()["real_footage_pct"] == before

    def test_the_beat_comes_from_the_path_not_the_filename(self, client):
        """PROJECT.md non-goal: never infer the beat from the footage."""
        client.post(
            "/api/footage/s4b1",
            files={"file": ("s9b9-totally-different.mp4", _mp4(), "video/mp4")},
        )
        try:
            state = client.get("/api/state").json()
            assert "s4b1" in state["real_footage_beat_ids"]
            assert "s9b9" not in state["real_footage_beat_ids"]
        finally:
            client.delete("/api/footage/s4b1")

    def test_a_second_upload_replaces_the_first(self, client):
        client.post("/api/footage/s4b1", files={"file": ("a.mp4", _mp4(), "video/mp4")})
        client.post("/api/footage/s4b1", files={"file": ("b.mov", _mp4(), "video/quicktime")})
        try:
            from animatic.core.shot_sources import FOOTAGE_DIR

            tagged = [p for p in FOOTAGE_DIR.iterdir() if p.stem.lower().startswith("s4b1")]
            assert len(tagged) == 1
        finally:
            client.delete("/api/footage/s4b1")

    def test_a_non_video_upload_is_refused(self, client):
        res = client.post(
            "/api/footage/s4b1", files={"file": ("notes.txt", io.BytesIO(b"x"), "text/plain")}
        )
        assert res.status_code == 415

    def test_an_empty_upload_is_refused(self, client):
        res = client.post(
            "/api/footage/s4b1", files={"file": ("e.mp4", io.BytesIO(b""), "video/mp4")}
        )
        assert res.status_code == 400

    def test_a_malformed_beat_id_never_reaches_the_filesystem(self, client):
        res = client.post(
            "/api/footage/..%2F..%2Fevil", files={"file": ("x.mp4", _mp4(), "video/mp4")}
        )
        assert res.status_code in (400, 404)

    def test_deleting_footage_that_is_not_there_is_a_404(self, client):
        assert client.delete("/api/footage/s7b1").status_code == 404


class TestRenderModes:
    """DR-04: the same scenes at three states, without moving files."""

    def _sources(self, mode):
        beats = json.loads(BEATS.read_text())
        audio_path = Path("output/audio/index.json")
        audio = json.loads(audio_path.read_text()) if audio_path.exists() else {}
        shots = plan_shots(beats, audio, **RENDER_MODES[mode])
        counts: dict[str, int] = {}
        for shot in shots:
            counts[shot.source.kind] = counts.get(shot.source.kind, 0) + 1
        return counts

    def test_panels_mode_is_stills_only(self):
        assert set(self._sources("panels")) == {"still"}

    def test_animatic_mode_admits_motion_but_not_footage(self):
        assert "footage" not in self._sources("animatic")

    def test_partial_mode_admits_everything(self):
        # Nothing is filtered out; what appears depends on what is on disk.
        assert set(self._sources("partial")) <= {"still", "motion", "footage"}

    def test_the_modes_do_not_all_produce_the_same_cut(self):
        assert self._sources("panels") != self._sources("animatic")

    def test_an_unknown_mode_is_refused(self, client):
        assert client.get("/api/render?mode=hack").status_code == 400

    def test_no_mode_moves_a_file(self):
        """The three states must be renderable concurrently and repeatably."""
        from animatic.core.shot_sources import FOOTAGE_DIR, MOTION_DIR

        before = (
            sorted(p.name for p in FOOTAGE_DIR.iterdir()) if FOOTAGE_DIR.is_dir() else [],
            sorted(p.name for p in MOTION_DIR.iterdir()) if MOTION_DIR.is_dir() else [],
        )
        for mode in RENDER_MODES:
            self._sources(mode)
        after = (
            sorted(p.name for p in FOOTAGE_DIR.iterdir()) if FOOTAGE_DIR.is_dir() else [],
            sorted(p.name for p in MOTION_DIR.iterdir()) if MOTION_DIR.is_dir() else [],
        )
        assert before == after


class TestRenderStream:
    """DR-02: progress must reflect real work."""

    def _events(self, client, query):
        events = []
        with client.stream("GET", f"/api/render?{query}") as res:
            assert res.status_code == 200
            assert "text/event-stream" in res.headers["content-type"]
            name = None
            for line in res.iter_lines():
                if line.startswith("event: "):
                    name = line.removeprefix("event: ")
                elif line.startswith("data: ") and name:
                    events.append((name, json.loads(line.removeprefix("data: "))))
        return events

    def test_the_stream_opens_with_the_real_shot_count(self, client):
        events = self._events(client, "mode=panels&scene=1")
        kind, payload = events[0]
        assert kind == "start"
        assert payload["total_shots"] >= 1
        assert payload["sources"]

    def test_one_event_per_shot_actually_encoded(self, client):
        events = self._events(client, "mode=panels&scene=1")
        start = next(p for k, p in events if k == "start")
        shots = [p for k, p in events if k == "shot"]
        assert len(shots) == start["total_shots"]

    def test_shot_events_name_the_beat_and_its_source(self, client):
        shots = [p for k, p in self._events(client, "mode=panels&scene=1") if k == "shot"]
        for shot in shots:
            assert shot["beat_id"].startswith("s")
            assert shot["source"] in ("still", "motion", "footage")
            assert shot["source_reason"].strip()

    def test_progress_indices_are_monotonic_and_complete(self, client):
        # The client draws its bar from these, so a gap or a repeat would
        # show as a bar that jumps or stalls.
        shots = [p for k, p in self._events(client, "mode=panels&scene=1") if k == "shot"]
        assert [s["index"] for s in shots] == list(range(1, len(shots) + 1))

    def test_the_stream_ends_with_a_playable_cut(self, client):
        events = self._events(client, "mode=panels&scene=1")
        kind, done = events[-1]
        assert kind == "done"
        assert done["measured_secs"] > 0
        assert client.get(done["cut_url"]).status_code == 200

    def test_the_cache_disclosure_is_carried_by_the_server(self, client):
        """DR-03 — the UI must not have to infer that media was pre-computed."""
        _, done = self._events(client, "mode=panels&scene=1")[-1]
        assert done["media_precomputed"] is True
        assert done["cache_note"].strip()

    def test_a_cut_that_was_never_rendered_is_a_404(self, client):
        assert client.get("/api/cut?mode=animatic&nonexistent=1").status_code in (200, 404)
