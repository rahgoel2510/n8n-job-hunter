#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log() { echo -e "${GREEN}[n8n]${NC} $1"; }
warn() { echo -e "${YELLOW}[n8n]${NC} $1"; }
err() { echo -e "${RED}[n8n]${NC} $1" >&2; }

cmd_setup() {
  log "Setting up n8n-job-hunter..."
  if [ ! -f .env ]; then
    cp .env.example .env
    warn "Created .env from .env.example — edit it with your real credentials"
  fi
  docker compose pull
  docker compose up -d
  log "Waiting for n8n to be ready..."
  for i in $(seq 1 30); do
    if curl -sf http://localhost:5678/healthz > /dev/null 2>&1; then
      log "n8n is ready at http://localhost:5678"
      return 0
    fi
    sleep 2
  done
  err "n8n did not become ready in 60s"
  return 1
}

cmd_start() { docker compose up -d && log "Started"; }
cmd_stop() { docker compose down && log "Stopped"; }
cmd_restart() { docker compose restart && log "Restarted"; }
cmd_logs() { docker compose logs -f --tail="${1:-100}"; }
cmd_status() { docker compose ps; }
cmd_update() { docker compose pull && docker compose up -d && log "Updated"; }

cmd_import() {
  local wf="${1:-workflows/job_hunter_pipeline.json}"
  if [ ! -f "$wf" ]; then err "Workflow file not found: $wf"; return 1; fi
  log "Importing $wf..."
  docker compose exec -T n8n n8n import:workflow --input="/home/node/workflows/$(basename "$wf")"
  log "Imported successfully. Activate it in the n8n UI."
}

cmd_clean() {
  warn "This will remove all n8n data. Are you sure? (y/N)"
  read -r confirm
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    docker compose down -v
    log "Cleaned all data and volumes"
  fi
}

cmd_shell() { docker compose exec n8n /bin/sh; }

usage() {
  cat <<EOF
Usage: ./n8n.sh <command>

Commands:
  setup     First-time setup (create .env, pull image, start)
  start     Start n8n container
  stop      Stop n8n container
  restart   Restart n8n container
  logs      Tail container logs (optional: number of lines)
  status    Show container status
  update    Pull latest image and restart
  import    Import workflow JSON (default: workflows/job_hunter_pipeline.json)
  clean     Remove all data and volumes (destructive)
  shell     Open shell in n8n container
EOF
}

case "${1:-}" in
  setup)   cmd_setup ;;
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  restart) cmd_restart ;;
  logs)    cmd_logs "${2:-100}" ;;
  status)  cmd_status ;;
  update)  cmd_update ;;
  import)  cmd_import "${2:-}" ;;
  clean)   cmd_clean ;;
  shell)   cmd_shell ;;
  *)       usage ;;
esac
