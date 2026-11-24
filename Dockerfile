# MIHCSME Editor (examples/marimo/mihcsme_app.py) served as a read-only marimo app.
# Built from this repository's source, so the image matches the commit it was built from.
# Build from the repo root:  docker build -t mihcsme-app .
# zeroc-ice is only published as a linux/amd64 wheel, so the image is amd64 only.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OMERO's Ice runtime (prebuilt wheel, Python 3.12, linux x86_64)
ARG ZEROC_ICE_WHEEL=https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20240202/zeroc_ice-3.6.5-cp312-cp312-manylinux_2_28_x86_64.whl
RUN pip install "${ZEROC_ICE_WHEEL}"

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install ".[app,omero]" "llm==0.28" "llm-openrouter==0.5" \
    && rm -rf /src

RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --chown=app:app examples/marimo/mihcsme_app.py .
USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# `marimo run` serves the app only (code hidden, not editable).
# Authentication is left to the reverse proxy (ShinyProxy), hence --no-token.
CMD ["marimo", "run", "mihcsme_app.py", \
     "--host", "0.0.0.0", "--port", "8080", \
     "--headless", "--no-token", "--no-sandbox"]
