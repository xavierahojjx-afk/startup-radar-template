#!/usr/bin/env bash
# Stop hook — fast lint+format gate (NOT `make ci`). Surfaces anti-patterns from this session.
# exit 2 = block (hardcoded secrets, requirements.txt edits when pyproject exists, uv.lock edits).
# exit 0 = allow (warnings printed to stdout become next-turn context).
set -uo pipefail

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  exit 0
fi

CHANGED=$( { git diff --name-only HEAD 2>/dev/null; git diff --cached --name-only 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } | sort -u | grep -v '^$' || true)

if [ -z "${CHANGED}" ]; then
  exit 0  # Nothing to check — quiet.
fi

ISSUES=""
BLOCK=0

PY_FILES=$(echo "${CHANGED}" | grep -E '\.py$' || true)

# 1. print() in library code
if [ -n "${PY_FILES}" ]; then
  LIBRARY_PY=$(echo "${PY_FILES}" | grep -Ev '^(startup_radar/cli\.py|startup_radar/research/deepdive\.py|tests/|\.claude/)' || true)
  if [ -n "${LIBRARY_PY}" ]; then
    PRINTS=$(echo "${LIBRARY_PY}" | xargs grep -lE '^[^#]*\bprint\(' 2>/dev/null | head -3 || true)
    if [ -n "${PRINTS}" ]; then
      ISSUES="${ISSUES}
WARN: print() in library code: ${PRINTS} — use a logger."
    fi
  fi
fi

# 2. bare/broad except
if [ -n "${PY_FILES}" ]; then
  BARE=$(echo "${PY_FILES}" | xargs grep -lE 'except\s*:|except\s+Exception\s*:' 2>/dev/null | head -3 || true)
  if [ -n "${BARE}" ]; then
    ISSUES="${ISSUES}
WARN: bare/broad except in: ${BARE} — narrow the exception or log+re-raise."
  fi
fi

# 3. os.getenv outside config layer
if [ -n "${PY_FILES}" ]; then
  CONFIG_OK=$(echo "${PY_FILES}" | grep -Ev '^startup_radar/config/' || true)
  if [ -n "${CONFIG_OK}" ]; then
    ENV=$(echo "${CONFIG_OK}" | xargs grep -lE 'os\.getenv|os\.environ\b' 2>/dev/null | head -3 || true)
    if [ -n "${ENV}" ]; then
      ISSUES="${ISSUES}
WARN: os.getenv/os.environ outside config layer in: ${ENV}"
    fi
  fi
fi

# 4. hardcoded secrets (literal assignment, ≥16 chars, common keys)
SECRET_PAT='(api_key|apikey|api-key|secret|password|passwd|token|bearer)\s*[:=]\s*["\047][A-Za-z0-9_\-]{16,}'
SECRETS=$(echo "${CHANGED}" | xargs grep -ilE "${SECRET_PAT}" 2>/dev/null | head -3 || true)
if [ -n "${SECRETS}" ]; then
  ISSUES="${ISSUES}
BLOCK: potential hardcoded secret in: ${SECRETS}"
  BLOCK=1
fi

# 5. requirements.txt edits when pyproject.toml exists
if echo "${CHANGED}" | grep -q '^requirements\.txt$'; then
  if [ -f pyproject.toml ] && grep -q '^\[project\]' pyproject.toml 2>/dev/null; then
    ISSUES="${ISSUES}
BLOCK: requirements.txt edited but pyproject.toml exists. Edit pyproject.toml; regenerate via uv lock."
    BLOCK=1
  fi
fi

# 6. uv.lock manual edits — block only if uv.lock is the *only* change
#    (hand-edit signal). Legitimate regeneration via `uv add`/`uv sync`
#    also touches pyproject.toml (or other code), so we skip the block
#    when anything else changed. The Edit/Write(uv.lock) deny in
#    settings.json is the primary guardrail; this is defence in depth.
if echo "${CHANGED}" | grep -q '^uv\.lock$'; then
  NON_LOCK=$(echo "${CHANGED}" | grep -v '^uv\.lock$' || true)
  if [ -z "${NON_LOCK}" ]; then
    ISSUES="${ISSUES}
BLOCK: uv.lock changed alone — looks hand-edited. Run \`uv lock\` to regenerate."
    BLOCK=1
  fi
fi

# 7. Run lint (NOT full CI). Fast, ≤5s.
if [ -f Makefile ] && grep -q '^lint:' Makefile; then
  LINT_OUT=$(make lint 2>&1 || true)
  if echo "${LINT_OUT}" | grep -qE '(error|Error|ERROR|would reformat)'; then
    ISSUES="${ISSUES}

LINT FAILED:
${LINT_OUT}"
  fi
fi

if [ -n "${ISSUES}" ]; then
  printf "Pre-stop checks:\n%s\n" "${ISSUES}"
fi

if [ "${BLOCK}" -eq 1 ]; then
  exit 2
fi
exit 0
