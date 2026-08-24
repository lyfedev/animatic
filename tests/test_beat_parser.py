"""Unit tests for the beat parser pipeline."""

from __future__ import annotations

import json
from itertools import islice
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from animatic.core.beat_extractor import Beat
from animatic.core.pdf_extractor import (
    _extract_full_text,
    _split_by_scene,
    extract_scenes,
)
from animatic.main import app

client = TestClient(app)

PDF_PATH = Path("docs/rocky-1976.pdf")

# ---------------------------------------------------------------------------
# PDF extractor tests
# ---------------------------------------------------------------------------

def test_extract_scenes_returns_8_scenes():
    scenes = extract_scenes(PDF_PATH, first_n=8)
    assert len(scenes) == 8


def test_extract_scenes_all_nonempty():
    """Every scene must have text — but a slug-only scene is legitimate.

    Rocky scene 1 is the bare slug "INT. BLUE DOOR FIGHT CLUB - NIGHT";
    the action it introduces is written as scene 2 (a SUPERIMPOSE). So a
    per-scene length floor is the wrong assertion — require a heading on
    each, and real body text across the demo set as a whole.
    """
    scenes = extract_scenes(PDF_PATH, first_n=8)
    for num, text in scenes.items():
        assert text.strip(), f"Scene {num} is empty"
        assert str(num) in text.split("\n")[0], f"Scene {num} lost its heading"
    total_words = sum(len(t.split()) for t in scenes.values())
    assert total_words > 900, f"demo set too thin: {total_words} words"


def test_extract_scenes_first_is_fight_club():
    scenes = extract_scenes(PDF_PATH, first_n=8)
    first_text = list(scenes.values())[0]
    assert "INT." in first_text or "EXT." in first_text


def test_extract_scenes_returns_scenes_1_to_8():
    """The demo set is scenes 1-8. Contiguous, no gaps, no scene 9.

    Regression guard: an INT/EXT-only heading pattern silently dropped
    scene 2 (a SUPERIMPOSE title card, not a slug line) and shifted the
    range to 1,3-9. Downstream phases key panels, audio, motion and
    footage filenames off these numbers, so pin the exact set.
    """
    scenes = extract_scenes(PDF_PATH, first_n=8)
    assert list(scenes.keys()) == [1, 2, 3, 4, 5, 6, 7, 8]


def test_scene_2_is_present_and_carries_the_fight():
    """Scene 2 is the opening fight — the single biggest scene in the demo.

    It has no INT./EXT. slug, so it is exactly the scene a naive heading
    pattern loses. Its body must contain the fight, not be an empty stub.
    """
    scenes = extract_scenes(PDF_PATH, first_n=8)
    assert 2 in scenes, "scene 2 (SUPERIMPOSE title card) must not be dropped"
    body = scenes[2]
    assert "ROCKY BALBOA" in body
    assert "BLACK FIGHTER" in body
    assert len(body.split()) > 400, "scene 2 should carry the full fight-club scene"


def test_extract_scenes_preserves_appearance_order():
    """Scenes must come back in document order, not re-sorted by number.

    Checks each returned block's real offset in the source text, so a
    regression to numeric sorting would be caught on a script whose
    numbering is out of order.
    """
    scenes = extract_scenes(PDF_PATH, first_n=20)
    assert len(scenes) == 20

    full_text = _extract_full_text(PDF_PATH)
    offsets = [full_text.index(text[:60]) for text in scenes.values()]
    assert offsets == sorted(offsets), "scenes are not in document order"


def test_split_by_scene_takes_first_n_by_appearance_not_number():
    """Directly pin the appearance-order contract with out-of-order input.

    A renumbered insert (scene 5 appearing after 12) must not be pulled
    forward by numeric sorting.
    """
    text = (
        "1 INT. FIRST - DAY 1\nBody one.\n"
        "12 INT. SECOND - DAY 12\nBody two.\n"
        "5 INT. THIRD - DAY 5\nBody three.\n"
    )
    scene_map = _split_by_scene(text)
    assert list(scene_map.keys()) == [1, 12, 5]
    assert list(islice(scene_map.items(), 2)) == [
        (1, scene_map[1]),
        (12, scene_map[12]),
    ]


# ---------------------------------------------------------------------------
# Beat schema validation tests (using mock Gemini response)
# ---------------------------------------------------------------------------

_MOCK_BEATS_JSON = json.dumps([
    {
        "beat": 1,
        "scene_heading": "INT. TEST - NIGHT",
        "type": "establishing",
        "content": "A dark room.",
        "duration_secs": 3.0,
        "motion_candidate": False,
        "reason": "Opening establishing shot sets location.",
        "characters": [],
        "dialogue": [],
    },
    {
        "beat": 2,
        "scene_heading": "INT. TEST - NIGHT",
        "type": "action",
        "content": "A fight breaks out.",
        "duration_secs": 5.0,
        "motion_candidate": True,
        "reason": "High-intensity action beat.",
        "characters": ["ROCKY"],
        "dialogue": [],
    },
    {
        "beat": 3,
        "scene_heading": "INT. TEST - NIGHT",
        "type": "dialogue",
        "content": "Rocky speaks.",
        "duration_secs": 4.0,
        "motion_candidate": False,
        "reason": "Key dialogue exchange.",
        "characters": ["ROCKY", "ADRIAN"],
        "dialogue": [
            {"character": "ROCKY", "line": "Yo, Adrian."},
            {"character": "ADRIAN", "line": "... I was worried."},
        ],
    },
])


def _make_mock_response(text: str) -> MagicMock:
    mock = MagicMock()
    mock.text = text
    return mock


@patch("animatic.core.beat_extractor.genai.Client")
def test_extract_beats_returns_beats(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_BEATS_JSON)

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(1, "INT. TEST - NIGHT\nSome action.")

    # 3 raw beats in, 4 out: the ROCKY/ADRIAN exchange splits into two turns.
    assert len(beats) == 4
    assert all(isinstance(b, Beat) for b in beats)


@patch("animatic.core.beat_extractor.genai.Client")
def test_all_beats_have_required_fields(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_BEATS_JSON)

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(1, "INT. TEST - NIGHT\nSome action.")

    for beat in beats:
        assert beat.beat_id, "beat_id must be non-empty"
        assert beat.reason, "reason must be non-empty"
        assert beat.duration_secs > 0, "duration must be positive"
        assert beat.type in {"action", "dialogue", "establishing"}


@patch("animatic.core.beat_extractor.genai.Client")
def test_beat_ids_are_unique(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_BEATS_JSON)

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(1, "INT. TEST - NIGHT\nSome action.")

    ids = [b.beat_id for b in beats]
    assert len(ids) == len(set(ids)), "All beat_ids must be unique"


@patch("animatic.core.beat_extractor.genai.Client")
def test_motion_candidates_flagged_correctly(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_BEATS_JSON)

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(1, "INT. TEST - NIGHT\nA fight.")

    motion = [b for b in beats if b.motion_candidate]
    assert len(motion) == 1
    assert motion[0].type == "action"


# ---------------------------------------------------------------------------
# Dialogue attribution — one speaker per line
# ---------------------------------------------------------------------------

@patch("animatic.core.beat_extractor.genai.Client")
def test_dialogue_lines_keep_their_speaker(mock_client_cls):
    """Each line carries exactly one speaker.

    Regression guard: `dialogue` used to be a single string, so a two-person
    exchange came back merged ("Ya movin' like a bum -- ... Just gimme the
    water.") with both names in `characters`. Phase 5 assigns a voice per
    character and cannot split a blob like that.
    """
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_BEATS_JSON)

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(1, "INT. TEST - NIGHT\nTalk.")

    spoken = [b for b in beats if b.dialogue]
    # One beat per speaker turn, each holding a single attributed line.
    assert len(spoken) == 2
    assert [(b.characters, b.dialogue[0].character, b.dialogue[0].line) for b in spoken] == [
        (["ROCKY"], "ROCKY", "Yo, Adrian."),
        (["ADRIAN"], "ADRIAN", "... I was worried."),
    ]
    for b in spoken:
        assert len(b.dialogue) == 1
        assert b.dialogue[0].character, "every line must name its speaker"


@patch("animatic.core.beat_extractor.genai.Client")
def test_beats_without_speech_have_empty_dialogue(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_BEATS_JSON)

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(1, "INT. TEST - NIGHT\nAction.")

    assert beats[0].dialogue == []
    assert beats[0].spoken_words == 0
    assert beats[0].duration_source == "model"


def test_legacy_string_dialogue_is_coerced_not_crashed():
    """An older cached beat list must load, flagged rather than mis-voiced."""
    from animatic.core.beat_extractor import _parse_lines

    lines = _parse_lines("Ya movin' like a bum -- Just gimme the water.")
    assert len(lines) == 1
    assert lines[0].character == "UNKNOWN"
    assert _parse_lines(None) == []
    assert _parse_lines([]) == []


# ---------------------------------------------------------------------------
# Duration floor — a beat must be long enough to speak its own lines
# ---------------------------------------------------------------------------

def test_duration_is_raised_to_fit_its_dialogue():
    """Phase 7 cuts each shot to duration_secs, so speech must fit inside it."""
    from animatic.core.beat_extractor import Beat, Line, _apply_duration_floor

    beat = Beat(
        beat_id="s3b4", scene=3, beat=4, scene_heading="INT. DRESSING ROOM - NIGHT",
        type="dialogue", content="The promoter itemises the deductions.",
        duration_secs=6.0, motion_candidate=False, reason="Pay transaction.",
        characters=["PROMOTER"],
        dialogue=[Line("PROMOTER", "Twenty bucks for the locker an' cornerman -- "
                                   "Two bucks for the towel an' shower, seven for tax -- "
                                   "The house owes ya, sixty-one dollars.")],
    )
    _apply_duration_floor(beat)

    assert beat.duration_secs > 6.0
    assert beat.duration_secs == beat.min_speakable_secs
    assert beat.duration_source == "dialogue_floor"
    assert "duration raised" in beat.reason, "adjustment must stay machine-readable"


def test_duration_is_left_alone_when_already_long_enough():
    from animatic.core.beat_extractor import Beat, Line, _apply_duration_floor

    beat = Beat(
        beat_id="s4b3", scene=4, beat=3, scene_heading="INT. TROLLEY - NIGHT",
        type="dialogue", content="Rocky explains himself.", duration_secs=8.0,
        motion_candidate=False, reason="Short admission.", characters=["ROCKY"],
        dialogue=[Line("ROCKY", "I'm a fighter.")],
    )
    _apply_duration_floor(beat)

    assert beat.duration_secs == 8.0
    assert beat.duration_source == "model"


def test_every_dialogue_beat_can_speak_its_lines():
    """The invariant Phase 5 and Phase 7 depend on, asserted end to end."""
    from animatic.core.beat_extractor import Beat, Line, _apply_duration_floor

    for words, given in ((26, 6.0), (15, 5.0), (11, 3.5), (3, 20.0)):
        beat = Beat(
            beat_id="x", scene=1, beat=1, scene_heading="H", type="dialogue",
            content="c", duration_secs=given, motion_candidate=False, reason="r",
            characters=["A"], dialogue=[Line("A", " ".join(["word"] * words))],
        )
        _apply_duration_floor(beat)
        assert beat.duration_secs >= beat.min_speakable_secs


# ---------------------------------------------------------------------------
# Speaker-turn splitting — film cuts on speaker turns
# ---------------------------------------------------------------------------

def _exchange_beat():
    from animatic.core.beat_extractor import Beat, Line
    return Beat(
        beat_id="", scene=2, beat=0, scene_heading="INT. CLUB - NIGHT",
        type="dialogue", content="The cornerman needles Rocky.", duration_secs=9.0,
        motion_candidate=False, reason="Corner exchange.",
        characters=["CORNERMAN", "ROCKY"],
        dialogue=[
            Line("CORNERMAN", "... Ya waltzin' -- Give the suckers some action."),
            Line("ROCKY", "Hey --"),
            Line("CORNERMAN", "Ya movin' like a bum -- Want some advice --"),
            Line("ROCKY", "... Just gimme the water."),
        ],
    )


def test_multi_turn_beat_is_split_one_beat_per_turn():
    """A four-line exchange is four shots, not one 12s held frame."""
    from animatic.core.beat_extractor import _split_speaker_turns

    out = _split_speaker_turns([_exchange_beat()])

    assert len(out) == 4
    assert [b.characters for b in out] == [
        ["CORNERMAN"], ["ROCKY"], ["CORNERMAN"], ["ROCKY"]
    ]
    for b in out:
        assert len(b.dialogue) == 1, "each split beat holds exactly one turn"
        assert b.type == "dialogue"
        assert not b.motion_candidate, "a speaker turn is never a motion candidate"
        assert "split" in b.reason, "the split must stay machine-readable"


def test_split_preserves_every_line_in_order():
    from animatic.core.beat_extractor import _split_speaker_turns

    original = _exchange_beat()
    out = _split_speaker_turns([original])

    before = [(x.character, x.line) for x in original.dialogue]
    after = [(x.character, x.line) for b in out for x in b.dialogue]
    assert after == before, "splitting must not drop, reorder or reword a line"


def test_consecutive_lines_by_one_speaker_stay_one_turn():
    """Two lines in a row from the same character is one shot, not two."""
    from animatic.core.beat_extractor import Beat, Line, _split_speaker_turns

    beat = Beat(
        beat_id="", scene=3, beat=0, scene_heading="INT. ROOM - DAY",
        type="dialogue", content="c", duration_secs=5.0, motion_candidate=False,
        reason="r", characters=["PROMOTER", "ROCKY"],
        dialogue=[
            Line("PROMOTER", "Twenty bucks for the locker."),
            Line("PROMOTER", "Two bucks for the towel."),
            Line("ROCKY", "Yeah."),
        ],
    )
    out = _split_speaker_turns([beat])

    assert len(out) == 2
    assert len(out[0].dialogue) == 2 and out[0].characters == ["PROMOTER"]
    assert len(out[1].dialogue) == 1 and out[1].characters == ["ROCKY"]


def test_single_turn_and_silent_beats_pass_through_untouched():
    from animatic.core.beat_extractor import Beat, Line, _split_speaker_turns

    solo = Beat(
        beat_id="s4b3", scene=4, beat=3, scene_heading="INT. TROLLEY - NIGHT",
        type="dialogue", content="Rocky explains.", duration_secs=3.0,
        motion_candidate=False, reason="Admission.", characters=["ROCKY"],
        dialogue=[Line("ROCKY", "I'm a fighter.")],
    )
    silent = Beat(
        beat_id="s5b1", scene=5, beat=1, scene_heading="EXT. STREET - NIGHT",
        type="action", content="Rocky walks.", duration_secs=4.0,
        motion_candidate=True, reason="Walk.", characters=["ROCKY"], dialogue=[],
    )
    out = _split_speaker_turns([solo, silent])

    assert out == [solo, silent]
    assert out[1].motion_candidate, "action beats keep their motion flag"


@patch("animatic.core.beat_extractor.genai.Client")
def test_split_beats_are_renumbered_contiguously(mock_client_cls):
    """beat_id/beat must stay dense after a split — Phase 8 keys footage off them."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _make_mock_response(
        json.dumps([
            {
                "beat": 1, "scene_heading": "INT. CLUB - NIGHT", "type": "action",
                "content": "Rocky fights.", "duration_secs": 5.0,
                "motion_candidate": True, "reason": "Fight.", "characters": ["ROCKY"],
                "dialogue": [],
            },
            {
                "beat": 2, "scene_heading": "INT. CLUB - NIGHT", "type": "dialogue",
                "content": "They talk.", "duration_secs": 9.0,
                "motion_candidate": False, "reason": "Corner.",
                "characters": ["CORNERMAN", "ROCKY"],
                "dialogue": [
                    {"character": "CORNERMAN", "line": "Ya movin' like a bum --"},
                    {"character": "ROCKY", "line": "... Just gimme the water."},
                ],
            },
        ])
    )

    from animatic.core.beat_extractor import extract_beats
    beats = extract_beats(2, "INT. CLUB - NIGHT\nStuff.")

    assert [b.beat_id for b in beats] == ["s2b1", "s2b2", "s2b3"]
    assert [b.beat for b in beats] == [1, 2, 3]


def test_split_beat_duration_derives_from_its_own_words():
    """Each turn is timed by what it says, not by a share of the parent."""
    from animatic.core.beat_extractor import _apply_duration_floor, _split_speaker_turns

    out = _split_speaker_turns([_exchange_beat()])
    for b in out:
        _apply_duration_floor(b)

    for b in out:
        assert b.duration_secs == b.min_speakable_secs
        assert b.duration_source == "dialogue_floor"
        assert "derived" in b.reason
    # "Hey --" must not inherit the long line's duration.
    assert out[1].duration_secs < out[0].duration_secs


# ---------------------------------------------------------------------------
# Scene timing from page geometry — one page is one minute
# ---------------------------------------------------------------------------

def test_scene_line_counts_include_blank_lines():
    """Blank lines are the script's own pacing notation and must be counted.

    extract_text() collapses them, so line counts come from character
    positions on the page's 12pt grid instead. Scene 7 is 5 lines top to
    bottom — 3 of text and 2 blank — which is 5/54 of a page.
    """
    from animatic.core.scene_timing import scene_line_counts

    counts = scene_line_counts(PDF_PATH, first_n=8)
    assert counts[7] == 5
    assert set(counts) == {1, 2, 3, 4, 5, 6, 7, 8}


def test_scene_durations_are_one_minute_per_page():
    from animatic.core.scene_timing import scene_targets, secs_for_lines

    assert secs_for_lines(54) == 60.0
    assert secs_for_lines(27) == 30.0

    targets = scene_targets(PDF_PATH, first_n=8)
    assert targets[7] == pytest.approx(5.6, abs=0.1)
    total = sum(targets.values())
    # Scenes 1-8 occupy roughly four script pages.
    assert 230 < total < 280, total


def test_scenes_tile_the_page_without_gaps_or_overlap():
    """Each scene runs heading-to-heading, so line counts are contiguous."""
    from animatic.core.scene_timing import scene_line_counts

    counts = scene_line_counts(PDF_PATH, first_n=8)
    # Scenes 1-8 span pages 2-5 of the PDF; at 54 lines a page that is a
    # little over 4 pages of grid. Every line is claimed exactly once, so the
    # total is the distance from scene 1's heading to scene 9's.
    assert sum(counts.values()) == pytest.approx(230, abs=25)
    assert all(v >= 1 for v in counts.values())


def test_budget_fit_hits_the_target():
    from animatic.core.beat_extractor import Beat, Line, fit_scene_to_budget

    beats = [
        Beat("s4b1", 4, 1, "H", "establishing", "c", 4.0, False, "r"),
        Beat("s4b2", 4, 2, "H", "dialogue", "c", 3.0, False, "r",
             ["ROCKY"], [Line("ROCKY", "I'm a fighter.")]),
        Beat("s4b3", 4, 3, "H", "dialogue", "c", 3.0, False, "r",
             ["WOMAN"], [Line("WOMAN", "... Yo' iz an accident.")]),
    ]
    fit_scene_to_budget(beats, 22.2)

    assert sum(b.duration_secs for b in beats) == pytest.approx(22.2, abs=0.3)
    for b in beats:
        assert b.duration_source == "page_budget"
        assert "page geometry" in b.reason


def test_budget_fit_never_pushes_speech_below_its_floor():
    """Speech is incompressible — a tight budget must not clip a line."""
    from animatic.core.beat_extractor import Beat, Line, fit_scene_to_budget

    long_line = " ".join(["word"] * 40)
    beats = [
        Beat("s1b1", 1, 1, "H", "action", "c", 10.0, False, "r"),
        Beat("s1b2", 1, 2, "H", "dialogue", "c", 5.0, False, "r",
             ["A"], [Line("A", long_line)]),
    ]
    floor = beats[1].min_speakable_secs
    fit_scene_to_budget(beats, 6.0)  # far less than the speech needs

    assert beats[1].duration_secs >= floor
    for b in beats:
        assert b.duration_secs > 0


def test_budget_fit_scales_a_scene_up_as_well_as_down():
    from animatic.core.beat_extractor import Beat, fit_scene_to_budget

    def scene():
        return [Beat(f"s2b{i}", 2, i, "H", "action", "c", 4.0, False, "r")
                for i in range(1, 4)]

    up, down = scene(), scene()
    fit_scene_to_budget(up, 36.0)
    fit_scene_to_budget(down, 6.0)

    assert sum(b.duration_secs for b in up) == pytest.approx(36.0, abs=0.3)
    assert sum(b.duration_secs for b in down) == pytest.approx(6.0, abs=0.3)


# ---------------------------------------------------------------------------
# API endpoint test
# ---------------------------------------------------------------------------

@patch("animatic.api.beats.extract_scenes")
@patch("animatic.api.beats.extract_beats")
@patch("animatic.api.beats.assemble_and_write")
def test_post_beats_parse_returns_200(mock_assemble, mock_extract_beats, mock_extract_scenes):
    mock_extract_scenes.return_value = {1: "INT. TEST - NIGHT\nSome action."}
    mock_extract_beats.return_value = [
        Beat(
            beat_id="s1b1", scene=1, beat=1,
            scene_heading="INT. TEST - NIGHT",
            type="action", content="Fight.", duration_secs=4.0,
            motion_candidate=True, reason="Action beat.", characters=["ROCKY"],
        )
    ]
    mock_assemble.return_value = "s3://animatic-media-628818/beats/latest.json"

    response = client.post("/beats/parse")
    assert response.status_code == 200
    data = response.json()
    assert data["total_beats"] == 1
    assert data["s3_uri"].startswith("s3://")
    assert len(data["scenes"]) == 1
