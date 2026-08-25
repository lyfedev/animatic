"""Which beats get motion, and why every other beat does not.

PROJECT.md's rule is "motion generation is cost-constrained — most beats are
stills". That makes selection the substance of this phase, not the generation:
a Veo call costs roughly a minute of wall clock and counts against a per-model
daily cap, so the question is which handful of beats earn one.

Three things this module owns, matching ROADMAP criteria 1, 2 and 3:

- motion goes to no more than the budgeted number of beats
- **every beat** carries motion true/false and a reason, not just the winners.
  A beat that did not get motion because it ranked twelfth is a different fact
  from a beat that was never eligible, and the index says which.
- action beats outrank dialogue, which outranks establishing

Ranking is deterministic. Within a type, a longer beat wins — motion reads on
screen in proportion to how long it is held, so eight seconds of movement is
worth more than three. Ties break on beat_id so two runs of the same beat list
always choose the same shots.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# The default budget. PROJECT.md says most beats are stills and does not put a
# number on it; 4 of 49 is 8%, which matches the `motion_candidate` flag the
# beat parser already sets and keeps a full run inside one Veo sitting.
DEFAULT_BUDGET = 4

# Higher wins. Straight from ROADMAP criterion 3.
_TYPE_RANK = {"action": 3, "dialogue": 2, "establishing": 1}
_UNKNOWN_TYPE_RANK = 0


@dataclass(frozen=True)
class MotionChoice:
    """One beat's motion decision, with the reason it was made."""

    beat_id: str
    scene: int
    beat: int
    motion: bool
    reason: str
    rank: int


def select_for_motion(
    beats: list[dict[str, Any]],
    budget: int = DEFAULT_BUDGET,
    only: str | None = None,
) -> list[MotionChoice]:
    """Decide motion for every beat in the list.

    Returns one MotionChoice per beat, in beat order — never only the selected
    ones. Criterion 2 is about the whole beat list.
    """
    # `motion_candidate` outranks everything else, because it is the only
    # signal here that is about whether the beat CONTAINS movement rather than
    # about what category it falls in. Phase 2 set it per beat while reading
    # the scene; ranking purely on type and length ignored that judgement and
    # put all four clips inside scene 2, dropping s8b6 ("shifts abruptly from
    # singing into a bullish fighting stance and throws a right cross") in
    # favour of a longer beat that is mostly a held reaction.
    ranked = sorted(
        beats,
        key=lambda b: (
            not b.get("motion_candidate", False),
            -_TYPE_RANK.get(b.get("type", ""), _UNKNOWN_TYPE_RANK),
            -float(b.get("duration_secs", 0)),
            b["beat_id"],
        ),
    )

    chosen = {b["beat_id"] for b in ranked[:max(0, budget)]}
    if only is not None:
        # An explicit single-beat request overrides the ranking but not the
        # accounting: the index still records why every other beat is a still.
        chosen = {only}

    total = len(beats)
    choices = []
    for position, beat in enumerate(ranked, start=1):
        picked = beat["beat_id"] in chosen
        choices.append(
            MotionChoice(
                beat_id=beat["beat_id"],
                scene=beat["scene"],
                beat=beat["beat"],
                motion=picked,
                rank=position,
                reason=_reason(beat, position, picked, budget, total, only),
            )
        )

    return sorted(choices, key=lambda c: (c.scene, c.beat))


def _reason(
    beat: dict[str, Any],
    position: int,
    picked: bool,
    budget: int,
    total: int,
    only: str | None,
) -> str:
    """The machine-readable justification NFR-04 requires, for both outcomes."""
    beat_type = beat.get("type", "unknown")
    secs = beat.get("duration_secs", 0)

    if only is not None:
        if picked:
            return f"explicitly requested with --only {only}"
        return (
            f"not requested — this run selected only {only}; ranked "
            f"{position} of {total} ({beat_type}, {secs}s)"
        )

    flagged = "flagged a motion candidate by the beat parser" if beat.get(
        "motion_candidate"
    ) else "not flagged a motion candidate"

    if picked:
        return (
            f"rank {position} of {total} within a budget of {budget}: "
            f"{beat_type} beat, {secs}s, {flagged} — a flagged beat outranks "
            f"an unflagged one, action outranks dialogue outranks "
            f"establishing, and a longer beat outranks a shorter one"
        )
    return (
        f"still — ranked {position} of {total}, outside the budget of "
        f"{budget} ({beat_type} beat, {secs}s, {flagged})"
    )
