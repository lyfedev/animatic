# Animatic — ROADMAP.md

## Milestone 1 — Rocky Demo (Deadline: 2026-09-09)

The complete working demo: Rocky scenes 1–8, hosted on AWS, live beat parsing and footage swap, three-state render.

---

### Phase 1 — Project Scaffold & Infrastructure
**Goal:** Repo, Python project structure, AWS hosting skeleton, CI, dependency setup.

- Python project layout (`src/`, `tests/`, `scripts/`)
- AWS infrastructure: S3 buckets, ECS or Lambda hosting, CloudFront CDN
- GitHub repo, public, OSI license
- `.env` / secrets management for Google Cloud credentials
- Basic FastAPI or Flask web server, health-check endpoint live at public URL
- README with run-from-scratch instructions

**Verification:** `curl <hosted-url>/health` returns 200. Repo is public with license badge.

---

### Phase 2 — Beat Parser
**Goal:** Ingest Rocky PDF → structured beat list with machine-readable reasons.

- PDF ingestion (PyMuPDF or pdfplumber)
- Scene segmentation (scenes 1–8)
- Beat extraction per scene, density-aware (action / dialogue / establishing)
- Every beat carries: beat_id, scene, type, content, reason, duration_estimate
- Beat list serialised to JSON
- Unit tests for parser with Rocky scenes 1–8

**Verification:** `parse_beats(rocky-1976.pdf, scenes=[1..8])` returns valid JSON beat list, all beats have `reason` field.

---

### Phase 3 — Asset Management & Manifest
**Goal:** Named asset slots, temp-art fallback, manifest output.

- Asset slot registry (character, location slots)
- Reference art ingestion from supplied files
- Temp-art generation via Google Imagen for empty slots
- Asset manifest: slot name, priority, source (supplied / generated), reason
- Slot-file replacement triggers re-generation of dependent panels

**Verification:** Running with zero reference art produces a complete asset manifest with all slots filled by generated temp art.

---

### Phase 4 — Panel Generation
**Goal:** Black line-art panel per beat, consistent style, facial feature rules.

- Google Imagen prompt pipeline for line-art panels
- Style enforcement: black line art on white, consistent weight
- Facial feature rule: wide/medium = no features; close-up = brow/mouth/nose only
- Each panel carries: beat_id, asset_slots_used, prompt, reason
- Panel caching (re-use if beat + assets unchanged)

**Verification:** All beats in scenes 1–8 have a panel. Style audit passes visual checklist.

---

### Phase 5 — Audio Synthesis
**Goal:** Synthetic dialogue, action narration, music cues.

- Dialogue synthesis via Google TTS (per speaking part, consistent voice per character)
- Action narration for beats with no dialogue
- Music generation where script specifies a music cue
- Audio assets per beat, keyed to beat_id

**Verification:** Every beat has an audio asset. Dialogue beats use character voice; non-dialogue beats use narrator voice.

---

### Phase 6 — Motion Generation (Selected Beats)
**Goal:** Cost-constrained motion applied to selected high-value beats.

- Beat selection algorithm (action beats prioritised, budget cap)
- Motion generation via Google Veo or equivalent
- Selection and skip reasons recorded per beat
- Fallback: still panel if motion fails or over budget

**Verification:** Motion applied to ≤N selected beats. Every beat has `motion: true/false` and `motion_reason`.

---

### Phase 7 — Video Assembly
**Goal:** Timed video cut from panels, motion, audio.

- FFmpeg-based assembly pipeline
- Shot duration from beat duration estimate
- Concatenate: panels / motion clips / audio per beat
- Output: single video file (MP4)
- Shot duration carries machine-readable reason

**Verification:** `assemble(beat_list)` produces a watchable MP4 of Rocky scenes 1–8.

---

### Phase 8 — Footage Replacement & Per-Shot State
**Goal:** Live swap of animatic shots with real footage; rebuild cut.

- Footage ingest: filename-based beat tagging
- Per-shot state tracker: animatic | footage, % real
- Re-render pipeline: drop tagged shots, insert footage, reassemble
- Per-shot state manifest output

**Verification:** Adding a beat-tagged MP4 file and re-running produces an updated cut with that shot replaced. `state.json` shows correct % real.

---

### Phase 9 — Web UI & Demo Shell
**Goal:** Hosted demo UI — three-state render, progress indicators, cache disclosure.

- Web UI (FastAPI + lightweight frontend, or Next.js thin wrapper)
- Scene state selector: all panels / partial footage / all footage
- Live beat parsing triggered from UI
- Live footage swap triggered from UI
- Progress indicators driven by real backend events (SSE or WebSocket)
- Cache disclosure banner if media is pre-computed
- Anonymous access, no auth

**Verification:** Anonymous visitor at hosted URL can trigger live beat parse, swap a shot, and view all three scene states.

---

### Phase 10 — Polish, Submission, Demo Video
**Goal:** Everything required for submission.

- Three pre-rendered videos: no footage / partial / full footage
- Demo video ≤3 minutes
- Written description (features, tech, data sources, findings)
- README verified: runs from scratch
- Repository public, license confirmed in About
- Resolve IBM Bob evidence question with organisers

**Verification:** All 5 Definition of Done items checked off.

---

## Backlog (deferred)
- Multi-script support
- User-supplied script upload
- Shot size / camera direction inference
- Coverage planning
