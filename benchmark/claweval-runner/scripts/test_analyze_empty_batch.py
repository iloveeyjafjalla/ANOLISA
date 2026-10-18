#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests for analyze.py on an empty batch_results.json.

Regression test for #4324: `main()` divided by the task and trial counts when it
rendered the summary text, so an empty `batch_results.json` — a run that errored
before its first trial, or a trace directory filtered to nothing — crashed after
Step 1 (the LLM judge calls) and Step 3 (the table build), leaving no
`summary.txt`, `summary.csv` or `report.json` behind: the expensive part of the
run was paid and every output was lost.

The fixture pre-seeds a previous run's `reports/` directory, which makes the
script skip report generation, so the test exercises the summary path with no
judge calls at all.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("analyze.py")

# analyze.py imports the judge client at module load; without it the script
# cannot even be driven, and that is a missing dependency rather than a defect.
HAS_OPENAI = importlib.util.find_spec("openai") is not None


@unittest.skipUnless(HAS_OPENAI, "analyze.py imports the openai judge client")
class AnalyzeEmptyBatchTests(unittest.TestCase):
    def run_analysis(self, batch_payload):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        trace_dir = root / "traces" / "trace-a"
        trace_dir.mkdir(parents=True)
        (trace_dir / "batch_results.json").write_text(json.dumps(batch_payload), encoding="utf-8")
        out = root / "results"
        reports = out / "previous-run" / "reports"
        reports.mkdir(parents=True)
        (reports / "one.json").write_text("{}", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--trace-dir", str(trace_dir),
                "--output-dir", str(out),
                "--judge-api-key", "dummy",
                "--judge-model", "dummy",
            ],
            capture_output=True, text=True, timeout=120,
        )
        return result, out / "trace-a"

    def test_an_empty_batch_still_writes_its_summary(self):
        result, output_dir = self.run_analysis([])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("ZeroDivisionError", result.stderr)

        summary = (output_dir / "summary.txt").read_text(encoding="utf-8")
        self.assertIn("Summary: 0 tasks", summary)
        self.assertIn("Trials: 0 total", summary)
        self.assertTrue((output_dir / "summary.csv").is_file(), "the CSV must be written too")
        self.assertTrue((output_dir / "report.json").is_file(), "the structured report must be written")

    def test_a_real_batch_keeps_its_rates(self):
        result, output_dir = self.run_analysis([
            {
                "task_id": "task-1",
                "task_name": "task-1",
                "difficulty": "easy",
                "avg_passed": True,
                "trials": [{"passed": True}, {"passed": False}],
            },
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = (output_dir / "summary.txt").read_text(encoding="utf-8")
        self.assertIn("Summary: 1 tasks, 1 passed (100.0%)", summary)
        self.assertIn("Trials: 2 total, 1 passed (50.0%)", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
