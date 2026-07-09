# Dockerfile — builds the "Verse Helper" API image for Mercy Lutheran.
# Project 7 — Ship a Model in a Box. Hand-authored (not the starter copied).
#
# Design goals, one per rubric line:
#   - PIN the base image (never :latest) so the build is the same next year.
#   - Multi-stage build so the final image stays small (build tools don't ship).
#   - Install dependencies BEFORE copying source, so Docker caches the slow step.
#   - Run as a NON-ROOT user (least privilege on a network with minors on it).
#   - A HEALTHCHECK that hits a real endpoint, so "up" means "actually serving."

# ---------- Stage 1: build the Python dependencies ----------
FROM python:3.12.7-slim AS builder
WORKDIR /app

# Build everything into a self-contained virtual environment we can copy later.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy ONLY requirements first. This layer is cached and re-used on every build
# where requirements.txt hasn't changed — the expensive pip install is skipped.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Stage 2: the lean runtime image ----------
FROM python:3.12.7-slim AS runtime

# Create an unprivileged user. Root inside a container is root on the host kernel;
# we do not want the web-facing app running with that power.
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

# Bring over just the finished venv from the builder — no compilers in the final image.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the application source LAST (it changes most often; keep it out of cached layers).
COPY app.py .

# Drop privileges before the app ever runs.
USER appuser

EXPOSE 8000

# "Alive" is not "serving." This probe calls the app's own /health route.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

# Start the API server.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
