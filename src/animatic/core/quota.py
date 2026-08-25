"""A local ledger of generation calls, so the UI can price an action.

Google's caps are per model per day — 100 requests, on a rolling window — and
there is no API to ask how many are left. The only way to know is to count what
this project spends.

That matters because of how the caps fail. A run that hits one does not stop
politely: Phase 5's did, and it turned a complete 49-clip index into 39 good
entries and 10 failures. And some actions are far more expensive than they
look — swapping Rocky's model sheet redraws 31 panels, a third of a day's image
budget, from a single click.

So this counts, and the UI shows the count and the price of a button *before*
the button, rather than discovering the wall halfway through.

**It is an estimate, deliberately.** The ledger is local: another machine, a
CLI run, or anything else on the same Google project spends from the same cap
and is invisible here. Reported as a floor on what has been used, never as an
authoritative remaining balance — a number presented as certain and wrong is
worse than one presented as approximate.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LOCAL_LEDGER = Path("output/quota-ledger.json")

# Google's documented per-model cap. Rolling, not midnight-reset: requests age
# out gradually, which is why a probe an hour after a stated 12-hour wait
# succeeded during Phase 5.
DAILY_CAP = 100
WINDOW = timedelta(hours=24)

# What each action costs, for pricing a button before it is pressed.
COST_PER_PANEL = 1
COST_PER_CLIP = 1
COST_PER_MOTION = 1
COST_PER_EDIT = 1


def record(model: str, count: int = 1, path: Path | None = None) -> None:
    """Note `count` calls against `model`."""
    path = LOCAL_LEDGER if path is None else path
    entries = _load(path)
    entries.append(
        {
            "model": model,
            "count": int(count),
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _write(entries, path)


def spent(model: str, path: Path | None = None) -> int:
    """Calls against `model` inside the rolling window, as far as we know."""
    cutoff = datetime.now(timezone.utc) - WINDOW
    total = 0
    for entry in _load(path):
        if entry.get("model") != model:
            continue
        try:
            when = datetime.fromisoformat(entry["at"])
        except (KeyError, ValueError):
            continue
        if when >= cutoff:
            total += int(entry.get("count", 1))
    return total


def budget(models: dict[str, str], path: Path | None = None) -> dict[str, Any]:
    """What is left per model, and the honesty about how well we know it.

    `models` maps a label the UI uses ("panels", "voices") to the model id.
    """
    per_model = {}
    for label, model in models.items():
        used = spent(model, path)
        per_model[label] = {
            "model": model,
            "spent_here": used,
            "cap": DAILY_CAP,
            "remaining_estimate": max(0, DAILY_CAP - used),
        }
    return {
        "window_hours": int(WINDOW.total_seconds() // 3600),
        "models": per_model,
        "is_estimate": True,
        "note": (
            "Counted from this machine only. A CLI run, another machine or "
            "anything else on the same Google project spends from the same cap "
            "and is not visible here, so treat this as a floor on what has been "
            "used rather than a balance."
        ),
    }


def price(panels: int = 0, clips: int = 0, motion: int = 0, edits: int = 0) -> int:
    """What an action will cost in generation calls."""
    return (
        panels * COST_PER_PANEL
        + clips * COST_PER_CLIP
        + motion * COST_PER_MOTION
        + edits * COST_PER_EDIT
    )


def _load(path: Path | None = None) -> list[dict[str, Any]]:
    path = LOCAL_LEDGER if path is None else path
    if not path.exists():
        return []
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        logger.warning("quota ledger at %s is unreadable (%s)", path, exc)
        return []
    return doc.get("calls", [])


def _write(entries: list[dict[str, Any]], path: Path) -> None:
    # Drop anything well outside the window so the file cannot grow forever.
    cutoff = datetime.now(timezone.utc) - WINDOW * 2
    kept = [
        e for e in entries
        if _at(e) is None or _at(e) >= cutoff
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"calls": kept}, indent=2))


def _at(entry: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(entry["at"])
    except (KeyError, ValueError):
        return None
