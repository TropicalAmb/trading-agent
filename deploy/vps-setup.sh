#!/usr/bin/env bash
# Minimal VPS bootstrap for the trading agent (Ubuntu/Debian).
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (or via sudo)."
  exit 1
fi

apt-get update
apt-get install -y docker.io docker-compose-v2 git
systemctl enable --now docker

APP_DIR="${APP_DIR:-/opt/trading-agent}"
if [[ ! -d "$APP_DIR" ]]; then
  echo "Clone/copy the repo to $APP_DIR first, then re-run."
  exit 1
fi

cd "$APP_DIR"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — edit credentials before starting."
fi

mkdir -p data
docker compose up -d --build
docker compose ps
echo "Done. Use: docker compose logs -f agent"
echo "If Gateway needs login/2FA, connect VNC to host:5900"
