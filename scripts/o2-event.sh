#!/usr/bin/env bash
# Envía un evento del pipeline a OpenObserve (stream "cicd_events") vía HTTP/JSON (RF-03).
# Uso: scripts/o2-event.sh <event_type> <status> [detalle] [archivo_json_extra]
#   event_type: tests | deploy | deploy_blocked
#   status:     success | failure | skipped
# Requiere: O2_URL, O2_USER, O2_PASSWORD  (secrets de GitHub)
set -euo pipefail

EVENT_TYPE="${1:?event_type}"
STATUS="${2:?status}"
DETAIL="${3:-}"
EXTRA_FILE="${4:-}"

if [ -z "${O2_URL:-}" ]; then
  echo "O2_URL no configurado; se omite el envío a OpenObserve"
  exit 0
fi

EXTRA='{}'
if [ -n "$EXTRA_FILE" ] && [ -f "$EXTRA_FILE" ]; then EXTRA="$(cat "$EXTRA_FILE")"; fi

BODY=$(jq -n \
  --arg event_type "$EVENT_TYPE" \
  --arg status "$STATUS" \
  --arg detail "$DETAIL" \
  --arg commit "${GITHUB_SHA:-local}" \
  --arg commit_short "${GITHUB_SHA:0:7}" \
  --arg commit_message "${COMMIT_MESSAGE:-}" \
  --arg branch "${GITHUB_REF_NAME:-local}" \
  --arg actor "${GITHUB_ACTOR:-local}" \
  --arg repository "${GITHUB_REPOSITORY:-}" \
  --arg workflow "${GITHUB_WORKFLOW:-}" \
  --arg run_id "${GITHUB_RUN_ID:-}" \
  --arg run_url "${GITHUB_SERVER_URL:-}/${GITHUB_REPOSITORY:-}/actions/runs/${GITHUB_RUN_ID:-}" \
  --arg event "${GITHUB_EVENT_NAME:-}" \
  --argjson extra "$EXTRA" \
  '[{event_type:$event_type, status:$status, detail:$detail, commit:$commit,
     commit_short:$commit_short, commit_message:$commit_message, branch:$branch,
     actor:$actor, repository:$repository, workflow:$workflow, run_id:$run_id,
     run_url:$run_url, trigger:$event} + $extra]')

echo "$BODY"
curl -sS --fail-with-body --max-time 15 \
  -u "${O2_USER}:${O2_PASSWORD}" \
  -H "Content-Type: application/json" \
  -d "$BODY" \
  "${O2_URL%/}/api/default/cicd_events/_json" || echo "::warning::No se pudo enviar el evento a OpenObserve"
