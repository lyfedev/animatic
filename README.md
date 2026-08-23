# Animatic

A screenplay-to-watchable-rough-cut system. Takes a script and produces drawn panels, synthetic voices, generated motion, and a timed video. Real footage clips can replace animatic shots incrementally; the cut rebuilds on each swap.

> Built for the IBM Bob × Google Cloud hackathon. Demo: Rocky (1976), scenes 1–8.

## Status

🚧 In development — submission deadline 2026-09-09.

## What it does

- Parses a screenplay PDF into a structured beat list
- Generates black line-art panels for each beat (Google Imagen)
- Synthesises dialogue and narration audio (Google TTS)
- Applies generated motion to selected beats (Google Veo)
- Assembles everything into a timed MP4 via FFmpeg
- Accepts real footage clips tagged by beat number — swaps them in and rebuilds the cut

## Tech stack

- **Python** — core pipeline
- **AWS** — hosting, storage (S3), compute
- **Google Cloud AI** — Imagen (panels), TTS (audio), Veo (motion)
- **FFmpeg** — video assembly

## Running locally

_Instructions will be added as the project is built._

## License

MIT
