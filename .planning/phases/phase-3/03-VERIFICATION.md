---
phase: phase-3
verified: 2026-08-25T02:15:00Z
status: gaps_found
score: 6/7 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "Supplied reference art is ingested and takes priority over generated art (ROADMAP criterion 3)"
    status: failed
    reason: >-
      Commit 5f581e0 (landed mid-phase, before 03-03 executed) restricted reference-art
      adoption to a named `assets/reference-art/<slot_id>/` directory, so a loose
      filename-token match is recorded only as an unadopted "candidate" and never
      promoted. This was a deliberate, well-reasoned fix (a loose token match had
      silently promoted a halftone photograph into a cut that is otherwise flat black
      line art, violating PROJECT.md's "consistent line weight and style" rule) — but
      its effect is that the project's actual supplied reference material is not
      wired to any slot. The live manifest confirms this: `reference_backed: 0`,
      `generated: 16`. Nothing in the current, real system takes priority over
      generated art, because nothing is designated as reference art. The
      slot-directory mechanism itself is real, implemented, and covered by a
      genuine (unmocked) filesystem test — this is a data/curation gap, not a
      code defect — but the observable truth the roadmap criterion states
      ("is ingested and takes priority") does not hold for the system as shipped.
    artifacts:
      - path: "assets/reference-art/"
        issue: "Holds 4 loose, undesignated files (rocky_porkpie.jpg, rocky_porkpie2.jpg, rocky_trunks_front.jpg, boxing_poses.jpeg); no assets/reference-art/<slot_id>/ directory exists for any of the 16 slots"
      - path: "output/assets/manifest.json"
        issue: "reference_backed: 0 — every one of the 16 shipped slots, including rocky, sources its art from generation, not supplied reference material"
    missing:
      - "A human designation step — move the intended Rocky reference photo(s) into assets/reference-art/rocky/ — to exercise the mechanism on real project data and produce at least one reference_backed slot in the live manifest"
      - "Or: an explicit accepted override in a future VERIFICATION.md revision, recording that ROADMAP criterion 3 is satisfied by a tested-but-currently-unexercised mechanism, with the policy rationale (5f581e0) as the reason"
---

# Phase 3: Asset Management & Manifest — Verification Report

**Phase Goal:** Named asset slots, temp-art fallback, manifest output.
**Verified:** 2026-08-25T02:15:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

All evidence below was independently reproduced against the real codebase and the real,
live artifacts on disk (`output/beats.json`, `docs/rocky-1976.pdf`, `output/assets/manifest.json`,
`output/assets/generated/*.jpg`) — not inferred from the three SUMMARY.md files, which are
treated here only as a map of what to check, not as evidence in themselves.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running with zero reference art produces a complete manifest with every slot filled by generated temp art (ROADMAP criterion 1) | ✓ VERIFIED | Live `output/assets/manifest.json`: `total_slots: 16`, `generated: 16`, `reference_backed: 0`, every slot has a non-empty `art_uri` pointing at a real file on disk (all 13 files present, sha256 `content_hash` in the manifest matches the real file bytes for all 16 entries, independently recomputed). `tests/test_asset_manifest.py::test_manifest_complete_with_no_reference_art` also exercises this with reference art absent. |
| 2 | Every character and location in the beat list resolves to exactly one slot (ROADMAP criterion 2) | ✓ VERIFIED | Independently recomputed from `output/beats.json` + `docs/rocky-1976.pdf`, not from the manifest: 9 distinct `characters[]` values across 49 beats, 8 raw scene headings across 8 scenes where scene 2 (`INT. BOXING CLUB - NIGHT`) is Gemini-invented text, not a real PDF slug (`pdf_extractor.extract_scenes` confirms scene 2 has no `INT./EXT.` line). Folding scene 2 into scene 1 per D-02 yields 7 distinct locations, matching the manifest's `location_slots: 7` exactly. `EXT. ROCKY'S APARTMENT` (scene 6) and `INT. ROCKY'S APARTMENT` (scene 8) are two separate slots in both the live manifest and the registry code (`slot_resolver._resolve_locations` keeps the `INT.`/`EXT.` token in the normalisation key). 9 + 7 = 16, matching `total_slots: 16`, `character_slots: 9`. No name/heading is missing or double-counted. |
| 3 | Supplied reference art is ingested and takes priority over generated art (ROADMAP criterion 3) | ✗ FAILED | See `gaps` above. The slot-directory matching mechanism (`reference_art.resolve_reference_art`) is real and tested against real bytes on a real filesystem (`tests/test_asset_manifest.py::test_slot_directory_designates_reference_art`, `test_slot_directory_beats_filename_token` — both build actual files under `tmp_path` and call the production function, not a mock). But **no slot in the live system is currently reference-backed** — `reference_backed: 0` in `output/assets/manifest.json`. The project's actual supplied reference photos sit loose and undesignated. Ruling: the mechanism exists and works; the criterion as an observable truth about the shipped system does not currently hold. |
| 4 | Replacing a slot file and re-running regenerates the panels that use it (ROADMAP criterion 4) | ✓ VERIFIED (mechanism; scoped) | Independently reproduced against the real production code and real production data (not fixtures): loaded the actual 16 resolved `Slot` objects via `resolve_slots`/`resolve_reference_art`, populated their art fields from the real `output/assets/manifest.json`, then called `asset_manifest.build_manifest` twice — once unchanged (`stale_beat_ids == []`) and once with `int_rockys_hallway`'s content_hash altered to simulate a real file replacement. Result: `stale_beat_ids == ['s7b1']` (exactly `int_rockys_hallway`'s one real beat_id) and `art_changed` True on that slot only — matching 03-03-SUMMARY's independently-unverifiable claim exactly. **Scope note, re-ruling the prior plan-check finding:** no panels exist yet (Phase 4 has not started), so "regenerates the panels" cannot be observed inside Phase 3 by construction — Phase 3's actual, verifiable deliverable is the `content_hash` + per-slot `beat_ids` + `stale_beat_ids` signal Phase 4 is contracted to consume. This is confirmed here as a legitimate, working phase-boundary handoff, not a stub. |
| 5 | Each manifest entry records slot name, priority, source and reason (ROADMAP criterion 5) | ✓ VERIFIED | All 16 live manifest entries carry non-empty `slot_id`, `priority_rank` + `priority_reason` (restating beats/seconds/share, e.g. `"31 beat(s), 152.3s, 59.6%... rank 1 of 16..."`), `source` (`"generated"` throughout), and `source_reason` (e.g. `"reused existing art at ... — prompt unchanged since the previous manifest"`) — independently checked field-by-field across all 16 entries, none empty. |
| 6 | Two characters who speak in the same scene are never given the same voice (D-04/D-06) | ✓ VERIFIED | Confirmed from `output/beats.json` directly: `FIGHTER #1` and `FIGHTER #2` both speak in scene 3 (`s3b2`, `s3b3`, `s3b4`). `slot_resolver.assert_no_voice_collisions` is called unconditionally inside `resolve_slots` on every run (not just in tests) and raises `ValueError` on any same-scene voice collision. `tests/test_slot_resolver.py::test_assert_no_voice_collisions_raises_on_a_deliberate_collision` forces a real collision (mutates `fighter_2.voice_id = fighter_1.voice_id`) and confirms it raises — this is a genuine regression test, not a tautology, since `voice_id` is not hard-coded distinct by the test itself. Ran in isolation: passes. |
| 7 | Google Cloud SDK only for AI — no other AI models/frameworks/APIs (NFR-03) | ✓ VERIFIED | `requirements.txt`: only `google-genai`. `src/animatic/core/asset_generator.py` imports only `from google import genai` / `from google.genai import types`. Repo-wide grep for `openai`, `anthropic`, `langchain`, `cohere`, `mistralai`, `ollama` (source, scripts, requirements, pyproject) returns zero matches. |

**Score:** 6/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/animatic/core/slot_resolver.py` | 16-slot registry, priority, art/voice axes | ✓ VERIFIED | 455 lines, real logic (not stubbed); independently confirmed correct against beats.json + PDF |
| `src/animatic/core/style.py` | Shared D-08/D-09 style prompt | ✓ VERIFIED | `STYLE_BLOCK` imported by `asset_generator`; wording matches D-09's positive-prose, no-storyboard-word rule |
| `src/animatic/core/asset_generator.py` | D-12 image call shape, generation loop | ✓ VERIFIED | Real `genai.Client` call, no `system_instruction`; `generate_missing_art` groups by `art_slot_id`, orders by priority, reuses on unchanged prompt, isolates per-group failure |
| `src/animatic/core/asset_manifest.py` | Manifest assembly, change detection | ✓ VERIFIED | `build_manifest`/`_detect_changes` independently exercised against real production slots/beats above |
| `src/animatic/core/reference_art.py` | Reference-art ingestion, priority over generation | ✓ VERIFIED (unexercised in prod) | Real, tested mechanism; zero live matches (see gap above) |
| `src/animatic/core/s3_writer.py` | Shared honest S3 writer | ✓ VERIFIED | `put_bytes` returns explicit `S3Result(uri, ok, error)`, never fabricates success on `ClientError`/`ProfileNotFound` |
| `scripts/build_assets.py` | CLI entry point | ✓ VERIFIED | 4-step pipeline (resolve → reference → generate → manifest); `--dry-run`, `--only`, `--force`, `--reference-dir` all present |
| `output/assets/manifest.json` | 16-entry manifest, real data | ✓ VERIFIED | Real, on disk, all fields populated, all 16 content hashes match real files |
| `output/assets/generated/*.jpg` | 13 real art files | ✓ VERIFIED | 13 files present, real JPEG sizes (83KB–756KB), hashes match manifest |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `slot_resolver._resolve_locations` | `pdf_extractor.extract_scenes` | Direct call, ground truth for "has a real slug" | ✓ WIRED | Confirmed by reading the source; independently reproduced the same 7-location result from raw PDF + beats.json |
| `reference_art.resolve_reference_art` | `asset_generator.generate_missing_art` | A slot with `source == "reference"` is skipped in the generation loop | ✓ WIRED | Confirmed in code (`generate_missing_art` groups only unresolved slots); currently never exercised in production because no slot resolves to reference (see gap) |
| `asset_manifest.build_manifest` | `output/assets/manifest.json` + S3 | `write_manifest` → `s3_writer.put_bytes` | ✓ WIRED | Live manifest has `s3_ok: true`, confirmed via `aws s3api head-object` per 03-03-SUMMARY (S3 network calls not independently re-run here to avoid mutating live infra during verification) |
| `style.STYLE_BLOCK` | `asset_generator._subject_note` / prompts | Prompt text composition | ✓ WIRED | Live manifest's `prompt` field for every slot contains the exact `STYLE_BLOCK` text plus a subject clause |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full test suite passes | `PYTHONPATH=src .venv/bin/python -m pytest tests/ -q` | 81 passed, 2 warnings, 43.19s | ✓ PASS |
| Voice-collision guard fires on a forced collision | `pytest tests/test_slot_resolver.py -k voice_collision` | 2 passed (including the deliberate-collision test) | ✓ PASS |
| Slot math (16 = 9 + 7) reproducible outside the app | Independent Python script reading `output/beats.json` + PDF | 9 characters, 7 locations, matches manifest exactly | ✓ PASS |
| Change-detection mechanism on real production data | Independent Python script: `resolve_slots` + `resolve_reference_art` + `build_manifest` against the real manifest, with one slot's hash altered | `stale_beat_ids == ['s7b1']` only, matching `int_rockys_hallway`'s one real beat | ✓ PASS |
| Real art files match their manifest content_hash | Independent sha256 recompute of all 16 `art_uri` files | 16/16 match | ✓ PASS |
| No non-Google AI SDK anywhere in the repo | `grep -rE 'openai|anthropic|langchain|cohere|mistralai|ollama' src/ scripts/ requirements.txt` | No matches | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| FR-02 | 03-01, 03-02, 03-03 | Asset management: named slots, temp-art fallback, reference-art priority, manifest | ⚠️ PARTIAL | Slot resolution, temp-art fallback, and manifest fully satisfied; reference-art priority (the "accept... reference art" bullet) not currently exercised in production (see gap) |
| NFR-03 | 03-01, 03-02 | Google Cloud SDK only for AI | ✓ SATISFIED | Confirmed by repo-wide grep and import inspection |
| NFR-04 | 03-01, 03-02, 03-03 | Every generated artifact carries a machine-readable reason | ✓ SATISFIED | All 16 manifest entries carry non-empty `priority_reason`, `source_reason`, `merge_reason` |

No orphaned requirements: REQUIREMENTS.md has no explicit "Phase 3" mapping section beyond FR-02/NFR-04 (ROADMAP header) and NFR-03 (plan-declared, additive) — all are claimed by the three plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers found in any Phase 3 source file | — | Clean |
| `output/assets/generated/black_fighter.jpg` | — | Content-fidelity gap (not a style/facial-feature failure) — see Notable Finding below | ℹ️ Info | Non-blocking for Phase 3's own success criteria; recommend logging |
| `output/assets/generated/int_rockys_apartment.jpg` | — | Small filled-black garment shape, minor two-tone departure | ℹ️ Info | Already logged in WINDOWS.md id 4, `open`, correctly not treated as a D-09 failure mode |

### Notable Finding: `black_fighter.jpg` reads as a modern soldier, not a 1976 boxer

Visually inspected directly (not taken on the SUMMARY's word). The image is clean line
art with a correctly blank, featureless face — it fully complies with D-09 and
PROJECT.md's no-facial-features rule, confirming 03-ART-REVIEW's second-pass verdict on
that specific point. But the figure wears a beret, tactical vest with pouches and
webbing, a slung rifle, and a flowing cape/cloak over combat boots — a military
operator silhouette, not a boxer. Nothing in the character's slot prompt describes the
figure beyond the bare name `BLACK FIGHTER`; the model filled in the rest and produced
a design that does not read as a Rocky-era boxing opponent.

**Ruling:** this does not make any of the five ROADMAP success criteria false. All five
are about slot completeness, resolution, priority, reference-art precedence, change
detection, and manifest field content — none require that generated art content be a
correct genre/costume match to the script. This is the same class of gap the phase's
own backlog (S-01) already anticipates and validates a fix for ("generation alone
yields similar-looking characters... a bare name" is exactly what produced this). It
belongs in `.planning/WINDOWS.md` as a new, non-blocking item and in the S-01 backlog,
not as a Phase 3 blocker. **It is currently untracked** — 03-ART-REVIEW.md's five-point
checklist has no "reads as the script's character" column for characters (only for
locations), so this specific failure mode was structurally unable to be caught by the
phase's own review process. Recommend adding it to WINDOWS.md and noting the review
checklist gap for Phase 4/5's own art-QA passes.

## Human Verification Required

None required to resolve this report's `gaps_found` status — the criterion 3 gap is a
data/curation decision (designate reference art, or accept the current policy via an
override), not a question that needs visual judgment to resolve. The `black_fighter.jpg`
content-fidelity finding above is a genuine visual/quality judgment call, but it does not
block phase-goal achievement and is recommended for WINDOWS.md rather than a phase-3 gate.

## Gaps Summary

One of five ROADMAP success criteria — criterion 3, reference-art priority — does not
hold in the live system as shipped, despite the underlying mechanism being real,
correctly implemented, and covered by genuine (unmocked) filesystem tests. The cause is
a deliberate, well-documented mid-phase policy tightening (commit `5f581e0`): loose
filename-token matches, which had silently promoted a stylistically-mismatched
photograph into the cut, are no longer auto-adopted — only a named
`assets/reference-art/<slot_id>/` directory counts as a designation. No file in the
project's actual supplied reference material has been moved into such a directory, so
`reference_backed: 0` across the whole live manifest.

This is a two-line fix (`mkdir assets/reference-art/rocky && mv <file> assets/reference-art/rocky/`,
then re-run `build_assets.py`) if the intent is to demonstrate the criterion on real
project data, or a one-line acceptance (an explicit override in a future verification
pass) if the intent is that the policy change itself satisfies the phase goal and the
roadmap criterion's wording should be read as "the mechanism exists," not "reference art
is currently in use." Both are legitimate; this report does not resolve the choice on
the developer's behalf, per the phase brief's instruction to rule plainly rather than
hedge on *what the evidence shows*, while leaving the *policy* decision itself to the
developer.

All other criteria (1, 2, 4, 5), the D-06 voice-collision guard, and the NFR-03 AI
constraint are independently verified against real code and real data, not SUMMARY
claims.

---

*Verified: 2026-08-25T02:15:00Z*
*Verifier: Claude (gsd-verifier)*
