---
phase: phase-3
plan: 01
subsystem: assets
tags: [google-genai, gemini-3.1-flash-image, boto3, s3, slot-resolution, difflib, hashlib]

requires:
  - phase: phase-2
    provides: output/beats.json (49 beats, scenes 1-8), pdf_extractor.extract_scenes
provides:
  - "slot_resolver.resolve_slots(beats, pdf_path) -> list[Slot] — 16 ranked, art/voice-resolved slots"
  - "style.STYLE_BLOCK / build_slot_prompt — shared D-08/D-09 style prompt, imported by Phase 4"
  - "asset_generator.generate_slot_art(slot, prompt) -> (bytes, mime_type) — D-12 call shape"
  - "asset_manifest.build_manifest / write_manifest / write_slot_art — honest s3_ok manifest writer"
  - "scripts/build_assets.py — CLI: --dry-run, --only <slot_id>"
affects: [phase-4-panel-generation, phase-5-audio-synthesis]

actuals:
  tokens: 14992
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Slot dataclass with 25 fields declared up front (Task 1), populated incrementally across 3 tasks — later tasks never invent new fields"
    - "Location identity re-derives ground truth from the PDF (pdf_extractor.extract_scenes), never trusts beats.json's model-invented scene_heading"
    - "Prompt-injection-adjacent lesson: a location's own proper name in the prompt reads as a literal label to the image model — color words and quoted/title-cased names get hand-painted onto signs; strip and lowercase before use"
    - "Honest S3 write result (s3_ok/s3_reason) instead of beat_assembler's swallow-ClientError-return-local:// pattern"

key-files:
  created:
    - src/animatic/core/slot_resolver.py
    - src/animatic/core/style.py
    - src/animatic/core/asset_generator.py
    - src/animatic/core/asset_manifest.py
    - scripts/build_assets.py
    - tests/test_slot_resolver.py
    - tests/test_asset_manifest.py
    - tests/test_style.py
  modified:
    - src/animatic/config.py

key-decisions:
  - "Priority ranking ties broken by beat count then slot_id (not specified in CONTEXT.md, needed for determinism)"
  - "write_slot_art falls back to slot_id when art_slot_id is unset (Task 1 runs before Task 3 populates art_slot_id) — always safe since art_slot_id == slot_id for locations and bespoke characters"
  - "Colour words stripped from a location's display name before it reaches the image prompt — a general defence, not a per-slot hack, after 'blue' in 'BLUE DOOR FIGHT CLUB' repeatedly caused a blue-filled door despite the monochrome style rule"

patterns-established:
  - "Prompt subject clauses for location art request an empty, peopleless establishing view and explicitly forbid hand-painted signage/lettering, in addition to STYLE_BLOCK's own rules — two layers of defense against the model's tendency to add diegetic text"

requirements-completed: [FR-02, NFR-03, NFR-04]

coverage:
  - id: D1
    description: "resolve_slots collapses beats.json + the PDF into 16 ranked slots (9 characters, 7 locations), with scene 2 inheriting scene 1's location and EXT./INT. Rocky's apartment staying separate"
    requirement: "FR-02"
    verification:
      - kind: unit
        ref: "tests/test_slot_resolver.py::test_resolve_slots_returns_16_slots"
        status: pass
      - kind: unit
        ref: "tests/test_slot_resolver.py::test_fight_club_merges_scene_2_by_inheritance"
        status: pass
      - kind: unit
        ref: "tests/test_slot_resolver.py::test_rockys_apartment_int_and_ext_stay_separate_slots"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every slot carries a priority rank (1-16, unique) with beats/seconds/share restated in priority_reason (NFR-04)"
    requirement: "NFR-04"
    verification:
      - kind: unit
        ref: "tests/test_slot_resolver.py::test_priority_ranks_are_unique_1_to_16"
        status: pass
      - kind: unit
        ref: "tests/test_slot_resolver.py::test_every_priority_reason_restates_beats_secs_and_share"
        status: pass
    human_judgment: false
  - id: D3
    description: "Minor characters share one generic art slot; all 9 characters have distinct voice_ids; a deliberate voice collision raises"
    requirement: "FR-02"
    verification:
      - kind: unit
        ref: "tests/test_slot_resolver.py::test_minor_characters_share_one_generic_art_slot"
        status: pass
      - kind: unit
        ref: "tests/test_slot_resolver.py::test_assert_no_voice_collisions_raises_on_a_deliberate_collision"
        status: pass
    human_judgment: false
  - id: D4
    description: "One real slot (int_blue_door_fight_club) generated via a live gemini-3.1-flash-image call and written to a manifest, locally and to S3, with an honest s3_ok/s3_reason"
    requirement: "FR-02"
    verification:
      - kind: unit
        ref: "tests/test_asset_manifest.py::test_tracer_slot_resolves_generates_and_writes_manifest"
        status: pass
      - kind: manual_procedural
        ref: "output/assets/generated/int_blue_door_fight_club.jpg — visually inspected"
        status: pass
    human_judgment: false
  - id: D5
    description: "Generated art is flat black linework on white with no chrome (border/binding/caption) and no drawn-in words, per D-09"
    verification:
      - kind: manual_procedural
        ref: "output/assets/generated/int_blue_door_fight_club.jpg — visually confirmed after 5 real-API iterations, final image clean"
        status: pass
    human_judgment: true
    rationale: "Image quality/style compliance is a visual judgment call the plan itself flags with a <human-check> — automated tests pin STYLE_BLOCK's wording (no 'storyboard', no bare negations) but cannot verify what the model actually rendered."

duration: 32min
completed: 2026-08-24
status: complete
---

# Phase 3 Plan 01: Slot Registry, Style Prompt, and Manifest Tracer Summary

**16-slot registry (9 characters, 7 locations) resolved from beats.json + the PDF, ranked by screen-time share, with one real gemini-3.1-flash-image call proving the manifest pipeline end to end (local + S3)**

## Performance

- **Duration:** 32 min
- **Started:** 2026-08-24T22:32:00Z (approx, worktree setup)
- **Completed:** 2026-08-24T23:04:00Z
- **Tasks:** 3
- **Files modified:** 9 (8 created, 1 modified)

## Accomplishments
- `slot_resolver.resolve_slots` collapses 8 scene headings and 9 character names into 16 deduplicated, priority-ranked slots — scene 2's SUPERIMPOSE inherits scene 1's `INT. BLUE DOOR FIGHT CLUB` (D-02), and `EXT.`/`INT. ROCKY'S APARTMENT` stay two separate slots because the INT./EXT. token survives normalisation (D-03, correcting 03-RESEARCH.md's stale 6-location table)
- Every slot carries a checkable priority: rank 1 is `rocky` (31 beats, 152.3s, 59.6%), rank 2 is `int_blue_door_fight_club` (20 beats, 117.8s, 46.1%), matching 03-CONTEXT.md's own numbers exactly
- Four minor characters (`fighter_1`, `fighter_2`, `fan`, `announcer`) share one `generic_minor_character` art slot while each keeps a distinct, project-wide-unique `voice_id` — `assert_no_voice_collisions` proves FIGHTER #1/FIGHTER #2 (who speak to each other in scene 3) can never collide
- `style.STYLE_BLOCK` pins D-09's positive-only, storyboard-word-free style prose; `tests/test_style.py` asserts on the imported constant's value
- One real end-to-end run: `python scripts/build_assets.py --only int_blue_door_fight_club` made a live `gemini-3.1-flash-image` call and a real S3 write to `animatic-media-628818`, producing a manifest entry with `source_scenes: [1, 2]`, a non-empty `merge_reason`, a sha256 `content_hash`, and `s3_ok: true`

## Task Commits

Each task was committed atomically (Tasks 2 and 3 carried `tdd="true"` — RED then GREEN commits):

1. **Task 1: End-to-end "one slot becomes manifest art"** (tracer) - `0a6c5ec` (feat)
2. **Task 2: Resolve all 16 slots** (tdd) - `f17f2af` (test — RED), `b6025f8` (feat — GREEN)
3. **Task 3: Priority ranking, generic art slots, voice registry** (tdd) - `a77c547` (test — RED), `ca6295f` (feat — GREEN)

**Plan metadata:** (this commit, following)

_All GREEN implementations passed on the first attempt after RED — no separate REFACTOR commit was needed._

## Files Created/Modified
- `src/animatic/core/slot_resolver.py` - `Slot` dataclass (25 fields), location resolution (D-02/D-03/D-03a), character resolution, priority ranking (D-10/D-11), art/voice axes (D-04/D-05/D-06/D-07), `assert_no_voice_collisions`
- `src/animatic/core/style.py` - `STYLE_BLOCK` (D-08/D-09 shared style prose) and `build_slot_prompt`
- `src/animatic/core/asset_generator.py` - `generate_slot_art` (D-12 call shape, no `system_instruction`), `AssetGenerationError`
- `src/animatic/core/asset_manifest.py` - `build_manifest`, `write_manifest` (honest `s3_ok`/`s3_reason`, T-03-05), `write_slot_art` (sha256 `content_hash`, T-03-01 safe paths)
- `scripts/build_assets.py` - CLI entry point (`--beats`, `--pdf`, `--only`, `--dry-run`); location prompts request an empty, peopleless view with colour words stripped from the location's own name
- `tests/test_slot_resolver.py` - 18 tests pinning the exact 16-slot registry, priority numbers, art/voice axes, and the voice-collision guard
- `tests/test_asset_manifest.py` - 7 tests including the tracer end-to-end test and honest-S3-failure regression test
- `tests/test_style.py` - 5 tests pinning D-09 at the constant's value
- `src/animatic/config.py` - added `gemini_image_model: str = "gemini-3.1-flash-image"`

## Decisions Made
- Priority-rank ties break by beat count then slot_id (deterministic, not specified in CONTEXT.md — needed since two slots could theoretically tie on seconds)
- `write_slot_art`'s filename falls back to `slot_id` when `art_slot_id` is empty, since Task 1 runs before Task 3 populates the art axis; harmless post-Task-3 since the two are always equal for locations and bespoke characters
- Location image prompts strip literal colour words (any colour, not just "blue") from the location's display name before building the subject clause — a general defence against the model treating a colour word in a proper name as a literal instruction to paint that colour, discovered on this exact slot (`BLUE DOOR FIGHT CLUB`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `write_slot_art` built an empty filename before the art axis existed**
- **Found during:** Task 1 (first real tracer run)
- **Issue:** `write_slot_art` built its output filename from `slot.art_slot_id`, which is a Task 3 field — on the Task 1 tracer run it was still `""`, producing `output/assets/generated/.jpg`
- **Fix:** Fall back to `slot.slot_id` when `art_slot_id` is unset
- **Files modified:** `src/animatic/core/asset_manifest.py`
- **Verification:** Re-ran the tracer; file now writes to `output/assets/generated/int_blue_door_fight_club.jpg`
- **Committed in:** `0a6c5ec` (Task 1 commit)

**2. [Rule 1 - Bug] Generated art violated D-09's own explicit visual checklist across five real-API iterations**
- **Found during:** Task 1's human-check step (self-performed, since the executor runs autonomously)
- **Issue:** The first-draft prompt (a bare `"<name> (location)"` subject clause) produced a populated fight scene with a detailed crowd of faces and a hand-lettered "BLUE DOOR FIGHT CLUB" banner — violating D-09's own check ("no words drawn into the frame") and PROJECT.md's no-facial-features-in-wide-shots rule. Successive iterations still leaked a colored door, an "EXIT" sign, a "RULES" poster, and a full border frame before converging on a clean result.
- **Fix:** Iterated `STYLE_BLOCK` (explicit two-tone framing; "every wall/prop/sign/plaque stays a blank unlettered shape" instead of the weaker "surfaces are pure white") and the CLI's location subject-note builder (requests an empty, peopleless establishing view; explicitly states no door/wall/sign is captioned or hand-painted with the location's own name; strips literal colour words from the name before it reaches the prompt) across 5 real-API generations until the image was clean: no color, no border/binding, no caption, no drawn-in words.
- **Files modified:** `src/animatic/core/style.py`, `scripts/build_assets.py`
- **Verification:** Final generated image visually inspected — flat black-on-white linework, empty room, no text anywhere
- **Committed in:** `0a6c5ec` (Task 1 commit)

**3. [Rule 1 - Bug] Stray f-string with no placeholders**
- **Found during:** Task 1 (IDE diagnostic on `scripts/build_assets.py`)
- **Issue:** `print(f"\nStep 3/3  Writing manifest...")` had no interpolation
- **Fix:** Changed to a plain string
- **Files modified:** `scripts/build_assets.py`
- **Committed in:** `0a6c5ec` (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs found and fixed while proving the tracer)
**Impact on plan:** All fixes necessary for the tracer's own done criteria (a correctly-named art file, a D-09-compliant image) and code cleanliness. No scope creep — all changes stayed within Task 1's declared files.

## Issues Encountered
- The worktree was branched before the phase-3 planning docs (`03-CONTEXT.md`, `03-RESEARCH.md`, the three PLAN.md files) existed on `main`. Fast-forward merged the worktree branch onto `main` (a clean, docs-only fast-forward — no conflicts) before starting, to pick up the plan files.
- The worktree was also missing `.env`, `.venv`, `docs/rocky-1976.pdf`, `assets/reference-art/*`, and `output/beats.json` — the first three are gitignored/generated and the PDF+reference-art were tracked-but-missing from a partial checkout. Copied `.env`, symlinked `.venv`, and copied `output/beats.json` + `output/smoke/` from the primary checkout; restored `docs/` and `assets/reference-art/` via `git checkout HEAD --`.
- Image generation is non-deterministic (no seed parameter in the D-12 call shape) — reaching a fully D-09-compliant image required 5 real API calls with prompt iteration in between, not 1. This cost is inherent to the generative approach, not a plan defect.

## Known Stubs

None — the tracer's manifest entry is fully real (real image, real hash, real S3 write). The 15 non-tracer slots resolved by `resolve_slots` carry no art yet (`source`, `art_uri`, `content_hash` all empty/default) — this is intentional per Task 1/2/3's scope (03-02 generates the remaining 15 slots' art) and is visible in the manifest itself via the empty `source` field, not silently stubbed.

## Threat Flags

None — all five threat-register entries from the plan's `<threat_model>` (T-03-01 through T-03-05, plus T-03-SC) were implemented as specified: safe write paths via `Path(name).name` + slot_id, the API key read only through `settings.google_api_key` and never logged, honest `s3_ok`/`s3_reason` instead of `beat_assembler`'s swallow-and-fake-success pattern, and no new package-manager installs.

## User Setup Required

None - no external service configuration required. `GOOGLE_API_KEY` and AWS credentials (`newaccount` profile) were already configured per `.planning/STATE.md`'s Google AI Access smoke test.

## Next Phase Readiness
- `slot_resolver.Slot`, `resolve_slots`, `style.STYLE_BLOCK`/`build_slot_prompt`, and `asset_generator.generate_slot_art` are the fixed interface Phase 4 (panels) and Phase 5 (voices) import — all names match the plan's `<interface_contract>` exactly, unchanged.
- 03-02 is next: generate the remaining 15 slots' art (currently unresolved — `source`/`art_uri`/`content_hash` empty), fold in the `beat_assembler` S3-honesty fix this phase modeled, and likely add reference-art matching for the Rocky character slot (4 supplied reference images not yet wired in).
- No blockers. `python scripts/build_assets.py --dry-run` confirms all 16 slots resolve and rank correctly before any further real API spend.

## Self-Check: PASSED

All 8 created files confirmed present on disk (`ls -la` per file). All 5 task
commits confirmed present via `git cat-file -e`: `0a6c5ec`, `f17f2af`,
`b6025f8`, `a77c547`, `ca6295f`.

---
*Phase: phase-3*
*Completed: 2026-08-24*
