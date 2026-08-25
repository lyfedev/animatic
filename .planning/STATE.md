---
gsd_state_version: 1.0
current_phase: 3
current_phase_name: 3/3 plans executed, verification pending; Phase 4 next
status: unknown
stopped_at: Completed 03-03-PLAN.md — real run, art review, Asset Slot Contract
last_updated: "2026-08-25T01:38:53.114Z"
state_head: 7776c83a82ceb9d9925ab3802a57864336abc6de
progress:
  total_phases: 10
  completed_phases: 0
  total_plans: 5
  completed_plans: 3
  percent: 0
---

# Animatic — STATE.md

## Current State

- **Milestone:** 1 — Actor
- **Phase:** 3 — 3/3 plans executed, verification pending (see 03-ART-REVIEW.md); Phase 4 (Panel Generation) is next
- **Active work:** None
- **Last updated:** 2026-08-24
- **Hosted URL:** http://animatic-alb-1855813211.us-east-1.elb.amazonaws.com (HTTP only — no TLS, see Phase 1 gap)

## Milestone Status

### Milestone 1 — Actor (minimum: generate first animatics)

| Phase | Title | Status | Verified |
|-------|-------|--------|----------|
| 1 | Project Scaffold & Infrastructure | ⚠️ Complete, 1 gap | [1-VERIFICATION.md](phases/phase-1/1-VERIFICATION.md) — 5/6, no CloudFront CDN |
| 2 | Beat Parser | ✅ Complete | [2-VERIFICATION.md](phases/phase-2/2-VERIFICATION.md) — scenes 1-8, 18/18 dialogue lines, durations floored |
| 3 | Asset Management & Manifest | 🔄 3/3 plans executed, verification pending | [03-03-SUMMARY.md](phases/phase-3/03-03-SUMMARY.md) |
| 4 | Panel Generation | ⬜ Not started | — |
| 5 | Audio Synthesis | ⬜ Not started | — |
| 6 | Motion Generation | ⬜ Not started | — |
| 7 | Video Assembly | ⬜ Not started | — |

### Milestone 2 — Box Office (footage replacement + external-facing demo)

| Phase | Title | Status |
|-------|-------|--------|
| 8 | Footage Replacement & Per-Shot State | ⬜ Not started |
| 9 | Web UI & Demo Shell | ⬜ Not started |
| 10 | Polish, Submission, Demo Video | ⬜ Not started |

## Key Decisions

- Language: Python
- Cloud hosting: AWS account `339482628818` (profile: `newaccount`, user: `temp_lighthouse`)
- All Animatic AWS resources prefixed `animatic-` to avoid collision with existing lighthouse project
- AI services: Google Cloud only (google-adk, google-genai, google-generativeai, google-cloud-aiplatform)
- Demo content: Rocky (1976), scenes 1–8, fixed
- No user script upload on demo
- Every commit attributed to IBM Bob via `Co-authored-by` trailer

## Open Questions

- [ ] How is IBM Bob usage evidenced in the submission? (pass/fail eligibility — resolve with organisers before Phase 10)
- [ ] CloudFront CDN + TLS: add to the CDK stack, or amend ROADMAP Phase 1 to drop the deliverable? (Phase 1 gap — demo URL is HTTP-only)
- [x] Panel style: smoke test returned greyscale shading with storyboard chrome (notebook binding, caption text, the words "NO FACIALS" drawn into the frame) instead of clean black line art on white. **Resolved by `style.STYLE_BLOCK` (D-08/D-09)** — a real 13-image run judged against the five D-09/PROJECT.md points in `03-ART-REVIEW.md` came back flat black linework on white, no chrome, no drawn-in words, and (after one `--force` regeneration with a strengthened character subject clause) no facial features on any sampled character. The developer's end-of-phase gate is `03-ART-REVIEW.md`'s per-image verdicts, not a re-run of the check. Phase 4 imports the same `STYLE_BLOCK` so panels do not drift from this art (D-08).
- [ ] Live `POST /beats/parse` on the hosted URL has not been exercised (costs a Gemini call, overwrites `beats/latest.json`). The brief requires live beat parsing — prove before Phase 9.
- [ ] Should `.bob/artifacts/` be committed? It is currently untracked, and may be the evidence trail for the IBM Bob question above.

## Phase 2 — Beat Contract (settled 2026-08-24)

`Beat.dialogue` is a **list of `{character, line}`**, never a string. One speaker per
entry, screenplay wording verbatim (leading ellipses included). Phase 5 assigns a voice
per `character`, so merging speakers breaks voice assignment.

Each beat also carries `duration_source` (`model` | `dialogue_floor`), `spoken_words`
and `min_speakable_secs`. A dialogue beat is widened to `words/2.5 + 0.5/line` when the
model under-estimates, and the adjustment is written into `reason` so shot duration
keeps a machine-readable justification.

**One beat per speaker turn.** Film cuts on speaker turns, so a four-line exchange is
four shots, never one held frame. The prompt asks for this and `_split_speaker_turns`
enforces it deterministically; consecutive lines by one character stay together as one
turn. Each split beat is timed from its own words, so "Hey --" does not inherit a long
line's duration.

Current output: **47 beats**, scenes 1-8, 204.4s (3.4 min), **18/18 script dialogue
lines captured and attributed 1:1 to beats**, 0 multi-turn beats, 0 beats shorter than
their speech. Average shot 5.2s — **decided 2026-08-24: longer beats are accepted.** Runtime is
governed by the page budget; beat count stays as extracted rather than being inflated
to chase a faster cut. Revisit only if the assembled video actually reads as slow.

**Scene runtime comes from script page geometry**, not from model guesses: one page is
one minute, a scene claims every line from its own heading to the next (blanks
included), and `scene_timing.py` recovers those counts from character positions on the
12pt grid because `extract_text()` collapses blank lines. Scene durations are then
fitted to that budget, with speech time as an incompressible floor. Needs only the PDF
— nothing is calibrated against the reference film, which the future flow will not
have and whose final cut does not match the script anyway.

Scenes 1-8 = 255.6s (4.26 min); the beat list matches it to 0.1s.

## Verification Debt (resolved 2026-08-24)

`config.json` sets `verification: true`, but Phases 1 and 2 were marked complete
with no VERIFICATION.md. Both have now been verified retroactively against live
evidence (hosted health endpoint, real PDF, real S3 object) rather than from
SUMMARY claims. Findings folded into Open Questions above.

Also fixed in the same pass:

- `.gitignore` credential patterns broadened — a live GCP service-account key was
  untracked but *not* ignored in a public repo. Git history checked: never committed.
  The key still sits in the working tree; moving it out requires a `.env` edit.

- `pdf_extractor.extract_scenes` sorted scenes numerically while its docstring
  promised appearance order. Harmless for Rocky (headings ascend), now correct
  and pinned by tests.

- **`_BEAT_SCHEMA` was dead code** — defined but never passed to the API, which used
  only `response_mime_type="application/json"`. Now wired via `response_schema`, so the
  beat structure is actually enforced by the model rather than hoped for.

- **Dialogue exchanges collapsed into one string.** `dialogue` was a single `str` and the
  prompt asked for "the key line", so two speakers merged into one blob and 11 of 18
  script lines vanished. Now a list of attributed lines; coverage 37% → 100%.

- **Scene 2 was being dropped entirely.** The heading regex required an
  INT./EXT. slug, but scene 2 is a SUPERIMPOSE title card — and it carries the
  whole 532-word opening fight. Its text was absorbed into scene 1 and the demo
  range silently became 1,3-9, wrongly including scene 9. Regex now matches any
  `N … N` numbered heading; the demo set is scenes 1-8 as originally documented.
  Pinned by `test_extract_scenes_returns_scenes_1_to_8` and
  `test_scene_2_is_present_and_carries_the_fight`.

## Google AI Access — smoke-tested 2026-08-24 ✅

All verified with real calls on `GOOGLE_API_KEY`; artifacts in `output/smoke/`.
| Capability | Model | Result |
|---|---|---|
| Panels (Phase 4) | `gemini-3.1-flash-image` | ✅ 697 KB image returned |
| Audio (Phase 5) | `gemini-2.5-flash-preview-tts` | ✅ 2.1s PCM @ 24 kHz, voice `Charon` |
| Motion (Phase 6) | `veo-3.1-fast-generate-preview` | ✅ 2.35 MB MP4 in 46s |
| Assembly (Phase 7) | ffmpeg 7.1.1 | ✅ installed locally |
No allowlist gating. Veo `-fast` turnaround ~46s/clip informs the Phase 6 budget cap.
Note: TTS/Veo are **preview** models — pin versions and expect deprecation churn.

## Phase 3 Plan 01 — Slot Registry Tracer (complete 2026-08-24)

`slot_resolver.resolve_slots(beats, pdf_path)` returns **16 ranked slots**
(9 characters, 7 locations) — confirmed the RESEARCH doc's own "6 locations"
table was stale; 03-CONTEXT.md's D-03 correction (keep INT./EXT. as part of
the normalisation key) is what this plan implements and pins by test.

Rank 1 is `rocky` (31 beats, 152.3s, 59.6% of the 255.7s cut); rank 2 is
`int_blue_door_fight_club` (20 beats, 117.8s, 46.1%). Four minor characters
(`fighter_1`, `fighter_2`, `fan`, `announcer`) share one `generic_minor_
character` art slot but keep distinct `voice_id`s — `assert_no_voice_
collisions` proves FIGHTER #1/#2 (who speak to each other in scene 3) can
never be cast to the same voice.

One real end-to-end run proved the whole pipeline: a live
`gemini-3.1-flash-image` call + a real S3 write to `animatic-media-628818`
for the `int_blue_door_fight_club` slot. Getting a D-09-compliant image
(flat black linework, no color, no signage, no border) took 5 real-API
iterations — the model kept painting a location's own name onto a sign
(a proper noun in the prompt reads as a caption to render) and a colour
word in the name ("blue") onto whatever it named, even with an unquoted,
lowercased subject clause. Fix: strip colour words from location names
before they reach the prompt, and explicitly state that doors/walls/signs
stay blank rather than only stating the model's own positive style rules.
This is a real, general Gemini image-prompting lesson worth carrying into
Phase 4's panel prompts.

`asset_manifest.write_manifest` never reports an S3 failure as a success —
fixing the `beat_assembler._write_s3` swallow-and-fake-success pattern
flagged in Phase 2's verification (T-03-05).

15 of 16 slots have no art yet (03-02's job) — visible in the manifest via
an empty `source` field per slot, not silently stubbed.

## Phase 3 Plan 02 — Reference Art, Full Generation, Honest Manifest (complete 2026-08-24)

`reference_art.resolve_reference_art` matches the 4 supplied files in
`assets/reference-art/` against the 16-slot registry: `rocky` resolves to
`source="reference"` with all 3 rocky-named files (filename-token match),
`boxing_poses.jpeg` is recorded as unmatched with a reason. A slot
directory (`assets/reference-art/<slot_id>/`) wins outright over a
filename-token match.

`asset_generator.generate_missing_art` filled the remaining 15 slots — a
real run made 12 `gemini-3.1-flash-image` calls (7 locations, 4 bespoke
characters, 1 shared `generic_minor_character` for the four minor
characters) and wrote real art to `output/assets/generated/` and S3. A
second real run reused all 12 files with zero new API calls (3.4s vs
127.5s) because each group's prompt matched the previous manifest.

`s3_writer.put_bytes` is now the one place in the codebase that talks to
`boto3` — `beat_assembler._write_s3` and `asset_manifest` both route
through it, keeping their existing return contracts but logging failure
at ERROR (T-03-05, closing the `beat_assembler` gap flagged in Phase 2's
verification).

Change detection (ROADMAP criterion 4) verified against the real
manifest: swapping `generic_minor_character.jpg`'s bytes and re-running
marked exactly the 4 minor characters' 5 beat_ids stale; restoring and
re-running twice settled back to `stale_beat_ids == []`.

**Known visual-quality gap, resolved 03-03:** the 2 facial-feature gaps and
the 1 peopleless-location gap logged here were all fixed in 03-03's art
review pass (strengthened character subject clause + one `--force`
regeneration) — closed in `.planning/WINDOWS.md`, see the Asset Slot
Contract below.

## Phase 3 Plan 03 — Real Run, Art Review, Asset Slot Contract (complete 2026-08-25)

A real end-to-end run of `scripts/build_assets.py` against the live API produced the
full 16-slot manifest and 13 real art files (all 16 slots are now generated — see the
reference-art note below). Numbers checked against the beat list: `int_blue_door_
fight_club` 20 beats/117.8s spanning scenes 1-2; `ext_rockys_apartment` and
`int_rockys_apartment` present as two separate slots; rank 1 is `rocky` at 31 of 49
beats/152.3s; lowest-share location is `int_rockys_hallway` at 1 beat.

A clean second run reused all 13 files with zero API calls and `stale_beat_ids == []`.
The replace-and-restore experiment (ROADMAP criterion 4) was demonstrated live: copying
`ext_street.jpg`'s bytes over `int_rockys_hallway.jpg` and re-running named exactly that
slot's one beat (`s7b1`) stale and nothing else; restoring the original bytes and
re-running twice settled back to `stale_beat_ids == []`.

The art review (`03-ART-REVIEW.md`) sampled the required 4 slots plus 4 more against
the five D-09/PROJECT.md points. 2 of the 4 required samples (`black_fighter`,
`generic_minor_character`) failed the no-facial-features rule — the character subject
clause in `asset_generator._subject_note` said the head was "a smooth, unbroken white
shape" but didn't say which specific lines must not appear inside it, so the model kept
drawing eyes/brow/nose/mouth anyway. Rewrote the clause to name the missing linework
explicitly, then ran one `--force` regeneration pass (the plan's stated ceiling). All 8
re-sampled slots passed on the second pass. This closed all 3 of Plan 02's logged
`.planning/WINDOWS.md` gaps; one new minor, non-blocking item was logged (a filled-black
garment shape in `int_rockys_apartment` — not a D-09 failure mode).

**Deviation from the plan text:** commit `5f581e0` (landed after 03-03 was written, before
it executed) restricts reference-art adoption to a named `assets/reference-art/<slot_id>/`
directory only — filename-token matches are recorded as candidates, never auto-adopted.
`assets/reference-art/`'s 4 loose rocky-named/boxing files are therefore never adopted, so
`rocky` is now a **generated** slot rather than the reference-backed slot Plan 02 shipped.
This plan's numbers (13 distinct art files, not 12; `reference_backed: 0`) reflect that.

## Phase 3 — Asset Slot Contract (settled 2026-08-24)

The registry Phase 4 and Phase 5 consume without re-deriving it.

**Where it lives.** `output/assets/manifest.json` locally,
`s3://animatic-media-628818/assets/manifest.json` in S3. The manifest
carries `beats_source` (the beat list path) and `beats_generated_at` (that
list's own `generated_at`), so a manifest can always be tied to the exact
beat list it was built from. Art files live in `output/assets/generated/`
and `assets/art/` in the same bucket, named `<art_slot_id>.<ext>`.

**16 slots: 9 characters, 7 locations.** Not 8 — scene 2 is a SUPERIMPOSE
title card with no slug of its own and inherits scene 1's location (D-02).
Not 6 — the leading `INT.`/`EXT.` token is kept as part of the
normalisation key on purpose, so `EXT. ROCKY'S APARTMENT` and
`INT. ROCKY'S APARTMENT` stay two separate slots: same building, entirely
different picture — a street-facing facade at night versus a one-room
interior (D-03). Every merge and every split is recorded in the slot's own
`merge_reason`, so a wrong guess is visible rather than silent.

**Art slots and voice identities are separate axes and do not collapse the
same way (D-04).** `art_slot_id` is what Phase 4 keys panel prompts on —
the four minor characters (`fighter_1`, `fighter_2`, `fan`, `announcer`,
each ≤2 beats) share one `generic_minor_character` art slot (D-05).
`voice_id` is what Phase 5 casts from and is unique per character, because
FIGHTER #1 and FIGHTER #2 talk to each other in scene 3 and a shared voice
would make that one person talking to themselves (D-06);
`assert_no_voice_collisions` is the regression guard for that invariant.
Phase 3 built the voice_id key only — Phase 5 maps it to a real TTS voice
name (D-07).

**Priority means share of finished screen time (D-10),** not a generation
order or a cost band: each slot's `priority_rank`, `beats`, `duration_secs`
and `share_pct` are all recorded so the ranking is checkable (D-11). Its
actionable use: it is the ranked answer to which slots would most benefit
from real reference art being supplied. Current ranking: rank 1 `rocky`
(31 beats, 152.3s, 59.6% share), rank 2 `int_blue_door_fight_club` (20
beats, 117.8s, 46.1%), rank 16 `fighter_2` (1 beat, 3.0s, 1.2%).

**Reference art beats generated art**, matched by `assets/reference-art/
<slot_id>/` (a named slot directory — wins outright, unambiguous) first
and filename tokens second (D-01, no alias map). **As of a fix that
landed between 03-03 being written and executed (`5f581e0`), only the
slot-directory mechanism designates reference art** — a filename-token
match is recorded as a *candidate*, offered for future designation, never
adopted automatically. `assets/reference-art/`'s four loose files
(`boxing_poses.jpeg`, `rocky_porkpie.jpg`, `rocky_porkpie2.jpg`,
`rocky_trunks_front.jpg`) all sit loose, not in a slot directory, so none
are adopted — **`rocky` is currently a generated slot, not a
reference-backed one**, a change from Plan 02's shipped state. Unmatched
and candidate files are always reported in the manifest
(`unmatched_reference_files`), never silently dropped (NFR-04). To
designate real reference art for a slot, create
`assets/reference-art/<slot_id>/` and put the file(s) there.

**`content_hash` plus `stale_beat_ids` is the change signal.** Phase 4
keys its panel cache on `(art_slot_id, content_hash)` and redraws exactly
the beats the manifest names as stale. Verified live on the real manifest
in 03-03: replacing `int_rockys_hallway.jpg`'s bytes and re-running marked
exactly that slot's one beat_id (`s7b1`) stale and nothing else; restoring
the original bytes and re-running settled `stale_beat_ids` back to `[]`.

**The shared style constant lives in `src/animatic/core/style.py`
(`STYLE_BLOCK`)** — Phase 4 imports the same constant so panels and slot
art do not visually drift apart (D-08). Do not add a second, per-phase
style block.

## Deadline

2026-09-09 14:00 PDT

## Decisions

- [Phase ?]: Phase 3 Plan 01: slot_resolver resolves 16 slots (9 char + 7 loc); rank 1 rocky, rank 2 int_blue_door_fight_club; image prompts must strip color words from location names to avoid the model painting that color onto whatever it names
- [Phase 3]: Plan 02: reference art matched by slot_directory (wins outright) then filename_token (token-subset, not substring); generate_missing_art groups by art_slot_id and orders by min priority_rank so shared slots generate at their highest-priority member's rank; s3_writer.put_bytes centralizes all S3 writes in the codebase behind one honest S3Result
- [Phase 3]: Phase 3 Plan 03: real 16-slot manifest + 13 art files shipped; rocky is now generated (not reference-backed) per 5f581e0's slot-directory-only rule; strengthened no-facial-features subject clause fixed a repeat regression; Asset Slot Contract settled in STATE.md for Phase 4/5

## Session

**Last session:** 2026-08-25T01:38:47.553Z
**Stopped at:** Completed 03-03-PLAN.md — real run, art review, Asset Slot Contract
**Resume file:** None

## Performance Metrics

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 3 P01 | 32min | 3 tasks | 9 files |
| Phase 3 P02 | 62min | 3 tasks | 7 files |
| Phase 3 P03 | 25min | 3 tasks | 5 files |
