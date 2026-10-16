#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests for shared-formula ranges in xlsx_shift_rows.py.

Regression test for #3648: `process_worksheet()` rewrote the `<f>` text of a
formula cell but never its `ref` attribute. A shared formula group is declared
by its master (`<f t="shared" ref="B2:B4" si="0">A2*2</f>`) and its consumers
are only valid *inside* that range; after an insert the members move while the
declared range stayed behind, so a relocated consumer sat outside its own group
— invalid OOXML that Excel answers with a repair prompt.

The fixture is this repo's own template with the master/consumer trio written
into it, and the real script is driven the way `xlsx_insert_row.py` drives it.

Usage: python3 src/os-skills/others/xlsx/scripts/test_xlsx_shift_rows_shared_ref.py
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

SCRIPTS = Path(__file__).resolve().parent
TEMPLATE = SCRIPTS.parent / "templates" / "minimal_xlsx"
NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# A group whose master sits above the insertion point and whose consumers sit
# on and below it, so the range has to grow to keep them inside.
SHARED_GROUP = (
    '<row r="2"><c r="B2"><f t="shared" ref="B2:B4" si="0">A2*2</f><v>4</v></c></row>'
    '<row r="3"><c r="B3"><f t="shared" si="0"/><v></v></c></row>'
    '<row r="4"><c r="B4"><f t="shared" si="0"/><v></v></c></row>'
)


class ShiftRowsSharedRefTests(unittest.TestCase):
    def workbook_with_group(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        work = Path(tmp.name) / "work"
        shutil.copytree(TEMPLATE, work)
        sheet = work / "xl" / "worksheets" / "sheet1.xml"
        text = sheet.read_text(encoding="utf-8")
        self.assertEqual(text.count("</sheetData>"), 1)
        sheet.write_text(text.replace("</sheetData>", SHARED_GROUP + "</sheetData>"), encoding="utf-8")
        return work

    def shift(self, work, at=3, delta=1):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "xlsx_shift_rows.py"), str(work), "insert", str(at), str(delta)],
            capture_output=True, text=True, timeout=120,
        )

    @staticmethod
    def shared_master(work):
        sheet = ET.parse(work / "xl" / "worksheets" / "sheet1.xml").getroot()
        for formula in sheet.iter(f"{{{NS_MAIN}}}f"):
            if formula.get("si") and formula.text:
                return formula
        return None

    def test_the_declared_range_follows_its_members(self):
        work = self.workbook_with_group()
        result = self.shift(work)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

        master = self.shared_master(work)
        self.assertIsNotNone(master, "the group must survive the shift")
        self.assertEqual(master.get("ref"), "B2:B5",
                         "the relocated consumer at B5 must stay inside the declared range")
        self.assertEqual(master.text, "A2*2", "a reference above the insertion point does not move")

    def test_a_shift_below_the_group_leaves_its_range_alone(self):
        work = self.workbook_with_group()
        result = self.shift(work, at=9, delta=1)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.shared_master(work).get("ref"), "B2:B4")


if __name__ == "__main__":
    unittest.main(verbosity=2)
