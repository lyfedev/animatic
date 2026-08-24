# Phase 3: Asset Management & Manifest - Context

**Gathered:** 2026-08-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Named asset slots, temp-art fallback, and a manifest. Every character and location
referenced by the beat list resolves to exactly one slot; supplied reference art fills
the slots it covers; every remaining slot is filled by generated temp art so the
pipeline never blocks on a missing input. Output is an asset manifest recording slot
name, priority, source and reason.

Scope anchor from the current beat list: **17 slots — 9 characters, 8 location
headings.** Supplied reference art covers Rocky only, so 16 slots need generated art.

NOT this phase: generating the per-beat panels themselves (Phase 4), voice synthesis
(Phase 5). This phase establishes the slot registry those phases consume.

</domain>

<decisions>
## Implementation Decisions

### Slot Identity
- **D-01:** Slot identity is resolved **automatically, with no human alias list**. The
  system makes its best guess and records how it guessed. A first pass does not get
  hand-curated input.
- **D-02:** A scene whose heading is not an `INT.`/`EXT.` slug **inherits the location
  of the preceding scene**. This is deterministic and fixes the known case: script
  scene 2 is a `SUPERIMPOSE` title card with no slug of its own, and the extractor
  invented `INT. BOXING CLUB - NIGHT` for it while script scene 1 calls the same room
  `INT. BLUE DOOR FIGHT CLUB - NIGHT`. Same room, two names, two would-be slots.
  — **Reversibility:** reversible — a resolver rule, local to slot assignment.
- **D-03 (CORRECTED 2026-08-24):** Beyond the inheritance rule, resolve remaining
  headings by normalising the time-of-day suffix and punctuation, then clustering what
  is left semantically. Every merge records both source headings and why they were
  judged the same place, so a wrong guess is visible in the manifest rather than silent.

  **`INT.` and `EXT.` are NOT normalised away.** The original wording said to drop them;
  that was wrong. Research caught it: dropping the prefix merges scene 6
  `EXT. ROCKY'S APARTMENT - NIGHT` with scene 8 `INT. ROCKY'S APARTMENT - NIGHT`. Same
  building, entirely different picture — a street-facing facade at night versus a
  one-room interior. A location slot exists to hold *art*, so interior and exterior of
  one address are two slots. Correct count is **7 locations**, not 6 (over-merged) and
  not 8 (scene 2 unmerged).
  — **Reversibility:** reversible — merges are data in the manifest, re-runnable.
- **D-03a:** Ground truth for "does this scene have a real slug" is the PDF, not
  `beats.json`. Verified 2026-08-24: `scene_heading` in the beat list is model output,
  and scene 2 is the *only* scene where it diverges from the script — every other scene
  copied the slug verbatim. So D-02 must test the raw heading from
  `pdf_extractor.extract_scenes()` against a slug regex. That is a local PDF re-read,
  no LLM cost.

### Character Slots and Voices
- **D-04:** **Art slots and voice identities are separate axes and do not collapse the
  same way.** Minor characters share generic *visual* slots; they must not share
  *voices*.
- **D-05:** Minor characters (1-2 beats, unnamed function roles — `FIGHTER #1`,
  `FIGHTER #2`, `FAN`, `ANNOUNCER`) map to **generic art slots** rather than getting
  bespoke generated character art.
- **D-06:** **Two characters who speak in the same scene must never be given the same
  voice.** `FIGHTER #1` and `FIGHTER #2` talk to each other in scene 3 — sharing a
  generic art slot is fine, sharing a voice is not, because the exchange becomes one
  person talking to themselves. Voice identity is therefore per named character, not
  per art slot, and the registry must enforce distinctness within a scene.
  — **Reversibility:** costly — Phase 5 casts voices from this key; changing the axis
  later means recasting and regenerating all dialogue audio.
- **D-07:** All 9 characters in the beat list speak, so the slot registry doubles as
  the voice registry Phase 5 consumes. Build the key once here rather than twice.

### Style Consistency
- **D-08:** A **shared generic style prompt** drives consistency across all generated
  slots — one style definition applied to every generation, rather than per-slot
  prompt wording.
  — **Reversibility:** reversible — regenerating temp art is cheap.
- **D-09:** The style prompt must actively suppress the failure modes observed in the
  Google AI smoke test (2026-08-24): the model returned greyscale with heavy shading
  instead of black line art on white, added storyboard chrome (spiral notebook binding,
  a panel caption), and rendered instruction words into the frame as artwork. Notably
  the phrase "storyboard panel" *caused* the chrome. The facial-feature rule was
  respected. Evidence: `output/smoke/panel_test_0.png`.

### Manifest Priority
- **D-10:** User did not have a definition in mind, so priority is defined here as
  **how much of the finished cut depends on the slot** — its share of total screen
  time, not a generation order or a cost band. Rocky appears in 31 of 49 beats; the
  hallway appears in 1. If Rocky's art is wrong the whole animatic is wrong.
- **D-11:** This definition serves every downstream use at once: it is the order to
  generate in, the order to spend budget on, and — the actionable one — the ranked
  answer to "which slots would most benefit from real reference art being supplied".
  Each entry records the underlying numbers (beats, seconds, share) as its reason, so
  the ranking is checkable rather than asserted.
  — **Reversibility:** reversible — a derived field, recomputable from the beat list.

### Known-Good Image Call (do not re-spike)
- **D-12:** The smoke test that produced `output/smoke/panel_test_0.png` used
  `client.models.generate_content(model="gemini-3.1-flash-image", contents=<prompt>,
  config=types.GenerateContentConfig(response_modalities=["IMAGE"]))` with the
  `GOOGLE_API_KEY` backend and **no** `system_instruction`. The image came back as
  `inline_data` on a part of `candidates[0].content.parts`, mime `image/jpeg`, 697 KB.
  Research flagged that `system_instruction` with an image-output model raises
  `ClientError` on the API-key backend — consistent with the above, since the working
  call did not use it. **Fold the D-08 shared style block into the prompt text.** No
  spike task needed to rediscover this call shape.

### Claude's Discretion
- Slot naming scheme and manifest file format and location.
- Which specific generic art slots exist and how a character is judged "minor".
- Change-detection mechanism for slot-file replacement (content hash vs mtime) and
  what a replacement invalidates — user did not raise it; default to content hashing,
  which is re-runnable and does not depend on filesystem timestamps.
- How the style prompt is expressed and where it lives.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract
- `.planning/ROADMAP.md` §Phase 3 — goal, 5 success criteria, dependencies
- `.planning/REQUIREMENTS.md` §FR-02 — asset management requirements
- `.planning/REQUIREMENTS.md` §NFR-03 — Google Cloud SDK only, no other AI APIs
- `.planning/REQUIREMENTS.md` §NFR-04 — every artifact carries a machine-readable reason

### Visual style rules
- `.planning/PROJECT.md` §Visual Style — black line art on white, consistent line
  weight, no facial features in wide/medium, close-ups carry brow/mouth/nose only

### Upstream data this phase consumes
- `output/beats.json` — 49 beats, scenes 1-8; `characters[]` and `scene_heading` are
  the inputs to slot resolution
- `src/animatic/core/beat_extractor.py` — `Beat` and `Line` dataclasses; `Line.character`
  is the voice key
- `.planning/phases/phase-2/2-VERIFICATION.md` — records why scene 2 has no slug of its
  own, which is the root of the duplicate-location case

### Prior art in the codebase
- `src/animatic/core/beat_assembler.py` — S3 write pattern and the local+S3 dual write;
  note its open warning (swallows `ClientError`, returns `local://` while the API still
  answers 200) — worth fixing here since this phase writes manifests to the same bucket
- `.planning/STATE.md` §Google AI Access — smoke-tested model ids and results

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `beat_assembler.assemble_and_write`: established local+S3 write pattern for a
  generated artifact; the manifest writer should follow it.
- `config.Settings`: typed pydantic settings already carry `google_api_key`,
  `gemini_model` and `media_bucket`.
- `gemini-3.1-flash-image` verified working via `GOOGLE_API_KEY` — 697 KB image
  returned, no allowlist gating.

### Established Patterns
- Every generated artifact carries a `reason` field; Phase 2 extended this with
  `duration_source` to name *which rule* set a value. The manifest should follow the
  same shape — a value plus the rule that produced it.
- Deterministic post-processing over model output: Phase 2 asks the model for the right
  shape in the prompt *and* enforces it in code (`_split_speaker_turns`). Slot
  resolution should do the same rather than trusting the model alone.
- Tests pin exact expected sets rather than counts (`test_extract_scenes_returns_scenes_1_to_8`).

### Integration Points
- Reads `output/beats.json` (or the S3 copy) for characters and scene headings.
- Writes a manifest alongside `beats/latest.json` in `s3://animatic-media-628818`.
- Phase 4 consumes slots to build panel prompts; Phase 5 consumes voice identities.

</code_context>

<specifics>
## Specific Ideas

- "this will have to make a first pass without help. Your slot identity has to make
  it's best guess." — no hand-curated alias map in the first pass.
- "minor characters should be generic, but two identical voices can't talk to each
  other." — the constraint that separates art slots from voice identities (D-04, D-06).
- "i think you need a generic style prompt to drive consistency." — D-08.
- "i dpn't know what the manifest priority is." — definition proposed in D-10/D-11 for
  review at plan time.
- Standing preference from this session: ship a best first pass; do not stall on the
  ten reasons it is not yet perfect.

</specifics>

<deferred>
## Deferred Ideas

- Hand-curated slot alias map / human-in-the-loop slot correction — explicitly excluded
  from the first pass (D-01). Revisit if automatic resolution proves wrong on inspection.
- CloudFront CDN and TLS for the hosted URL — Phase 1 gap, now in the roadmap backlog.
- `beat_assembler` robustness (swallowed `ClientError` returning `local://` under a 200;
  uncaught `ProfileNotFound`) — not this phase's goal, but this phase writes to the same
  bucket, so fold the fix in if it is cheap.

</deferred>

---

*Phase: 3-Asset Management & Manifest*
*Context gathered: 2026-08-24*
