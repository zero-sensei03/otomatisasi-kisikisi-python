#!/usr/bin/env bash

revision_has_test_deps() {
  local interpreter="$1"
  [[ -x "$interpreter" ]] || return 1
  "$interpreter" -c 'import importlib.util; names=("pytest", "pytest_cov", "coverage"); raise SystemExit(any(importlib.util.find_spec(name) is None for name in names))' >/dev/null 2>&1
}

prepare_revision_python() {
  local root="$1"
  local revision_venv="${REVISION_VENV:-$root/.venv-revision}"
  local candidate

  if [[ -n "${REVISION_PYTHON:-}" ]]; then
    if ! revision_has_test_deps "$REVISION_PYTHON"; then
      echo "REVISION_PYTHON must point to an interpreter with pytest, pytest-cov and coverage." >&2
      return 2
    fi
    return 0
  fi

  local candidates=("$root/.venv/bin/python")
  if [[ -n "${REVISION_VENV:-}" ]]; then
    candidates=("$revision_venv/bin/python" "$root/.venv/bin/python")
  else
    candidates+=("$revision_venv/bin/python")
  fi
  for candidate in "${candidates[@]}"; do
    if revision_has_test_deps "$candidate"; then
      export REVISION_PYTHON="$candidate"
      echo "Using test environment: $REVISION_PYTHON"
      return 0
    fi
  done

  if ! command -v uv >/dev/null 2>&1; then
    echo "Test dependencies are missing and uv was not found. Install uv or set REVISION_PYTHON." >&2
    return 2
  fi

  echo "Preparing isolated revision environment at $revision_venv (production .venv is untouched)."
  if ! UV_PROJECT_ENVIRONMENT="$revision_venv" uv sync --project "$root" --frozen --group dev; then
    echo "Could not prepare the revision environment. Check package registry access or provide REVISION_PYTHON." >&2
    return 2
  fi
  candidate="$revision_venv/bin/python"
  if ! revision_has_test_deps "$candidate"; then
    echo "The revision environment does not contain the required pytest dependencies." >&2
    return 2
  fi
  export REVISION_PYTHON="$candidate"
  echo "Using test environment: $REVISION_PYTHON"
}
