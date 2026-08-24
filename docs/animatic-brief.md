# Animatic — project brief

Brief, not a spec. Write the spec before building.

---

## WHAT TO BUILD

A system that takes a screenplay and produces a watchable rough cut of the film: drawn panels, generated motion on selected beats, synthetic voices for all dialogue and action narration, assembled into a timed video.

Individual shots can then be replaced with real footage. The cut rebuilds. Repeat until the film is entirely real.

## USER

A writer, director or financier deciding whether a story works before it is shot.

## INPUTS

- Screenplay, PDF
- Character and location reference art, as image files in named slots
- Real footage clips, each tagged with its beat number in the filename

## OUTPUTS

- Beat list derived from the script
- Asset manifest: which art is needed, and which slots matter most
- A watchable video file of the assembled cut
- Per-shot state: animatic or footage, and the percentage of the cut that is real

## REQUIRED BEHAVIOUR

- Produces a complete cut from a script alone. Any asset slot with no supplied art gets temp art generated, so the system never blocks on missing inputs.
- Replacing the file in an asset slot and re-running regenerates the panels that use it.
- Adding a beat-tagged footage file and re-running replaces that shot and re-renders the cut.
- Every generated artifact carries a machine-readable reason: why a beat boundary fell there, why a scene produced N beats, why a shot holds for N seconds, why a beat was selected for motion, why an asset slot is high priority.
- Beat density varies with content. An action scene yields more beats than a dialogue scene. An establishing scene may yield one.
- Motion generation is cost-constrained. Most beats are stills; motion is reserved for selected beats.

## HARD CONSTRAINTS

- Submission deadline: 2026-09-09, 14:00 PDT.
- Partner track is IBM. Must be built using IBM Bob.
- AI services: Google Cloud only. No non-Google AI models, agent frameworks or AI APIs. Non-AI third-party services are unrestricted.
- Must run on web. A hosted URL is required and must work for an anonymous visitor.
- Public repository with an OSI-approved license detectable in the repository About section.
- Google Cloud SDK imported and called at runtime. Accepted packages: `google-adk`, `google-genai`, `google-generativeai`, `google-cloud-aiplatform`.
- New code only, authored within the contest window (opened 2026-07-27).

## DEMO REQUIREMENTS

- Fixed content: Rocky (1976), scenes 1 through 8. Script supplied.
- The hosted URL accepts no user-supplied script. No open input of any kind.
- Generated media may be pre-computed and cached. If cached, the UI must say so.
- Beat parsing and footage replacement must execute live, not replay.
- Progress indicators must reflect real work. Never simulate progress.
- Must be able to render the same scene at three states: all panels, partial footage, all footage.

## VISUAL REQUIREMENTS

- Black line art on white.
- No facial features in wide or medium shots. Close-ups limited to brow line, mouth line, nose.
- Consistent line weight and style across every generated image.

## AUDIO REQUIREMENTS

- Synthetic dialogue for every speaking part.
- Narration of action lines in beats with no dialogue.
- Generated music where the script specifies a music cue.

## NON-GOALS

Do not build these. They are excluded deliberately.

- Shot lists, shot sizes, camera directions, coverage plans. The system produces beats, not a shooting board.
- Inference of which beat a footage file belongs to. The filename carries it.
- Comparison of footage against the script, or any report of deviation from it.
- Arbitrary user script upload on the hosted demo.

## SUPPLIED MATERIAL

- `rocky-1976.pdf` — full script, master revision 1976-01-07
- `rocky-demo-plan.md` — scene scope, character list, asset list, walkthrough of the intended output
- `hackathon-brief.md` — full competition rules and submission requirements
- `scope-v1.md` — decisions already made and features explicitly deferred
- Reference art files, supplied separately

## DEFINITION OF DONE

1. Hosted URL renders the Rocky cut, parses beats live, and accepts a shot replacement that re-renders.
2. Repository is public, licensed, and runs from its own instructions.
3. Three rendered videos of the same scene: no footage, partial footage, full footage.
4. Demo video, 3 minutes or under, showing the system functioning.
5. Written description covering features, technologies, data sources, and findings.

## OPEN QUESTION TO RESOLVE BEFORE BUILDING

How usage of IBM Bob is evidenced in the submission. This is a pass/fail eligibility gate and the requirement is not published. Resolve with the organisers.
