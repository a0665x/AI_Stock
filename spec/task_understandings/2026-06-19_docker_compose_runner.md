# Docker Compose + run.sh packaging

Date: 2026-06-19

## Goal
將 Streamlit 股票決策儀表板包成 Docker Compose 專案，並提供一鍵式 `run.sh` 管理入口。

## Added files
- `Dockerfile`
  - 基於 `python:3.11-slim`
  - 安裝 ARM/aarch64 可用的 build tools、OpenBLAS、Python dependencies
  - 啟動 `streamlit run src/ai_stock/app.py --server.port=8507 --server.address=0.0.0.0`
  - 內建 Streamlit healthcheck
- `docker-compose.yml`
  - service: `ai-stock-dashboard`
  - container: `ai-stock-dashboard`
  - image: `ai-stock-dashboard:latest`
  - port: `${APP_PORT:-8507}:8507`
  - volume: `./runtime:/app/runtime`
- `.dockerignore`
  - 排除 `.venv/`、cache、build artefacts、runtime logs
- `run.sh`
  - 支援 `up`, `down`, `down_up`, `restart`, `build`, `rebuild`, `log(s)`, `status`, `url(s)`, `test`, `shell`, `config`
  - 自動偵測 `docker compose` plugin 或 legacy `docker-compose`
  - `up/status/url` 會列出 Local、LAN、Tailscale MagicDNS、Tailscale IP URL

## Verified
- `bash -n run.sh`: pass
- `bash run.sh --help`: pass
- `bash run.sh config`: Docker Compose config parsed successfully
- `bash run.sh build`: Docker image built successfully on ARM/aarch64; `shap` and `futu-api` installed
- `bash run.sh test`: container pytest passed, `8 passed`
- `bash run.sh up`: service started via Docker Compose
- Health endpoint: `http://127.0.0.1:8507/_stcore/health` returned `ok`
- Generated URLs on current host:
  - Local: `http://127.0.0.1:8507`
  - LAN: `http://192.168.1.121:8507`
  - Tailscale DNS: `http://agx-monitor.tail9e662c.ts.net:8507`
  - Tailscale IP: `http://100.94.21.85:8507`

## Notes
- `run.sh` can be executed with `bash run.sh ...` if execute bit is not set yet.
- A previous local `.venv` Streamlit process occupied port 8507 and was stopped so Docker Compose could bind the port.
- This packaging does not configure Tailscale Serve/Funnel; it only generates URLs from the host's existing Tailscale state.
