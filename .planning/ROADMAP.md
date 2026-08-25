# Roadmap: Animatic

## Overview

From a screenplay PDF to a watchable rough cut, then to a hosted demo that swaps real
footage in shot by shot. Milestone 1 (Actor) builds the generation pipeline end to end —
beats, assets, panels, audio, motion, assembly — until a Rocky animatic plays. Milestone 2
(Box Office) wraps that pipeline in a public UI with live parsing, live footage
replacement, and the submission deliverables.

## Phases

**Milestone 1 — Actor:** minimum functionality, can we generate the first animatics?
**Milestone 2 — Box Office:** footage replacement and an external-facing demo.

- [x] **Phase 1: Project Scaffold & Infrastructure** - Repo, Python layout, AWS hosting skeleton, CI, health endpoint
- [x] **Phase 2: Beat Parser** - Rocky PDF to a structured beat list with machine-readable reasons
- [ ] **Phase 3: Asset Management & Manifest** - Named asset slots, temp-art fallback, manifest output
- [ ] **Phase 4: Panel Generation** - Black line-art panel per beat, consistent style, facial feature rules
- [ ] **Phase 5: Audio Synthesis** - Synthetic dialogue, action narration, music cues
- [ ] **Phase 6: Motion Generation** - Cost-constrained motion on selected high-value beats
- [ ] **Phase 7: Video Assembly** - Timed video cut from panels, motion and audio
- [ ] **Phase 8: Footage Replacement & Per-Shot State** - Live swap of animatic shots for real footage
- [ ] **Phase 9: Web UI & Demo Shell** - Hosted demo, three-state render, real progress indicators
- [ ] **Phase 10: Polish, Submission, Demo Video** - Everything required for submission

## Phase Details

### Phase 1: Project Scaffold & Infrastructure

**Goal**: Repo, Python project structure, AWS hosting skeleton, CI, dependency setup.
**Depends on**: Nothing (first phase)
**Requirements**: NFR-01, NFR-02
**Success Criteria** (what must be TRUE):

  1. `curl <hosted-url>/health` returns 200 from a public URL
  2. Repository is public with an OSI-approved license detectable in the About section
  3. A fresh clone runs from the README instructions alone
  4. AWS infrastructure provisions S3 storage and container hosting

**Plans**: 1 plan

Plans:

- [x] 01-01: Scaffold, infra, CI, health endpoint

### Phase 2: Beat Parser

**Goal**: Ingest Rocky PDF into a structured beat list with machine-readable reasons.
**Depends on**: Phase 1
**Requirements**: FR-01, NFR-04
**Success Criteria** (what must be TRUE):

  1. Parsing the Rocky PDF returns a valid JSON beat list for scenes 1-8
  2. Every beat carries beat_id, scene, type, content, reason and duration
  3. Beat density varies with content — action scenes yield more beats than establishing
  4. Every spoken line in the script appears in the beat list, attributed to one speaker
  5. Shot duration is derived from the script, not guessed, and records why

**Plans**: 1 plan

Plans:

- [x] 02-01: PDF extractor, Gemini beat extractor, assembler, S3 writer, API

### Phase 3: Asset Management & Manifest

**Goal**: Named asset slots, temp-art fallback, manifest output.
**Depends on**: Phase 2
**Requirements**: FR-02, NFR-04
**Success Criteria** (what must be TRUE):

  1. Running with zero reference art produces a complete asset manifest with every slot filled by generated temp art
  2. Every character and location in the beat list resolves to exactly one slot
  3. Supplied reference art is ingested and takes priority over generated art
  4. Replacing a slot file and re-running regenerates the panels that use it
  5. Each manifest entry records slot name, priority, source and reason

**Plans**: 3/3 plans executed

Plans:

- [x] 03-01-PLAN.md — Tracer: one slot end to end, then the full 16-slot registry (7 locations, 9 characters), priority ranking and the voice key
- [x] 03-02-PLAN.md — Reference-art ingestion, temp-art generation for every empty slot, manifest assembly with change detection and an honest S3 write
- [x] 03-03-PLAN.md — Real end-to-end run, art review against the D-09 failure modes, and the Asset Slot Contract for Phases 4 and 5

### Phase 4: Panel Generation

**Goal**: Black line-art panel per beat, consistent style, facial feature rules.
**Depends on**: Phase 3
**Requirements**: FR-03, NFR-03, NFR-04
**Success Criteria** (what must be TRUE):

  1. Every beat in scenes 1-8 has a generated panel
  2. Panels are black line art on white with consistent line weight
  3. Wide and medium shots carry no facial features; close-ups carry brow, mouth and nose only
  4. Each panel records beat_id, asset slots used, prompt and reason
  5. Re-running with unchanged beats and assets reuses cached panels

**Plans**: TBD

Plans:

- [ ] 04-01: TBD (set during planning)

### Phase 5: Audio Synthesis

**Goal**: Synthetic dialogue, action narration, and music cues per beat.
**Depends on**: Phase 2
**Requirements**: FR-05, NFR-03, NFR-04
**Success Criteria** (what must be TRUE):

  1. Every beat has an audio asset keyed to its beat_id
  2. Every speaking part is voiced, with a consistent voice per character
  3. Beats with no dialogue carry narration of their action lines
  4. Music is generated where the script specifies a music cue
  5. No beat's audio is longer than the beat's duration

**Plans**: TBD

Plans:

- [ ] 05-01: TBD (set during planning)

### Phase 6: Motion Generation

**Goal**: Cost-constrained motion applied to selected high-value beats.
**Depends on**: Phase 4
**Requirements**: FR-04, NFR-03, NFR-04
**Success Criteria** (what must be TRUE):

  1. Motion is applied to no more than the budgeted number of beats
  2. Every beat carries motion true/false and a motion reason
  3. Action beats are prioritised over dialogue and establishing beats
  4. A beat falls back to its still panel when motion fails or exceeds budget

**Plans**: TBD

Plans:

- [ ] 06-01: TBD (set during planning)

### Phase 7: Video Assembly

**Goal**: Timed video cut from panels, motion and audio — the first watchable animatic.
**Depends on**: Phase 4, Phase 5, Phase 6
**Requirements**: FR-06, NFR-04
**Success Criteria** (what must be TRUE):

  1. Assembling the beat list produces a watchable MP4 of Rocky scenes 1-8
  2. Each shot runs for its beat's duration
  3. Audio stays in sync with its shot and is never clipped
  4. Shot duration carries a machine-readable reason

**Plans**: TBD

Plans:

- [ ] 07-01: TBD (set during planning)

### Phase 8: Footage Replacement & Per-Shot State

**Goal**: Live swap of animatic shots for real footage, rebuilding the cut.
**Depends on**: Phase 7
**Requirements**: FR-07, FR-08, NFR-04
**Success Criteria** (what must be TRUE):

  1. Adding a beat-tagged MP4 and re-running produces an updated cut with that shot replaced
  2. Beat number is read from the filename, never inferred from the footage
  3. `state.json` reports per-shot state and the correct percentage of the cut that is real
  4. Removing a footage file restores the animatic shot on the next run

**Plans**: TBD

Plans:

- [ ] 08-01: TBD (set during planning)

### Phase 9: Web UI & Demo Shell

**Goal**: Hosted demo UI — three-state render, real progress indicators, cache disclosure.
**Depends on**: Phase 8
**Requirements**: DR-01, DR-02, DR-03, DR-04, NFR-01
**Success Criteria** (what must be TRUE):

  1. An anonymous visitor at the hosted URL can trigger a live beat parse
  2. An anonymous visitor can swap a shot and see the cut rebuild
  3. All three scene states render: all panels, partial footage, all footage
  4. Progress indicators are driven by real backend events, never simulated
  5. The UI discloses when media is pre-computed and cached

**Plans**: TBD

Plans:

- [ ] 09-01: TBD (set during planning)

### Phase 10: Polish, Submission, Demo Video

**Goal**: Everything required for submission.
**Depends on**: Phase 9
**Requirements**: NFR-02, NFR-05
**Success Criteria** (what must be TRUE):

  1. Three pre-rendered videos exist: no footage, partial footage, full footage
  2. A demo video of three minutes or less shows the system functioning
  3. A written description covers features, technologies, data sources and findings
  4. The README is verified to run from scratch on a clean machine
  5. All five Definition of Done items are checked off

**Plans**: TBD

Plans:

- [ ] 10-01: TBD (set during planning)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Project Scaffold & Infrastructure | 1/1 | Complete (1 gap: no CDN) | 2026-08-23 |
| 2. Beat Parser | 1/1 | Complete | 2026-08-24 |
| 3. Asset Management & Manifest | 3/3 | In Progress|  |
| 4. Panel Generation | 0/TBD | Not started | - |
| 5. Audio Synthesis | 0/TBD | Not started | - |
| 6. Motion Generation | 0/TBD | Not started | - |
| 7. Video Assembly | 0/TBD | Not started | - |
| 8. Footage Replacement & Per-Shot State | 0/TBD | Not started | - |
| 9. Web UI & Demo Shell | 0/TBD | Not started | - |
| 10. Polish, Submission, Demo Video | 0/TBD | Not started | - |

## Backlog (deferred)

### Human steering of generation (captured 2026-08-24)

Raised after seeing Phase 3's unassisted output: generation alone yields similar-looking
characters and generic rooms, so the product is a first pass the user redirects, not a
one-shot generator. **Gated on an experiment** — if a short description cannot meaningfully
change a character or a room, there is no reason to build an interface for it.

- **S-01 Slot inspector with description override** — show every location and character
  slot, let the user add a description that feeds regeneration.

  - **Validated 2026-08-24:** two sentences turned the cornerman from a generic
    middle-aged man in a fishing vest into a stooped seventy-year-old swamped in a
    cardigan; the dressing room gained a low ceiling, a bolted bench and cracked tiles.
    Decisive for characters, which otherwise generate from a bare name.

  - **Requirement found while testing:** user text must pass through
    `style._strip_on_screen_text`, and the no-lettering rule has to survive being diluted
    by it — the described room came back with "DOJO LOCKER ROOM" painted on a sign the
    baseline had left blank, and "dojo" is not in the script.

  - **Scene-context inheritance (2026-08-24, mechanism built, NOT wired).** A character's
    world is derivable from the locations of the scenes they appear in — fully generic,
    nothing names a genre or a character, so a different script yields a different world.
    `style.character_context()` implements it with tests. Proven to fix identity: the same
    slot that generated a soldier in a beret and tactical vest generated a boxer in a
    hoodie with hand wraps, and WOMAN became an older trolley rider in a headscarf with a
    shopping bag rather than a generic woman.
    **Now wired (2026-08-24).** The earlier attempts failed because the location
    description is a *scene*: left open-ended it staged the figure inside the room, and
    rewording toward wardrobe-only broke identity instead. What fixed it was ORDER — the
    context clause now closes with a restatement of the isolation rule, so the last thing
    the model reads is "one lone figure on a blank page", not a room. Those attempts were
    also polluted by the hat defect below, which was perturbing every generation while the
    context wording was being judged.
  - **Feeds from reference-art candidates:** loose files are now offered rather than
    adopted (see below), and this inspector is where a human designates them. Half-built already: slot
  replacement, `content_hash` and `stale_beat_ids` exist (FR-02). Missing is the UI and a
  *text* channel — today only an image file can be swapped. Backend hook is small:
  `style.describe_slot()` already composes the location subject, so an override field it
  prefers slots straight in. Natural home: Phase 9.

- **S-02 Beat stretch** — let the user ask for more beats in a scene (e.g. the fight).
  Genuinely new; nothing in the roadmap covers editing beats. Mechanically a re-parse of
  one scene at higher density, but it invalidates downstream slots, panels and timing, so
  it needs stale-tracking to extend past assets.

  - **Validated 2026-08-24:** scene 2 went 19 → 27 beats with all 10 spoken lines kept and
    the new beats genuinely distinct moments, not padding.

  - **Decided: not built now.** Beats stand as initially rendered and become updatable
    later. Nothing in Phases 3-8 may assume beats are immutable in a way that blocks this.

  - **Rule for when it is built: a stretch ADDS time; it must not re-time other beats.**
    Today `fit_scene_to_budget` scales every beat in a scene to hit the page target, so the
    27-beat stretch came back at the same 115.8s with mean shot pushed 6.1s → 3.7s. That is
    wrong twice: the user asked for the fight to play longer and it did not, and beats they
    had already approved silently changed length. Measured unfitted, the same stretch runs
    124.4s (+8.8s). So page geometry is the DEFAULT when no one has said otherwise, and an
    explicit direction overrides it — existing beats keep their durations, new beats add
    their own, the scene grows. Matters before Phase 5 and 7 cut audio and shots to
    durations, since re-timing an approved beat invalidates both.

- **S-03 Model sheet conditioning** — supply a reference sheet to drive character
  consistency. **RISK CLEARED 2026-08-24.** Multi-image reference conditioning is
  ACCEPTED by `gemini-3.1-flash-image`: feeding the `black_fighter` character plate and
  the `int_blue_door_fight_club` location plate plus a prompt returned one composed panel
  carrying the character's build and clothing and the room's ring, benches, chairs and
  fittings. Evidence: `output/experiments/refcond_panel.jpg`.
  **HELD 2026-08-24 — do not build into Phase 4 yet.** The capability is proven and the
  risk is closed, but reference-image conditioning is not being adopted as Phase 4's
  generation path for now. Phase 4 generates panels without it unless that is revisited.
  **This validates the Phase 3 asset architecture** — characters isolated on white and
  locations with no people are a vocabulary that genuinely combines, not two disconnected
  outputs. Phase 4 should generate each panel by conditioning on the slot plates its beat
  uses, rather than regenerating from text and discarding the assets.
  Note: the spike panel has facial features, so Phase 4 still owns applying PROJECT.md's
  shot-size rule (none in wide/medium, brow/mouth/nose in close-ups) at panel level.

- **S-04 Video splice replacing beats** — already scoped as Phase 8 (FR-07/FR-08). Listed
  here only to close the loop on the same idea set.

Scope note: the Definition of Done does not require steering. Steering makes the demo
better, not complete — pipeline to a watchable cut first.

- Multi-script support
- User-supplied script upload
- Shot size / camera direction inference
- Coverage planning
- CloudFront CDN and TLS for the hosted URL (Phase 1 gap — currently HTTP only)
