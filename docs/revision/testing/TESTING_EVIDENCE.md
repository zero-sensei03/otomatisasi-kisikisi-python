# Test evidence index

This index is generated/updated per `run_revision.sh` execution. Treat output artifacts as tied to their timestamp, worktree state and commit; a dirty checkout must be recorded in the environment JSON.

- `reports/summary/unit-tests.log`, `unit-junit.xml`: unit suite (when `tests`/`all` runs).
- `reports/summary/integration-tests.log`, `integration-junit.xml`: integration suite (when `tests`/`all` runs).
- `reports/summary/coverage-tests.log`, `pytest-junit.xml`: full suite with coverage.
- `reports/coverage/coverage.json`, `.xml`, `.txt`, `.csv`, `htmlcov/`: coverage evidence.
- `reports/performance/local_pdf_benchmark.csv/.json`: local synthetic PDF parser measurements.
- `reports/summary/environment.json`: runtime and dependency versions, host metadata, commit; contains no secrets.
- `reports/coverage/coverage_summary.html`: combined printable dashboard.
- `reports/revision_reports.zip`: report bundle.

Direct invocation of FastAPI route handlers is reported as handler/service testing, not an HTTP browser test. Mocked AI results are not AI quality evidence. Keep raw artifacts with the report and do not edit test actual-result fields to turn missing evidence into pass.
