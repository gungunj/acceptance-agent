#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"

CLI_BIN="$(resolve_cli_bin)"
TASK_ID="$(ensure_task_id "${CLI_BIN}" "${1:-}")"
echo "${TASK_ID}"
