#!/usr/bin/env python3
"""Tests for the Faker-based CCPS data generator."""

import io
import unittest
from contextlib import redirect_stdout

try:
    import faker  # noqa: F401
    HAS_FAKER = True
except ModuleNotFoundError:
    HAS_FAKER = False

from edumetrics.cli import main
from edumetrics.metrics import district_summary, teacher_report


@unittest.skipUnless(HAS_FAKER, "faker is not installed")
class FakerDistrictTests(unittest.TestCase):
    def setUp(self) -> None:
        from edumetrics.faker_data import build_ccps_district_faker

        self.build = build_ccps_district_faker

    def test_builds_all_ccps_levels(self) -> None:
        district = self.build(seed=5, students_per_school=6, teachers_per_school=3)
        levels = {school.level for school in district.schools.values()}
        self.assertEqual(levels, {"ES", "MS", "HS"})
        self.assertEqual(len(district.schools), 24)
        self.assertEqual(len(district.students), 24 * 6)
        names = {school.name for school in district.schools.values()}
        self.assertIn("Piccowaxen Middle", names)
        self.assertIn("J.C. Parks Elementary", names)

    def test_grade_levels_match_building_level(self) -> None:
        district = self.build(seed=5, students_per_school=6, teachers_per_school=3)
        for student in district.students.values():
            level = district.schools[student.school_id].level
            if level == "ES":
                self.assertIn(student.grade_level, (3, 4, 5))
            elif level == "MS":
                self.assertIn(student.grade_level, (6, 7, 8))
            else:
                self.assertIn(student.grade_level, (9, 10, 11, 12))

    def test_deterministic_per_seed(self) -> None:
        a = self.build(seed=9, students_per_school=5, teachers_per_school=3)
        b = self.build(seed=9, students_per_school=5, teachers_per_school=3)
        self.assertEqual(
            [s.name for s in a.students.values()],
            [s.name for s in b.students.values()],
        )
        self.assertEqual(district_summary(a), district_summary(b))

    def test_names_look_like_faker_output(self) -> None:
        district = self.build(seed=5, students_per_school=6, teachers_per_school=3)
        sample = next(iter(district.students.values())).name
        self.assertGreaterEqual(len(sample.split()), 2)

    def test_metrics_run_on_faker_district(self) -> None:
        district = self.build(seed=5, students_per_school=8, teachers_per_school=3)
        summary = district_summary(district)
        self.assertEqual(summary["students"], 24 * 8)
        self.assertGreater(summary["attendance_rate"], 0.8)
        rows = teacher_report(district)
        self.assertEqual(len(rows), 24 * 3)

    def test_roster_preview(self) -> None:
        from edumetrics.faker_data import roster_preview

        district = self.build(seed=5, students_per_school=6, teachers_per_school=3)
        lines = roster_preview(district, count=4)
        self.assertEqual(len(lines), 4)
        self.assertIn("Elementary", lines[0])


@unittest.skipUnless(HAS_FAKER, "faker is not installed")
class FakerCliTests(unittest.TestCase):
    def _run(self, *argv: str):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = main(list(argv))
        return status, buffer.getvalue()

    def test_faker_district_command(self) -> None:
        status, output = self._run("--faker", "district")
        self.assertEqual(status, 0)
        self.assertIn("Charles County Public Schools", output)
        self.assertIn("Piccowaxen Middle", output)

    def test_faker_roster_command(self) -> None:
        status, output = self._run("--faker", "roster")
        self.assertEqual(status, 0)
        self.assertIn("Roster preview", output)

    def test_faker_equity_command(self) -> None:
        status, output = self._run("--faker", "equity", "--subject", "ELA")
        self.assertEqual(status, 0)
        self.assertIn("FARMS", output)


class MissingFakerTests(unittest.TestCase):
    def test_clear_error_when_faker_absent(self) -> None:
        import edumetrics.faker_data as module

        original = module.Faker
        module.Faker = None
        try:
            from edumetrics.models import EducationDataError

            with self.assertRaises(EducationDataError):
                module.build_ccps_district_faker()
        finally:
            module.Faker = original


if __name__ == "__main__":
    unittest.main()
