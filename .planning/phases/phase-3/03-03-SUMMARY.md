---
phase: phase-3
plan: 03
subsystem: assets
tags: [gemini-3.1-flash-image, s3, asset-manifest, art-review, style-prompt]

requires:
  - phase: phase-3
    plan: 02
    provides: "reference_art.resolve_reference_art, asset_generator.generate_missing_art, s3_writer.put_bytes, asset_manifest.build_manifest/write_manifest/write_reference_art — the full generation/manifest pipeline"
provides:
  - "output/assets/manifest.json — real, live-API-generated 16-slot manifest, all 16 slots art-backed, stale_beat_ids == [] (settled)"
  - "output/assets/generated/*.jpg + s3://animatic-media-628818/assets/art/*.jpg — 13 real art files, all D-09/PROJECT.md-compliant on the reviewed sample"
  - ".planning/phases/phase-3/03-ART-REVIEW.md — per-image verdicts against the five D-09/PROJECT.md points, staged for the end-of-phase human gate"
  - "STATE.md 'Phase 3 — Asset Slot Contract' — manifest location/provenance, 16-slot/7-location rule, art_slot_id vs voice_id axis split, priority-as-screen-share, reference-art matching rules, content_hash/stale_beat_ids change signal, shared STYLE_BLOCK — the fixed interface Phase 4/5 read instead of re-deriving"
  - "strengthened no-facial-features subject clause in asset_generator._subject_note — names the specific interior linework (eyebrow/eye/nose/mouth) that must not appear, fixing a repeat failure mode from Plan 02"
affects: [phase-4-panel-generation, phase-5-audio-synthesis]

actuals:
  tokens: 6796
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Facial-feature suppression must name the specific interior linework inside a full descriptive sentence ('no eyebrow, eye, nose or mouth line interrupting that plane') rather than only describing the head shape positively ('a smooth, unbroken white shape') — the latter reads to the model as license to still draw a face inside that shape"
    - "A --force regeneration pass after a style-clause fix is the correct way to re-judge art quality on the real manifest without special-casing individual slots via --only (which would truncate the manifest to one slot)"
    - "Art review evidence belongs in a phase-directory file (03-ART-REVIEW.md), not just prose in the SUMMARY, so the end-of-phase human gate has a durable, per-image record of what was actually looked at"

key-files:
  created:
    - .planning/phases/phase-3/03-ART-REVIEW.md
  modified:
    - src/animatic/core/asset_generator.py
    - .planning/STATE.md
    - .planning/WINDOWS.md
    - README.md

key-decisions:
  - "rocky is judged and shipped as a GENERATED slot, not reference-backed — commit 5f581e0 (landed after 03-03 was written, before it executed) restricts reference-art adoption to a named assets/reference-art/<slot_id>/ directory; the 3 loose rocky-named files in assets/reference-art/ sit outside any slot directory and are recorded only as unadopted candidates. This changes the plan's stated '12 generated art files, rocky reference-backed' to 13 generated art files, reference_backed: 0. Adapted per the phase brief's explicit instruction, documented here rather than silently reconciled."
  - "Fixed the character subject clause (not STYLE_BLOCK) for the facial-feature regression — the failure was specific to how _subject_note described a blank head, not the shared style block; style.py's protected 6e263e8 fixes (location-grounded subject clauses, on-screen-text stripping) were left untouched per the phase brief"
  - "One --force regeneration pass performed (the plan's own stated ceiling before the 2026-09-09 deadline) — all 8 re-sampled slots (both required characters, the two required locations, plus 4 more spot-checks) passed on the second pass; no further iteration"
  - "Closed all 3 of Plan 02's open .planning/WINDOWS.md items (verified visually resolved in the force-regenerated art) and logged one new minor, non-blocking item (a filled-black garment shape in int_rockys_apartment) rather than iterating further to chase it — not one of the three D-09 failure modes"

patterns-established:
  - "Asset Slot Contract in STATE.md, in the same register as the Phase 2 Beat Contract — a settled, dated section downstream phases read directly instead of re-deriving the registry from code"

requirements-completed: [FR-02, NFR-04]

coverage:
  - id: D1
    description: "A real end-to-end run of scripts/build_assets.py against the live gemini-3.1-flash-image API and real S3 produced a complete 16-slot manifest with all 16 slots art-backed (13 distinct files; rocky included since it is no longer reference-backed after 5f581e0)"
    requirement: "FR-02"
    verification:
      - kind: integration
        ref: "python scripts/build_assets.py — real run, 13 real gemini-3.1-flash-image calls, output/assets/manifest.json total_slots=16, all art_uri populated"
        status: pass
      - kind: unit
        ref: "python -c manifest assertion script from 03-03-PLAN.md Task 1 <automated> block — total_slots/character_slots/location_slots, both rockys-apartment slots present, all art_uri/source_reason/priority_reason non-empty, ranks 1..16 unique, stale_beat_ids == []"
        status: pass
    human_judgment: false
  - id: D2
    description: "A clean second run reuses all art with zero new API calls and stale_beat_ids == []; replacing a real slot file (int_rockys_hallway.jpg) and re-running names exactly that slot's one beat_id (s7b1) stale and nothing else; restoring and re-running settles stale_beat_ids back to []"
    requirement: "NFR-04"
    verification:
      - kind: integration
        ref: "run2.log — second run reused 13/13 files, 0 API calls, 2.2s vs 136.9s first run, stale_beat_ids == []"
        status: pass
      - kind: integration
        ref: "run3_swapped.log + manifest state after swap — stale_beat_ids == ['s7b1'], stale_beat_reason 'int_rockys_hallway: content_hash changed', no other slot's art_changed == true"
        status: pass
      - kind: integration
        ref: "restore + two settle re-runs — stale_beat_ids == [] after restoring int_rockys_hallway.jpg's original bytes"
        status: pass
    human_judgment: false
  - id: D3
    description: "Generated art judged against the five D-09/PROJECT.md points (flat black linework, sits alone in frame, no drawn-in words, no facial features, reads as the script's places) on the required 4 samples plus 4 more; 2 of 4 required samples failed the no-facial-features rule on the first pass, fixed via a strengthened subject clause and one --force regeneration, all 8 re-sampled slots pass on the second pass"
    requirement: "FR-02"
    verification:
      - kind: manual_procedural
        ref: ".planning/phases/phase-3/03-ART-REVIEW.md — per-image verdicts for int_blue_door_fight_club, ext_street, black_fighter, generic_minor_character, rocky, promoter, woman, cornerman, int_dressing_room, int_rockys_apartment"
        status: pass
    human_judgment: true
    rationale: "Image content compliance against a visual style rule (D-09/PROJECT.md's no-facial-features rule) is inherently a human/visual judgment call, and generation is non-deterministic (no seed parameter per D-12) — 03-ART-REVIEW.md records the executor's own visual judgment for the end-of-phase human gate to confirm or override, per this task's explicit <human-check> verification requirement."
  - id: D4
    description: "STATE.md carries a Phase 3 Asset Slot Contract section covering manifest location/provenance, the 16-slot/7-location rule and why, the art_slot_id vs voice_id axis separation, priority as share-of-screen-time, reference-art matching rules (including the post-03-03-authoring reference-art tightening), and the content_hash/stale_beat_ids change signal; README documents build_assets.py"
    requirement: "NFR-04"
    verification:
      - kind: other
        ref: "grep -q 'Asset Slot Contract' .planning/STATE.md && grep -q 'build_assets.py' README.md"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-25
status: complete
---

# Phase 3 Plan 03: Real Run, Art Review, and the Asset Slot Contract Summary

**A real live-API run produced a complete, verified 16-slot manifest with 13 real art files (rocky now generated, not reference-backed, per a post-authoring reference-art rule change); a facial-feature regression found during review was fixed and re-verified across 8 slots; the Asset Slot Contract is now settled in STATE.md for Phase 4/5**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-25T01:15:57Z (worktree fast-forward onto Wave 2's tip, 5f581e0)
- **Completed:** 2026-08-25T01:35:37Z
- **Tasks:** 3 (all `type="auto"`)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- `scripts/build_assets.py` ran for real against the live `gemini-3.1-flash-image` API and real S3 (`animatic-media-628818`): 16-slot manifest, 13 distinct art files written locally to `output/assets/generated/` and to `s3://animatic-media-628818/assets/art/` — confirmed via `aws s3api head-object` and `aws s3 ls`. Every plan-specified number checked against the real manifest: `int_blue_door_fight_club` 20 beats/117.8s across scenes 1-2; both `ext_rockys_apartment` and `int_rockys_apartment` present as separate slots; rank 1 is `rocky` at 31/49 beats, 152.3s; lowest-share location `int_rockys_hallway` at 1 beat; `boxing_poses.jpeg` recorded in `unmatched_reference_files`
- Reuse proven live: a second run with no changes reused all 13 files with **zero** new API calls (2.2s vs 136.9s) and `stale_beat_ids == []`
- ROADMAP criterion 4 (change detection) demonstrated on real files, not fixtures: copying different bytes over `int_rockys_hallway.jpg` and re-running marked exactly that slot's one beat (`s7b1`) stale and nothing else; restoring the original bytes and re-running twice settled `stale_beat_ids` back to `[]`
- Art review (`03-ART-REVIEW.md`) sampled the required 4 slots — `int_blue_door_fight_club`, `ext_street`, `black_fighter`, `generic_minor_character` — plus 4 more (`rocky`, `promoter`, `woman`, `cornerman`, `int_dressing_room`, `int_rockys_apartment`) against the five D-09/PROJECT.md points. Both locations passed on the first pass; **2 of 2 required character samples failed the no-facial-features rule** (drawn-in eyes/brow/nose/mouth)
- Fixed `asset_generator._subject_note`'s character subject clauses — replaced the passive "the head is a smooth, unbroken white shape" phrasing with an explicit description naming the interior linework that must not appear ("no eyebrow, eye, nose or mouth line interrupting that plane anywhere"), inside a full descriptive sentence per D-09's positive-prose rule. One `python scripts/build_assets.py --force` regeneration pass (13 real API calls, 132.4s) followed; all 8 re-sampled slots passed all five points on the second pass
- Closed all 3 of Plan 02's open `.planning/WINDOWS.md` items (`generic_minor_character.jpg`/`promoter.jpg` facial features, `ext_street.jpg` sleeping figure) — verified resolved in the force-regenerated art, not just assumed. Logged one new, non-blocking item: a small filled-black garment shape in `int_rockys_apartment.jpg` (not one of the D-09 chrome/shading/text failure modes)
- STATE.md gained a `## Phase 3 — Asset Slot Contract (settled 2026-08-24)` section (Phase 2 Beat Contract's register): manifest location/provenance, the 16-slot/7-location rule and why (D-02/D-03), the art_slot_id/voice_id axis separation (D-04/D-05/D-06/D-07), priority as screen-time share (D-10/D-11), reference-art matching rules including the post-authoring tightening (5f581e0), and content_hash/stale_beat_ids as the change signal Phase 4 keys its panel cache on
- README's "Running locally" section now documents both `scripts/parse_beats.py` (previously undocumented) and `scripts/build_assets.py`, with the reference-art slot-directory convention

## Task Commits

1. **Task 1: Real end-to-end run, then prove the change signal on real files** — no commit (produced no trackable diff: `output/` is gitignored repo-wide, so the manifest and generated art never enter git; evidence is captured in this SUMMARY and `03-ART-REVIEW.md` instead, per the plan's own "record the S3 URIs either way" instruction)
2. **Task 2: Review the generated art against the D-09 failure modes and stage it for sign-off** — `218892e` (fix — strengthened subject clause + `03-ART-REVIEW.md`), `6611c1b` (docs — WINDOWS.md ledger updates: 3 closed, 1 new)
3. **Task 3: Write down the Asset Slot Contract for Phase 4 and Phase 5** — `7776c83` (docs — STATE.md contract + README)

_Task 1 required no code or tracked-file changes — it is a real operational run, and `output/` (the manifest and art) is gitignored. Its plan-specified evidence (console output, three manifest states) is captured above and in the commit that follows it, per the plan's explicit instruction not to force a commit of gitignored binaries._

## Files Created/Modified
- `.planning/phases/phase-3/03-ART-REVIEW.md` (new) — per-image verdicts against the five D-09/PROJECT.md points, both before and after the style-clause fix, for 10 of 13 generated slots
- `src/animatic/core/asset_generator.py` — `_subject_note`'s bespoke-character and minor-character clauses rewritten to explicitly name the interior facial linework that must not appear
- `.planning/STATE.md` — new Asset Slot Contract section, Phase 3 Plan 03 completion note, resolved panel-style Open Question, Phase 3 milestone row marked complete, new Decisions entry
- `.planning/WINDOWS.md` — 3 Plan 02 items marked `fixed` (verified resolved), 1 new minor item logged
- `README.md` — `parse_beats.py` and `build_assets.py` added to "Running locally", with the reference-art slot-directory convention documented

## Decisions Made
- Judged and shipped `rocky` as a generated slot rather than reference-backed, following the phase brief's explicit override of the plan text (`5f581e0` landed after 03-03 was written) — see `key-decisions` in frontmatter and the "Deviations from Plan" section below
- Fixed the character subject clause in `asset_generator.py`, not `style.py`'s `STYLE_BLOCK` — the facial-feature failure was local to how a blank head was described for character prompts, and `style.py`'s protected fixes from commit `6e263e8` (location-grounded subject clauses, on-screen-text stripping) were left untouched exactly as the phase brief instructed
- Performed exactly one `--force` regeneration pass, matching the plan's own stated ceiling ("a second regeneration pass is the sensible ceiling before the 2026-09-09 deadline") — did not iterate further once all 8 re-sampled slots passed
- Marked all 3 of Plan 02's `.planning/WINDOWS.md` items `fixed` only after direct visual re-inspection of the corresponding files in the force-regenerated set, not by assumption

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Character subject clause allowed the model to draw facial features despite a "blank head" instruction**
- **Found during:** Task 2 (art review) — 2 of the 4 plan-required samples (`black_fighter`, `generic_minor_character`) failed the no-facial-features point
- **Issue:** `asset_generator._subject_note`'s character clauses said "The head is a smooth, unbroken white shape, with hair, hat and jaw described by the same outline work" — descriptive of the shape but silent on what must NOT be inside it, so the model kept drawing eyebrows/eyes/nose/mouth on both bespoke and minor characters
- **Fix:** Rewrote both clauses to name the specific interior linework that must not appear ("no eyebrow, eye, nose or mouth line interrupting that plane anywhere"), inside a full descriptive sentence consistent with D-09's positive-prose rule; ran `python scripts/build_assets.py --force` to regenerate all 13 slots and re-judged
- **Files modified:** `src/animatic/core/asset_generator.py`
- **Verification:** 8 of 13 slots re-inspected after the fix (all bespoke characters + `generic_minor_character` + 4 locations) — all pass on the second pass; full suite 81/81 unaffected (no test pinned the old wording)
- **Committed in:** `218892e`

**2. [Task-directed, not a Rule 1-4 auto-fix] `rocky` treated as generated, not reference-backed**
- **Found during:** Task 1 setup — before running, confirmed via `reference_art.py`'s docstring and the phase brief's explicit note that commit `5f581e0` (landed after 03-03-PLAN.md was authored) restricts reference-art adoption to a named `assets/reference-art/<slot_id>/` directory; the 3 loose rocky-named files under `assets/reference-art/` no longer designate reference art
- **Issue:** The plan text says "the full 16-slot manifest and the 12 generated art files (rocky is reference-backed and is not generated)" — stale relative to the shipped code
- **Fix:** Ran the pipeline as-is (no code change needed — `resolve_reference_art` already implements the slot-directory-only rule correctly); `rocky` resolved to `source="generated"` and was included in the 13-call generation batch. Recorded this explicitly everywhere the plan's stale assumption would otherwise mislead: this SUMMARY, `03-ART-REVIEW.md`, and the new STATE.md Asset Slot Contract
- **Files modified:** none (behavior already correct in `reference_art.py`; documentation-only adaptation)
- **Verification:** `output/assets/manifest.json` shows `reference_backed: 0`, `generated: 16`, `rocky`'s `source == "generated"`, `match_rule == ""`
- **Committed in:** N/A (no code change — this is a documented deviation in behavior vs. the plan's stale assumption, not a bug fix)

---

**Total deviations:** 2 (1 Rule 1 — a real bug in prompt wording caught by the plan's own art-review task; 1 explicitly phase-brief-directed adaptation to a code change that landed after the plan was authored, not an auto-fix under Rules 1-4)
**Impact on plan:** Both stayed within task scope. No architectural changes. The rocky/reference-art adaptation changes reported counts (13 distinct art files, not 12; `reference_backed: 0`, not 1) but not the manifest's shape, the change-detection contract, or any success criterion.

## Issues Encountered
- **`output/beats.json`, `.env`, `.venv` were missing from the worktree** (gitignored/generated, not restorable via git checkout) — copied `.env` and `output/beats.json`, symlinked `.venv`, all from the primary checkout at `/Volumes/VM3/vockelldev/cinemachallenge/animatic`, without printing contents. `docs/` and `assets/reference-art/` were already present via the Wave 1/2 fast-forward merge (tracked files).
- **Worktree branch was exactly at the merge-base with `feat/phase-3-asset-management`** (no unique commits of its own) — fast-forward merged cleanly onto `5f581e0` with no conflicts before starting.
- **The `--force` regeneration pass changed every slot's `content_hash`**, which meant an intermediate manifest state showed all 49 beats stale relative to the pre-force manifest (expected — every slot's art genuinely changed). One additional clean re-run (no `--force`) was needed after the review pass to settle `stale_beat_ids` back to `[]` before Task 1's automated verification would pass; this is documented here rather than treated as a bug, since it is exactly the change-detection contract working as designed.
- **`.venv` is a symlink, not a directory**, so the repo's `.venv/` gitignore pattern (trailing slash) does not match it — it shows as untracked (`?? .venv`) rather than ignored. Left as-is (not committed, not added to `.gitignore`); this mirrors 03-02's own documented experience with the same setup.

## Known Stubs

None of the 16 slots are unfilled or stubbed — every slot has real art, a real content hash, and a real S3 upload (`s3_ok: true`). One minor, logged visual-quality item remains (see `.planning/WINDOWS.md` id 4): a small filled-black garment shape in `int_rockys_apartment.jpg` — not a stub, not a D-09 failure mode, not blocking Phase 4.

## Threat Flags

None. All 5 threat-register entries from this plan's `<threat_model>` were honored: no API key, credential or `.env` value appears in the manifest, STATE.md, README, or `03-ART-REVIEW.md` (T-03-02); `s3_ok`/`s3_reason` are recorded honestly in the manifest and this summary reports the real S3 URIs verified via `aws s3api head-object` rather than asserting success (T-03-05); generation stayed within one full run plus one `--force` regeneration (T-03-06); `03-ART-REVIEW.md` records per-image verdicts with a human-check for the end-of-phase gate (T-03-07); no package-manager installs occurred (T-03-SC).

## User Setup Required

None — no external service configuration required. `GOOGLE_API_KEY` and the `newaccount` AWS profile were already configured (copied from the primary checkout's `.env`, matching Wave 1/2's precedent).

## Next Phase Readiness
- `output/assets/manifest.json` is a real, complete, settled 16-slot manifest (`stale_beat_ids: []`, all art_uri populated, `reference_backed: 0`, `generated: 16`) that Phase 4 can read directly for panel-generation prompts.
- The Asset Slot Contract in `.planning/STATE.md` (`## Phase 3 — Asset Slot Contract (settled 2026-08-24)`) is the fixed interface Phase 4 (art_slot_id, STYLE_BLOCK) and Phase 5 (voice_id) consume without re-deriving the registry from code.
- `src/animatic/core/style.py`'s `STYLE_BLOCK` is unchanged and is what Phase 4 must import for its own panel prompts, per D-08 and the contract's explicit instruction not to add a second style block.
- **Known gap for a future pass (not blocking):** a single filled-black garment shape in `int_rockys_apartment.jpg` — logged in `.planning/WINDOWS.md` id 4, regenerate with `--force` if stricter two-tone compliance is wanted before Phase 4 begins consuming this image.
- **Note for Phase 4/5 planning:** `rocky` is a generated slot, not reference-backed, as of this plan — if Phase 4/5 planning assumed rocky's art came from the supplied photo reference, that assumption is now stale; the generated `rocky.jpg` (blank-faced, fedora, consistent with the shared style) is what's in the manifest and on S3.
- No blockers.

## Self-Check: PASSED

All 4 referenced files confirmed present on disk (`output/assets/manifest.json`, `.planning/phases/phase-3/03-ART-REVIEW.md`, `.planning/STATE.md`, `README.md`). All 3 task commits confirmed present via `git log --oneline`: `218892e`, `6611c1b`, `7776c83`. Full test suite: 81/81 passing (`PYTHONPATH=src .venv/bin/python -m pytest tests/ -q`), unchanged from Plan 02's baseline (no new tests required — no test pinned the changed prompt wording). Manifest verification script from Task 1's `<automated>` block: passes (16 slots, unique ranks 1..16, all art_uri/reasons populated, `stale_beat_ids == []`). S3 confirmed via `aws s3api head-object`/`aws s3 ls`: 13 art files + manifest.json present in `s3://animatic-media-628818`.

---
*Phase: phase-3*
*Completed: 2026-08-25*
