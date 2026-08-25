# Animatic

A screenplay-to-watchable-rough-cut system. Takes a script and produces drawn panels, synthetic voices, generated motion, and a timed video. Real footage clips can replace animatic shots incrementally; the cut rebuilds on each swap.

> Built for the IBM Bob × Google Cloud hackathon. Demo: Rocky (1976), scenes 1–8.

[![Deploy](https://github.com/lyfedev/animatic/actions/workflows/deploy.yml/badge.svg)](https://github.com/lyfedev/animatic/actions/workflows/deploy.yml)

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

- **Python 3.12** — core pipeline
- **AWS** — hosting (ECS Fargate + ALB), storage (S3)
- **Google Cloud AI** — Imagen (panels), TTS (audio), Veo (motion)
- **FFmpeg** — video assembly

## Prerequisites

- Python 3.12+
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configured
- [AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) (`npm install -g aws-cdk`)
- Docker (for local container testing)

## Running locally

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Copy and fill in environment variables
cp .env.example .env
# Edit .env with your Google Cloud project and credentials

# 4. Run tests
PYTHONPATH=src pytest tests/ -v

# 5. Start the server
PYTHONPATH=src uvicorn animatic.main:app --reload
# → http://localhost:8000/health

# 6. Parse the screenplay into a beat list
PYTHONPATH=src python scripts/parse_beats.py

# 7. Resolve asset slots and generate/fetch their art
PYTHONPATH=src python scripts/build_assets.py
# Reference art goes in assets/reference-art/, either as flat files named
# after a slot or (preferred — the only mechanism that's adopted
# automatically) in a folder named after the slot, e.g.
# assets/reference-art/rocky/photo.jpg. Any slot without reference art is
# filled with generated temp art so the pipeline never blocks on a missing
# input.

# 8. Generate one black line-art panel per beat
PYTHONPATH=src python scripts/build_panels.py
# --scene N generates just that scene's beats. Unchanged beats and
# unchanged slot art reuse their existing panels with no API call; edit a
# beat's content, change a beat's shot size, or replace a dependent slot's
# art and re-run — only the affected panels redraw, and everything else
# stays cached.
```

## Deploying to AWS

```bash
# 1. Bootstrap CDK (first time only)
cd infra
cdk bootstrap --profile newaccount

# 2. Deploy the stack
cdk deploy --profile newaccount

# The ALB DNS name is printed as output — that is your hosted URL.
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ENVIRONMENT` | No | `development` or `production` (default: `development`) |
| `AWS_REGION` | No | AWS region (default: `us-east-1`) |
| `GOOGLE_API_KEY` | **Yes** | Gemini API key — required for beat parsing |
| `GEMINI_MODEL` | No | Gemini model id (default: `gemini-3.6-flash`) |
| `MEDIA_BUCKET` | No | S3 bucket for generated media (default: `animatic-media-628818`) |
| `GOOGLE_CLOUD_PROJECT` | Phase 3+ | Google Cloud project ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | Phase 3+ | Path to service account JSON |

> Keep credential files **outside** the repo — it is public. `.gitignore` covers
> common key filenames, including the `<project>-<keyid>.json` shape that GCP
> service-account keys download as, but an out-of-tree path is the safer default.

In production, `GOOGLE_CLOUD_PROJECT` and credentials are read from AWS SSM Parameter Store at `/animatic/google-cloud-project` and `/animatic/google-application-credentials-json`.

## License

MIT
