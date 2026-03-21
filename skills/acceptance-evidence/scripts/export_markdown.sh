#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"

TASK_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-id)
      TASK_ID="${2:-}"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--task-id <task_id>]" >&2
      exit 1
      ;;
  esac
done

CLI_BIN="$(resolve_cli_bin)"
TASK_ID="$(ensure_task_id "${CLI_BIN}" "${TASK_ID}")"
"${CLI_BIN}" export-markdown --task-id "${TASK_ID}"
