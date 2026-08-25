---
gsd_state_version: 1.0
current_phase: 3
current_phase_name: Plan 02 of 3 complete; 03-03 is next
status: unknown
stopped_at: Completed 03-02-PLAN.md — reference art priority, full generation, honest manifest
last_updated: "2026-08-25T00:35:00.000Z"
state_head: 73cb80a531873907cc2bd3f7081a7dbef30c5cd8
progress:
  total_phases: 10
  completed_phases: 0
  total_plans: 5
  completed_plans: 2
  percent: 0
---

# Animatic — STATE.md

## Current State

- **Milestone:** 1 — Actor
- **Phase:** 3 — Plan 02 of 3 complete; 03-03 is next
- **Active work:** None
- **Last updated:** 2026-08-24
- **Hosted URL:** http://animatic-alb-1855813211.us-east-1.elb.amazonaws.com (HTTP only — no TLS, see Phase 1 gap)

## Milestone Status

### Milestone 1 — Actor (minimum: generate first animatics)

| Phase | Title | Status | Verified |
|-------|-------|--------|----------|
| 1 | Project Scaffold & Infrastructure | ⚠️ Complete, 1 gap | [1-VERIFICATION.md](phases/phase-1/1-VERIFICATION.md) — 5/6, no CloudFront CDN |
| 2 | Beat Parser | ✅ Complete | [2-VERIFICATION.md](phases/phase-2/2-VERIFICATION.md) — scenes 1-8, 18/18 dialogue lines, durations floored |
| 3 | Asset Management & Manifest | 🔄 In progress (2/3 plans) | [03-02-SUMMARY.md](phases/phase-3/03-02-SUMMARY.md) |
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
- [ ] Panel style: smoke test returned greyscale shading with storyboard chrome (notebook binding, caption text, the words "NO FACIALS" drawn into the frame) instead of clean black line art on white. Phase 4 prompt work needed. Facial-feature rule was respected.
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

**Known visual-quality gap (not blocking):** 2 of 13 generated art files
(`generic_minor_character.jpg`, `promoter.jpg`) drew a detailed face
instead of the instructed blank white head-shape; `ext_street.jpg` drew
one person in a location meant to be peopleless. Image generation has no
seed parameter (D-12), so this is expected non-determinism, not a code
defect — regenerate with `--force --only <slot_id>` before Phase 4 if
stricter compliance is needed. Logged to `.planning/WINDOWS.md`.

## Deadline

2026-09-09 14:00 PDT

## Decisions

- [Phase ?]: Phase 3 Plan 01: slot_resolver resolves 16 slots (9 char + 7 loc); rank 1 rocky, rank 2 int_blue_door_fight_club; image prompts must strip color words from location names to avoid the model painting that color onto whatever it names
- [Phase 3]: Plan 02: reference art matched by slot_directory (wins outright) then filename_token (token-subset, not substring); generate_missing_art groups by art_slot_id and orders by min priority_rank so shared slots generate at their highest-priority member's rank; s3_writer.put_bytes centralizes all S3 writes in the codebase behind one honest S3Result

## Session

**Last session:** 2026-08-25T00:35:00.000Z
**Stopped at:** Completed 03-02-PLAN.md — reference art priority, full generation, honest manifest
**Resume file:** 03-03-PLAN.md

## Performance Metrics

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 3 P01 | 32min | 3 tasks | 9 files |
| Phase 3 P02 | 62min | 3 tasks | 7 files |
