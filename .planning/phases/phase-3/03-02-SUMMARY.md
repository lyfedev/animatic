---
phase: phase-3
plan: 02
subsystem: assets
tags: [reference-art, filename-token-matching, boto3, s3, content-hash, gemini-3.1-flash-image]

requires:
  - phase: phase-3
    plan: 01
    provides: "slot_resolver.resolve_slots (16 slots), style.STYLE_BLOCK/build_slot_prompt/describe_slot, asset_generator.generate_slot_art (D-12 call shape), asset_manifest.build_manifest/write_manifest/write_slot_art (tracer shape)"
provides:
  - "reference_art.resolve_reference_art(slots, reference_dir) -> ReferenceScan — slot_directory / filename_token matching, mutates matched slots to source='reference'"
  - "reference_art.content_hash_file(path) — chunked sha256, T-03-03"
  - "asset_generator.generate_missing_art(slots, beats, previous_manifest=None, force=False, on_progress=None) — priority-ordered generation loop with reuse and per-group failure isolation"
  - "s3_writer.put_bytes(key, body, content_type) -> S3Result(uri, ok, error) — shared honest S3 writer, T-03-05"
  - "asset_manifest.build_manifest(slots, beats, beats_source=..., unmatched_reference_files=None, previous_manifest=None) — full 16-entry manifest with change detection"
  - "asset_manifest.write_reference_art(slot, source_path) — copies reference bytes into the shared output/S3 tree"
  - "output/assets/manifest.json — real 16-entry manifest, 1 reference-backed + 15 generated-backed, s3_ok=true"
affects: [phase-4-panel-generation, phase-5-audio-synthesis]

actuals:
  tokens: 16831
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "Reference art matched by two mechanisms in priority order — slot_directory (unambiguous, wins outright) then filename_token (token-set-subset match, not substring, so short slot_ids like 'fan' can't swallow an unrelated filename)"
    - "Shared s3_writer.put_bytes(key, body, content_type) -> S3Result centralizes the session/profile handling that beat_assembler and asset_manifest previously duplicated; every S3 write in the codebase now goes through one honest function"
    - "Change detection compares content_hash + source per slot_id against the previous manifest.json on disk — 'newly appeared', 'content_hash changed' and 'source flipped' are the three ways a slot becomes stale, each named in the reason line"
    - "Generation grouped by art_slot_id (not slot_id) so the four minor characters are generated once and the result copied onto all four — reuse and failure are both per-group, not per-slot"

key-files:
  created:
    - src/animatic/core/reference_art.py
    - src/animatic/core/s3_writer.py
  modified:
    - src/animatic/core/asset_generator.py
    - src/animatic/core/asset_manifest.py
    - src/animatic/core/beat_assembler.py
    - scripts/build_assets.py
    - tests/test_asset_manifest.py

key-decisions:
  - "Kept 6e263e8's location-description fix (style.describe_slot grounds LOCATION subject clauses in beat content, not the slot name) and its character-name-only rule unchanged, per explicit instruction — did not revert or 'improve' it"
  - "Added PROJECT.md's no-facial-features rule to character subject clauses as positive prose ('the head is a smooth, unbroken white shape, with hair, hat and jaw described by the same outline work') rather than a negation, consistent with D-09's phrasing rule — this was missing from the post-fix build_assets.py and is a Rule 2 addition (missing correctness requirement)"
  - "generate_missing_art groups by art_slot_id and orders groups by the min priority_rank of their members, so a shared generic slot is generated at the rank of its highest-priority member"
  - "Reuse check compares the previous manifest entry's recorded prompt (not just file existence) and reads the resolved previous art_uri directly, rather than reconstructing a filename — matches CLI usage exactly (two separate script runs) and is what the tests exercise"
  - "write_reference_art leaves source/source_reason/source_files/match_rule untouched (Task 1's job) and only handles the mechanical copy+hash+upload — keeps Task 1's matching reason distinct from Task 3's write outcome"
  - "beat_assembler._write_s3 keeps its exact return contract (real s3:// URI or local:// marker) after the s3_writer refactor, only the log level changed WARNING->ERROR, so Phase 2's API/CLI needed no changes and its test suite stayed green untouched"

patterns-established:
  - "A manifest's own top-level fields (beats_source, beats_generated_at) tie it back to the exact beat list it was built from, extending Phase 2's 'value plus the rule that produced it' precedent to cross-artifact provenance"

requirements-completed: [FR-02, NFR-03, NFR-04]

coverage:
  - id: D1
    description: "resolve_reference_art matches assets/reference-art/'s 4 supplied files: rocky resolves to source 'reference' with all 3 rocky-named files (filename_token), boxing_poses.jpeg is recorded in unmatched with a reason, and a slot_directory match wins over a filename_token match for the same slot"
    requirement: "FR-02"
    verification:
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_reference_art_takes_priority"
        status: pass
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_unmatched_reference_file_is_recorded"
        status: pass
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_slot_directory_beats_filename_token"
        status: pass
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_content_hash_changes_on_file_replace"
        status: pass
      - kind: integration
        ref: "python scripts/build_assets.py — real run, rocky.jpg confirmed uploaded via aws s3api head-object"
        status: pass
    human_judgment: false
  - id: D2
    description: "generate_missing_art fills all 16 slots with art when reference art is absent (13 distinct files), shares one file across the 4 minor characters, generates in priority_rank order, reuses existing art on an unchanged prompt without a second API call, and isolates one group's failure from the rest"
    requirement: "FR-02"
    verification:
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_manifest_complete_with_no_reference_art"
        status: pass
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_minor_characters_share_one_art_file"
        status: pass
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_generation_order_follows_priority"
        status: pass
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_existing_art_is_reused_without_a_second_call"
        status: pass
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_one_slot_failure_does_not_abort_the_run"
        status: pass
      - kind: integration
        ref: "python scripts/build_assets.py — real run, 12 real gemini-3.1-flash-image calls, 12 distinct files with rocky reference-backed"
        status: pass
    human_judgment: false
  - id: D3
    description: "build_manifest returns 16 fully-shaped entries with non-empty reason fields; re-running with no changes yields stale_beat_ids == []; replacing one slot's art (or flipping generated<->reference) marks exactly that slot's beat_ids stale; a failed S3 put is recorded honestly, never as a local:// success"
    requirement: "NFR-04"
    verification:
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_manifest_entry_shape"
        status: pass
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_all_slots_have_nonempty_reason"
        status: pass
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_rerun_with_no_changes_has_no_stale_beats"
        status: pass
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_replacing_slot_art_marks_its_beats_stale"
        status: pass
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_reference_file_appearing_flips_source_and_marks_stale"
        status: pass
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_s3_failure_is_recorded_not_hidden"
        status: pass
      - kind: integration
        ref: "python scripts/build_assets.py run twice in a row, then a manual byte-swap of generic_minor_character.jpg — real manifest showed stale_beat_ids == [] on the unchanged rerun and exactly the 4 minor characters' 5 beat_ids stale after the swap"
        status: pass
    human_judgment: false
  - id: D4
    description: "Generated art visually matches D-09 (flat black-on-white linework, no chrome, no drawn-in text) on most slots; PROJECT.md's no-facial-features rule was violated on 2 of 6 spot-checked images (generic_minor_character, promoter both drew a detailed face) and one location (ext_street) drew a person despite the peopleless-view instruction"
    verification:
      - kind: manual_procedural
        ref: "output/assets/generated/*.jpg — 6 of 13 files visually inspected"
        status: fail
    human_judgment: true
    rationale: "Image content is a visual judgment call; generation is non-deterministic (no seed parameter in the D-12 call shape) and the task's own instructions direct not to block the wave on art-quality iteration — the compliance gaps found are documented as Known Stubs below rather than fixed by burning additional real API calls."

duration: 62min
completed: 2026-08-24
status: complete
---

# Phase 3 Plan 02: Reference Art Priority, Full Generation, and an Honest Manifest Summary

**Reference art (rocky) now wins over generation via slot-directory/filename-token matching; the remaining 15 slots get real gemini-3.1-flash-image art through a priority-ordered, reuse-aware, failure-isolated loop; and the manifest gained change detection plus a shared s3_writer that never reports a failed S3 write as success**

## Performance

- **Duration:** 62 min
- **Started:** 2026-08-24T23:XX (worktree setup + FF-merge onto Wave 1's tip)
- **Completed:** 2026-08-25T00:34Z
- **Tasks:** 3 (all `tdd="true"`, RED then GREEN each)
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments
- `reference_art.resolve_reference_art` matches `assets/reference-art/`'s 4 supplied files against the 16-slot registry: `rocky` resolves to `source="reference"` with all 3 rocky-named files (`filename_token`), `boxing_poses.jpeg` is recorded in `unmatched_reference_files` with a reason instead of being silently dropped (NFR-04), and a `slot_directory` match is proven to win over a `filename_token` match for the same slot
- `asset_generator.generate_missing_art` fills every slot without reference art: grouped by `art_slot_id` (the 4 minor characters share `generic_minor_character`) and generated in `priority_rank` order (D-10/D-11) — real run produced **12 distinct art files** (7 locations, 4 bespoke characters, 1 generic minor; rocky excluded as reference-backed), matching the plan's exact "15 slots generated-backed, 12 distinct art files" spec
- Reuse works end to end: a second real run of `scripts/build_assets.py` reused all 12 previously-generated files (0 new API calls, 3.4s total vs. 127.5s for the first real run) because each group's prompt matched the previous manifest's recorded prompt
- `s3_writer.put_bytes` centralizes the S3 session/profile handling that `beat_assembler` and `asset_manifest` used to duplicate, and both now route through it — `beat_assembler._write_s3` keeps its exact `s3://...`/`local://...` return contract (Phase 2's API/CLI untouched) but logs failure at ERROR instead of WARNING (T-03-05)
- Change detection (ROADMAP criterion 4) was verified against the **real** manifest, not just mocks: replacing `generic_minor_character.jpg`'s bytes and re-running marked exactly the 4 minor characters' 5 beat_ids (`s2b11, s2b18, s3b2, s3b3, s3b4`) stale and nothing else; restoring the bytes and re-running twice settled back to `stale_beat_ids == []`
- Real S3 confirmed via `aws s3api head-object`: `s3://animatic-media-628818/assets/art/rocky.jpg` exists with the correct content-length and `ServerSideEncryption: AES256`

## Task Commits

Each task carried `tdd="true"` — RED then GREEN:

1. **Task 1: Ingest supplied reference art and give it priority over generation** — `3bf9ed2` (test — RED), `23e62ca` (feat — GREEN)
2. **Task 2: Generate temp art for every slot that has none** — `471e5e7` (test — RED), `4245b84` (feat — GREEN)
3. **Task 3: Manifest assembly, change detection, and an honest S3 write** — `bc1ef85` (test — RED), `73cb80a` (feat — GREEN)

_All GREEN implementations passed on the first attempt after RED (aside from one self-caught test-expectation bug in `test_manifest_entry_shape`, fixed before commit — see Deviations) — no separate REFACTOR commit was needed for any task._

## Files Created/Modified
- `src/animatic/core/reference_art.py` (new) — `resolve_reference_art`, `content_hash_file`, `ReferenceScan`; slot_directory then filename_token matching, mutates matched slots in place
- `src/animatic/core/s3_writer.py` (new) — `put_bytes`/`S3Result`; the one place in the codebase that talks to `boto3.Session`/`put_object`
- `src/animatic/core/asset_generator.py` — `generate_missing_art`, `_subject_note`, `_reuse_art`; priority-grouped generation loop with reuse and per-group failure isolation
- `src/animatic/core/asset_manifest.py` — `build_manifest` gained `beats`/`beats_source`/`unmatched_reference_files`/`previous_manifest`; `_detect_changes` (change detection); `write_reference_art`; `write_manifest`/`write_slot_art` now route through `s3_writer.put_bytes`
- `src/animatic/core/beat_assembler.py` — `_write_s3` refactored to call `s3_writer.put_bytes`; same return contract, ERROR-level logging
- `scripts/build_assets.py` — added `--force`/`--reference-dir`; 4-step pipeline (resolve → ingest reference → generate → write manifest); loads the previous manifest for reuse + change detection
- `tests/test_asset_manifest.py` — 16 new tests (Tasks 1–3) plus 3 existing tests updated for the new `build_manifest` signature and the `s3_writer` patch target

## Decisions Made
- Kept 6e263e8's fix (location subject clauses grounded in beat content via `style.describe_slot`; characters keep their name, not a beat description) exactly as instructed — did not revert or alter it
- Added PROJECT.md's "no facial features" rule to character subject clauses as positive prose (a smooth, unbroken white head-shape) — this was the one piece of the pre-existing character prompt that hadn't yet incorporated that rule; added as a Rule 2 (missing correctness requirement) fix, not a plan deviation, since Task 2's own action text calls for it
- `generate_missing_art` orders `art_slot_id` groups by the **minimum** `priority_rank` among their members, so a shared generic slot is generated at its highest-priority member's rank
- Reuse compares the previous manifest's recorded `prompt` string, not just file mtime/existence — matches two-separate-script-runs CLI usage exactly, which is what both the unit test and the real second run exercised
- `write_reference_art` deliberately does not touch `source`/`source_reason`/`source_files`/`match_rule` (Task 1's fields) — it only performs the mechanical copy+hash+upload, keeping "how we matched it" and "where the bytes ended up" as separate concerns

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Bespoke/generic character subject clauses didn't state PROJECT.md's no-facial-features rule**
- **Found during:** Task 2 (writing `_subject_note`)
- **Issue:** The pre-existing `build_assets.py::_subject_note` (from commit 6e263e8) grounded character subjects in the display name only, with no mention of PROJECT.md §Visual Style's "no facial features in wide/medium shots" rule — a correctness requirement the plan's own Task 2 action text calls for ("PROJECT.md §Visual Style governs the head... a reference sheet is a full figure, so the face carries no features")
- **Fix:** Added positive-prose wording ("The head is a smooth, unbroken white shape, with hair, hat and jaw described by the same outline work as the rest of the figure") to both the bespoke-character and generic-minor-character subject clauses in `asset_generator._subject_note`, following D-09's rule of stating constraints as positive prose rather than negation
- **Files modified:** `src/animatic/core/asset_generator.py`
- **Verification:** Visual inspection of generated art — `black_fighter.jpg` and `woman.jpg` show a correctly blank head-shape; see Known Stubs below for the 2 slots where the model didn't comply despite the instruction
- **Committed in:** `4245b84` (Task 2 GREEN commit)

**2. [Rule 1 - Bug] `test_manifest_entry_shape`'s own expectation was wrong for a first-run manifest**
- **Found during:** Task 3 GREEN — first pytest run after implementing `build_manifest`
- **Issue:** The test asserted `manifest["stale_beat_ids"] == []` for a `build_manifest` call with no `previous_manifest` — but "newly appeared" is correctly treated as a change (a first run has nothing to compare against, so every slot's beats are, correctly, reported as needing a first render)
- **Fix:** Corrected the assertion to expect both beat_ids as stale on a from-scratch manifest, matching the documented `_detect_changes` semantics
- **Files modified:** `tests/test_asset_manifest.py`
- **Verification:** Full suite green after the fix (80/80)
- **Committed in:** `73cb80a` (Task 3 GREEN commit — fixed before the commit was made, not a follow-up)

---

**Total deviations:** 2 (1 Rule 2 — missing correctness requirement per the plan's own action text; 1 Rule 1 — a self-authored test bug caught before commit)
**Impact on plan:** Both fixes stayed within the declared task scope. No architectural changes, no scope creep.

## Issues Encountered
- **Worktree was stale relative to Wave 1.** The worktree's branch HEAD (`2313e69`) predated all of Phase 3, including 03-01's merge and the critical `6e263e8` location-description fix the task explicitly said to preserve. Fast-forward merged the worktree branch onto `feat/phase-3-asset-management`'s tip (`6e263e8`) before starting — a clean, no-conflict fast-forward since the worktree branch had no commits of its own beyond that ancestor.
- **Worktree was missing `.env`, `.venv`, `output/beats.json`, `output/smoke/`** (gitignored/generated, not restorable via git checkout). Copied `.env`, symlinked `.venv`, and copied `output/beats.json`/`output/smoke/` from the primary checkout at `/Volumes/VM3/vockelldev/cinemachallenge/animatic` without printing contents. `docs/` and `assets/reference-art/` were already present via the fast-forward merge (they're tracked files, not gitignored).
- **Image generation is non-deterministic** (no seed parameter, per D-12's known call shape) — 2 of 13 generated art files did not fully comply with PROJECT.md's no-facial-features rule despite the positive-prose instruction, and one location drew a person despite an explicit peopleless-view instruction. Per the task's explicit "do not block waiting for human approval on art quality — generate, save, report paths" instruction, these were not iterated further; documented below instead. This mirrors 03-01's own documented experience with the same underlying non-determinism.

## Known Stubs

None of the 16 slots are unfilled or empty — every slot has real art, a real hash, and (for rocky) a real S3-uploaded reference copy. The following are **visual quality gaps**, not missing/stub data, found during spot-check of 6 of 13 generated files:

- `output/assets/generated/generic_minor_character.jpg` — drew a detailed face (eyes, brow, hairline) rather than the instructed blank white head-shape. Affects `announcer`, `fan`, `fighter_1`, `fighter_2` (all share this art_slot_id).
- `output/assets/generated/promoter.jpg` — drew a detailed face (open mouth, eyebrows) rather than the instructed blank white head-shape.
- `output/assets/generated/ext_street.jpg` — otherwise a clean, peopleless establishing view, but drew one small sleeping figure on the sidewalk despite the "no people present anywhere in the shot" instruction.

Compliant on inspection: `int_blue_door_fight_club.jpg`, `black_fighter.jpg`, `woman.jpg` (all correctly blank-headed / peopleless / text-free). Not individually re-inspected: the remaining 7 files (`int_dressing_room`, `int_trolley`, `ext_rockys_apartment`, `int_rockys_hallway`, `int_rockys_apartment`, `cornerman`, plus `rocky.jpg` which is supplied reference art, not generated). A future pass (Phase 4 kickoff or a dedicated art-QA pass) can regenerate `generic_minor_character` and `promoter` with `--force` if stricter visual compliance is required before panel generation begins; this plan's own success criteria (slot filling, priority, source/reason, S3 honesty) do not depend on it.

## Threat Flags

None — all 6 threat-register entries from the plan's `<threat_model>` (T-03-01, T-03-02, T-03-03, T-03-05, T-03-06, T-03-SC) were implemented as specified: reference-art write paths built from `Path(name).name` plus the resolver's own slot_id (never a raw scanned filename), the API key read only via `settings.google_api_key` and never logged, `content_hash_file` chunked-reads reference art, `s3_writer.put_bytes` returns an explicit `ok`/`error` and never fabricates success, generation is capped at the 13 distinct art slots with reuse-unless-`--force`, and no new package-manager installs occurred.

## User Setup Required

None — no external service configuration required. `GOOGLE_API_KEY` and the `newaccount` AWS profile were already configured (per `.planning/STATE.md`'s Google AI Access smoke test and Wave 1's setup).

## Next Phase Readiness
- `reference_art.resolve_reference_art`, `asset_generator.generate_missing_art`, `s3_writer.put_bytes`, and `asset_manifest.build_manifest`/`write_manifest`/`write_reference_art` are the fixed interface this plan adds on top of 03-01's `slot_resolver`/`style`/`asset_generator.generate_slot_art` — all consumable by 03-03 and Phase 4/5 without further changes.
- `output/assets/manifest.json` on disk is a real, complete, 16-entry manifest (1 reference-backed, 15 generated-backed, `s3_ok: true`) — Phase 4 can read it directly for panel-generation prompts and `stale_beat_ids` for cache invalidation.
- Known gap for a future pass (not blocking): `generic_minor_character.jpg` and `promoter.jpg` show facial detail beyond PROJECT.md's rule; `ext_street.jpg` shows one figure in a location meant to be peopleless. Regenerate with `python scripts/build_assets.py --force --only <slot_id>` if stricter compliance is needed before Phase 4 begins consuming these images.
- No blockers.

## Self-Check: PASSED

All 7 modified/created files confirmed present on disk. All 6 task commits confirmed present via `git log --oneline`: `3bf9ed2`, `23e62ca`, `471e5e7`, `4245b84`, `bc1ef85`, `73cb80a`. Full test suite: 80/80 passing (`PYTHONPATH=src .venv/bin/python -m pytest tests/ -q`), up from 65 at plan start.

---
*Phase: phase-3*
*Completed: 2026-08-24*
