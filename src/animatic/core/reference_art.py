"""Reference art ingestion (D-01, ROADMAP criterion 3).

Matches supplied files under `assets/reference-art/` to resolved slots and
gives them priority over generated art — `resolve_reference_art` mutates
matched slots' `source` to "reference" in place, and Task 2's generation
loop skips any art_slot_id already resolved that way, so a slot with
reference art is never passed to the image model.

FR-02 asks for reference art "in named slots", and D-01 forbids a
hand-curated alias list — the system makes its best guess and records how
it guessed. Two mechanisms, in this priority order:

1. Slot directory — `assets/reference-art/<slot_id>/` holds art for that
   slot explicitly. This is the named-slot interface FR-02 describes and it
   is unambiguous, so it wins outright (match_rule "slot_directory").
2. Filename token — for flat files directly under the reference directory,
   every token of the slot_id (split on "_"/"-") must appear among the
   filename stem's own tokens. Token equality rather than bare substring
   matching, so a short slot_id such as "fan" cannot swallow an unrelated
   filename (match_rule "filename_token").

A file that matches no slot by either mechanism is recorded in
`ReferenceScan.unmatched` with a reason, so a mis-named file is visible
rather than silently ignored (NFR-04) — `boxing_poses.jpeg` is the live
example among this project's four supplied files.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from animatic.core.slot_resolver import Slot

_CHUNK_SIZE = 65536
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class ReferenceScan:
    """Result of matching `assets/reference-art/` against a slot list.

    The matched slots themselves are mutated in place by
    `resolve_reference_art` (source/source_files/match_rule/source_reason/
    art_uri/content_hash); this dataclass carries the bookkeeping that has
    no single slot to live on: which slot_ids matched, and which files
    matched nothing.
    """

    matched_slot_ids: list[str] = field(default_factory=list)
    unmatched: list[dict[str, str]] = field(default_factory=list)


def content_hash_file(path: Path) -> str:
    """sha256 hex digest of `path`, streamed in chunks (T-03-03).

    Never reads the whole file into memory — a chunked
    `hashlib.sha256().update()` loop instead.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _tokenize(stem: str) -> set[str]:
    return set(_TOKEN_RE.findall(stem.lower()))


def resolve_reference_art(slots: list[Slot], reference_dir: Path | str) -> ReferenceScan:
    """Match files under `reference_dir` against `slots`.

    Mutates every matched slot's `source` ("reference"), `source_files`
    (sorted, as given by the caller — repository-relative when
    `reference_dir` itself is repository-relative), `match_rule`,
    `source_reason`, `art_uri` (the active file — first in sorted order)
    and `content_hash` (of that active file) in place. The remaining files
    for a matched slot stay in `source_files` for Phase 4, which can
    condition on several reference images at once.

    An empty or missing `reference_dir` resolves nothing and raises
    nothing — FR-02's "never block on a missing input" applies to the
    reference directory itself, not just to individual files within it.
    """
    reference_dir = Path(reference_dir)
    scan = ReferenceScan()
    if not reference_dir.is_dir():
        return scan

    slot_by_id = {s.slot_id: s for s in slots}

    # Pass 1 — slot directories win outright; unambiguous by construction.
    dir_matched: set[str] = set()
    for entry in sorted(reference_dir.iterdir()):
        if not entry.is_dir() or entry.name not in slot_by_id:
            continue
        files = sorted(p for p in entry.iterdir() if p.is_file())
        if not files:
            continue
        _apply_match(
            slot_by_id[entry.name],
            files,
            match_rule="slot_directory",
            source_reason=(
                f"{len(files)} file(s) in assets/reference-art/{entry.name}/ "
                f"matched slot {entry.name!r} by slot directory — reference "
                f"art takes priority over generation"
            ),
        )
        scan.matched_slot_ids.append(entry.name)
        dir_matched.add(entry.name)

    # Pass 2 — flat files directly under reference_dir, filename-token match.
    slot_tokens = {sid: _tokenize(sid) for sid in slot_by_id}
    by_slot: dict[str, list[Path]] = {}
    for entry in sorted(reference_dir.iterdir()):
        if not entry.is_file():
            continue
        file_tokens = _tokenize(entry.stem)
        matched = [
            sid
            for sid, tokens in slot_tokens.items()
            if tokens and tokens.issubset(file_tokens)
        ]
        if len(matched) == 1:
            by_slot.setdefault(matched[0], []).append(entry)
        elif not matched:
            scan.unmatched.append(
                {
                    "path": str(entry),
                    "reason": (
                        "no slot_id's tokens are a subset of this "
                        "filename's tokens"
                    ),
                }
            )
        else:
            scan.unmatched.append(
                {
                    "path": str(entry),
                    "reason": (
                        f"filename tokens matched multiple slots "
                        f"{sorted(matched)} — ambiguous, left unresolved"
                    ),
                }
            )

    for sid, files in by_slot.items():
        if sid in dir_matched:
            continue
        files = sorted(files)
        _apply_match(
            slot_by_id[sid],
            files,
            match_rule="filename_token",
            source_reason=(
                f"{len(files)} file(s) matched slot {sid!r} on filename "
                f"tokens ({', '.join(f.stem for f in files)}) — reference "
                f"art takes priority over generation"
            ),
        )
        scan.matched_slot_ids.append(sid)

    return scan


def _apply_match(
    slot: Slot, files: list[Path], match_rule: str, source_reason: str
) -> None:
    sorted_files = sorted(str(f) for f in files)
    active = Path(sorted_files[0])
    slot.source = "reference"
    slot.source_files = sorted_files
    slot.match_rule = match_rule
    slot.source_reason = source_reason
    slot.art_uri = str(active)
    slot.content_hash = content_hash_file(active)
