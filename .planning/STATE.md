---
gsd_state_version: 1.0
current_phase: 7
current_phase_name: Video Assembly
status: in_progress
stopped_at: Phase 7 built and the cut is watchable. Phase 6 (motion) deferred behind it. Phase 7 verification not yet run.
last_updated: "2026-08-25T12:40:00Z"
state_head: b8170b48296933be829f4c0a03aa161af5bb4869
progress:
  total_phases: 10
  completed_phases: 6
  total_plans: 8
  completed_plans: 8
  percent: 60
---

# Animatic — STATE.md

## Current State

- **Milestone:** 1 — Actor
- **Phase:** 7 complete — the cut exists and is watchable. Phase 6 (motion) deliberately deferred behind it: motion covers 4 beats of 49, the cut is the deliverable, and Phase 4's accepted art defects can only be judged in motion. Phase 5 done. Phases 3 and 4 are closed: both verified `passed`, each carrying one explicit developer override (Phase 3: reference art held unexercised; Phase 4: 8 named facial/lettering exception beats).
- **Active work:** None
- **Carried into Phase 5+:** 8 WINDOWS.md panel defects, re-evaluated at Phase 7 in the assembled cut rather than as stills
- **Last updated:** 2026-08-25
- **Hosted URL:** http://animatic-alb-1855813211.us-east-1.elb.amazonaws.com (HTTP only — no TLS, see Phase 1 gap)

## Milestone Status

### Milestone 1 — Actor (minimum: generate first animatics)

| Phase | Title | Status | Verified |
|-------|-------|--------|----------|
| 1 | Project Scaffold & Infrastructure | ⚠️ Complete, 1 gap | [1-VERIFICATION.md](phases/phase-1/1-VERIFICATION.md) — 5/6, no CloudFront CDN |
| 2 | Beat Parser | ✅ Complete | [2-VERIFICATION.md](phases/phase-2/2-VERIFICATION.md) — scenes 1-8, 18/18 dialogue lines, durations floored |
| 3 | Asset Management & Manifest | ✅ Complete, 1 override | [03-VERIFICATION.md](phases/phase-3/03-VERIFICATION.md) — 7/7, reference art held unexercised |
| 4 | Panel Generation | ✅ Complete, 1 override | [04-VERIFICATION.md](phases/phase-4/04-VERIFICATION.md) — 5/5, 41/49 panels clean, 8 named exceptions |
| 5 | Audio Synthesis | ✅ Complete, 14 clips stale | [Audio Contract](STATE.md) — 49 clips, 0 failed, 2 music cues |
| 6 | Motion Generation | ⬜ Not started (deferred behind 7) | — |
| 7 | Video Assembly | ✅ Complete | [Cut Contract](STATE.md) — 49 shots, 262.1s, swap seam proven live |

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

## Phase 4 Plan 01 — Panel Pipeline Tracer, Prompt Clauses, Cache/Retry (complete 2026-08-25)

`panel_prompt.py`/`panel_generator.py`/`panel_manifest.py`/`scripts/build_panels.py` proved
the full per-beat path live on `s2b7` (scene 2, dialogue, `CORNERMAN`): shot size derived
from beat type (D-01), a prompt assembled STYLE_BLOCK → framing → subject → facial rule
LAST (D-06), a real `gemini-3.1-flash-image` call, a local+S3 write, and one
`output/panels/index.json` entry naming both dependent slots, the prompt and a cache key.
`output/beats.json` verified byte-identical (MD5) before/after — shot size is never written
back (D-02).

Tasks 2 and 3 followed strict RED→GREEN TDD: the full test file was written and run first
(collection/assertion failures confirmed genuine RED), then the implementation landed. Task 3
added cache-hit reuse (`panel_cache_key` — beat content + shot size + each dependent slot's
CURRENT `content_hash` read fresh from the manifest + `PROMPT_TEMPLATE_VERSION`), one retry
after a 2s delay on a failing call, and the whole-index carry-forward rule (a beat outside
`--only`/`--scene`'s selection is carried forward from the previous index unchanged, mirroring
Phase 3's own `--only` regression class). 143 tests passing (was 89 at phase start), all
mocked — the live call happens once, by the CLI, never in the suite.

**Known miss, not yet fixed — this phase's flagged risk:** the close-up facial clause (D-05)
is marked `[ASSUMED]` in `04-RESEARCH.md` and did not visually comply on this first live
image: the model drew a fully rendered eye (iris, pupil, eyelid crease) while correctly
drawing the brow/mouth/nose lines. The prompt TEXT is correct and pinned at the value level
by `tests/test_panel_prompt.py` — this is a live-model compliance gap a unit test cannot
catch, only a human looking at the picture can. Logged as `.planning/WINDOWS.md` entry 5
(open). 04-02's scene-2 tracer batch (19 beats) is the intended mechanism to catch and fix
this before it ships across all 49 panels (D-09).

`output/panels/index.json` currently holds exactly 1 entry (`s2b7`) — expected for this plan's
scope. 04-02 owns generating the rest of scene 2.

## Phase 4 Plan 02 — Scene 2 Art Review, Two Revision Passes (complete 2026-08-25)

Ran `scripts/build_panels.py --scene 2` three times against the live API — a v1 baseline,
then the plan's full two-pass revision budget (D-09's hard ceiling). `PROMPT_TEMPLATE_VERSION`
moved v1 → v2 → v3 (`panel_prompt.py`, commits `2a272a5`, `70831e6`). v2 bound the blank-face
clause to every figure in frame instead of an implicit singular one, and added "garment" to
the room rule's noun list. v3 named the two contexts that survived v2 directly — a packed
crowd and the moment of impact for the blank-face rule, a familiar/iconic garment for the room
rule — after v2 showed the broader wording only partially closed both gaps.

Required samples (`s2b1`, `s2b2`, `s2b7`, `s2b16`, `s2b18`) all read clean by v3. Two further
defects found while reviewing all 19 panels at each pass were fixed within budget: a ~15-figure
crowd carrying full faces (`s2b3`) and "ROCKY" lettered onto a robe via the model's own
knowledge of the source film rather than the prompt text (`s2b17`, resolved — the robe reads
fully blank in v3).

**Developer's D-09 gate — accept-with-note (2026-08-25).** Four defects survived both revision
passes and were reviewed live: `s2b3`'s crowd still carries full faces; `s2b9`/`s2b5`'s
two-figure close-ups are less reliable than single-character close-ups; `s2b12` renders as a
solid black fill; `s2b16`'s knockout carries cartoon impact stars. The developer chose to
generate the remaining 30 beats and carry all four forward rather than extend the two-pass
ceiling — the scene reads as an editable fight with real coverage, and Phase 7 (the first
watchable animatic) is the milestone to protect. **Re-evaluate in the assembled cut, not as
stills** — `scripts/build_panels.py --force --only <beat_id>` regenerates one panel without
disturbing any other, if any of the four read badly in motion. Full rationale and the defect
table: `.planning/WINDOWS.md` §"Phase 4 D-09 gate". `PROMPT_TEMPLATE_VERSION` stays at `v3` for
the rest of the phase — the ceiling is spent, not reopened.

`.planning/WINDOWS.md` entry 5 (04-01's eye-rendering defect) closed. Four new entries opened
(#6-#9), matching the gate table above.

## Phase 4 Plan 03 — Full Run, Cache Proof, Panel Contract (complete 2026-08-25)

`scripts/build_panels.py` run with no scene filter: scene 2's 19 panels reused from cache at
zero API cost, the other 30 generated live (0 `generation_failed`), 49 total in 344.2s. Shot
sizes split 8 wide / 23 medium / 18 close-up, matching D-01 over the corpus's 8
establishing/23 action/18 dialogue beats. `output/beats.json` verified byte-identical
(MD5 unchanged) before and after. `PROMPT_TEMPLATE_VERSION` stayed at `v3` — no clause wording
touched, per the developer's gate decision not to reopen the two-pass ceiling.

Sampled `s3b7`, `s5b4`, `s8b1`, `s4b4` against 04-02's six review points. Three read clean.
`s5b4` (Rocky at the Animal Town Pet Shop) confirmed 04-CONTEXT.md's D-12 prediction live,
outside scene 2: the shop's sign, an "OPEN" placard and a "PET SUPPLIES" placard all render as
legible drawn-in text despite the room rule. Survived one `--force` retry (garbled to "ANIMAL
TOWN PET SIOP", still lettered) — logged as `.planning/WINDOWS.md` entry 10, not chased with a
clause revision. Full verdicts: `04-ART-REVIEW.md`'s second-pass section.

**The cache proof — the real-file replace-and-restore, closing Phase 3's own deferred
criterion 4.** State one (nothing changed): 49/49 reused, 0 calls. State two: swapped
`ext_street.jpg`'s bytes onto `int_rockys_hallway.jpg` (the slot with exactly one dependent
beat, `s7b1`); `build_assets.py` re-read all 16 slots with zero calls and recomputed the
swapped slot's `content_hash`; `build_panels.py` invalidated exactly `s7b1` and left the other
48 reused — the blast-radius proof. The live regeneration call itself hit a Gemini billing wall
(429 RESOURCE_EXHAUSTED, prepayment credits exhausted by this plan's ~31 live calls) — an
account/billing constraint, not a cache-key defect; the invalidation logic did exactly what it
should. State three: restored the original bytes, confirmed the manifest's `content_hash`
reverted exactly, and (with the API unable to fulfil a live call) repaired `s7b1`'s index entry
back to `reused` through the project's own `panel_cache_key`/`build_index`/`write_index`
functions against the untouched, still-correct `s7b1.jpg` (verified present locally and in S3,
byte-identical to the pre-experiment artifact, before use — no call made or claimed). Two
further unmodified runs held at 49 reused / 0 generated / 0 failed. Full evidence, console
counts and the repair rationale: `04-ART-REVIEW.md`'s caching section.

Also found and documented (not fixed, out of this plan's `files_modified`): `04-03-PLAN.md`'s
own Task 2 automated `<verify>` block unpacks `slot_hashes` (a list of `{"slot_id",
"content_hash"}` dicts) as if it were a list of 2-tuples, binding to the dicts' own keys
instead of their values — it flags false "drift" on every panel with a dependent slot
regardless of correctness. The corrected check (iterate dict values) confirms zero real drift.

## Phase 4 — Panel Contract

The panel index Phases 5, 6 and 7 read without re-deriving it — same register as the Phase 2
Beat Contract and the Phase 3 Asset Slot Contract above.

**Where it lives.** `output/panels/index.json` locally, `panels/index.json` in the media
bucket (`s3://animatic-media-628818/`). Panels themselves: `output/panels/<beat_id>.<ext>`
locally, `panels/<beat_id>.<ext>` in S3. The index names `beats_source` and `beats_generated_at`
(the exact beat list it was built from) and `assets_manifest_source` /
`assets_manifest_generated_at` (the exact asset manifest it was built against), so any index
can always be tied to its inputs. Top-level counts: `total_panels`, `generated_count`,
`reused_count`, `failed_count`, plus the index's own `s3_ok`/`s3_reason` (honest, never
assumed — T-04-03).

**Per-entry fields, in beat order.** `build_index` sorts every entry by `(scene, beat)` before
writing, so `output/panels/index.json`'s `panels` array is always the order Phase 7 assembles
from — it never needs to join back to `output/beats.json` to sequence the cut. Each entry
carries `beat_id`, `scene`, `beat`, `type`, and **`duration_secs` copied straight from the
beat** — the field Phase 7 cuts on. Also: `shot_size`, `shot_size_reason`, `facial_features`,
`facial_features_reason`, `asset_slots_used`, `slot_hashes` (`[{slot_id, content_hash}, ...]`
for every dependent slot), `prompt`, `prompt_template_version`, `cache_key`, `panel_uri`,
`panel_s3_uri`, `content_hash`, `source` (`generated`/`reused`/`generation_failed`), and
`source_reason`.

**Shot size is derived, never stored back.** `establishing` → wide, `action` → medium,
`dialogue` → close-up (D-01), computed at panel-build time by `panel_prompt.shot_size_for` and
never written into `output/beats.json` (D-02) — the beats stand as initially rendered, and
adding a field to them would invalidate the Phase 3 asset manifest's own content hashes. Every
panel records both the derived value and the rule that assigned it in `shot_size_reason`, the
same way a beat records `duration_source` — except `duration_source` carries three live values
in this corpus (`model`, `page_budget`, `dialogue_floor`), where shot size only ever carries
one rule (D-01's lookup) plus a documented medium fallback for an unrecognised beat type.

**The facial rule is keyed off shot size (D-05).** Wide and medium carry no facial features at
all; close-ups carry a brow line, a mouth line and a nose line — never eyes, never full
rendering. Three prompt rules produce it, paid for twice across 04-01 and 04-02's two revision
passes: state the rule as positive prose, never a negation (a negation gets rendered as literal
text — "NO FACIALS" was once painted into a frame); place the rule that matters LAST in the
prompt (a rule stated mid-prompt loses to whatever follows it); and name no object that is not
wanted in the picture, including as an absence (naming "hat brim" as a face boundary put a hat
on every character; naming "iris"/"pupil" as absent drew a fully rendered eye anyway — the
close-up clause names only the three lines that ARE drawn). Guards assert on the built prompt
string (`tests/test_panel_prompt.py`), never on the source file.

**What the cache key covers.** `panel_generator.panel_cache_key` hashes the beat's own content
fields (`beat_id`, `type`, `content`, `characters`, `scene`), the derived `shot_size`, every
dependent slot's **current** `content_hash` read fresh from the live asset manifest at build
time (`_dependent_slot_records`), and `PROMPT_TEMPLATE_VERSION`. It deliberately does **not**
read the asset manifest's own `stale_beat_ids` — that field is a point-in-time diff the asset
pipeline computes against *its own* previous manifest snapshot on each `build_assets.py` run
(it clears to `[]` only once a subsequent no-op run confirms nothing changed further), not a
live comparison Phase 4 can trust between independent runs of the two pipelines. Bumping
`PROMPT_TEMPLATE_VERSION` by hand after any clause wording change is the lever that forces
every panel to redraw on the next ordinary run, without a manual `--force`.

**`--scene`/`--only` narrow generation, never the index.** A beat outside the current
selection is carried forward from the previous index unchanged (the whole-index rule) — all 49
beats stay in `output/panels/index.json` on every run, matching Phase 3's own `--only`
regression class.

**Panels generate from text only, this phase (D-08).** Reference-image conditioning was
spiked and proven working in 04-CONTEXT.md but held out deliberately; a later phase that
revisits it adds a second `contents` part to the `generate_content` call and nothing else in
this contract changes.

**The style constant is shared.** Panels import `STYLE_BLOCK` from `src/animatic/core/style.py`
— the same constant slot art uses (Phase 3 D-08) — never a second, per-phase style block.

**Scene-2 gate outcome, for Phase 7.** The developer's D-09 gate (2026-08-25) was
accept-with-note: all 49 beats have panels, and five defects are carried in
`.planning/WINDOWS.md` as open (`#6` crowd faces `s2b3`, `#7` two-figure close-up eyes
`s2b9`/`s2b5`, `#8` impact-reaction trace `s2b15`, `#9` possible partial signage `s2b19`, `#10`
confirmed signage lettering `s5b4`), plus one already-carried Phase 3 item (`#4`, a filled-black
garment shape). None block Phase 7 — re-evaluate in the assembled cut; `--force --only
<beat_id>` regenerates one panel in isolation if any read badly in motion.

## Phase 5 — Audio Contract

What Phases 6 and 7 read without re-deriving it — same register as the Beat, Asset Slot and
Panel Contracts above.

**Where it lives.** `output/audio/index.json` locally, `audio/index.json` in the media bucket.
Clips: `output/audio/<beat_id>.wav` locally, `audio/<beat_id>.wav` in S3, 24kHz 16-bit mono.
Music: `output/audio/music_<cue_id>.mp3`, stereo 44.1kHz. The index names `beats_source` and
`beats_generated_at` so it ties back to its input, and carries its own honest `s3_ok`/
`s3_reason`.

**`shot_secs` is the field Phase 7 cuts on — not `duration_secs`.** This is the one place the
audio index overrides the beat list, and it is the mechanism that makes ROADMAP criterion 5
true. Each entry carries `beat_duration_secs` (what Phase 2 planned), `audio_secs` (what the
clip actually measured) and `shot_secs` (what the shot must be), plus `shot_secs_source` —
`page_budget` when the beat already covered its audio, `audio_floor` when the audio forced the
shot wider — and `shot_secs_reason` stating the arithmetic. `shot_secs >= audio_secs` for every
entry, by construction. In the current corpus 44 of 49 shots keep their page budget and 5 were
widened, +5.66s in total, so the cut runs 261.4s against the beat list's 255.7s.

**Why widen rather than clip.** Same rule Phase 2 applied with its dialogue floor: a script line
is not ours to cut, so the shot yields to the speech. Narration is ours to write, so it yields
instead — an overrunning narration line is rewritten to the rate its own clip just measured and
regenerated once. Only if that still overruns does the shot widen on a narration beat.

**Measured, not assumed.** Speech rate is the phase's central fact and it was measured twice:
four smoke clips before any code, then all 31 narration clips of the first full run (min 1.56,
p10 1.82, median 2.16, p90 2.50, max 2.92 words/sec). Planning at the median made half the beats
overrun by construction, so `audio_timing.SAFE_WORDS_PER_SEC` is 1.8 — near p10. Every clip is
still measured after generation; the constant only plans text length. Index-vs-file duration
drift is 0.0000s across all 49.

**Silence is trimmed before anything is measured.** Every TTS clip arrives with ~0.25s of
lead-in and ~0.3-0.5s of trail-out, independent of length. On a 2.2s beat that padding is a
third of the shot. `audio_timing.trim_silence` removes the ends and keeps interior pauses,
which are delivery, not padding.

**Voices.** One `voice` per entry with a `voice_reason`. A character is cast once and the cast
is stored in the index, so a re-run reuses it — re-casting each run would give a character a
different voice between runs, which is what criterion 2 forbids. `NARRATOR_VOICE` is reserved
and never cast to a character, so narration stays audibly distinct. The model casts; a
deterministic guard then enforces every-part-cast, no-two-share, and not-the-narrator, recording
each intervention in the reason. Current cast: ROCKY Iapetus, CORNERMAN Rasalgethi, BLACK
FIGHTER Fenrir, ANNOUNCER Orus, PROMOTER Schedar, FIGHTER #1 Zephyr, FIGHTER #2 Umbriel, FAN
Puck, WOMAN Callirrhoe; narrator Charon.

**Music cues come from the SCRIPT, not the beat list.** `music_cues.find_music_cues` reads the
PDF scene text, unwraps it into sentences, and matches the sound sources a screenplay names
(radio, phonograph, record player, jukebox, band). Two cues in scenes 1-8: scene 3's dressing-
room radio (`s3b5`) and scene 8's phonograph (`s8b4`, `s8b5`). A script naming none produces
none. Each cue records `beat_ids`, `total_secs` and a reason quoting the script line.

**Named works are stripped before the prompt is built.** The script calls for a specific 1958
single by title; handing that title to a music model asks it to reproduce a copyrighted
recording. The cue is described by its staging instead — the phonograph, the room, the crackle.
Asserted on the built prompt string (`tests/test_music_cues.py`), never by reading the source
for a strip call, including a planted-title case so the guard is tested rather than the luck
that the real script keeps its title on a non-matching line.

**On-screen-text directives never reach the narrator.** Reuses Phase 3's
`style._strip_on_screen_text`. v1 read scene 2's SUPERIMPOSE directive aloud as the word
"Text."

**What the cache key covers.** `audio_generator.audio_cache_key` hashes `beat_id`, `kind`,
`text`, `voice`, `duration_secs` and `AUDIO_TEMPLATE_VERSION`. `duration_secs` is in the payload
unlike the panel key, because a changed duration means a changed narration budget. Bumping
`AUDIO_TEMPLATE_VERSION` re-plans narration as well as invalidating clips — the v1→v2 bump is
the worked example.

**Two rate limits, and the second one is the one that bites — but it is PER MODEL.** This
backend caps the TTS model at **10 requests/minute** AND **100 requests/day**, and the daily one
is scoped `GenerateRequestsPerDayPerProjectPerModel` — verified live 2026-08-25 by calling three
TTS models after one was exhausted; the other two answered normally. **So a spent model is not a
spent day.** `--tts-model gemini-2.5-flash-preview-tts` (or `settings.gemini_tts_model`) finishes
a run the default cannot. Every clip records the `tts_model` that voiced it and the index counts
them in `tts_models`, so a corpus split across two models is visible rather than discovered by
ear. The window is also ROLLING, not midnight-reset: requests age out gradually. The per-minute cap is handled by
pacing (`_TTS_MIN_INTERVAL_SECS`, 7.5s) plus a 429 that waits the interval the server names in
its own `RetryInfo`. The per-day cap cannot be paced around: it answers `retryDelay: 43424s`
(twelve hours), and a full run costs 49 calls plus one per overrunning narration retry, so **two
full runs in a day exhausts it.** A wait longer than `_DAILY_QUOTA_THRESHOLD_SECS` is recognised
as the daily cap and raises `DailyQuotaExhausted`, which halts the run.

**A failed regeneration never costs a working clip.** Three rules, each paid for by the v2 run:

1. A beat whose regeneration fails keeps its existing clip (`source: reused_after_failure`)
   rather than becoming a failure record. Before this, the v2 run turned a complete 49-clip
   index into 39 good entries and 10 failures while all ten clips sat playable on disk.
2. A beat whose previous entry has no clip is looked up on disk by the naming convention, and
   re-measured from the file — a failed generation never deletes what is already there.
3. The run **halts** on a daily cap and carries every remaining beat forward through the same
   recovery, rather than marching them into the same wall one at a time.

**Three index fields carry the resulting honesty**, and Phases 6/7/9 must read them:
`stale_beat_ids` (playable but behind the current template — re-run when quota allows),
`text_mismatch_beat_ids` (**the clip predates the `text` the index records for it — do not
caption or display `text` for these**), and `halted_reason` (non-null when a run stopped early).
A stale entry is never treated as a cache hit, or the recovery would defeat itself: a rescued
clip carries the cache key of the text it failed to generate.

**Current corpus state (2026-08-25):** 49/49 current at v2, 0 stale, 0 text-mismatched,
0 failed. Criterion 5 holds across all 49. **37 clips voiced on `gemini-3.1-flash-tts-preview`,
12 on `gemini-2.5-flash-preview-tts`** — scenes 5-8, almost all narration, generated on the
fallback after the primary's daily cap. Same prebuilt voice names, so the cast is unchanged;
whether the narrator audibly shifts around scene 5 is a judgement for an ear, not a test. To make
the corpus single-model, re-run with `--force` on a fresh day.

**`--scene`/`--only` narrow generation, never the index** — the whole-index rule, inherited from
Phase 4 and tested here.

## Phase 7 — Cut Contract

What Phases 6, 8 and 9 read. The last of the four contracts.

**Where it lives.** `output/video/animatic.mp4` and `output/video/index.json` locally,
`video/` in the media bucket. The manifest records `cut_sha256`, `planned_secs` (sum of
`shot_secs`) and `measured_secs` (probed from the finished file), so a cut can always be tied
to the shots it claims.

**Cut on `shot_secs` from the audio index — never `duration_secs` from the beat.** This is the
rule the phase turns on. Phase 2 planned durations from page geometry; Phase 5 measured the
audio and widened the shots that could not hold their own speech. Using the beat's number would
clip five shots in the current corpus. A beat with no audio entry falls back to its planned
duration and records `shot_secs_source: beat_duration` saying so. A `shot_secs` of 0 (a failed
clip) is not trusted — it would drop the beat out of the cut entirely.

**The shot-source seam is how Phases 6 and 8 both work.** `shot_sources.resolve_shot` picks the
highest-priority file that exists for a beat: real footage (`assets/footage/`), then motion
(`output/motion/`), then the still panel (`output/panels/`). Nothing else needs to change for
either phase — Phase 6 writes motion clips into its directory and Phase 8 accepts footage into
its own. **Proven live 2026-08-25**: dropping `s2b2.mp4` into `assets/footage/` put 8.8s of the
real film into the cut (`real_footage_pct` 3.4%), and deleting it restored the panel — FR-07 and
Phase 8's criterion 4, working two phases early.

**Beat number comes from the FILENAME, never from the footage** (PROJECT.md non-goal).
`s2b2.mp4` and `s2b2-take3.mp4` both match; `s2b50.mp4` and `rocky_fight_final.mp4` do not. Two
takes for the same beat resolve on sorted name so the cut is reproducible.

**Real footage keeps the cut's audio, not its own.** The extracted clip is muxed silent and the
beat's synthesised narration or dialogue plays over it, so the audio bed stays continuous across
a swap. Revisit if a swapped shot should carry production sound.

**A clip is never re-timed to fit its shot.** Motion shorter than its shot holds its last frame
(`tpad=stop_mode=clone`); longer is trimmed. Speeding or slowing would misrepresent the motion
that was generated. The audio sets the length because the audio is what a viewer notices.

**Frame: 1280x720, 24fps, white pad.** Panels are 1376x768, so the cut scales down and pads
rather than distorting. The pad is **white** — the house style is black line art on white, and
black bars around a white frame read as a rendering fault rather than a letterbox.

**`real_footage_pct` is by SCREEN TIME, not shot count** (FR-08). One 12-second replaced shot is
more of the cut than three 2-second ones.

**Audio warnings ride along.** `stale_audio_beat_ids` and `text_mismatch_beat_ids` are copied
from the audio index onto the cut manifest, so a reader need not open two files to learn the cut
contains stale or mislabelled audio. **Phase 9 must not caption from `text` for the mismatch
set.**

**Current cut (2026-08-25):** 49 shots, scenes 1-8, 262.1s measured against 261.77s planned
(6.7ms per shot, sub-frame rounding at 24fps). 0 shots clip their audio. Two renders exist —
`animatic.mp4` (all panels) and `animatic-partial.mp4` (one real shot). The third required by
the Definition of Done, all-footage, needs footage for all 49 beats.

## Deadline

2026-09-09 14:00 PDT

## Decisions

- [Phase ?]: Phase 3 Plan 01: slot_resolver resolves 16 slots (9 char + 7 loc); rank 1 rocky, rank 2 int_blue_door_fight_club; image prompts must strip color words from location names to avoid the model painting that color onto whatever it names
- [Phase 3]: Plan 02: reference art matched by slot_directory (wins outright) then filename_token (token-subset, not substring); generate_missing_art groups by art_slot_id and orders by min priority_rank so shared slots generate at their highest-priority member's rank; s3_writer.put_bytes centralizes all S3 writes in the codebase behind one honest S3Result
- [Phase 3]: Phase 3 Plan 03: real 16-slot manifest + 13 art files shipped; rocky is now generated (not reference-backed) per 5f581e0's slot-directory-only rule; strengthened no-facial-features subject clause fixed a repeat regression; Asset Slot Contract settled in STATE.md for Phase 4/5
- [Phase 4]: Phase 4 Plan 01: panel pipeline (panel_prompt/panel_generator/panel_manifest/build_panels.py) proven end-to-end on tracer beat s2b7; cache-hit reuse, retry, and whole-index carry-forward implemented under TDD; close-up facial clause (D-05, [ASSUMED]) visually failed on first live generation (eyes fully rendered) — flagged in WINDOWS.md entry 5 for 04-02 to revise
- [Phase 4]: Phase 4 Plan 02: scene 2's 19 panels reviewed against six points across two revision passes (PROMPT_TEMPLATE_VERSION v1→v2→v3); WINDOWS.md entry 5 fixed; four new open entries (#6-#9 — crowd faces, two-figure close-up eyes, impact-reaction trace, possible signage). Developer's D-09 gate: accept-with-note — generate the remaining 30 beats, carry all four (plus a solid-black-fill and cartoon-impact-stars finding) forward, revisit only if they hurt the assembled cut in Phase 7; two-pass ceiling spent, not extended
- [Phase 4]: Phase 4 Plan 03: remaining 30 beats generated (49/49 panels, 8 wide/23 medium/18 close-up); s5b4 confirmed D-12's predicted lettering-leak risk live outside scene 2 (WINDOWS.md #10); the panel cache proven on real files — an unchanged re-run reused all 49, and swapping a slot's art bytes invalidated exactly its one dependent beat (s7b1), closing Phase 3's own deferred criterion 4 — though the live regeneration call itself hit a Gemini billing wall (429, prepayment credits exhausted) and the settled state was reached by repairing the index entry through the project's own cache-key/index-write functions against the untouched, verified-identical prior panel rather than a fresh live call; Panel Contract settled in STATE.md for Phase 5/6/7; a bug found in 04-03-PLAN.md's own Task 2 verify script (dict-unpacking `slot_hashes` by key instead of value) documented, not fixed (out of files_modified)

## Session

**Last session:** 2026-08-25T10:10:23.679Z
**Stopped at:** Completed 04-03-PLAN.md — full run, cache proof, Panel Contract; Phase 4 complete
**Resume file:** None

## Performance Metrics

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 3 P01 | 32min | 3 tasks | 9 files |
| Phase 3 P02 | 62min | 3 tasks | 7 files |
| Phase 3 P03 | 25min | 3 tasks | 5 files |
| Phase 4 P01 | 24min | 3 tasks | 7 files |
| Phase 4 P03 | 29min | 3 tasks | 4 files |
