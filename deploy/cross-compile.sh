#!/usr/bin/env bash
# deploy/cross-compile.sh
#
# Cross-compile aevum for AWS c7g.xlarge (aarch64-unknown-linux-gnu, light_node)
# and upload the binary to the Membrane Router via scp.
#
# Prerequisites on the build machine (M1 Ultra, genesis_node):
#   brew install zig            # https://ziglang.org
#   cargo install cargo-zigbuild
#   rustup target add aarch64-unknown-linux-gnu
#
# Usage:
#   ./deploy/cross-compile.sh              # build + upload
#   ./deploy/cross-compile.sh --build-only # skip scp
#   DRY_RUN=1 ./deploy/cross-compile.sh   # print commands, do not execute

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

TARGET="aarch64-unknown-linux-gnu"
FEATURES="light_node"
BINARY_NAME="aevum"
WORKSPACE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_PATH="${WORKSPACE_ROOT}/target/${TARGET}/release/${BINARY_NAME}"

REMOTE_USER="ec2-user"
REMOTE_HOST="100.116.253.50"
REMOTE_DIR="~/aevum/"

BUILD_ONLY=0
DRY_RUN="${DRY_RUN:-0}"

# ── Argument parsing ──────────────────────────────────────────────────────────

for arg in "$@"; do
    case "$arg" in
        --build-only) BUILD_ONLY=1 ;;
        --help|-h)
            echo "Usage: $0 [--build-only]"
            echo "  --build-only   cross-compile only; skip scp upload"
            echo "  DRY_RUN=1      print commands without executing"
            exit 0
            ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────

run() {
    if [[ "${DRY_RUN}" == "1" ]]; then
        echo "[DRY_RUN] $*"
    else
        echo "+ $*"
        "$@"
    fi
}

# ── Step 1: cross-compile ─────────────────────────────────────────────────────

echo "==> Building aevum for ${TARGET} (features=${FEATURES})"
echo "    workspace: ${WORKSPACE_ROOT}"

run cargo zigbuild \
    --release \
    --features "${FEATURES}" \
    --target "${TARGET}" \
    --manifest-path "${WORKSPACE_ROOT}/Cargo.toml"

echo "==> Build complete: ${OUTPUT_PATH}"

# Sanity-check that the binary was actually produced.
if [[ "${DRY_RUN}" != "1" ]] && [[ ! -f "${OUTPUT_PATH}" ]]; then
    echo "ERROR: expected binary not found at ${OUTPUT_PATH}" >&2
    exit 1
fi

# ── Step 2: upload ────────────────────────────────────────────────────────────

if [[ "${BUILD_ONLY}" -eq 1 ]]; then
    echo "==> --build-only set; skipping upload."
    exit 0
fi

echo "==> Uploading to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}"
run scp \
    -o StrictHostKeyChecking=accept-new \
    "${OUTPUT_PATH}" \
    "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}"

echo "==> Upload complete."
echo ""
echo "Restart the service on the remote host:"
echo "  ssh ${REMOTE_USER}@${REMOTE_HOST} 'sudo systemctl restart aevum'"
