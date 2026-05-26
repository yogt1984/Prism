# Prism — Deployment Guide

Deploy Prism on a single VPS using Docker Compose.

## Prerequisites

- A VPS with Docker and Docker Compose installed (e.g. Hetzner CX32, ~$15/mo)
- An Anthropic API key
- (Optional) Brave Search API key, Resend API key, ntfy.sh topic

## 1. Clone and configure

```bash
git clone https://github.com/yogt1984/Prism.git
cd Prism
cp deploy/env.production.example .env
```

Edit `.env` and fill in your API keys. At minimum, set `ANTHROPIC_API_KEY`.

## 2. Build the image

```bash
docker compose build
```

## 3. Initialize the database

```bash
docker compose run --rm prism prism db init
docker compose run --rm prism prism source seed
```

## 4. Start in production mode

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

This starts two services:
- **scheduler** — runs discovery, analysis, and briefing on schedule
- **api** — serves the REST API on port 8000

## 5. Verify

```bash
# Check services are running
docker compose ps

# Health check
curl http://localhost:8000/health
curl http://localhost:8000/health/ready

# View logs
docker compose logs -f scheduler
docker compose logs -f api
```

## 6. Create a test user

```bash
docker compose run --rm prism prism user add \
  --email you@example.com \
  --interests "finance,technology"
```

## 7. Backups

Set up a daily backup via cron:

```bash
crontab -e
```

Add:

```
0 3 * * * cd /path/to/Prism && docker compose run --rm prism prism db backup --rotate 7
```

This creates a daily backup at 3 AM and keeps the 7 most recent.

## 8. Monitoring

If you set `NTFY_TOPIC` in `.env`, Prism sends push alerts on:
- Agent cycle failures
- Zero-result discovery cycles
- Email delivery failures

Install the ntfy app on your phone to receive them.

## 9. Updating

```bash
git pull
docker compose build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

The scheduler and API restart automatically with the new image.

## 10. Useful commands

```bash
# Run a single discovery cycle manually
docker compose run --rm prism prism cycle discover

# Check database stats
docker compose run --rm prism prism db stats

# Export data as JSON
docker compose run --rm prism prism db export

# View pipeline status
docker compose run --rm prism prism status
```
