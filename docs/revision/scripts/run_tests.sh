#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OUT="$ROOT/docs/revision/reports/summary"
mkdir -p "$OUT"
cd "$ROOT"
source "$ROOT/docs/revision/scripts/prepare_python.sh"
prepare_revision_python "$ROOT" || exit $?
PYTHON="$REVISION_PYTHON"
export REVISION_PYTHON
run_test() {
  local suite="$1" junit="$2" log="$3"
  echo "== pytest $suite =="
  DATABASE_URL=sqlite:// SECRET_KEY=revision-test-only DEBUG=false "$PYTHON" -m pytest "$suite" -v --junitxml="$junit" 2>&1 | tee "$log"
  return "${PIPESTATUS[0]}"
}
failed=0
run_test tests/unit "$OUT/unit-junit.xml" "$OUT/unit-tests.log" || failed=1
run_test tests/integration "$OUT/integration-junit.xml" "$OUT/integration-tests.log" || failed=1
run_test tests/ "$OUT/all-tests-junit.xml" "$OUT/all-tests.log" || failed=1
exit "$failed"
