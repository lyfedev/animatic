"""Motion prompts — animate the panel, do not redraw it.

Phase 6 seeds Veo with the beat's existing panel rather than generating from
text alone. That is the whole design: a text-only clip would be a NEW picture
competing with art the developer has already reviewed, and the style, the
framing and the facial rule would all have to be re-won. Seeded, the clip is a
continuation of the panel.

**The first live clip proved the seed is not enough.** `s2b2`'s panel carries
one mouth line and no eyes; the 8-second clip generated from it came back with
a full eye — iris and pupil — an eyebrow, and a broadened grin. Veo drifts
toward a conventional cartoon face given half a chance, exactly as the image
model did across Phase 4's two revision passes.

So the clauses Phase 4 paid for are reused here verbatim, under the same three
rules that made them work:

- state the rule as positive prose, never a negation — a negation gets
  rendered ("NO FACIALS" was once painted into a frame)
- put the rule that matters LAST, because a rule stated mid-prompt loses to
  whatever follows it
- name no object that is not wanted in the picture, including as an absence —
  naming "the eyes" as absent drew a fully rendered eye anyway

One rule is new, and it is the one this phase owns: **the clip may move, but
it may not invent.** The first clip grew a crowd that was not in the panel
between second one and second three. A shot whose background changes mid-take
does not read as an animatic of that panel; it reads as a different shot.
"""

from __future__ import annotations

from typing import Any

from animatic.core.panel_prompt import (
    _BLANK_FACE_CLAUSE,
    _BLANK_ROOM_CLAUSE,
    _CLOSEUP_FACE_CLAUSE,
    shot_size_for,
)

MOTION_PROMPT_VERSION = "v1"

# Leads the prompt: what this clip IS, before anything about what moves.
_CONTINUATION_CLAUSE = (
    "This is the supplied drawing, brought to life as it already stands. "
    "Every line keeps the same black weight on the same white ground, every "
    "figure keeps the same build, hair and clothing, and the camera holds "
    "exactly where it is — no push in, no pan, no cut."
)

# The rule this phase adds. Stated as what the frame HOLDS rather than as a
# list of things not to add, per D-07.
_NO_INVENTION_CLAUSE = (
    "The room stays exactly as populated as the drawing shows it: the same "
    "figures, the same furniture, the same fittings, present from the first "
    "frame to the last and unchanged in number throughout."
)


def motion_description(beat: dict[str, Any]) -> str:
    """What moves, taken from the beat's own action line.

    Nothing here knows anything about boxing. A different script yields a
    different description because the description IS the beat's content.
    """
    action = beat["content"].rstrip(".")
    return f"Within that held frame, this is what moves: {action}."


def build_motion_prompt(beat: dict[str, Any]) -> str:
    """Assemble the full prompt for one beat's motion clip.

    Order is deliberate and matches D-06's finding: the facial rule lands
    LAST, after the room rule, because it is the rule that fails first when
    something follows it.
    """
    # `shot_size_for` returns (size, reason) — comparing the tuple to a string
    # is silently always false, which handed every close-up the wide/medium
    # clause. The three clips generated before this was caught are all action
    # beats (medium), so their clause was right by accident, not by logic.
    shot_size, _ = shot_size_for(beat)
    facial = _CLOSEUP_FACE_CLAUSE if shot_size == "close-up" else _BLANK_FACE_CLAUSE

    return "\n\n".join(
        [
            _CONTINUATION_CLAUSE,
            motion_description(beat),
            _NO_INVENTION_CLAUSE,
            _BLANK_ROOM_CLAUSE,
            facial,
        ]
    )
