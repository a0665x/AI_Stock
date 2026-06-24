#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="ai-stock"
SERVICE_NAME="ai-stock-dashboard"
APP_PORT="${APP_PORT:-8507}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
export HOST_UID="${HOST_UID:-$(id -u)}"
export HOST_GID="${HOST_GID:-$(id -g)}"

cd "$ROOT_DIR"

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" "$@"
  else
    echo "找不到 docker compose。請先安裝 Docker Compose plugin 或 docker-compose。" >&2
    exit 1
  fi
}

local_urls() {
  echo "Local URL:      http://127.0.0.1:${APP_PORT}"
  echo "LAN URL:        http://$(hostname -I 2>/dev/null | awk '{print $1}'):${APP_PORT}"
}

tailscale_urls() {
  if ! command -v tailscale >/dev/null 2>&1; then
    echo "Tailscale URL:  未偵測到 tailscale 指令；若已用其他方式接入，請用該節點 IP + :${APP_PORT}"
    return 0
  fi

  if ! tailscale status >/dev/null 2>&1; then
    echo "Tailscale URL:  tailscale 尚未登入或 daemon 未啟動"
    return 0
  fi

  local ts_ip=""
  ts_ip="$(tailscale ip -4 2>/dev/null | head -n1 || true)"

  local ts_dns=""
  ts_dns="$(tailscale status --json 2>/dev/null | python3 -c 'import json, sys; data=json.load(sys.stdin); print((data.get("Self") or {}).get("DNSName", "").rstrip("."))' 2>/dev/null || true)"

  if [[ -n "$ts_dns" ]]; then
    echo "Tailscale DNS:  http://${ts_dns}:${APP_PORT}"
  fi
  if [[ -n "$ts_ip" ]]; then
    echo "Tailscale IP:   http://${ts_ip}:${APP_PORT}"
  fi
  if [[ -z "$ts_dns" && -z "$ts_ip" ]]; then
    echo "Tailscale URL:  已偵測到 tailscale，但無法取得 MagicDNS/IP"
  fi
}

print_urls() {
  echo
  local_urls
  tailscale_urls
  echo
}

usage() {
  cat <<EOF
AI Stock Dashboard runner

Usage:
  ./run.sh <command> [args]

Commands:
  help, --help, -h       顯示說明
  up                     建置並背景啟動 Docker Compose 服務
  down                   停止並移除容器
  down_up                down 後重新 up
  restart                down_up 的別名
  build                  只建置 image
  rebuild                不用 cache 重新建置 image
  log, logs              追蹤服務 log
  status, ps             查看 compose / container 狀態與 URL
  url, urls              顯示 Local / LAN / Tailscale URL
  test                   在容器內跑 pytest
  shell                  進入服務容器 shell
  config                 顯示 docker compose 合併後設定

Environment:
  APP_PORT=8507          對外映射 port，預設 8507
  COMPOSE_FILE=docker-compose.yml

Examples:
  ./run.sh up
  ./run.sh status
  ./run.sh logs
  ./run.sh down_up
  APP_PORT=8510 ./run.sh up
EOF
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "找不到 docker 指令。請先安裝 Docker。" >&2
    exit 1
  fi
}

sync_portfolio_file() {
  mkdir -p docker_runtime/portfolio
  local src=""
  if [[ -f my_stocks.json ]]; then
    src="my_stocks.json"
  elif [[ -f my_sotcks.json ]]; then
    src="my_sotcks.json"
  fi
  if [[ -n "$src" ]]; then
    cp "$src" docker_runtime/portfolio/my_stocks.json
    echo "已同步本機持倉檔到 docker_runtime/portfolio/my_stocks.json（不會上傳 GitHub）。"
  fi
}

cmd="${1:-help}"
shift || true

case "$cmd" in
  help|--help|-h)
    usage
    ;;
  up)
    require_docker
    mkdir -p docker_runtime
    sync_portfolio_file
    compose_cmd up -d --build "$@"
    compose_cmd ps
    print_urls
    ;;
  down)
    require_docker
    compose_cmd down "$@"
    ;;
  down_up|restart)
    require_docker
    mkdir -p docker_runtime
    sync_portfolio_file
    compose_cmd down
    compose_cmd up -d --build "$@"
    compose_cmd ps
    print_urls
    ;;
  build)
    require_docker
    compose_cmd build "$@"
    ;;
  rebuild)
    require_docker
    compose_cmd build --no-cache "$@"
    ;;
  log|logs)
    require_docker
    compose_cmd logs -f --tail=200 "$@"
    ;;
  status|ps)
    require_docker
    compose_cmd ps
    print_urls
    ;;
  url|urls)
    print_urls
    ;;
  test)
    require_docker
    compose_cmd run --rm "$SERVICE_NAME" pytest -q "$@"
    ;;
  shell)
    require_docker
    compose_cmd exec "$SERVICE_NAME" /bin/bash "$@"
    ;;
  config)
    require_docker
    compose_cmd config "$@"
    ;;
  *)
    echo "未知指令：$cmd" >&2
    echo >&2
    usage >&2
    exit 2
    ;;
esac
