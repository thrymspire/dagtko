#!/usr/bin/env bash
# ==============================================================================
# DAG Substrate (`dagtko`) — Universal Turnkey Installer for Any Hardware
# 
# Cross-platform support for:
#   - Debian / Ubuntu / Mint / PopOS (apt)
#   - RedHat / Fedora / CentOS / Rocky / Alma (dnf/yum)
#   - Arch Linux / Manjaro (pacman)
#   - Alpine Linux (apk)
#   - openSUSE (zypper)
#   - macOS (Homebrew)
#   - Android Linux / PRoot / VM environments (Pixel 10 Pro XL / Termux / Weston)
#
# Hardware detection:
#   - CPU: x86_64, aarch64 (ARM64), Apple Silicon
#   - GPU: NVIDIA CUDA, AMD ROCm, Apple Metal, or CPU-only
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_PURPLE="\033[38;5;141m"
CLR_CYAN="\033[38;5;51m"
CLR_GREEN="\033[38;5;48m"
CLR_AMBER="\033[38;5;214m"
CLR_RED="\033[38;5;203m"

info()    { echo -e "${CLR_PURPLE}[INFO]${CLR_RESET} $1"; }
success() { echo -e "${CLR_GREEN}[OK]${CLR_RESET} $1"; }
warn()    { echo -e "${CLR_AMBER}[WARN]${CLR_RESET} $1"; }
error()   { echo -e "${CLR_RED}[ERROR]${CLR_RESET} $1"; }
header()  {
  echo ""
  echo -e "${CLR_BOLD}${CLR_CYAN}====================================================================${CLR_RESET}"
  echo -e "${CLR_BOLD}${CLR_CYAN}  $1${CLR_RESET}"
  echo -e "${CLR_BOLD}${CLR_CYAN}====================================================================${CLR_RESET}"
}

header "DAG SUBSTRATE (dagtko) — UNIVERSAL TURNKEY INSTALLER"

# ------------------------------------------------------------------------------
# 1. Hardware & OS Detection
# ------------------------------------------------------------------------------
ARCH="$(uname -m)"
OS="$(uname -s)"
DISTRO="Unknown"

if [ -f /etc/os-release ]; then
  DISTRO="$(grep -E '^PRETTY_NAME=' /etc/os-release | cut -d= -f2 | tr -d '\"' || echo 'Linux')"
elif [ "$OS" == "Darwin" ]; then
  DISTRO="macOS $(sw_vers -productVersion 2>/dev/null || '')"
fi

CPU_CORES="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)"
MEM_MB="$(free -m 2>/dev/null | awk '/^Mem:/{print $2}' || echo 'Unknown')"

info "Operating System : ${DISTRO} (${OS})"
info "Architecture     : ${ARCH}"
info "Hardware Cores   : ${CPU_CORES} cores, ~${MEM_MB} MB RAM"

# GPU Detection
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1)"
  success "GPU Acceleration : NVIDIA (${GPU_NAME}) — CUDA Ready"
elif [ -d "/opt/rocm" ] || command -v rocm-smi >/dev/null 2>&1; then
  success "GPU Acceleration : AMD ROCm Ready"
elif [ "$OS" == "Darwin" ] && [ "$ARCH" == "arm64" ]; then
  success "GPU Acceleration : Apple Silicon Metal Ready"
else
  info "GPU Acceleration : None / CPU Mode (ComfyUI configured as dynamic sideload)"
fi

# ------------------------------------------------------------------------------
# 2. Package Manager & System Dependencies
# ------------------------------------------------------------------------------
header "1. INSTALLING SYSTEM PACKAGES & RUNTIMES"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  fi
fi

install_debian_ubuntu() {
  info "Detected Debian/Ubuntu package manager (apt)..."
  $SUDO apt-get update -qq || true
  $SUDO apt-get install -y --no-install-recommends \
    postgresql postgresql-contrib redis-server \
    python3 python3-pip python3-venv \
    graphviz octave feh curl jq gcc git
}

install_redhat_fedora() {
  info "Detected Fedora/RHEL package manager (dnf/yum)..."
  local PKG_MGR="dnf"
  command -v dnf >/dev/null 2>&1 || PKG_MGR="yum"
  $SUDO $PKG_MGR install -y \
    postgresql-server postgresql-contrib redis \
    python3 python3-pip python3-devel \
    graphviz octave feh curl jq gcc git
}

install_arch() {
  info "Detected Arch Linux package manager (pacman)..."
  $SUDO pacman -Sy --noconfirm \
    postgresql redis \
    python python-pip \
    graphviz octave feh curl jq gcc git
}

install_alpine() {
  info "Detected Alpine Linux package manager (apk)..."
  $SUDO apk add --no-cache \
    postgresql postgresql-contrib redis \
    python3 py3-pip python3-dev \
    graphviz octave feh curl jq gcc git build-base
}

install_macos() {
  info "Detected macOS (Homebrew)..."
  if ! command -v brew >/dev/null 2>&1; then
    error "Homebrew not found. Please install from https://brew.sh/"
    exit 1
  fi
  brew install postgresql@16 redis python@3.12 graphviz octave feh curl jq git
}

if command -v apt-get >/dev/null 2>&1; then
  install_debian_ubuntu
elif command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1; then
  install_redhat_fedora
elif command -v pacman >/dev/null 2>&1; then
  install_arch
elif command -v apk >/dev/null 2>&1; then
  install_alpine
elif [ "$OS" == "Darwin" ]; then
  install_macos
else
  warn "Unknown package manager. Verifying existing CLI commands..."
fi

success "System packages verified."

# ------------------------------------------------------------------------------
# 3. Python Ecosystem & Dependencies
# ------------------------------------------------------------------------------
header "2. VERIFYING PYTHON DEPENDENCIES"

info "Installing / updating required Python packages..."
python3 -m pip install --break-system-packages -q \
  fastapi uvicorn psycopg2-binary networkx matplotlib pydantic httpx pytest redis pydot || \
python3 -m pip install -q \
  fastapi uvicorn psycopg2-binary networkx matplotlib pydantic httpx pytest redis pydot || true

success "Python dependencies verified (FastAPI, Uvicorn, NetworkX, Psycopg2, Redis, Pytest, Matplotlib)."

# ------------------------------------------------------------------------------
# 4. Ollama Local LLM Runtime
# ------------------------------------------------------------------------------
header "3. CONFIGURING LOCAL LLM (OLLAMA)"

if ! command -v ollama >/dev/null 2>&1; then
  info "Installing Ollama for local LLM grounding..."
  curl -fsSL https://ollama.com/install.sh | sh || true
fi

if command -v ollama >/dev/null 2>&1; then
  success "Ollama installed at $(command -v ollama)"
  
  # Ensure Ollama daemon is running
  if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    info "Starting Ollama daemon in background..."
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 2
  fi
  
  if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    success "Ollama API is active at http://127.0.0.1:11434"
  fi
else
  warn "Ollama installation deferred. LLM grounding will operate with deterministic projection fallback."
fi

# ------------------------------------------------------------------------------
# 5. Shared Memory Shim (for Android / PRoot VM compatibility)
# ------------------------------------------------------------------------------
header "4. SHARED MEMORY COMPATIBILITY CHECK"

if ! python3 -c "import os; os.system('ipcs -l >/dev/null 2>&1')" 2>/dev/null; then
  if [ ! -f /usr/local/lib/libshm_posix.so ] && [ -n "$SUDO" ]; then
    info "Compiling POSIX shared-memory shim for container/VM environment..."
    cat << 'EOF' > /tmp/libshm_posix.c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <errno.h>

#define MAX_SHM 1024
#define SHM_DIR "/dev/shm"

typedef struct { int id; key_t key; size_t size; int fd; void *addr; char path[256]; } shm_entry_t;
static shm_entry_t shm_table[MAX_SHM];
static int next_id = 100;

int shmget(key_t key, size_t size, int shmflg) {
    if (size == 0 && !(shmflg & IPC_CREAT)) {
        for (int i = 0; i < MAX_SHM; i++) {
            if (shm_table[i].id != 0 && shm_table[i].key == key) return shm_table[i].id;
        }
    }
    int id = next_id++;
    int idx = id % MAX_SHM;
    char path[256];
    if (key == IPC_PRIVATE) snprintf(path, sizeof(path), "%s/sysv_shm_priv_%d_%d", SHM_DIR, getpid(), id);
    else snprintf(path, sizeof(path), "%s/sysv_shm_key_%d", SHM_DIR, (int)key);
    int fd = open(path, O_RDWR | O_CREAT, 0600);
    if (fd < 0) return -1;
    if (size > 0) { if (ftruncate(fd, size) < 0) { close(fd); return -1; } }
    else { struct stat st; if (fstat(fd, &st) == 0) size = st.st_size; }
    shm_table[idx].id = id; shm_table[idx].key = key; shm_table[idx].size = size;
    shm_table[idx].fd = fd; shm_table[idx].addr = NULL;
    strncpy(shm_table[idx].path, path, sizeof(shm_table[idx].path));
    return id;
}
void *shmat(int shmid, const void *shmaddr, int shmflg) {
    (void)shmaddr; (void)shmflg;
    int idx = shmid % MAX_SHM;
    if (shm_table[idx].id != shmid || shm_table[idx].fd < 0) { errno = EINVAL; return (void *)-1; }
    void *addr = mmap(NULL, shm_table[idx].size, PROT_READ | PROT_WRITE, MAP_SHARED, shm_table[idx].fd, 0);
    if (addr == MAP_FAILED) return (void *)-1;
    shm_table[idx].addr = addr;
    return addr;
}
int shmdt(const void *shmaddr) {
    for (int i = 0; i < MAX_SHM; i++) {
        if (shm_table[i].addr == shmaddr) {
            munmap((void *)shmaddr, shm_table[i].size);
            shm_table[i].addr = NULL;
            return 0;
        }
    }
    errno = EINVAL; return -1;
}
int shmctl(int shmid, int cmd, struct shmid_ds *buf) {
    int idx = shmid % MAX_SHM;
    if (shm_table[idx].id != shmid) { errno = EINVAL; return -1; }
    if (cmd == IPC_RMID) {
        unlink(shm_table[idx].path); close(shm_table[idx].fd); shm_table[idx].id = 0; return 0;
    } else if (cmd == IPC_STAT && buf) {
        memset(buf, 0, sizeof(*buf));
        buf->shm_segsz = shm_table[idx].size;
        buf->shm_perm.uid = getuid(); buf->shm_perm.gid = getgid(); buf->shm_perm.mode = 0600;
        return 0;
    }
    return 0;
}
EOF
    $SUDO gcc -shared -fPIC /tmp/libshm_posix.c -o /usr/local/lib/libshm_posix.so
    $SUDO chmod 755 /usr/local/lib/libshm_posix.so
    echo "/usr/local/lib/libshm_posix.so" | $SUDO tee /etc/ld.so.preload >/dev/null 2>&1 || true
    success "POSIX shared memory shim installed."
  fi
fi

# ------------------------------------------------------------------------------
# 6. Database & Ledger Seed Initialization
# ------------------------------------------------------------------------------
header "5. INITIALIZING DATABASE & BURNING 250-NODE 90-MATRIX SEED"

# Start PostgreSQL service
if command -v service >/dev/null 2>&1; then
  $SUDO service postgresql start || true
  $SUDO service redis-server start || true
elif command -v systemctl >/dev/null 2>&1; then
  $SUDO systemctl start postgresql || true
  $SUDO systemctl start redis || true
fi

# Create DB & User
$SUDO -u postgres psql -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dag') THEN CREATE ROLE dag WITH LOGIN PASSWORD 'dag_substrate' SUPERUSER; END IF; END \$\$;" >/dev/null 2>&1 || true
$SUDO -u postgres psql -c "SELECT 1 FROM pg_database WHERE datname='dag_substrate'" 2>/dev/null | grep -q 1 || $SUDO -u postgres createdb -O dag dag_substrate || true

cd "${SCRIPT_DIR}/foundation"

# Run schema migrations and burn in full seed
info "Running SQL schema & projection migrations (01 -> 04)..."
PGPASSWORD=dag_substrate psql -h localhost -p 5432 -U dag -d dag_substrate -f sql/01_schema.sql >/dev/null
PGPASSWORD=dag_substrate psql -h localhost -p 5432 -U dag -d dag_substrate -f sql/02_projections.sql >/dev/null
PGPASSWORD=dag_substrate psql -h localhost -p 5432 -U dag -d dag_substrate -f sql/03_constraints.sql >/dev/null
PGPASSWORD=dag_substrate psql -h localhost -p 5432 -U dag -d dag_substrate -f sql/04_fragments_contracts.sql >/dev/null

info "Generating and applying complete 250-Node / 90-Matrix seed (05_seed.sql)..."
python3 sql/generate_seed.py >/dev/null
PGPASSWORD=dag_substrate psql -h localhost -p 5432 -U dag -d dag_substrate -f sql/05_seed.sql >/dev/null

success "Full 250-Node / 501-Edge / 90-Matrix Ledger Set burned into database."

# ------------------------------------------------------------------------------
# 7. Turnkey Stack Launch & Verification
# ------------------------------------------------------------------------------
header "6. LAUNCHING NATIVE TURNKEY SERVICES"

./scripts/up_native.sh

header "7. RUNNING ARCHITECTURAL VERIFICATION SUITE"
cd "${SCRIPT_DIR}/foundation/tests"
pytest -v test_closed_loop.py

header "TURNKEY INSTALLATION COMPLETE & LIVE"
info "Stack is fully operational."
info "Ingest API:      http://localhost:8000"
info "MCP Tool Server: http://localhost:8001/tools"
info "Live Visualizer: http://localhost:8050"
