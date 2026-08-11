#!/usr/bin/env bash
# ==============================================================================
# ComfyUI Dynamic Sideload Hook & Setup for DAG Substrate
# 
# Purpose:
#   Maintains seamless compatibility when repository is pulled across
#   different hardware (NVIDIA GPU workstations, Apple Silicon, Cloud VMs,
#   or CPU-only edge devices).
#
#   On compatible GPU hardware: Installs and launches live ComfyUI backend.
#   On lightweight/CPU hardware: Operates in standby mode with procedural fallback.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FOUNDATION_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_PURPLE="\033[38;5;141m"
CLR_CYAN="\033[38;5;51m"
CLR_GREEN="\033[38;5;48m"
CLR_AMBER="\033[38;5;214m"

info()    { echo -e "${CLR_PURPLE}[COMFY-SIDELOAD]${CLR_RESET} $1"; }
success() { echo -e "${CLR_GREEN}[OK]${CLR_RESET} $1"; }
warn()    { echo -e "${CLR_AMBER}[STANDBY]${CLR_RESET} $1"; }

echo -e "${CLR_BOLD}${CLR_CYAN}====================================================================${CLR_RESET}"
echo -e "${CLR_BOLD}${CLR_CYAN}  COMFYUI DYNAMIC SIDELOAD MANAGER (HARDWARE COMPATIBILITY HOOK)${CLR_RESET}"
echo -e "${CLR_BOLD}${CLR_CYAN}====================================================================${CLR_RESET}"

COMFY_DIR="${HOME}/ComfyUI"
COMFY_PORT="${COMFYUI_PORT:-8188}"
COMFY_HOST="${COMFYUI_HOST:-127.0.0.1}"

# 1. Hardware Detection
HAS_NVIDIA=0
HAS_ROCM=0
HAS_APPLE=0

if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  HAS_NVIDIA=1
  GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1)"
  info "NVIDIA GPU Detected: ${GPU_NAME} (Full acceleration enabled)"
elif [ -d "/opt/rocm" ] || command -v rocm-smi >/dev/null 2>&1; then
  HAS_ROCM=1
  info "AMD ROCm GPU Detected (ROCm acceleration enabled)"
elif [[ "$(uname -s)" == "Darwin" ]] && [[ "$(uname -m)" == "arm64" ]]; then
  HAS_APPLE=1
  info "Apple Silicon Detected (MPS acceleration enabled)"
else
  warn "No dedicated GPU detected on current host ($(uname -m))."
  warn "ComfyUI treated as dynamic side-load. Lightweight procedural glyph generation active."
fi

# 2. Check if already running
if curl -sf "http://${COMFY_HOST}:${COMFY_PORT}/system_stats" >/dev/null 2>&1; then
  success "ComfyUI is already LIVE on http://${COMFY_HOST}:${COMFY_PORT}"
  exit 0
fi

# 3. Handle Installation & Launch for GPU hosts
ACTION="${1:-status}"

if [[ "$ACTION" == "install" || "$ACTION" == "start" ]]; then
  if [ ! -d "${COMFY_DIR}" ]; then
    info "Cloning ComfyUI to ${COMFY_DIR}..."
    git clone https://github.com/comfyanonymous/ComfyUI.git "${COMFY_DIR}"
  fi

  info "Installing ComfyUI requirements..."
  python3 -m pip install --break-system-packages -q -r "${COMFY_DIR}/requirements.txt" || \
  python3 -m pip install -q -r "${COMFY_DIR}/requirements.txt"

  info "Launching ComfyUI in background..."
  cd "${COMFY_DIR}"
  nohup python3 main.py --listen "${COMFY_HOST}" --port "${COMFY_PORT}" > /tmp/comfyui.log 2>&1 &
  echo $! > /tmp/comfyui.pid
  
  sleep 3
  if curl -sf "http://${COMFY_HOST}:${COMFY_PORT}/system_stats" >/dev/null 2>&1; then
    success "ComfyUI successfully launched on http://${COMFY_HOST}:${COMFY_PORT}"
  else
    warn "ComfyUI launched. Initializing models (logs at /tmp/comfyui.log)..."
  fi
else
  info "Status check: Substrate is configured to route image MCP requests to ${COMFY_HOST}:${COMFY_PORT}."
  info "To start ComfyUI on this host when compatible: $0 start"
  info "Or export COMFYUI_URL=http://<remote-gpu-host>:8188 for remote outsourcing."
fi
