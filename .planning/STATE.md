# Animatic — STATE.md

## Current State
- **Milestone:** 1 — Actor
- **Phase:** 2 — Complete; Phase 3 is next
- **Active work:** None
- **Last updated:** 2026-08-24
- **Hosted URL:** http://animatic-alb-1855813211.us-east-1.elb.amazonaws.com (HTTP only — no TLS, see Phase 1 gap)

## Milestone Status

### Milestone 1 — Actor (minimum: generate first animatics)
| Phase | Title | Status | Verified |
|-------|-------|--------|----------|
| 1 | Project Scaffold & Infrastructure | ⚠️ Complete, 1 gap | [1-VERIFICATION.md](phases/phase-1/1-VERIFICATION.md) — 5/6, no CloudFront CDN |
| 2 | Beat Parser | ✅ Complete | [2-VERIFICATION.md](phases/phase-2/2-VERIFICATION.md) — scenes 1-8, 18/18 dialogue lines, durations floored |
| 3 | Asset Management & Manifest | ⬜ Not started | — |
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
- [ ] Shot rhythm vs runtime: runtime is now pinned to the page budget (4.26 min), so
      the only remaining lever on average shot length is beat COUNT. 49 beats over
      255.7s gives a 5.2s average; ~64 beats would give ~4s. Decide the target rhythm.
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
their speech. Average shot 5.2s.

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

## Deadline
2026-09-09 14:00 PDT
