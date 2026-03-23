#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/venv/bin"

if [[ -x "${VENV_DIR}/python" ]] && [[ -x "${VENV_DIR}/bandit" ]] && [[ -x "${VENV_DIR}/pip-audit" ]]; then
  PY_CMD="${VENV_DIR}/python"
  BANDIT_CMD="${VENV_DIR}/bandit"
  PIP_AUDIT_CMD="${VENV_DIR}/pip-audit"
else
  PY_CMD="$(command -v python3 || true)"
  BANDIT_CMD="$(command -v bandit || true)"
  PIP_AUDIT_CMD="$(command -v pip-audit || true)"
fi

if [[ -z "${PY_CMD}" ]]; then
  echo "error: python3 not found." >&2
  exit 1
fi

if [[ -z "${BANDIT_CMD}" ]] || [[ -z "${PIP_AUDIT_CMD}" ]]; then
  echo "error: bandit/pip-audit not found. Install in venv or system Python: pip install bandit pip-audit" >&2
  exit 1
fi

echo "[1/4] Bandit policy gate"
"${BANDIT_CMD}" -c "${ROOT_DIR}/security/bandit.yaml" -r "${ROOT_DIR}/app" -ll

echo "[2/4] Dependency vulnerability gate"
"${PIP_AUDIT_CMD}" -r "${ROOT_DIR}/requirements.txt"

echo "[3/4] Regression test gate"
"${PY_CMD}" -m unittest discover -s "${ROOT_DIR}/tests" -v

echo "[4/4] Dynamic security smoke gate"
"${PY_CMD}" "${ROOT_DIR}/scripts/security_smoke.py"

if [[ "${AQ_RUN_STAGING_REDIS_E2E:-false}" == "true" ]]; then
  echo "[5/5] Staging Redis E2E smoke gate"
  "${PY_CMD}" "${ROOT_DIR}/scripts/staging_redis_e2e_smoke.py" --redis-url "${AQ_STAGING_REDIS_URL:-${AQ_AUTH_RATE_LIMIT_REDIS_URL:-}}"
fi

if [[ "${AQ_RUN_STAGING_REDIS_CHAOS:-false}" == "true" ]]; then
  echo "[6/6] Staging Redis Toxiproxy chaos gate"
  "${PY_CMD}" "${ROOT_DIR}/scripts/staging_redis_toxiproxy_chaos.py"
fi

echo "Security gate: PASS"
