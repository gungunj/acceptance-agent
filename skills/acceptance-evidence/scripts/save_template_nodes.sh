#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"

TASK_ID=""
INPUT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-id)
      TASK_ID="${2:-}"
      shift 2
      ;;
    --input)
      INPUT_PATH="${2:-}"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--task-id <task_id>] --input <template_nodes.json>" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${INPUT_PATH}" ]]; then
  echo "Usage: $0 [--task-id <task_id>] --input <template_nodes.json>" >&2
  exit 1
fi

CLI_BIN="$(resolve_cli_bin)"
TASK_ID="$(ensure_task_id "${CLI_BIN}" "${TASK_ID}")"
"${CLI_BIN}" save-template-nodes --task-id "${TASK_ID}" --input "${INPUT_PATH}"
