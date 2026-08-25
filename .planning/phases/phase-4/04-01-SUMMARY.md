---
phase: 4-panel-generation
plan: 01
subsystem: media-generation
tags: [gemini, google-genai, image-generation, boto3, s3, caching, prompt-engineering]

# Dependency graph
requires:
  - phase: 3-asset-management
    provides: output/assets/manifest.json (16-slot registry with content_hash per slot), style.py (STYLE_BLOCK, _strip_on_screen_text), s3_writer.put_bytes, slot_resolver.resolve_slots/_slugify
provides:
  - src/animatic/core/panel_prompt.py (shot_size_for, build_panel_prompt, facial_clause_for)
  - src/animatic/core/panel_generator.py (generate_panel, generate_missing_panels, panel_cache_key)
  - src/animatic/core/panel_manifest.py (write_panel, build_index, write_index)
  - scripts/build_panels.py (CLI)
  - output/panels/index.json (49-beat index contract; only 1 entry populated this plan — s2b7)
  - one real close-up panel (s2b7) generated live and mirrored to S3
affects: [phase-4-02 (scene-2 tracer batch, expected to revise the close-up facial clause), phase-7-video-assembly (reads output/panels/index.json in beat order)]

# Actuals (#2632)
actuals:
  tokens: 18619
  tasks: 3
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-beat panel generation mirrors Phase 3's per-slot asset generation: same call shape, same local-then-S3 honesty, same failure isolation"
    - "Panel cache key is a self-computed sha256 over beat content + derived shot size + each dependent slot's CURRENT content_hash (read fresh from the manifest, not trusted from stale_beat_ids) + PROMPT_TEMPLATE_VERSION"
    - "Index writes after EACH panel is resolved (generated/reused/failed), never batched to the end — a run interrupted at panel 40 keeps 40 entries"
    - "Whole-index rule: --only/--scene narrow generation, never the index; beats outside the selection are carried forward from previous_index unchanged"

key-files:
  created:
    - src/animatic/core/panel_prompt.py
    - src/animatic/core/panel_generator.py
    - src/animatic/core/panel_manifest.py
    - scripts/build_panels.py
    - tests/test_panel_prompt.py
    - tests/test_panel_generator.py
    - tests/test_panel_manifest.py
  modified: []

key-decisions:
  - "Shot size is a pure lookup from beat['type'] (D-01) with a medium fallback for unrecognised types; never written back to output/beats.json (D-02, verified byte-identical before/after)"
  - "Panel prompt subject is beat['content'] stripped of on-screen-text directives and quoted lettering (D-12) — never dialogue lines, never scene_heading"
  - "Facial rule keyed off shot size and placed LAST in the prompt (D-06); wide/medium reuse Phase 3's proven asset_generator._subject_note wording verbatim"
  - "Close-up clause shows brow/mouth/nose as drawn lines and deliberately never names the eye's own anatomy (no iris/pupil/eyelid/eyebrow-arch) even as a thing left absent — naming an object as absent is the same mistake that put a hat on every character via 'hat brim' (D-07); tests/test_panel_prompt.py guards this at the value level"
  - "A beat naming no characters gets no facial clause; the blank-surface room clause closes the prompt instead and facial_features records not_applicable"
  - "Cache key intentionally omits duration_secs and the reason fields — neither changes the picture"
  - "One retry after a 2s delay on a failing image call, matching Phase 3's asset_generator precedent scaled down (no new dependency for a five-line mechanism)"

patterns-established:
  - "Value-level noun guards (test_style.py's pattern) extended to a second axis: eye anatomy, not just headwear/garment — a foreseeable class of 'naming the absent thing' bugs now has an automated test, not just a future visual review"

requirements-completed: [FR-03, NFR-03, NFR-04]

coverage:
  - id: D1
    description: "One beat travels the full path — beat list, manifest, derived shot size, prompt, live Gemini image call, local+S3 write, index entry — proven on s2b7 (a close-up dialogue beat)"
    requirement: "FR-03"
    verification:
      - kind: integration
        ref: "tests/test_panel_generator.py::test_tracer_beat_resolves_generates_and_writes_index"
        status: pass
      - kind: manual_procedural
        ref: "PYTHONPATH=src python scripts/build_panels.py --only s2b7 (live), output opened and viewed"
        status: pass
    human_judgment: false
  - id: D2
    description: "Shot size derives deterministically from beat type (D-01) with a reason recorded, never written back to output/beats.json (D-02)"
    requirement: "FR-03"
    verification:
      - kind: unit
        ref: "tests/test_panel_prompt.py::test_establishing_maps_to_wide, test_action_maps_to_medium, test_dialogue_maps_to_closeup, test_unrecognised_beat_type_falls_back_to_medium_not_raise, test_shot_size_for_does_not_mutate_the_beat_dict"
        status: pass
    human_judgment: false
  - id: D3
    description: "Both facial clauses are pinned at the value level: wide/medium name eyebrow/eye/nose/mouth as absent, close-up shows brow/mouth/nose and never names eye anatomy even as absent; neither clause names a headwear/garment noun; the facial rule lands last for a beat with characters"
    requirement: "FR-03"
    verification:
      - kind: unit
        ref: "tests/test_panel_prompt.py (29 tests, incl. test_closeup_facial_clause_names_no_eye_anatomy_noun, test_facial_clause_names_no_headwear_or_garment, test_facial_clause_is_last_for_a_beat_with_characters)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The close-up clause's actual visual compliance against a live model — whether the model actually leaves the eyes blank — cannot be judged by a unit test; the tracer's own live image shows it does NOT comply (eyes fully rendered)"
    verification: []
    human_judgment: true
    rationale: "Requires looking at the generated image against PROJECT.md's facial-feature rule; automated tests can only assert the prompt TEXT says the right thing, not that the model obeys it. Flagged as a known miss for 04-02's scene-2 tracer batch to revise."
  - id: D5
    description: "An unchanged re-run makes zero image calls (cache reuse); a slot content_hash change invalidates only its dependent beats; a PROMPT_TEMPLATE_VERSION bump invalidates every panel; a --only/--scene run still writes an index entry for every beat"
    requirement: "NFR-04"
    verification:
      - kind: integration
        ref: "tests/test_panel_generator.py::test_unchanged_rerun_makes_zero_calls_and_marks_every_panel_reused, test_slot_content_hash_change_invalidates_only_dependent_beats, test_prompt_template_version_bump_invalidates_every_panel, test_editing_a_beat_content_invalidates_only_that_beat, test_only_restricted_run_still_writes_an_entry_for_every_beat"
        status: pass
    human_judgment: false
  - id: D6
    description: "A failing image call is recorded generation_failed with the exception type/message after one retry, and the run continues to the next beat"
    requirement: "NFR-04"
    verification:
      - kind: unit
        ref: "tests/test_panel_generator.py::test_a_call_that_fails_twice_records_generation_failed_and_the_loop_continues, test_a_call_that_fails_once_then_succeeds_on_retry_produces_a_panel"
        status: pass
    human_judgment: false
  - id: D7
    description: "google-genai remains the only AI SDK imported anywhere in this phase (NFR-03)"
    requirement: "NFR-03"
    verification:
      - kind: other
        ref: "grep -rlE 'openai|anthropic|cohere|mistralai|ollama' src/ scripts/ — no matches"
        status: pass
    human_judgment: false

duration: 24min
completed: 2026-08-25
status: complete
---

# Phase 4 Plan 01: Panel Generation Pipeline Summary

**Per-beat panel pipeline (shot size + prompt + live Gemini image call + honest S3 write + incrementally-written index) proven end-to-end on one real close-up panel, with cache-hit reuse, retry, and the whole-index carry-forward rule under TDD.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-08-24T23:36:00Z (approx.)
- **Completed:** 2026-08-25T06:59:44Z (approx., wall time includes context-loading)
- **Tasks:** 3
- **Files modified:** 7 (all new: 4 source, 3 test)

## Accomplishments
- `panel_prompt.py`: `shot_size_for` (D-01 deterministic mapping, medium fallback for unrecognised types), `build_panel_prompt` assembling STYLE_BLOCK → framing → subject → facial rule LAST (D-06), and `facial_clause_for` routing wide/medium/close-up/no-character to their clause
- `panel_generator.py`: `generate_panel` (identical call shape to `asset_generator.generate_slot_art`, 16:9 aspect ratio, no `system_instruction`), `resolve_beat_slots`, `panel_cache_key`, and `generate_missing_panels` — the full per-beat loop with cache-hit reuse, one retry, and whole-index carry-forward
- `panel_manifest.py`: `write_panel` (beat_id-keyed local+S3 write), `build_index`/`write_index` (honest `s3_ok`/`s3_reason`, mirrors `asset_manifest.py`)
- `scripts/build_panels.py`: CLI with `--beats/--pdf/--manifest/--scene/--only/--force/--dry-run`
- **Live run**: `PYTHONPATH=src python scripts/build_panels.py --only s2b7` produced a real 329,538-byte black-line-art JPEG at `output/panels/s2b7.jpg`, mirrored to `s3://animatic-media-628818/panels/s2b7.jpg` (`s3_ok: true`), and one index entry at `output/panels/index.json` naming the beat, its derived close-up shot size and the rule that assigned it, both dependent asset slots (`int_blue_door_fight_club`, `cornerman`), the full prompt, and a cache key
- 143 tests passing (was 89 before this plan), all mocked — no live API calls in the automated suite
- `output/beats.json` verified byte-identical (MD5 match) before and after the run

## Task Commits

Each task was committed atomically:

1. **Task 1: One beat end-to-end** - `e38426b` (feat)
2. **Task 2: All three shot sizes and the facial rule, guarded at the value level** - `ec01bd8` (test, RED) → `d3191f6` (feat, GREEN)
3. **Task 3: Cache key, failure isolation, and the whole-index rule** - `0cb2f26` (test, RED) → `08c10f5` (feat, GREEN)

**Plan metadata:** (this commit, pending)

## Files Created/Modified
- `src/animatic/core/panel_prompt.py` - shot size derivation, prompt assembly, all three facial clauses
- `src/animatic/core/panel_generator.py` - image call, beat→slot resolution, cache key, the per-beat generation loop
- `src/animatic/core/panel_manifest.py` - panel write, index build/write (local-then-S3, honest)
- `scripts/build_panels.py` - CLI entry point
- `tests/test_panel_prompt.py` - 29 tests, value-level clause/mapping guards
- `tests/test_panel_generator.py` - 21 tests, tracer + cache/retry/whole-index behavior
- `tests/test_panel_manifest.py` - 8 tests, index shape/ordering/S3-honesty

## Decisions Made
- Followed the plan's TDD gate strictly for Tasks 2 and 3: Task 1 intentionally implemented only the mapping table + close-up branch (not wide/medium, not the no-character path, not cache reuse/retry/carry-forward) so that Task 2's and Task 3's test files, written first, would genuinely fail before their corresponding implementation landed — confirmed via `pytest` runs before each `feat` commit (RED), not assumed
- `generate_missing_panels` recomputes `panel_cache_key` for every selected beat on every run (including cache hits) rather than trusting any external staleness signal — this is deliberately more CPU work than trusting Phase 3's own `stale_beat_ids`, matching RESEARCH Pattern 1's reasoning that Phase 4 must keep its own record since the two phases run on independent schedules
- Retry delay is a bare `time.sleep(2)` (no backoff library) — five lines, matching the project's stated preference against a new dependency for a small mechanism

## Deviations from Plan

None from the plan's own written tasks — all three tasks executed as specified, including the TDD gate sequencing for Tasks 2 and 3.

**One significant finding, not a plan deviation but the phase's flagged risk materializing:** the close-up facial clause (D-05, marked `[ASSUMED]` in 04-RESEARCH.md) did not visually comply on its first live generation. The built prompt text correctly states the eyes stay part of the blank plane (verified at the value level by `tests/test_panel_prompt.py`), but the live model drew a fully rendered eye — iris, pupil, and an eyelid crease — while correctly drawing the brow, mouth and nose lines as instructed. This is exactly the outcome 04-RESEARCH.md's Assumption A1 predicted ("likely wrong given Phase 3's own history — budget at least one regeneration pass"), and exactly what D-09's tracer-scene-first strategy exists to catch cheaply, on 19 panels instead of 49, before this wording ships broadly. Logged to `.planning/WINDOWS.md` as entry 5 (open, kind `stub`) for 04-02 to address. No prompt-wording change was made in this plan — that revision belongs to 04-02 per the plan's own scope boundary ("Plan 04-02 validates it on 19 real panels and is expected to revise it").

## Issues Encountered

The worktree was missing `.env`, `.venv`, `docs/`, and `output/beats.json`/`output/assets/` at session start (a fresh worktree checkout). `docs/` and `assets/` turned out to already be present as real tracked directories once inspected (an earlier blind symlink attempt briefly created stray `assets/assets`/`docs/docs` symlinks-inside-directories, caught and removed before any commit). `.env`, `.venv`, `output/beats.json`, and `output/assets/` were symlinked from the sibling checkout at `/Volumes/VM3/vockelldev/cinemachallenge/animatic` without reading or printing their contents, per the plan's environment instructions.

## User Setup Required

None - no external service configuration required. `GOOGLE_API_KEY` and AWS credentials (`AWS_PROFILE=newaccount`) were already present in the linked `.env` and the local AWS config; both worked on the first live call.

## Next Phase Readiness

- The pipeline (prompt → generation → cache → index) is proven end-to-end and ready for 04-02 to run across scene 2's 19 beats.
- `output/panels/index.json` currently holds exactly 1 entry (`s2b7`) — this is expected; 04-01's scope was the tracer plus the mechanism, not the full run. 04-02 owns generating the rest of scene 2.
- **Blocker for 04-02 to actively manage, not fix blindly:** the close-up facial clause needs at least one wording revision before being trusted across 19 panels — see Deviations above and WINDOWS.md entry 5.

## Self-Check: PASSED

All 9 created files verified present on disk (7 code/test files + `output/panels/index.json` + `output/panels/s2b7.jpg`). All 5 commit hashes verified present in `git log`.

---
*Phase: 4-panel-generation*
*Completed: 2026-08-25*
