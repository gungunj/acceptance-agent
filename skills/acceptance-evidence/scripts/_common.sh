#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
STATE_DIR="${SKILL_DIR}/.state"
TASK_FILE="${STATE_DIR}/current_task_id"

resolve_cli_bin() {
  local cli_bin="acceptance-agent"
  if ! command -v "${cli_bin}" >/dev/null 2>&1; then
    if [[ -x "./acceptance-agent" ]]; then
      cli_bin="./acceptance-agent"
    else
      echo "acceptance-agent command not found. Please run: pip install -e ." >&2
      exit 1
    fi
  fi
  echo "${cli_bin}"
}

ensure_task_id() {
  local cli_bin="$1"
  local task_id="${2:-}"

  mkdir -p "${STATE_DIR}"

  if [[ -n "${task_id}" ]]; then
    echo "${task_id}" > "${TASK_FILE}"
    echo "${task_id}"
    return 0
  fi

  if [[ -f "${TASK_FILE}" ]]; then
    task_id="$(tr -d '[:space:]' < "${TASK_FILE}")"
    if [[ -n "${task_id}" ]]; then
      echo "${task_id}"
      return 0
    fi
  fi

  local title
  local description
  title="${ACCEPTANCE_TASK_TITLE:-OpenClaw Acceptance Task $(date +%Y%m%d-%H%M%S)}"
  description="${ACCEPTANCE_TASK_DESCRIPTION:-Created automatically by acceptance-evidence skill}"

  task_id="$("${cli_bin}" create-task --title "${title}" --description "${description}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
  echo "${task_id}" > "${TASK_FILE}"
  echo "Created task_id=${task_id}" >&2
  echo "${task_id}"
}
