# Cloud / VPS deployment (paper first)

## Goal

Run the autonomous futures paper agent on a Linux VPS so your laptop can be closed.
Scans, decisions, paper fills, position management, journal, and dashboard continue on the server.

## Requirements

- Small VPS (1 vCPU / 1–2 GB RAM is enough for paper Yahoo mode)
- Docker + Docker Compose
- Outbound HTTPS (Yahoo delayed data)

## Quick start

```bash
git clone <your-repo> trading-agent
cd trading-agent
cp .env.example .env
# Edit .env — keep ALLOW_LIVE_TRADING=false and USE_MOCK_BROKER=true for paper

docker compose -f docker-compose.paper.yml --profile paper up -d --build
```

Persistent journal/blotter lives in the `agent-data` Docker volume (survives container recreate).

## Health

```bash
docker compose -f docker-compose.paper.yml --profile paper ps
docker compose -f docker-compose.paper.yml --profile paper logs -f paper-agent
```

Container uses `restart: unless-stopped` and a healthcheck against `scripts/healthcheck.py`.

## Dashboard access (do not expose naked to the internet)

Preferred options:

1. **SSH tunnel** from your laptop:
   `ssh -L 8080:127.0.0.1:8787 user@vps`
2. **Tailscale / WireGuard** private network
3. Reverse proxy with basic auth (Caddy/Nginx) if you must publish HTTPS

Copy or mount `data/paper_trading_view.html` / serve from volume; the blotter HTML auto-refreshes.

Webhook port 8787 must not be public without `WEBHOOK_SECRET` and preferably not public at all.

## Multi-agent later

```bash
docker compose -f docker-compose.paper.yml --profile multi up -d
```

Use `config/agent_profiles/*.yaml` for independent strategy profiles. Portfolio coordinator blocks opposite/duplicate exposure on the shared account unless config allows it.

## Real-time later

Change only:

```yaml
market_data:
  provider: <realtime_provider>
execution:
  dry_run: false   # only after ALLOW_LIVE_TRADING=true and broker ready
mode: live
```

Do not rewrite strategy engines.
