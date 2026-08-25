FROM python:3.12-slim

# ffmpeg is not optional — assembling the cut IS the product, and every render
# the demo performs shells out to it. Without this the container serves a page
# whose only button 500s.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/
# The screenplay ships in the image: DR-02 requires beat parsing to execute
# live on the hosted demo, and it cannot parse a PDF that is not there.
COPY docs/rocky-1976.pdf ./docs/

ENV PYTHONPATH=/app/src
EXPOSE 8000

# Generated media lives in S3, not in the image — panels, audio and motion are
# ~50MB and change independently of the code. The container fetches them at
# start and serves from local disk. `--allow-empty` so a boot before the first
# pipeline run degrades to an honest 503 rather than a crash loop.
CMD ["sh", "-c", "python scripts/fetch_media.py --allow-empty || true; exec uvicorn animatic.main:app --host 0.0.0.0 --port 8000"]
