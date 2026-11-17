#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REV="$ROOT/docs/revision"
REPORTS="$REV/reports"
SUMMARY="$REPORTS/summary"
MODE="${1:-all}"
case "$MODE" in all|tests|coverage|performance|report) ;; *) echo "Usage: bash docs/revision/run_revision.sh [all|tests|coverage|performance|report]" >&2; exit 2 ;; esac
mkdir -p "$REPORTS/coverage/htmlcov" "$REPORTS/performance" "$REPORTS/black_box" "$SUMMARY" "$REV/testing/test_evidence"
cd "$ROOT"

source "$REV/scripts/prepare_python.sh"
prepare_revision_python "$ROOT" || exit $?
PYTHON="$REVISION_PYTHON"
export REVISION_PYTHON
run_python() {
  "$PYTHON" "$@"
}
run_pytest() {
  DATABASE_URL=sqlite:// SECRET_KEY=revision-test-only DEBUG=false "$PYTHON" -m pytest "$@"
}

echo "Project: $ROOT"
run_python -c 'import sys, importlib.util; required=("pytest", "pytest_cov", "coverage"); missing=[name for name in required if importlib.util.find_spec(name) is None]; print("Python:", sys.version); print("Testing modules:", {name: importlib.util.find_spec(name) is not None for name in required}); raise SystemExit(bool(missing))' || { echo "Test dependencies missing: run uv sync --group dev" >&2; exit 2; }
DATABASE_URL=sqlite:// SECRET_KEY=revision-test-only DEBUG=false run_python -c 'from app.core.config import Settings; from app.integrations.ai.settings import AISettings; app=Settings(); ai=AISettings(); print("Application config:", {"app_name": app.app_name, "debug": app.debug, "database_configured": bool(app.database_url)}); print("AI config:", {"provider": ai.ai_provider, "model": ai.ai_model, "timeout_seconds": ai.ai_timeout_seconds, "api_key_configured": bool(ai.gemini_api_key)}); assert app.database_url and app.secret_key and ai.ai_timeout_seconds > 0' || { echo "Application config validation failed." >&2; exit 2; }
echo "Test DB isolation: tests/conftest.py forces SQLite in-memory; no migration or production DB operation is part of this runner."
echo "AI mode: external Gemini API is not called by pytest; mocks are used."
run_python "$REV/scripts/collect_evidence.py" || exit 1

failed=0
case "$MODE" in
  tests)
    bash "$REV/scripts/run_tests.sh" || failed=1
    ;;
  coverage)
    run_pytest tests/ -v --junitxml="$SUMMARY/pytest-junit.xml" --cov=app --cov-report=term-missing --cov-report="html:$REPORTS/coverage/htmlcov" --cov-report="xml:$REPORTS/coverage/coverage.xml" --cov-report="json:$REPORTS/coverage/coverage.json" 2>&1 | tee "$SUMMARY/coverage-tests.log"
    [[ "${PIPESTATUS[0]}" -eq 0 ]] || failed=1
    ;;
  performance)
    run_python "$REV/scripts/run_performance.py" --output-dir "$REPORTS/performance" || failed=1
    ;;
  report)
    ;;
  all)
    bash "$REV/scripts/run_tests.sh" || failed=1
    run_pytest tests/ -v --junitxml="$SUMMARY/pytest-junit.xml" --cov=app --cov-report=term-missing --cov-report="html:$REPORTS/coverage/htmlcov" --cov-report="xml:$REPORTS/coverage/coverage.xml" --cov-report="json:$REPORTS/coverage/coverage.json" 2>&1 | tee "$SUMMARY/coverage-tests.log"
    [[ "${PIPESTATUS[0]}" -eq 0 ]] || failed=1
    run_python "$REV/scripts/run_performance.py" --output-dir "$REPORTS/performance" || failed=1
    ;;
esac

run_python "$REV/scripts/generate_report.py" || failed=1
echo
echo "Revision artifacts: $REPORTS"
echo "Coverage dashboard: $REPORTS/coverage/coverage_summary.html"
echo "Detailed HTML: $REPORTS/coverage/htmlcov/index.html"
echo "JUnit XML: $SUMMARY/pytest-junit.xml (if coverage/tests mode ran)"
echo "CSV/JSON benchmark: $REPORTS/performance/"
echo "Download bundle: $REPORTS/revision_reports.zip"
if [[ "$failed" -ne 0 ]]; then echo "One or more checks failed. Reports were generated where possible." >&2; exit 1; fi
echo "Selected revision checks completed. Review report status; not all manual/live evidence is covered."
exit 0
