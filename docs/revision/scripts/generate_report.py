#!/usr/bin/env python3
"""Create printable/downloadable revision and coverage summaries."""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime
from html import escape
from pathlib import Path


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def test_counts(path: Path) -> dict:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return {"tests": None, "failures": None, "errors": None, "skipped": None}
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    totals = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.attrib.get(key, 0))
    return totals


def junit_cases(path: Path) -> list[dict]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return []
    cases = []
    for case in root.iter("testcase"):
        status = "FAIL" if case.find("failure") is not None or case.find("error") is not None else "SKIP" if case.find("skipped") is not None else "PASS"
        cases.append({"name": case.attrib.get("name", ""), "classname": case.attrib.get("classname", ""), "status": status})
    return cases


def available_test_counts(summary_dir: Path) -> dict:
    for full in (summary_dir / "pytest-junit.xml", summary_dir / "all-tests-junit.xml"):
        if full.exists():
            return test_counts(full)
    suites = [summary_dir / "unit-junit.xml", summary_dir / "integration-junit.xml", summary_dir / "black-box-junit.xml"]
    existing = [path for path in suites if path.exists()]
    if not existing:
        return {"tests": None, "failures": None, "errors": None, "skipped": None}
    totals = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    for path in existing:
        values = test_counts(path)
        for key in totals:
            totals[key] += values.get(key) or 0
    return totals


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    reports = root / "docs/revision/reports"
    coverage_dir = reports / "coverage"
    summary_dir = reports / "summary"
    coverage_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)
    coverage = read_json(coverage_dir / "coverage.json")
    tests = available_test_counts(summary_dir)
    junit_path = summary_dir / "pytest-junit.xml"
    if not junit_path.exists():
        junit_path = summary_dir / "all-tests-junit.xml"
    cases = junit_cases(junit_path)
    performance = read_json(reports / "performance/local_pdf_benchmark.json")
    environment = read_json(summary_dir / "environment.json") or {}
    total = coverage.get("totals", {}) if coverage else {}
    percent = total.get("percent_covered")
    files = []
    if coverage:
        for name, data in coverage.get("files", {}).items():
            info = data.get("summary", {})
            files.append({"file": name, "statements": info.get("num_statements", 0), "covered": info.get("covered_lines", 0), "missing": info.get("missing_lines", 0), "coverage_percent": info.get("percent_covered", 0), "missing_line_numbers": ",".join(map(str, data.get("missing_lines", [])))})
    files.sort(key=lambda item: item["coverage_percent"])
    scenario_map = {
        "BB-001": ["test_login_returns_auth_cookies", "test_login_creates_session"],
        "BB-002": ["test_login_returns_auth_cookies", "test_login_creates_session"],
        "BB-003": ["test_current_session_rejects", "test_role_and_csrf_dependencies_enforce_access"],
        "BB-004": ["test_material_character_setting_accepts_and_persists_requested_maximum"],
        "BB-005": ["test_material_character_setting_accepts_and_persists_requested_maximum"],
        "BB-006": ["test_material_character_setting_rejects_invalid_values"],
        "BB-007": ["test_docx_extraction_normalizes_whitespace_and_returns_detected_mime"],
        "BB-008": ["test_pdf_extraction_reads_text_operator"],
        "BB-009": ["test_material_extractor_rejects_invalid_file"],
        "BB-010": ["test_public_url_without_redirect", "test_public_redirect_to_a_different_domain"],
        "BB-011": ["test_malformed_url_returns_failure", "test_redirect_loop_is_rejected", "test_redirect_to_local_private_or_metadata_target", "test_timeout_becomes_reference_failure", "test_oversized_response_is_rejected", "test_non_http_protocol"],
        "BB-012": ["test_generation_service_persists_questions_blueprint_duration_and_summary"],
        "BB-013": ["test_generation_repairs_invalid_ai_result_once_then_saves_valid_result"],
        "BB-014": ["test_gemini_http_error_preserves_provider_body_and_redacts_key", "test_gemini_transport_timeout_is_wrapped_as_provider_error", "test_generation_provider_failure_is_persisted_as_safe_failed_generation"],
        "BB-016": ["test_progress_status_endpoint_returns_safe_persisted_error_without_resubmitting"],
    }
    black_box_dir = reports / "black_box"
    black_box_dir.mkdir(parents=True, exist_ok=True)
    source_scenarios = reports.parent / "testing/test_scenarios.csv"
    with source_scenarios.open(newline="", encoding="utf-8") as source, (black_box_dir / "black_box_results.csv").open("w", newline="", encoding="utf-8") as target:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(target, fieldnames=list(reader.fieldnames or []) + ["matched_test_cases", "run_status"])
        writer.writeheader()
        for row in reader:
            scenario_id = row.get("Test ID", "")
            required = scenario_map.get(scenario_id, [])
            matched = [case for case in cases if any(pattern in case["name"] for pattern in required)]
            found = {pattern for pattern in required if any(pattern in case["name"] for case in cases)}
            if scenario_id == "BB-021" and performance:
                row["Actual Result"] = f"{performance.get('samples')} local parser samples; see performance CSV/JSON."
                status = "PASS (local microbenchmark only)"
            elif required and len(found) == len(required) and matched and all(case["status"] == "PASS" for case in matched):
                row["Actual Result"] = "; ".join(sorted({case["name"] for case in matched}))
                status = "PASS (mapped pytest cases)"
            elif matched and any(case["status"] == "FAIL" for case in matched):
                row["Actual Result"] = "; ".join(sorted({case["name"] for case in matched if case["status"] != "PASS"}))
                status = "FAIL (mapped pytest case failed)"
            elif matched:
                row["Actual Result"] = "; ".join(sorted({case["name"] for case in matched}))
                status = "PARTIAL (mapped cases unavailable/skipped)"
            else:
                row["Actual Result"] = "No matching automated case in current JUnit evidence; see manual evidence requirement."
                status = "NOT TESTED / NOT MAPPED"
            row["matched_test_cases"] = "; ".join(sorted({f"{case['classname']}::{case['name']} [{case['status']}]" for case in matched}))
            row["run_status"] = status
            writer.writerow(row)
    with (coverage_dir / "coverage.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["file", "statements", "covered", "missing", "coverage_percent", "missing_line_numbers"])
        writer.writeheader()
        writer.writerows(files)
    if coverage:
        text_lines = [
            "Ghiai.site coverage summary",
            f"Statements: {total.get('num_statements', 0)}",
            f"Covered: {total.get('covered_lines', 0)}",
            f"Missing: {total.get('missing_lines', 0)}",
            f"Coverage: {total.get('percent_covered', 0):.1f}%",
            "",
            "File | coverage | missing lines",
        ]
        text_lines.extend(f"{item['file']} | {item['coverage_percent']:.1f}% | {item['missing_line_numbers']}" for item in files)
        (coverage_dir / "coverage.txt").write_text("\n".join(text_lines) + "\n", encoding="utf-8")
    with (summary_dir / "test_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["tests", "failures", "errors", "skipped", "result"])
        writer.writerow([tests.get("tests"), tests.get("failures"), tests.get("errors"), tests.get("skipped"), "PASS" if tests.get("tests") is not None and tests.get("failures") == 0 and tests.get("errors") == 0 else "NOT RUN OR FAIL"])

    target_met = percent is not None and percent >= 80
    test_result = "PASS" if tests.get("tests") is not None and tests.get("failures") == 0 and tests.get("errors") == 0 else "NOT RUN OR FAIL"
    coverage_text = f"{percent:.1f}%" if percent is not None else "Belum dijalankan"
    table_rows = "\n".join(f"<tr><td>{escape(row['file'])}</td><td>{row['statements']}</td><td>{row['covered']}</td><td>{row['missing']}</td><td>{row['coverage_percent']:.1f}%</td><td>{escape(row['missing_line_numbers'])}</td></tr>" for row in files)
    lowest = files[:10]
    highest = list(reversed(files[-10:]))
    low_names = ", ".join(escape(row["file"]) for row in lowest) or "Belum tersedia"
    high_names = ", ".join(escape(row["file"]) for row in highest) or "Belum tersedia"
    measured = performance.get("duration_ms", {}) if performance else {}
    perf_html = (f"<p>{performance.get('samples')} sampel parser PDF lokal; min {measured.get('min'):.3f} ms, max {measured.get('max'):.3f} ms, rata-rata {measured.get('average'):.3f} ms, median {measured.get('median'):.3f} ms, P95 deskriptif {measured.get('p95_nearest_rank_descriptive'):.3f} ms.</p>" if performance else "<p>Belum dijalankan.</p>")
    created = datetime.now(UTC).isoformat()
    html = f"""<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Laporan Revisi Ghiai.site</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;color:#182230;max-width:1200px;margin:2rem auto;padding:0 1rem}}h1,h2{{color:#12324a}}.cards{{display:flex;gap:1rem;flex-wrap:wrap}}.card{{border:1px solid #ccd6df;border-radius:8px;padding:1rem;min-width:180px}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{border:1px solid #ccd6df;padding:.35rem;text-align:left;overflow-wrap:anywhere}}th{{background:#edf3f7;position:sticky;top:0}}.actions{{position:sticky;top:0;background:white;padding:.5rem 0}}button,a.button{{background:#123d58;color:white;padding:.55rem .8rem;border:0;border-radius:5px;text-decoration:none;cursor:pointer}}@media print{{@page{{size:A4 landscape;margin:12mm}}body{{max-width:none;margin:0;padding:0;font-size:10pt}}.actions{{display:none}}table{{font-size:7pt}}tr{{break-inside:avoid}}thead{{display:table-header-group}}h1{{string-set:report-title content()}}}}</style></head>
<body><div class="actions"><button onclick="window.print()">Print / Save as PDF</button> <a class="button" href="../revision_reports.zip">Download all reports (ZIP)</a> <a class="button" href="coverage.csv">CSV</a> <a class="button" href="coverage.json">JSON</a> <a class="button" href="coverage.xml">XML</a> <a class="button" href="htmlcov/index.html">Detailed HTML</a> <a class="button" href="../summary/test_summary.csv">Test summary</a> <a class="button" href="../black_box/black_box_results.csv">Black-box CSV</a></div>
<h1>Laporan Pengujian Revisi Ghiai.site</h1><p>Generated UTC: {escape(created)} · Commit: {escape(str(environment.get('git_commit') or 'tidak tersedia'))} · Dirty worktree: {escape(str(environment.get('git_worktree_dirty')))}</p>
<div class="cards"><section class="card"><b>Unit/integration (JUnit)</b><br>{escape(test_result)}<br>Total: {tests.get('tests') if tests.get('tests') is not None else 'n/a'} · gagal: {tests.get('failures')} · error: {tests.get('errors')} · skip: {tests.get('skipped')}</section><section class="card"><b>Coverage app</b><br>{escape(coverage_text)}<br>Statements: {total.get('num_statements','n/a')} · covered: {total.get('covered_lines','n/a')} · missing: {total.get('missing_lines','n/a')}</section><section class="card"><b>Target awal ≥80%</b><br>{'TERCAPAI' if target_met else ('BELUM TERCAPAI' if percent is not None else 'BELUM DIUJI')}</section></div>
<h2>Environment</h2><p>Python: {escape(str(environment.get('python','belum dikumpulkan')))}<br>Platform: {escape(str(environment.get('platform','belum dikumpulkan')))}<br>Database test: SQLite in-memory. AI eksternal: mocked/not called.</p>
<h2>Performance</h2>{perf_html}<p>Benchmark mikro sintetis lokal saja; tidak mewakili upload, PostgreSQL, Gemini atau server.</p>
<h2>Coverage file</h2><p>Highest: {high_names}<br>Lowest: {low_names}</p><table><thead><tr><th>File</th><th>Statements</th><th>Covered</th><th>Missing</th><th>Coverage</th><th>Missing lines</th></tr></thead><tbody>{table_rows}</tbody></table>
<h2>Batas bukti</h2><p>Coverage hanya dihitung pada source package app dan bukan bukti akurasi AI. Screenshot, penilaian manusia, Gemini live, PostgreSQL server dan production performance harus diisi/dilakukan manual. Lihat README paket untuk status tiap aspek.</p></body></html>"""
    (coverage_dir / "coverage_summary.html").write_text(html, encoding="utf-8")
    summary = {"generated_at_utc": created, "test_counts": tests, "coverage_percent": percent, "coverage_target_percent": 80, "coverage_target_met": target_met if percent is not None else None, "coverage_files": len(files), "performance_status": performance.get("status") if performance else "not_run", "screenshots_status": "not_collected", "ai_quality_status": "requires human evaluation"}
    (summary_dir / "revision_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    archive = reports / "revision_reports.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in reports.rglob("*"):
            if path.is_file() and path != archive:
                bundle.write(path, path.relative_to(reports))
    print(f"Generated {coverage_dir / 'coverage_summary.html'} and {archive}")
    return 1 if tests.get("tests") is not None and test_result != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
