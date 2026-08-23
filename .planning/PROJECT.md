# Animatic — PROJECT.md

## One-liner
A screenplay-to-watchable-rough-cut system: drawn panels, synthetic voices, generated motion, assembled into a timed video that rebuilds as real footage is swapped in.

## Problem
Writers, directors, and financiers need to validate whether a story works before committing to the cost of shooting. Traditional animatics are expensive and slow to produce. This system generates a complete rough cut from a script alone.

## Solution
Parse the screenplay into beats → generate line-art panels (or use supplied reference art) → add synthetic dialogue and action narration → assemble into a timed video. Real footage clips can replace animatic shots incrementally; the cut rebuilds on each swap.

## Users
- Writer / director / financier deciding whether a story works before it is shot.
- Demo audience: anonymous visitor at a hosted URL (Rocky 1976, scenes 1–8, fixed content).

## Tech Stack
- **Language:** Python
- **Cloud:** AWS (infrastructure, storage, hosting)
- **AI services:** Google Cloud only — `google-adk`, `google-genai`, `google-generativeai`, `google-cloud-aiplatform`
- **Runtime:** Web — hosted URL, accessible to anonymous visitors
- **Partner track:** IBM (built using IBM Bob)

## Hard Constraints
- Submission deadline: **2026-09-09 14:00 PDT**
- AI: Google Cloud SDK only — no other AI models, agent frameworks, or AI APIs
- Web-hosted with public anonymous access
- Public repository, OSI-approved license, detectable in repo About section
- New code only, authored after 2026-07-27
- Google Cloud SDK must be imported and called at runtime

## Demo Constraints (Fixed Content)
- Script: Rocky (1976), scenes 1–8 only
- No user-supplied script upload — fixed content only
- Generated media may be pre-computed and cached (UI must disclose if cached)
- Beat parsing and footage replacement must execute live
- Progress indicators must reflect real work (no simulated progress)
- Must render the same scene at three states: all panels / partial footage / all footage

## Key Behaviours
- Never blocks on missing assets — generates temp art for any empty slot
- Replacing an asset slot file and re-running regenerates affected panels
- Adding a beat-tagged footage file and re-running replaces that shot and re-renders cut
- Every generated artifact carries a machine-readable reason (beat boundary, shot duration, motion selection, asset priority)
- Beat density varies with content (action > dialogue > establishing)
- Motion generation is cost-constrained — most beats are stills

## Visual Style
- Black line art on white
- No facial features in wide/medium shots; close-ups: brow line, mouth line, nose only
- Consistent line weight and style across all generated images

## Audio
- Synthetic dialogue for every speaking part
- Narration of action lines in beats with no dialogue
- Generated music where script specifies a music cue

## Non-Goals (explicitly excluded)
- Shot lists, shot sizes, camera directions, coverage plans
- Inferring beat number from footage — filename carries it
- Comparing footage against script or reporting deviations
- Arbitrary user script upload on the hosted demo

## Supplied Material
- `rocky-1976.pdf` — full script
- `Rocky.mp4` — reference video
- `boxing_poses.jpeg`, `rocky_porkpie.jpg`, `rocky_porkpie2.jpg`, `rocky_trunks_front.jpg` — reference art

## Definition of Done
1. Hosted URL renders the Rocky cut, parses beats live, and accepts a shot replacement that re-renders
2. Repository is public, licensed, and runs from its own instructions
3. Three rendered videos of the same scene: no footage / partial footage / full footage
4. Demo video, ≤3 minutes, showing the system functioning
5. Written description covering features, technologies, data sources, and findings

## Open Questions
- [ ] How is IBM Bob usage evidenced in the submission (pass/fail eligibility gate — resolve with organisers)
