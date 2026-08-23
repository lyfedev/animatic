# Animatic — REQUIREMENTS.md

## Functional Requirements

### FR-01 Beat Parsing
- Parse a screenplay PDF into a structured beat list
- Beat density varies by scene type: action scenes yield more beats than dialogue; establishing scenes may yield one
- Every beat boundary carries a machine-readable reason

### FR-02 Asset Management
- Accept character and location reference art as image files in named slots
- Generate temp art for any empty slot — system never blocks on missing inputs
- Replacing a file in an asset slot and re-running regenerates all panels that use it
- Produce an asset manifest: which slots are needed and which are highest priority

### FR-03 Panel Generation
- Generate black line-art panels on white for each beat
- No facial features in wide or medium shots
- Close-ups: brow line, mouth line, nose only
- Consistent line weight and style across all generated images
- Every panel carries a machine-readable reason for its content

### FR-04 Motion Generation
- Apply generated motion to selected beats only (cost-constrained)
- Most beats are stills; motion reserved for selected beats
- Beat selection for motion carries a machine-readable reason

### FR-05 Audio Synthesis
- Synthetic dialogue for every speaking part
- Narration of action lines in beats with no dialogue
- Generated music where the script specifies a music cue

### FR-06 Video Assembly
- Assemble panels, motion clips, and audio into a timed video file
- Shot duration carries a machine-readable reason
- Output: watchable video file of the assembled cut

### FR-07 Footage Replacement
- Accept real footage clips tagged with beat number in filename
- Adding a beat-tagged footage file and re-running replaces that shot and re-renders the full cut
- Per-shot state output: animatic or footage, and percentage of cut that is real

### FR-08 Per-Shot State Tracking
- Track which shots are animatic vs real footage
- Report percentage of cut that is real
- Output per-shot state manifest

## Demo Requirements

### DR-01 Fixed Content
- Script: Rocky (1976), scenes 1–8, fixed — no user upload
- Hosted URL accessible to anonymous visitors

### DR-02 Live Execution
- Beat parsing must execute live (not replayed)
- Footage replacement must execute live
- Progress indicators must reflect real work

### DR-03 Caching Disclosure
- Generated media may be pre-computed and cached
- If cached, the UI must clearly disclose this

### DR-04 Three-State Render
- Must be able to render the same scene at three states:
  1. All panels (no footage)
  2. Partial footage
  3. All footage

## Non-Functional Requirements

### NFR-01 Hosting
- Deployed to AWS, publicly accessible via URL
- Runs for anonymous visitors without authentication

### NFR-02 Repository
- Public GitHub repository
- OSI-approved license, detectable in repo About section
- Runs from its own README instructions

### NFR-03 AI Constraint
- Google Cloud SDK only for AI: `google-adk`, `google-genai`, `google-generativeai`, `google-cloud-aiplatform`
- No other AI models, agent frameworks, or AI APIs

### NFR-04 Traceability
- Every generated artifact carries a machine-readable reason field

### NFR-05 Deadline
- Submission: 2026-09-09 14:00 PDT

## Deliverables
1. Hosted URL (animated Rocky cut, live beat parsing, live footage swap)
2. Public repository with license
3. Three rendered videos: all panels / partial footage / all footage
4. Demo video ≤3 minutes
5. Written description (features, technologies, data sources, findings)
