# Phase 4: Panel Generation - Context

**Gathered:** 2026-08-24
**Status:** Ready for planning

<domain>
## Phase Boundary

One black line-art panel per beat — 49 panels across scenes 1-8 — in a consistent style,
obeying PROJECT.md's facial-feature rules, each carrying beat_id, the asset slots it used,
its prompt and a machine-readable reason. Panels cache so an unchanged beat is not
regenerated.

NOT this phase: audio (Phase 5), motion (Phase 6), assembly into video (Phase 7).

</domain>

<decisions>
## Implementation Decisions

### Shot size
- **D-01:** Shot size is **derived deterministically from beat type**, no model call:
  `establishing → wide`, `action → medium`, `dialogue → close-up`. Free, testable,
  predictable across 49 beats, and it produces defensible grammar — the fight plays in
  wides and mediums, exchanges play close.
- **D-02:** Shot size is a **derived field computed alongside beats, never written back
  into the beat list.** Beats stand as initially rendered (roadmap S-02 decision); adding
  a field to them would contradict that and invalidate the Phase 3 manifest's hashes.
- **D-03:** **Rejected: generate at one framing and crop in.** The user offered it as a
  cheaper path and it is a reasonable instinct, but it fails on the one rule it has to
  serve. A close-up is the shot size that needs MORE face detail (brow, mouth, nose), so
  cropping into a featureless panel yields a blank face at high magnification, plus
  upscaling artifacts on line art. We already make one call per beat; the shot size costs
  nothing extra inside that call.
  — **Reversibility:** reversible — a prompt clause and a mapping table.
- **D-04:** Every panel records its shot size AND the rule that assigned it, following the
  `duration_source` precedent from Phase 2 (NFR-04).

### Facial features (PROJECT.md, non-negotiable)
- **D-05:** The facial rule is keyed off shot size: wide and medium carry **no** facial
  features; close-ups carry **brow line, mouth line and nose only** — never eyes, never
  full rendering.
- **D-06:** State it positively, never as a negation, and place it LAST in the prompt.
  This is the hardest-won lesson of Phase 3 and it cost several regenerations to learn:
  negations get rendered as literal text ("NO FACIALS" was painted into a frame), and a
  rule stated mid-prompt loses to whatever follows it. Both the character-isolation fix
  and the empty-room fix came down to moving the rule to the end.
- **D-07:** Name no object that is not wanted in the picture. The blank-face wording
  bounded the face by "the hairline, hat brim and jaw contour" and put a hat on every
  character in the film, including a boxer in trunks. `tests/test_style.py` guards the
  character prompt against headwear and garment nouns; the panel prompt needs the same
  guard.

### Reference conditioning
- **D-08:** **HELD — not used in Phase 4.** Multi-image conditioning was spiked and works
  (`output/experiments/refcond_panel.jpg`: the black_fighter plate plus the fight-club
  plate returned one composed panel keeping both). The capability is proven and S-03's
  risk is closed, but the user has explicitly held it out of this phase. Panels generate
  from text — the beat, the shot size, and the slot descriptions from the Phase 3 manifest.
  — **Reversibility:** reversible — an additional `contents` part on the call.

### Iteration strategy
- **D-09:** **Tracer scene, then the rest.** Generate scene 2's panels first — the fight,
  19 beats, the highest-value and highest-density scene — and put them in front of the user
  before generating the other 30. Phase 3 needed several rounds of looking at pictures to
  find output that was subtly wrong; catching a systemic prompt defect on 19 panels rather
  than 49 is the point.
- **D-10:** Budget context: generation runs ~10s per image, so a full 49-panel run is
  roughly 8-9 minutes. Caching (criterion 5) means a re-run after a fix only regenerates
  what changed.

### Known carry-forwards from Phase 3
- **D-11:** `promoter` reads as a modern staffer with a clipboard and lanyard, because
  scene 3's beats describe a dressing room and never mention the sport. Thin scene context
  is a live failure mode for any character whose scenes do not describe their world. It
  affects panels the same way it affected slots.
- **D-12:** Text still leaks onto LOCATION art occasionally (a "BOX'S GYM" sign appeared
  once). The Phase 3 guard covers character prompts only. Panels render rooms, so they
  inherit this risk.

### Claude's Discretion
- Panel storage layout, naming, and manifest/index format.
- Cache key composition — must at minimum cover beat content, shot size, and the slot
  art each panel depends on, so Phase 3's `stale_beat_ids` signal actually drives redraws
  (this is what closes ROADMAP criterion 4 from Phase 3).
- Whether panels are written to S3 per-panel or batched.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract
- `.planning/ROADMAP.md` §Phase 4 — goal and 5 success criteria
- `.planning/REQUIREMENTS.md` §FR-03 (panels), §NFR-03 (Google SDK only), §NFR-04 (reasons)
- `.planning/PROJECT.md` §Visual Style — the facial-feature and line-weight rules

### Upstream data consumed
- `output/beats.json` — 49 beats, scenes 1-8; `type` drives shot size, `content` drives subject
- `output/assets/manifest.json` — 16 slots with descriptions, art, `content_hash`, `beat_ids`
- `.planning/STATE.md` §"Phase 3 — Asset Slot Contract" — the handoff contract
- `.planning/phases/phase-3/03-VERIFICATION.md` — what Phase 3 actually delivered vs claimed

### Prior art that must be reused, not reinvented
- `src/animatic/core/style.py` — `STYLE_BLOCK` (shared style, D-08 of Phase 3),
  `describe_slot`, `character_context`, `_strip_on_screen_text`
- `src/animatic/core/asset_generator.py` — the working image call shape and the
  subject-note patterns, including the ordering lessons
- `src/animatic/core/s3_writer.py` — the honest `put_bytes`/`S3Result`
- `tests/test_style.py` — the value-level guard pattern (assert on the built string,
  never grep the source file)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `STYLE_BLOCK` is already the single style definition; panels must use it, not a variant.
- The image call shape is settled: `generate_content(model=..., contents=...,
  config=GenerateContentConfig(response_modalities=["IMAGE"]))`, NO `system_instruction`.
- `content_hash` + `stale_beat_ids` from Phase 3 are the caching signal.

### Established Patterns
- Prompt rules are stated positively and placed LAST.
- Guards assert on built strings, never on source files.
- Every generated value carries the rule that produced it.
- Deterministic post-processing over model output rather than trusting the model alone.

### Integration Points
- Reads `output/beats.json` and `output/assets/manifest.json`.
- Writes panels plus an index to `output/panels/` and S3.
- Phase 7 assembles panels in beat order at each beat's duration.

</code_context>

<specifics>
## Specific Ideas

- "you decide -- have gemini pick a shot or keep it standard and then you crop to the
  middle. let's just get to v1" — decision delegated; cropping considered and rejected
  in D-03 for a specific reason, not on principle.
- "Tracer scene, then the rest" — D-09.
- "let's wait on use of reference images" — D-08.
- Standing preference: best first pass, ship it, do not chase the ten reasons it is
  imperfect.

</specifics>

<deferred>
## Deferred Ideas

- Reference-image conditioning for panels (proven working, held by the user — D-08).
- S-01 slot description override, S-02 beat stretch — Phase 9 backlog.
- Fixing `promoter`'s thin context at the slot level — carried as D-11, not this phase's goal.

</deferred>

---

*Phase: 4-Panel Generation*
*Context gathered: 2026-08-24*
