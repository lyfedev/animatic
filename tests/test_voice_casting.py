"""Tests for casting — the guard, not the model.

The model's taste is not testable here. What is testable is the contract the
guard enforces on whatever the model returns, which is what ROADMAP criterion
2 ("a consistent voice per character") actually rests on.
"""

from __future__ import annotations

import pytest

from animatic.core.voice_casting import (
    GEMINI_VOICES,
    NARRATOR_VOICE,
    VoiceCastingError,
    _enforce_distinct,
    _hash_voice,
    build_casting_prompt,
    character_profiles,
)

BEATS = [
    {
        "beat_id": "s2b5",
        "scene": 2,
        "scene_heading": "INT. BOXING CLUB - NIGHT",
        "content": "The fighter sneers.",
        "dialogue": [{"character": "BLACK FIGHTER", "line": "I'm gonna bust his head."}],
    },
    {
        "beat_id": "s2b7",
        "scene": 2,
        "scene_heading": "INT. BOXING CLUB - NIGHT",
        "content": "Rocky answers.",
        "dialogue": [{"character": "ROCKY", "line": "Absolutely."}],
    },
    {
        "beat_id": "s3b2",
        "scene": 3,
        "scene_heading": "INT. DRESSING ROOM - NIGHT",
        "content": "Rocky again.",
        "dialogue": [{"character": "ROCKY", "line": "Just gimme the water."}],
    },
    {
        "beat_id": "s1b1",
        "scene": 1,
        "scene_heading": "INT. CLUB - NIGHT",
        "content": "Establishing.",
        "dialogue": [],
    },
]


def _profiles():
    return character_profiles(BEATS)


class TestCharacterProfiles:
    def test_only_speaking_parts_are_profiled(self):
        assert {p["character"] for p in _profiles()} == {"BLACK FIGHTER", "ROCKY"}

    def test_a_character_accumulates_every_line_and_scene(self):
        rocky = next(p for p in _profiles() if p["character"] == "ROCKY")
        assert rocky["lines"] == ["Absolutely.", "Just gimme the water."]
        assert rocky["scene_headings"] == [
            "INT. BOXING CLUB - NIGHT",
            "INT. DRESSING ROOM - NIGHT",
        ]

    def test_order_is_first_appearance(self):
        assert [p["character"] for p in _profiles()] == ["BLACK FIGHTER", "ROCKY"]


class TestCastingPrompt:
    def test_the_prompt_carries_the_evidence(self):
        prompt = build_casting_prompt(_profiles())
        assert "ROCKY" in prompt
        assert "Just gimme the water." in prompt
        assert "INT. DRESSING ROOM - NIGHT" in prompt

    def test_the_narrator_voice_is_not_offered(self):
        prompt = build_casting_prompt(_profiles())
        pool = prompt.split("Available voices:")[1].split("\n")[0]
        assert NARRATOR_VOICE not in pool

    def test_the_prompt_never_names_the_film(self):
        # Casting must work from the page, not from what the model remembers.
        prompt = build_casting_prompt(_profiles()).lower()
        assert "rocky-1976" not in prompt
        assert "screenplay of" not in prompt


class TestEnforceDistinct:
    def test_a_clean_proposal_is_left_alone(self):
        proposed = {
            "BLACK FIGHTER": {"voice": "Fenrir", "reason": "gravelly"},
            "ROCKY": {"voice": "Iapetus", "reason": "warm"},
        }
        cast = _enforce_distinct(_profiles(), proposed)
        assert cast["ROCKY"]["voice"] == "Iapetus"
        assert cast["ROCKY"]["reason"] == "warm"

    def test_two_characters_never_share_a_voice(self):
        proposed = {
            "BLACK FIGHTER": {"voice": "Fenrir", "reason": "a"},
            "ROCKY": {"voice": "Fenrir", "reason": "b"},
        }
        cast = _enforce_distinct(_profiles(), proposed)
        assert cast["BLACK FIGHTER"]["voice"] != cast["ROCKY"]["voice"]
        assert "already cast to BLACK FIGHTER" in cast["ROCKY"]["reason"]

    def test_the_first_to_appear_keeps_the_contested_voice(self):
        proposed = {
            "BLACK FIGHTER": {"voice": "Fenrir", "reason": "a"},
            "ROCKY": {"voice": "Fenrir", "reason": "b"},
        }
        cast = _enforce_distinct(_profiles(), proposed)
        assert cast["BLACK FIGHTER"]["voice"] == "Fenrir"

    def test_the_narrator_voice_is_taken_back(self):
        proposed = {
            "BLACK FIGHTER": {"voice": NARRATOR_VOICE, "reason": "a"},
            "ROCKY": {"voice": "Iapetus", "reason": "b"},
        }
        cast = _enforce_distinct(_profiles(), proposed)
        assert cast["BLACK FIGHTER"]["voice"] != NARRATOR_VOICE
        assert "reserved for narration" in cast["BLACK FIGHTER"]["reason"]

    def test_an_invented_voice_name_is_replaced(self):
        proposed = {
            "BLACK FIGHTER": {"voice": "Gandalf", "reason": "a"},
            "ROCKY": {"voice": "Iapetus", "reason": "b"},
        }
        cast = _enforce_distinct(_profiles(), proposed)
        assert cast["BLACK FIGHTER"]["voice"] in GEMINI_VOICES
        assert "not an available voice" in cast["BLACK FIGHTER"]["reason"]

    def test_a_character_the_model_skipped_is_still_cast(self):
        cast = _enforce_distinct(_profiles(), {"ROCKY": {"voice": "Iapetus", "reason": "b"}})
        assert cast["BLACK FIGHTER"]["voice"] in GEMINI_VOICES
        assert "no cast for this part" in cast["BLACK FIGHTER"]["reason"]

    def test_a_total_model_failure_still_casts_everyone(self):
        cast = _enforce_distinct(_profiles(), {})
        assert set(cast) == {"BLACK FIGHTER", "ROCKY"}
        assert len({c["voice"] for c in cast.values()}) == 2

    def test_every_entry_explains_itself(self):
        # NFR-04: every generated artifact carries a machine-readable reason.
        cast = _enforce_distinct(_profiles(), {})
        assert all(c["reason"].strip() for c in cast.values())


class TestHashFallback:
    def test_it_is_stable_across_calls(self):
        assert _hash_voice("PROMOTER", set()) == _hash_voice("PROMOTER", set())

    def test_it_never_returns_the_narrator_voice(self):
        names = [f"CHARACTER {i}" for i in range(200)]
        assert all(_hash_voice(n, set()) != NARRATOR_VOICE for n in names)

    def test_it_avoids_voices_already_taken(self):
        first = _hash_voice("PROMOTER", set())
        assert _hash_voice("PROMOTER", {first}) != first

    def test_adding_a_character_does_not_reshuffle_the_others(self):
        # An index-ordered cast would move everyone when a part is added.
        before = _hash_voice("ROCKY", set())
        after = _hash_voice("ROCKY", {_hash_voice("NEW GUY", set())})
        assert before == after or before == _hash_voice("NEW GUY", set())

    def test_running_out_of_voices_is_an_error_not_a_collision(self):
        taken = set(GEMINI_VOICES)
        with pytest.raises(VoiceCastingError):
            _hash_voice("ONE TOO MANY", taken)
