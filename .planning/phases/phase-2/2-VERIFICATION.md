---
phase: 2-beat-parser
verified: 2026-08-24T06:03:28Z
revised: 2026-08-24T09:10:00Z
status: human_needed
score: 6/6 must-haves verified
behavior_unverified: 1
overrides_applied: 0
verified_against_commit: 2213ac3d9eb046f7379e69236d99da8c9f3bcb99
note: >-
  Retroactive verification, revised twice. The first pass scored this 6/6 and
  certified scene segmentation on the strength of a docstring claim that Rocky
  "omits scene 2". That claim was false, and three defects sat behind it. All
  are now fixed and the beat list has been regenerated.
gaps_closed:
  - truth: "Scene segmentation isolates the demo scene set (scenes 1-8)"
    closed: "Heading regex no longer requires an INT./EXT. slug; first 8 scenes = 1-8, scene 2 restored with the full 532-word fight"
  - truth: "The beat list covers the demo scene set"
    closed: "Regenerated 2026-08-24 — 36 beats over scenes 1-8, written to output/beats.json and s3://animatic-media-628818/beats/latest.json"
  - truth: "Dialogue survives into the beat list"
    closed: "Beat.dialogue is now list[{character,line}]; 18/18 script lines captured and attributed (was 7/18)"
  - truth: "Dialogue beats are long enough to speak their lines"
    closed: "duration floor of words/2.5 + 0.5/line applied; 0 beats shorter than their speech, 4 raised, each recording duration_source and a reason"
behavior_unverified_items:
  - truth: "The deployed service parses beats live on request"
    test: "POST /beats/parse against the hosted ALB URL"
    expected: "200, s3_uri beginning s3://, fresh LastModified on beats/latest.json"
    why_human: "Spends a real Gemini call and overwrites the stored beat list"
human_verification:
  - test: "POST /beats/parse on the hosted URL, then re-check S3 LastModified"
    expected: "200, s3_uri starts with s3://, fresh object in the bucket"
    why_human: "The brief requires live beat parsing on the demo; must pass before Phase 9"
  - test: "Read the 36 beats against the script and judge pacing"
    expected: "Agreement that 196.4s (3.3 min) is the right runtime for ~5.8 min of screen time"
    why_human: "Pacing is an editorial judgement, not a checkable invariant"
---

# Phase 2: Beat Parser — Verification Report (revised)

**Phase Goal:** Ingest Rocky PDF → structured beat list with machine-readable reasons.
**Verified:** 2026-08-24T06:03:28Z · **Revised:** 2026-08-24T09:10:00Z
**Status:** human_needed — all gaps closed; live-endpoint check and a pacing call remain
**Re-verification:** Second revision of the initial retroactive pass

## What the first pass got wrong

The initial report scored this phase 6/6 and called segmentation ✓ VERIFIED. It was
wrong, and the way it went wrong is worth recording.

`pdf_extractor.extract_scenes` carried a docstring asserting Rocky "skips scene 2".
Evidence was then gathered *consistent with* that claim — every line containing
`INT.`/`EXT.` was checked against the regex, all matched, and the regex was pronounced
complete. But the check inherited the docstring's premise. Checking `INT.`/`EXT.` lines
against an `INT.`/`EXT.` pattern can only ever confirm itself; it cannot see a scene
that has neither. The question never asked was the plain one: **where is scene 2?**

It is on page 1:

```
2 SUPERIMPOSE OVER ACTION... "NOVEMBER 12, 1975 - 2
PHILADELPHIA"
... The club itself resembles a large unemptied trash-can.
```

Generic `N … N` matching finds **121** numbered headings where the old pattern found
107. The script's scenes run contiguously 1–122 (scene 93's trailing number is mangled
by pdfplumber as `9B3EN`). So "scenes 1 through 8" in the brief was literal and correct
all along — the parser was returning 1,3-9.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | PDF ingestion works on the real script | ✓ VERIFIED | 127,358 chars via pdfplumber |
| 2 | Scene segmentation isolates scenes 1-8 | ✓ VERIFIED (fixed) | Was `[1,3,4,5,6,7,8,9]`; now `[1,2,3,4,5,6,7,8]`. Scene 2 carries 532 words |
| 3 | Beat extraction is density-aware | ✓ VERIFIED | 13 beats for the fight (scene 2) → 1 for the hallway (scene 7) |
| 4 | Every beat carries beat_id, scene, type, content, reason, duration_estimate | ✓ VERIFIED | 36/36 beats, all fields non-empty, ids unique |
| 5 | Beat list serialised to JSON and stored | ✓ VERIFIED | `output/beats.json` + `s3://animatic-media-628818/beats/latest.json`, regenerated 2026-08-24 |
| 6 | Unit tests cover the parser | ✓ VERIFIED | **19 passed**, including scene-2, dialogue-attribution and duration-floor guards |

**Score:** 6/6 truths verified

### Current output

| Metric | Value |
|--------|-------|
| Beats | 36 across scenes 1-8 |
| Runtime | 196.4s (3.3 min) |
| Dialogue lines captured | **18/18 (100%)**, every one attributed to a single speaker |
| Unattributed lines | 0 |
| Beats shorter than their own speech | **0** |
| Durations raised by the floor | 4 (`s2b7`, `s2b8`, `s3b2`, `s3b5`) |
| Motion candidates | 4 |

## The three defects behind the first pass

**1. Scene 2 dropped (BLOCKER).** Covered above. Its 532 words — the entire opening
fight — were absorbed into scene 1, which is a bare 37-char slug line. Scene 9 was
wrongly pulled in to make up the count of 8.

**2. Dialogue exchanges collapsed into one string.** `Beat.dialogue` was a single
`str`, and the prompt asked for *"the key line of dialogue"* while instructing the model
to *"group coherent exchanges into one beat each"*. A back-and-forth could not be
represented, so it came back merged:

```
"Ya movin' like a bum -- Want some advice -- Just gimme the water."
    └─ CORNERMAN ─┘                          └─ ROCKY ─┘
```

attributed to `ROCKY/CORNERMAN`, with Rocky's `Absolutely.`, the cornerman's
`... Ya want some good advice?` and `... I just want the mouthpiece.` dropped entirely.
Only 7 of 18 script lines survived. PROJECT.md requires "synthetic dialogue for every
speaking part", and Phase 5 assigns a voice per character — neither is possible against
a blob. `dialogue` is now `list[{character, line}]`; coverage is 18/18.

**3. Durations under-ran their own dialogue.** 4 of 10 dialogue beats allocated less
time than their lines take to speak. Since Phase 5 synthesises per beat and Phase 7 cuts
each shot to `duration_secs`, that is clipped speech or A/V drift. A floor of
`words / 2.5 + 0.5 per line` is now applied, and each adjustment records
`duration_source: dialogue_floor` plus a written justification in `reason`, so shot
duration keeps the machine-readable reason PROJECT.md requires.

Also fixed: **`_BEAT_SCHEMA` was dead code.** It was defined but never passed to the
API, which sent only `response_mime_type="application/json"`. It is now wired through
`response_schema`, so beat structure is enforced by the model rather than hoped for.

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/animatic/core/pdf_extractor.py` | PDF → scene text | ✓ PASS | Generic heading match; scene 2 restored |
| `src/animatic/core/beat_extractor.py` | Scene text → beats | ✓ PASS | `Line` dataclass, duration floor, schema wired |
| `src/animatic/core/beat_assembler.py` | Assemble + persist | ⚠️ PARTIAL | Works, but swallows `ClientError` — see below |
| `src/animatic/api/beats.py` | `POST /beats/parse` | ✓ PASS | Wired at `:67` |
| `scripts/parse_beats.py` | CLI entrypoint | ✓ PASS | Wired at `:78` |
| `tests/test_beat_parser.py` | Parser tests | ✓ PASS | 19 tests |
| `output/beats.json` | Serialised output | ✓ PASS | Regenerated, scenes 1-8 |

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `pdf_extractor.py` | 15–18 | INT/EXT-only heading match | **BLOCKER — fixed** | Dropped scene 2 and 13 others script-wide; shifted the demo range |
| `beat_extractor.py` | 34, 55 | Single-string `dialogue` | **BLOCKER — fixed** | 11 of 18 script lines lost; blocked per-character voices in Phase 5 |
| `beat_extractor.py` | 42 | `_BEAT_SCHEMA` never passed to the API | WARNING — fixed | Structure unenforced; `response_schema` now set |
| `beat_assembler.py` | 86–88 | `ClientError` swallowed, returns `local://` | **WARNING — open** | `POST /beats/parse` answers 200 even when the S3 write failed. Phases 3–8 read from S3, so failure surfaces far from its cause |
| `beat_assembler.py` | 74 | `boto3.Session(profile_name=…)` | WARNING — open | `ProfileNotFound` isn't a `ClientError` — raises uncaught. Dev path only |
| `pdf_extractor.py` | — | Scene 93's trailing number mangled by pdfplumber (`9B3EN`) | INFO | Outside the 1-8 demo range; ignore unless scope widens |

## Open question: pacing

36 beats total 196.4s (3.3 min) against ~1,104 source words — roughly 5.8 minutes of
screen time at the standard ~190 words/page ≈ 1 minute heuristic. The duration floor
moved this from 2.6 to 3.3 min, but the animatic still runs about half the intended
length. For a tool whose stated purpose is judging whether a story works before it is
shot, pacing is the thing being judged, so this is worth an explicit decision rather
than an inherited default. Not a defect — a call for the owner.

## Gaps Summary

No open gaps. All four closed items are fixed in code, pinned by tests, and reflected in
regenerated data. Two `beat_assembler` robustness warnings remain open and are best
folded into Phase 3, which writes manifests to the same bucket. Status is
`human_needed` rather than `passed` because the deployed service's live-parse path is
still unexercised and the pacing question is unanswered.
