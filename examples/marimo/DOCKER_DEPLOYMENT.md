# Docker Deployment for MIHCSME OMERO App

The image is built from the repository root (`Dockerfile`, `.dockerignore`) and
installs `mihcsme-py` from the checked-out source, so it matches the commit it was
built from. It serves `mihcsme_app.py` with `marimo run` (app view only, no editor).

Pushes to `main`, version tags and releases publish the image to
`ghcr.io/leiden-cell-observatory/mihcsme-app` via `.github/workflows/docker.yml`.

## ShinyProxy

A spec is in `deploy/shinyproxy/application.yml`. Notes:

- `port: 8080` is the container port; ShinyProxy handles authentication, so the
  app runs with `--no-token`.
- `websocket-reconnection-mode: None`: a marimo session cannot be resumed after
  the websocket drops.
- The GHCR package is private by default. Either make it public (package
  settings on GitHub) or give ShinyProxy's Docker daemon credentials
  (`docker login ghcr.io` with a token that has `read:packages`).
- The image is `linux/amd64` only (the zeroc-ice wheel is x86_64 only).

## Building and Running Locally

### 1. Build the Docker image

```bash
# Run from the repository root
docker build -t mihcsme-omero-app .
```

### 2. Run the container

**Foreground** (logs visible in terminal, stops when you close it):
```bash
docker run -p 8080:8080 -it mihcsme-omero-app
```

**Background/detached** (keeps running after closing the terminal):
```bash
docker run -d -p 8080:8080 --name mihcsme-omero mihcsme-omero-app
```

Useful commands when running detached:
```bash
docker logs mihcsme-omero        # view logs
docker logs -f mihcsme-omero     # follow/stream logs
docker stop mihcsme-omero        # stop the container
docker start mihcsme-omero       # restart it
docker rm mihcsme-omero          # remove it
```

### 2a. Run with live-editable app script (recommended for development)

Mount the local `mihcsme_app.py` into the container so you can edit it without rebuilding:

**Linux/macOS:**
```bash
docker run -p 8080:8080 -v "$(pwd)/examples/marimo/mihcsme_app.py:/app/mihcsme_app.py" -it mihcsme-omero-app
```

**Windows (PowerShell):**
```powershell
docker run -p 8080:8080 -v "${PWD}\examples\marimo\mihcsme_app.py:/app/mihcsme_app.py" -it mihcsme-omero-app
```

Restart the container to pick up changes to `mihcsme_app.py` (`marimo run` does not reload the file unless you add `--watch` to the command).

### 3. Access the application

Open your browser and navigate to: http://localhost:8080

## Environment Variables

LLM features are off by default. Enable them with `MIHCSME_ENABLE_LLM=1` plus an OpenRouter key:

```bash
docker run -p 8080:8080 \
  -e OMERO_HOST=your-omero-host \
  -e OMERO_PORT=4064 \
  -e MIHCSME_ENABLE_LLM=1 \
  -e LLM_OPENROUTER_KEY=your-openrouter-key \
  -it mihcsme-omero-app
```

## Platform-Specific Notes

### Linux (x86_64)
The default configuration is set up for Linux x86_64 and includes the appropriate zeroc-ice wheel.

### Other Platforms
If you need to deploy on a different platform (ARM, macOS, Windows), you'll need to:

1. Pass a matching wheel with `--build-arg ZEROC_ICE_WHEEL=<url>`
2. Check the [zeroc-ice releases](https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases) for available wheels

## Health Check

The Docker container includes a health check endpoint at `/health` that runs every 30 seconds.

You can manually check the health status:

```bash
curl http://localhost:8080/health
```

Or check the API status:

```bash
curl http://localhost:8080/api/status
```

## Deployment to Cloud

This Docker image can be deployed to any cloud provider that supports Docker containers:

- **Google Cloud Run**: Use `gcloud run deploy`
- **AWS ECS/Fargate**: Push to ECR and deploy
- **Azure Container Instances**: Use `az container create`
- **DigitalOcean App Platform**: Connect your Git repository
- **Fly.io**: Use `fly deploy`

### Example: Google Cloud Run

```bash
# Tag for Google Container Registry
docker tag mihcsme-omero-app gcr.io/YOUR-PROJECT-ID/mihcsme-omero-app

# Push to GCR
docker push gcr.io/YOUR-PROJECT-ID/mihcsme-omero-app

# Deploy to Cloud Run
gcloud run deploy mihcsme-omero-app \
  --image gcr.io/YOUR-PROJECT-ID/mihcsme-omero-app \
  --platform managed \
  --port 8080 \
  --allow-unauthenticated
```

## Troubleshooting

### Build fails on zeroc-ice
If you're having issues with the zeroc-ice wheel, you may need to:
- Use a different Python version
- Find a compatible wheel for your platform
- Build zeroc-ice from source (advanced)

### Permission issues
The container runs as a non-root user (`app_user`) for security. If you need to modify this, edit the Dockerfile's `USER` instruction.

### Out of memory
If the build fails with memory issues, you can increase Docker's memory allocation in Docker Desktop settings.
