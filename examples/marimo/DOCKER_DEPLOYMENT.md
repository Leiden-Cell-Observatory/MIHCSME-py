# Docker Deployment for MIHCSME OMERO App

This directory contains a Dockerized version of the marimo OMERO app.

## Files

- `Dockerfile` - Docker image configuration (uses pip instead of uv)
- `requirements.txt` - Python dependencies
- `.dockerignore` - Files to exclude from Docker build
- `marimo_omero_app.py` - The main application

## Building and Running Locally

### 1. Build the Docker image

```bash
# Run from the examples/marimo/ directory
docker build -t mihcsme-omero-app .
```

### 2. Run the container

```bash
docker run -p 8080:8080 -it mihcsme-omero-app
```

### 3. Access the application

Open your browser and navigate to: http://localhost:8080

## Environment Variables

If you need to set environment variables for OMERO connection or LLM API keys:

```bash
docker run -p 8080:8080 \
  -e OMERO_HOST=your-omero-host \
  -e OMERO_PORT=4064 \
  -e LLM_API_KEY=your-api-key \
  -it mihcsme-omero-app
```

## Platform-Specific Notes

### Linux (x86_64)
The default configuration is set up for Linux x86_64 and includes the appropriate zeroc-ice wheel.

### Other Platforms
If you need to deploy on a different platform (ARM, macOS, Windows), you'll need to:

1. Update the zeroc-ice URL in `requirements.txt` to match your platform
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
