#!/usr/bin/env python3
"""Tests for the shared view layer and both dashboard front-ends."""

import os
import unittest

from edumetrics.data import build_ccps_district
from edumetrics.views import (
    curriculum_table,
    district_kpis,
    equity_table,
    school_names,
    school_table,
    teacher_table,
)


def _district():
    return build_ccps_district(seed=3, students_per_school=10, teachers_per_school=3)


class ViewLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.district = _district()

    def test_kpis_have_headline_fields(self) -> None:
        kpis = district_kpis(self.district)
        for key in ("District", "Students", "Attendance", "Avg GPA"):
            self.assertIn(key, kpis)
        self.assertEqual(kpis["District"], "Charles County Public Schools")

    def test_school_table_shape(self) -> None:
        columns, rows = school_table(self.district)
        self.assertEqual(len(rows), 10)
        self.assertEqual(len(columns), len(rows[0]))
        self.assertIn("North Point High", [row[0] for row in rows])

    def test_teacher_table_filter(self) -> None:
        _columns, all_rows = teacher_table(self.district)
        _columns, one_school = teacher_table(self.district, "La Plata High")
        self.assertEqual(len(all_rows), 30)
        self.assertEqual(len(one_school), 3)
        self.assertTrue(all(row[1] == "La Plata High" for row in one_school))

    def test_curriculum_and_equity_tables(self) -> None:
        columns, rows = curriculum_table(self.district)
        self.assertEqual(len(rows), 3)
        self.assertEqual(columns[2], "Coverage")
        columns, rows = equity_table(self.district)
        self.assertEqual(columns[0], "Subject")
        subjects = {row[0] for row in rows}
        self.assertEqual(subjects, {"ELA", "Math", "Science"})

    def test_school_names_sorted(self) -> None:
        names = school_names(self.district)
        self.assertEqual(names, sorted(names))
        self.assertIn("Westlake High", names)


class TextualDashboardTests(unittest.IsolatedAsyncioTestCase):
    async def test_tables_populate_and_tabs_switch(self) -> None:
        try:
            from textual.widgets import DataTable, TabbedContent

            from edumetrics_tui import CCPSDashboard
        except ModuleNotFoundError:
            self.skipTest("textual is not installed")

        app = CCPSDashboard(seed=3)
        async with app.run_test(size=(120, 40)) as pilot:
            schools = app.query_one("#schools-table", DataTable)
            self.assertEqual(schools.row_count, 10)
            teachers = app.query_one("#teachers-table", DataTable)
            self.assertEqual(teachers.row_count, 60)

            await pilot.press("4")
            self.assertEqual(app.query_one(TabbedContent).active, "equity")
            await pilot.press("2")
            self.assertEqual(app.query_one(TabbedContent).active, "teachers")

    async def test_reload_changes_seed(self) -> None:
        try:
            from edumetrics_tui import CCPSDashboard
        except ModuleNotFoundError:
            self.skipTest("textual is not installed")

        app = CCPSDashboard(seed=3)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("r")
            self.assertEqual(app.seed, 4)


@unittest.skipUnless(os.environ.get("DISPLAY"), "tkinter needs a display")
class TkDashboardTests(unittest.TestCase):
    def test_window_builds_and_loads_tables(self) -> None:
        from edumetrics_tk import MetricsApp

        app = MetricsApp(seed=3)
        try:
            app.update_idletasks()
            schools_tree = app.tables["Schools"].tree
            self.assertEqual(len(schools_tree.get_children()), 10)
            app.school_var.set("La Plata High")
            app.reload_teachers()
            teachers_tree = app.tables["Teachers"].tree
            self.assertEqual(len(teachers_tree.get_children()), 6)
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
