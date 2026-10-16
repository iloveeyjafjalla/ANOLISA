#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests for formula_check.py on input it cannot actually check.

Regression test for #3961, two fail-open input paths:

1. `--sheet NAME` that matches nothing skipped every sheet and still printed
   "PASS — No formula errors detected" with exit 0 — a typo in the sheet name
   read as a clean bill of health;
2. a zip that is not an OOXML workbook (no `xl/workbook.xml`, or malformed XML)
   reached the parser and died with a traceback instead of a verdict.

The tool is stdlib-only, so these cases need nothing but this repo's own
template and a plain zip.

Usage: python3 src/os-skills/others/xlsx/scripts/test_formula_check_uncheckable.py
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
TEMPLATE = SCRIPTS.parent / "templates" / "minimal_xlsx"


class FormulaCheckUncheckableInputTests(unittest.TestCase):
    def workbook(self):
        """The repo's template zipped back up into a real .xlsx."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        work = root / "work"
        shutil.copytree(TEMPLATE, work)
        path = root / "book.xlsx"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for member in sorted(work.rglob("*")):
                if member.is_file():
                    archive.write(member, member.relative_to(work).as_posix())
        return path

    def run_check(self, path, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "formula_check.py"), str(path), *args],
            capture_output=True, text=True, timeout=120,
        )

    def test_the_workbook_and_its_sheet_pass(self):
        """The control: a real sheet must still pass, or the fix is a false alarm."""
        result = self.run_check(self.workbook(), "--sheet", "Sheet1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_a_sheet_filter_that_matches_nothing_is_a_failure(self):
        result = self.run_check(self.workbook(), "--sheet", "Nope")
        self.assertNotEqual(result.returncode, 0,
                            "a filter that checked nothing must not exit 0")
        self.assertNotIn("PASS", result.stdout)
        self.assertIn("no sheet named 'Nope'", result.stdout + result.stderr)
        self.assertIn("Sheet1", result.stdout + result.stderr,
                      "the verdict must name the sheets that do exist")

    def test_a_zip_that_is_not_a_workbook_reports_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "not-a-workbook.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("readme.txt", "this is not OOXML")

            result = self.run_check(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr, "a checker owes a verdict, not a stack trace")
        self.assertIn("not an OOXML workbook", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
