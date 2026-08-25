# Animatic

**A screenplay becomes a watchable rough cut, and then becomes a real film one shot at a time.**

Demo content: *Rocky* (1976), scenes 1–8. Fixed — the demo does not accept script uploads.

---

## What it does

Feed it a screenplay PDF. It reads the script, breaks it into beats, draws a panel for each
one, casts and voices every speaking part, narrates the beats nobody speaks in, scores the
moments the script asks for music, animates a handful of high-value shots, and assembles the
lot into a timed video.

Then the useful part: drop a real footage clip named after a beat into a folder, re-run, and
that shot is real film. Delete it and the drawing comes back. The cut reports what percentage
of itself is real, by screen time.

That is the actual product idea — not "generate a video", but **a cut that starts entirely
imagined and converges on the finished film**, so a director can see whether the story works
before spending a day shooting it, and can keep watching it work as real footage lands.

---

## The pipeline

| Stage | In | Out |
|---|---|---|
| **Beats** | `rocky-1976.pdf` | 49 beats, scenes 1–8, 255.7s |
| **Assets** | beats | 16 named slots → 13 art files |
| **Panels** | beats + slots | 49 line-art panels, shot size derived per beat |
| **Audio** | beats | 49 clips — 18 dialogue, 31 narration — plus 2 music cues |
| **Motion** | selected beats + their panels | 3 animated shots |
| **Assembly** | all of it | `animatic.mp4`, 262.1s |
| **State** | what is on disk | `state.json` — per shot, and % real |

Every artifact is keyed by `beat_id`. `s2b5` names a beat, a panel, a voice clip, a motion
candidate, an S3 key and a shot in the cut. Every one of them carries a machine-readable
reason for its own existence: why the beat broke there, why the shot is that size, why the
shot is that long.

## Technologies

**Google Cloud AI for every generative step.** No other model provider is used anywhere in
the pipeline; `google-genai` is the only AI SDK in `requirements.txt`.

| Step | Model |
|---|---|
| Beat extraction, narration, voice casting | `gemini-3.6-flash` |
| Panels and character/location art | `gemini-3.1-flash-image` |
| Dialogue and narration | `gemini-3.1-flash-tts-preview` (fallback: `gemini-2.5-flash-preview-tts`) |
| Score | `lyria-3-clip-preview` |
| Motion | `veo-3.1-fast-generate-preview` |

Around them: **Python 3.12**, **FastAPI** for the demo shell and API, **FFmpeg** for
assembly, **pdfplumber** for the screenplay, **AWS** for hosting (ECS Fargate behind an ALB)
and storage (S3).

## Data sources

- `docs/rocky-1976.pdf` — the screenplay. The only input to the generative pipeline.
- `assets/Rocky.mp4` — the reference film, used **only** as stand-in footage to demonstrate
  the replacement mechanism. Nothing in the generative pipeline reads it, and nothing is
  calibrated against it. That matters: the real workflow is for a film that has not been shot,
  so a pipeline that needed the finished film would be a pipeline that could never be used.

---

## Findings

Six things this project learned the expensive way. They are the substance of it.

### 1. A negation gets rendered

Telling an image model what *not* to draw draws it. An early panel came back with the words
**"NO FACIALS"** lettered into the frame. Naming a thing as absent is still naming it:
describing the eyes as "left blank" produced a fully rendered eye, iris and pupil. Naming
"hat brim" while describing where a face ends put a hat on every character in the film.

The rules that work state what **is** drawn. The close-up clause never refers to eyes at all
— it says the face draws exactly three lines and describes the rest as one continuous blank
plane.

### 2. The rule that matters has to land last

A rule stated in the middle of a prompt loses to whatever follows it. The room's
no-lettering rule was in the prompt and still failed, because character panels closed on
their facial clause. Moving it to the end fixed it. Every prompt in this project is ordered
deliberately, and the tests assert on the **built string**, never on the source — a rule that
exists in the code but never reaches the model is the failure mode that taught this.

### 3. Measure the model, do not assume it

Phase 2 sized every dialogue beat assuming 2.5 words per second. The real measured rate
across 31 clips was min 1.56, **median 2.16**, p90 2.50. Planning at the median means half of
everything overruns by construction — 11 of 31 beats did. Planning near p10 fixed it.

Similarly: every TTS clip carries ~0.25s of lead-in and ~0.4s of trail-out silence regardless
of length. On a 2.2-second beat that padding is a third of the shot. Trimming it is what makes
the short beats fit at all.

### 4. Rate limits are two limits, and one of them is per model

The obvious cap is 10 requests/minute. The one that actually stops a run is **100 requests
per day, per model** — a full 49-beat audio pass plus retries very nearly exhausts it, and two
passes in a day certainly do. The saving grace, found by measurement rather than by reading:
the daily cap is scoped per model, so a spent model is not a spent day. Switching to a second
TTS model finished a run the first could not.

The deeper lesson was not about quotas. When the run hit the cap it turned a complete 49-clip
index into 39 good entries and 10 failures — while all ten clips sat playable on disk,
because a failed generation never deletes what is already there. **A run that cannot
regenerate should keep what it has.** That is now three rules: a failed beat keeps its clip,
the run halts rather than marching every remaining beat into the same wall, and the index says
plainly which clips are behind.

### 5. Seed video generation from art you have already approved

Veo generating from text produces a *new* picture that competes with the panel — the style,
the framing and the facial rules all have to be won again. Seeding it with the beat's existing
panel makes the clip a continuation of art already reviewed.

The seed alone is not enough. The first clip added a full eye to a face that had none and grew
a crowd into the background between second one and second three. Applying the panel phase's
own clauses — positive prose, rule last, name nothing unwanted — fixed both in a single
revision.

### 6. Verify against the artifact, not the record

Twice, a written record was wrong in a way that mattered, and both times the correction came
from opening the actual file.

A panel was logged as "a solid black fill" — judged from a 430-pixel contact-sheet thumbnail
where the character's black hair and shirt dominated. The real image had a fully rendered
face: the exact defect two revision passes had been spent eliminating, on the case reported
clean. And five tests passed locally while asserting nothing, because a monkeypatch had no
effect and the real directory happened to exist; CI, which has no such directory, caught it.

Every verification in this project now opens the artifact.

---

## Honest limits

- **8 of 49 panels** carry a facial-feature or lettering defect, named individually and
  accepted rather than hidden. Regenerating against the same prompt is a coin-flip, not a fix.
- **1 of 4 motion beats** was refused by Veo's content guardrails and falls back to its panel.
  The prompt was not reworded to get around the refusal.
- **12 of 49 voice clips** were generated on the fallback TTS model after the primary's daily
  cap. Same voice names, so the cast is unchanged; the index records which model spoke each
  line so a mixed corpus is visible rather than discovered by ear.
- **Reference-art conditioning is built and tested but deliberately unexercised** — nothing in
  the shipped run is reference-backed, because designating reference art is a curation
  decision and adopting a loose file without one caused a real defect.
- **Narration is compressed to what a shot can physically carry.** A 2.2-second beat holds
  about four words, so characterful detail in the action line is lost. That is a real trade,
  not a bug.

## Definition of Done

| # | Item | State |
|---|---|---|
| 1 | Hosted URL renders the cut, parses beats live, accepts a shot replacement | Built and working locally; hosted deploy runs on merge to `main` |
| 2 | Repository public, licensed (MIT), runs from its own instructions | Yes |
| 3 | Three rendered videos: no footage / partial / full | `01-no-footage.mp4` (0%), `02-partial-footage.mp4` (51.1%), `03-full-footage.mp4` (100%) |
| 4 | Demo video ≤ 3 minutes | **Outstanding** — needs a screen recording |
| 5 | Written description | This document |
