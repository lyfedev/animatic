# Phase 1 — Project Scaffold & Infrastructure

**Milestone:** 1 — Actor  
**Goal:** Python project layout, AWS infrastructure (S3 + ECS), secrets management, FastAPI health-check endpoint live at a public URL.  
**AWS account:** `339482628818` (profile: `newaccount`) — all resources prefixed `animatic-`  
**Verification:** `curl <hosted-url>/health` returns `{"status":"ok"}`. Repo is public with MIT license.

---

## Context & decisions

| Decision | Choice | Reason |
|---|---|---|
| Web framework | FastAPI | Async, lightweight, easy SSE in later phases |
| Hosting | AWS ECS Fargate + ALB | Persistent process needed for SSE/WebSocket in Phase 9; Lambda cold starts unsuitable |
| Container registry | AWS ECR | Native ECS integration |
| Static/media storage | S3 (`animatic-media-628818`) | Large generated files; prefix avoids lighthouse collision |
| Config/secrets | AWS SSM Parameter Store | Already available on this account; no extra cost |
| Python version | 3.12 (pinned in Dockerfile) | 3.14 is on host but 3.12 is the latest stable with full library support |
| Dependency management | `pip` + `requirements.txt` | Simple, no Poetry overhead for this stage |
| IaC | AWS CDK (Python) | CDK already bootstrapped on this account (cdk bootstrap bucket exists) |
| Region | `us-east-1` | Confirmed available; matches existing lighthouse resources |

---

## Task breakdown

### Task 1 — Python project layout
Create the source tree and base files.

**Files to create:**
```
src/
  animatic/
    __init__.py
    api/
      __init__.py
      health.py        ← /health endpoint
    core/
      __init__.py
    config.py          ← settings via pydantic-settings
tests/
  __init__.py
  test_health.py
scripts/
  run_local.sh
requirements.txt
requirements-dev.txt
Dockerfile
.env.example
```

**`requirements.txt`** (Phase 1 only — grows in later phases):
```
fastapi>=0.111
uvicorn[standard]>=0.29
pydantic-settings>=2.2
```

**`requirements-dev.txt`**:
```
pytest>=8
httpx>=0.27        ← for FastAPI TestClient
pytest-asyncio>=0.23
```

**Verification:** `pytest tests/` passes with `test_health.py` asserting GET `/health` → 200 `{"status":"ok"}`.

---

### Task 2 — Dockerfile & local run
Single-stage Dockerfile, Python 3.12 slim base.

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
ENV PYTHONPATH=/app/src
CMD ["uvicorn", "animatic.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`scripts/run_local.sh` — builds and runs locally on port 8000.

**Verification:** `docker build . && docker run -p 8000:8000 <image>` → `curl localhost:8000/health` returns 200.

---

### Task 3 — AWS infrastructure (CDK)
CDK app in `infra/` (Python CDK stack).

**Resources:**
- `animatic-ecr` — ECR repository for container images
- `animatic-media-628818` — S3 bucket, private, versioning on
- ECS Fargate cluster `animatic-cluster`
- ECS task definition + service (1 vCPU, 2GB RAM — sufficient for Phase 1)
- Application Load Balancer `animatic-alb`, HTTP listener on port 80
- ALB target group → ECS service port 8000
- IAM task role `animatic-task-role` — S3 read/write on `animatic-media-628818`

**CDK stack file:** `infra/animatic_stack.py`

**Verification:** `cdk deploy --profile newaccount` completes without errors. ALB DNS name output captured.

---

### Task 4 — GitHub Actions CI/CD pipeline
`.github/workflows/deploy.yml` — on push to `main`:

1. Run `pytest`
2. Build Docker image
3. Push to ECR (`animatic-ecr`)
4. Update ECS service to force new deployment

**Required GitHub secrets** (set manually once):
- `AWS_ACCESS_KEY_ID` — from `newaccount` / `temp_lighthouse`
- `AWS_SECRET_ACCESS_KEY`
- `ECR_REGISTRY` — `339482628818.dkr.ecr.us-east-1.amazonaws.com`
- `ECR_REPO` — `animatic-ecr`
- `ECS_CLUSTER` — `animatic-cluster`
- `ECS_SERVICE` — `animatic-service`

**Verification:** Push to main triggers workflow; ECS service updates; health check passes at ALB URL.

---

### Task 5 — Secrets / environment management
`.env.example` documents all required environment variables (no real values):

```
# Google Cloud
GOOGLE_CLOUD_PROJECT=
GOOGLE_APPLICATION_CREDENTIALS=

# AWS (injected by ECS task role — not needed locally if using aws sso)
AWS_REGION=us-east-1

# App
ENVIRONMENT=development
```

SSM parameter paths (to be populated before Phase 3 when Google Cloud is first needed):
- `/animatic/google-cloud-project`
- `/animatic/google-application-credentials-json`

ECS task definition reads these from SSM at runtime via `secrets:` block.

**Verification:** `python -c "from animatic.config import settings; print(settings.environment)"` prints `development` locally.

---

### Task 6 — README update
Update `README.md` with:
- Prerequisites (Python 3.12+, Docker, AWS CLI, CDK)
- Local run instructions
- Deploy instructions
- Environment variable reference

---

## Verification checklist

- [ ] `pytest tests/` — all tests pass locally
- [ ] `docker build .` — image builds without errors
- [ ] `docker run` + `curl localhost:8000/health` — returns `{"status":"ok"}`
- [ ] `cdk deploy --profile newaccount` — stack deploys, ALB DNS output shown
- [ ] `curl http://<alb-dns>/health` — returns `{"status":"ok"}` from AWS
- [ ] GitHub Actions workflow runs green on push to main
- [ ] S3 bucket `animatic-media-628818` exists and is private
- [ ] No `lighthouse-*` resources touched or modified

---

## Commit plan
Each task gets its own atomic commit with `Co-authored-by: IBM Bob <bob@ibm.com>` trailer:

1. `feat(scaffold): python project layout, fastapi health endpoint`
2. `feat(docker): dockerfile and local run script`
3. `feat(infra): cdk stack — ecr, s3, ecs fargate, alb`
4. `feat(ci): github actions deploy pipeline`
5. `feat(config): env management, ssm parameter paths, .env.example`
6. `docs: update readme with setup and deploy instructions`
