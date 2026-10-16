#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests for the worksheet-relationship resolution in the xlsx row/column tools.

Regression test for #3645: `find_ws_path()` in `xlsx_insert_row.py` and
`xlsx_add_column.py` joined the relationship Target straight onto the working
directory. A Target is relative to the part that declares the relationship —
`xl/`, the OPC default, and what this repo's own `templates/minimal_xlsx` uses
(`Target="worksheets/sheet1.xml"`) — so both tools looked for
`<work>/worksheets/sheet1.xml` and died with `FileNotFoundError` on any file
that follows the default, the repo's template included.
`formula_check.py` resolves the same relationship correctly; these two did not.

Every case unpacks this repo's own template into a temporary working directory
and runs the real script, so the fixture is the shape the tools ship for.

Usage: python3 src/os-skills/others/xlsx/scripts/test_xlsx_worksheet_rel_target.py
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


class WorksheetRelTargetTests(unittest.TestCase):
    def unpack_template(self):
        """The template is already an unpacked workbook: work on a copy, with
        one data row so a column can be added beside something."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        work = Path(tmp.name) / "work"
        shutil.copytree(TEMPLATE, work)
        sheet = work / "xl" / "worksheets" / "sheet1.xml"
        text = sheet.read_text(encoding="utf-8")
        self.assertEqual(text.count("</sheetData>"), 1)
        sheet.write_text(
            text.replace("</sheetData>", "  <row r='1'><c r='A1'><v>1</v></c></row>" + chr(10) + "  </sheetData>"),
            encoding="utf-8",
        )
        return work

    def run_tool(self, script, work, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), str(work), *args],
            capture_output=True,
            text=True,
            timeout=120,
        )

    @staticmethod
    def cell_addresses(work):
        sheet = ET.parse(work / "xl" / "worksheets" / "sheet1.xml").getroot()
        return {cell.get("r") for cell in sheet.iter(f"{{{NS_MAIN}}}c")}

    @staticmethod
    def shared_strings(work):
        tree = ET.parse(work / "xl" / "sharedStrings.xml").getroot()
        return "".join(node.text or "" for node in tree.iter(f"{{{NS_MAIN}}}t"))

    def test_inserting_a_row_resolves_the_default_relative_target(self):
        work = self.unpack_template()
        result = self.run_tool("xlsx_insert_row.py", work, "--at", "2", "--text", "A=Utilities")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("A2", self.cell_addresses(work), "the inserted row must land in the sheet")
        self.assertIn("Utilities", self.shared_strings(work))

    def test_adding_a_column_resolves_the_default_relative_target(self):
        work = self.unpack_template()
        result = self.run_tool("xlsx_add_column.py", work, "--col", "B", "--header", "Total")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("B1", self.cell_addresses(work), "the new column must land in the sheet")
        self.assertIn("Total", self.shared_strings(work))

    def test_an_absolute_target_still_resolves(self):
        """The other shape in the wild: Target="/xl/worksheets/sheet1.xml"."""
        work = self.unpack_template()
        rels = work / "xl" / "_rels" / "workbook.xml.rels"
        rels.write_text(
            rels.read_text(encoding="utf-8").replace(
                'Target="worksheets/sheet1.xml"', 'Target="/xl/worksheets/sheet1.xml"'
            ),
            encoding="utf-8",
        )
        result = self.run_tool("xlsx_insert_row.py", work, "--at", "2", "--text", "A=Absolute")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("A2", self.cell_addresses(work))


if __name__ == "__main__":
    unittest.main(verbosity=2)
