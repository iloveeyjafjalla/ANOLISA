#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests for summarize_results.py on an empty batch_results.json.

Regression test for #3859: the table-mode summary divided by the task and trial
counts, so an empty `batch_results.json` — a filter or range that matched
nothing, or a batch that errored before its first trial — rendered its header
table and then died with `ZeroDivisionError`, printing no summary at all.

The empty input must render a zero summary; a real batch must keep its rates,
so the guard is about the count being zero and not about dropping the numbers.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("summarize_results.py")


class SummarizeEmptyInputTests(unittest.TestCase):
    def run_summary(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "batch_results.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(path)],
                capture_output=True,
                text=True,
                timeout=120,
            )

    def test_an_empty_batch_renders_a_zero_summary(self):
        result = self.run_summary([])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("ZeroDivisionError", result.stderr)
        self.assertIn("Summary: 0 tasks", result.stdout)
        self.assertIn("Trials: 0 total", result.stdout)
        self.assertIn("(0.0%)", result.stdout)

    def test_a_real_batch_keeps_its_rates(self):
        result = self.run_summary([
            {"task_id": "task-1", "task_name": "task-1", "difficulty": "easy", "avg_passed": True,
             "trials": [{"passed": True}, {"passed": False}]},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Summary: 1 tasks, 1 passed (100.0%)", result.stdout)
        self.assertIn("Trials: 2 total, 1 passed (50.0%)", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
