#!/usr/bin/env python3
"""Safe local microbenchmark for the project's PDF text extractor."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.integrations.material.pdf_extractor import extract_pdf


def synthetic_pdf(repeats: int) -> bytes:
    text = b" ".join([b"(A small deterministic parser benchmark) Tj"] * repeats)
    return b"%PDF-1.4\n1 0 obj\n<< /Length " + str(len(text)).encode() + b" >>\nstream\n" + text + b"\nendstream\nendobj\n%%EOF"


def commit_id(root: Path) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], check=True, capture_output=True, text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--repeat-count", type=int, default=1000)
    args = parser.parse_args()
    if args.samples < 1 or args.samples > 1000 or args.repeat_count < 1 or args.repeat_count > 100000:
        parser.error("samples harus 1..1000 dan repeat-count 1..100000")

    root = ROOT
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    payload = synthetic_pdf(args.repeat_count)
    rows = []
    for sample in range(1, args.samples + 1):
        started = time.perf_counter()
        extracted = extract_pdf(payload)
        elapsed_ms = (time.perf_counter() - started) * 1000
        rows.append({"sample": sample, "operation": "pdf_text_extraction", "duration_ms": round(elapsed_ms, 4), "input_bytes": len(payload), "output_characters": len(extracted), "synthetic_fixture": True})

    with (output / "local_pdf_benchmark.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    values = [row["duration_ms"] for row in rows]
    sorted_values = sorted(values)
    p95 = sorted_values[max(0, min(len(sorted_values) - 1, int(0.95 * len(sorted_values) + 0.999) - 1))]
    summary = {
        "status": "measured_local_microbenchmark",
        "scope": "synthetic PDF text parsing only; no upload, database, URL, Gemini, or production server",
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "samples": len(values),
        "input_bytes": len(payload),
        "repeat_count": args.repeat_count,
        "duration_ms": {"min": min(values), "max": max(values), "average": statistics.mean(values), "median": statistics.median(values), "p95_nearest_rank_descriptive": p95},
        "environment": {"python": sys.version, "platform": platform.platform(), "processor": platform.processor() or None, "cpu_count": __import__("os").cpu_count(), "commit": commit_id(root)},
    }
    (output / "local_pdf_benchmark.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
