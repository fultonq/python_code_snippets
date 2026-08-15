#!/usr/bin/env python3
"""Tests for the CCPS education-metrics package."""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from edumetrics import build_ccps_district
from edumetrics.cli import main
from edumetrics.metrics import (
    MetricsError,
    attendance_rate,
    chronic_absentee_rate,
    curriculum_audit,
    district_summary,
    equity_gaps,
    growth_percentiles,
    proficiency_rate,
    school_report,
    teacher_effectiveness,
    teacher_report,
)
from edumetrics.models import (
    AssessmentResult,
    Course,
    District,
    Enrollment,
    School,
    Section,
    Student,
    Teacher,
    Unit,
    ValidationError,
)


def _student(sid, school="HS-X", present=171, enrolled=180, gpa=3.0, **flags):
    return Student(
        student_id=sid,
        name=sid,
        school_id=school,
        grade_level=9,
        days_enrolled=enrolled,
        days_present=present,
        gpa=gpa,
        **flags,
    )


def _fixture_district() -> District:
    """
    Tiny hand-computed district.

    Alice: 180/180 attendance, ELA growth 60->80 (level 4)
    Bob:   150/180 attendance (chronic), ELA growth 50->55 (level 2)
    Cara:  171/180 attendance, ELA growth 40->42 (level 3), FARMS
    """
    district = District(name="Fixture")
    district.add_school(School("HS-X", "Fixture High", "HS", 500))
    district.add_teacher(
        Teacher("T-1", "Ms. Rivers", "HS-X", "ELA", 8, True, 3.4, 30.0)
    )
    unit = Unit(
        unit_id="U1",
        title="Unit 1",
        required_standards=("RL.1", "RL.2", "W.1", "W.2"),
        taught_standards=("RL.1", "RL.2", "W.1"),
        assessed_standards=("RL.1", "W.2"),
        planned_days=20,
        actual_days=24,
    )
    district.add_course(Course("C-ELA", "English", "ELA", 9, [unit]))
    district.add_section(Section("SEC-1", "C-ELA", "T-1", "HS-X"))

    rows = [
        ("S-A", 180, 60.0, 80.0, 4, {}),
        ("S-B", 150, 50.0, 55.0, 2, {}),
        ("S-C", 171, 40.0, 42.0, 3, {"farms": True}),
    ]
    for sid, present, pre, post, level, flags in rows:
        student = _student(sid, present=present, **flags)
        student.assessments["ELA"] = AssessmentResult("ELA", pre, post, level)
        district.add_student(student)
        district.enroll(Enrollment(sid, "SEC-1", post))
    district.validate()
    return district


class ValidationTests(unittest.TestCase):
    def test_bad_records_raise(self) -> None:
        with self.assertRaises(ValidationError):
            School("", "Nameless", "HS", 100)
        with self.assertRaises(ValidationError):
            Teacher("T-1", "X", "HS-X", "Art", 3, True, 3.0, 10)
        with self.assertRaises(ValidationError):
            _student("S-1", present=200, enrolled=180)
        with self.assertRaises(ValidationError):
            AssessmentResult("Math", 50, 60, 7)
        with self.assertRaises(ValidationError):
            Enrollment("S-1", "SEC-1", 140.0)

    def test_unit_rejects_untracked_taught_standard(self) -> None:
        with self.assertRaises(ValidationError):
            Unit("U1", "Unit", ("A",), ("A", "B"), ("A",), 10, 10)

    def test_district_foreign_keys(self) -> None:
        district = District(name="Broken")
        district.add_school(School("HS-X", "X High", "HS", 100))
        district.add_teacher(Teacher("T-1", "A", "HS-MISSING", "ELA", 1, True, 3.0, 5))
        with self.assertRaises(ValidationError):
            district.validate()


class StudentMetricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.district = _fixture_district()
        self.students = list(self.district.students.values())

    def test_attendance_rate(self) -> None:
        expected = (180 + 150 + 171) / (3 * 180)
        self.assertAlmostEqual(attendance_rate(self.students), expected)

    def test_chronic_absentee_rate(self) -> None:
        self.assertAlmostEqual(chronic_absentee_rate(self.students), 1 / 3)

    def test_proficiency_rate(self) -> None:
        self.assertAlmostEqual(proficiency_rate(self.students, "ELA"), 2 / 3)
        with self.assertRaises(MetricsError):
            proficiency_rate(self.students, "Art")
        with self.assertRaises(MetricsError):
            proficiency_rate(self.students, "Math")

    def test_growth_percentiles(self) -> None:
        percentiles = growth_percentiles(self.district, "ELA")
        self.assertEqual(percentiles["S-C"], 0.0)   # +2 growth
        self.assertEqual(percentiles["S-B"], 50.0)  # +5 growth
        self.assertEqual(percentiles["S-A"], 100.0) # +20 growth

    def test_empty_inputs_raise(self) -> None:
        with self.assertRaises(MetricsError):
            attendance_rate([])
        with self.assertRaises(MetricsError):
            chronic_absentee_rate([])


class TeacherMetricTests(unittest.TestCase):
    def test_effectiveness_composite(self) -> None:
        district = _fixture_district()
        row = teacher_effectiveness(district, "T-1")
        self.assertEqual(row["students_scored"], 3)
        self.assertEqual(row["median_growth_percentile"], 50.0)
        expected = round(0.5 * 0.5 + 0.3 * ((3.4 - 1) / 3) + 0.2 * (30 / 40), 3)
        self.assertEqual(row["composite"], expected)
        self.assertEqual(row["rating"], "Effective")

    def test_unknown_teacher(self) -> None:
        with self.assertRaises(MetricsError):
            teacher_effectiveness(_fixture_district(), "T-404")

    def test_teacher_report_sorted(self) -> None:
        district = build_ccps_district(students_per_school=12, teachers_per_school=3)
        rows = teacher_report(district)
        scores = [row["composite"] for row in rows]
        self.assertEqual(scores, sorted(scores, reverse=True))


class CurriculumTests(unittest.TestCase):
    def test_audit_math(self) -> None:
        rows = curriculum_audit(_fixture_district())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertAlmostEqual(row["coverage"], 3 / 4)
        # assessed = {RL.1, W.2}; taught = {RL.1, RL.2, W.1} -> only RL.1 aligns
        self.assertAlmostEqual(row["assessment_alignment"], 1 / 2)
        self.assertEqual(row["pacing_variance_days"], 4)
        self.assertEqual(row["gaps"], ["W.2"])
        self.assertEqual(row["pass_rate"], round(1 / 3, 3))  # grades 80, 55, 42; only 80 >= 60


class EquityTests(unittest.TestCase):
    def test_gap_math(self) -> None:
        report = equity_gaps(_fixture_district(), "ELA")
        self.assertAlmostEqual(report["overall_proficiency"], round(2 / 3, 3))
        farms = report["subgroups"]["FARMS"]
        self.assertEqual(farms["students"], 1)
        self.assertAlmostEqual(farms["proficiency"], 1.0)
        self.assertAlmostEqual(farms["gap_points"], round((2 / 3 - 1.0) * 100, 1))
        self.assertFalse(farms["flagged"])


class DistrictBuildTests(unittest.TestCase):
    def test_ccps_builds_and_validates(self) -> None:
        district = build_ccps_district(students_per_school=10, teachers_per_school=3)
        self.assertEqual(district.name, "Charles County Public Schools")
        self.assertEqual(len(district.schools), 10)
        self.assertEqual(len(district.students), 100)
        names = {school.name for school in district.schools.values()}
        self.assertIn("North Point High", names)
        self.assertIn("La Plata High", names)

    def test_deterministic_by_seed(self) -> None:
        a = district_summary(build_ccps_district(seed=7, students_per_school=8, teachers_per_school=3))
        b = district_summary(build_ccps_district(seed=7, students_per_school=8, teachers_per_school=3))
        self.assertEqual(a, b)

    def test_school_report(self) -> None:
        district = build_ccps_district(students_per_school=10, teachers_per_school=3)
        report = school_report(district, "north point high")
        self.assertEqual(report["school"], "North Point High")
        self.assertEqual(report["enrollment"], 10)
        self.assertIn("Math", report["proficiency"])


class CliTests(unittest.TestCase):
    def _run(self, *argv: str):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = main(list(argv))
        return status, buffer.getvalue()

    def test_district_command(self) -> None:
        status, output = self._run("district")
        self.assertEqual(status, 0)
        self.assertIn("Charles County Public Schools", output)
        self.assertIn("North Point High", output)

    def test_school_command(self) -> None:
        status, output = self._run("school", "Westlake High")
        self.assertEqual(status, 0)
        self.assertIn("Westlake High", output)

    def test_teachers_command(self) -> None:
        status, output = self._run("teachers", "--school", "La Plata High", "--top", "3")
        self.assertEqual(status, 0)
        self.assertIn("Teacher effectiveness", output)

    def test_curriculum_and_equity(self) -> None:
        status, output = self._run("curriculum")
        self.assertEqual(status, 0)
        self.assertIn("coverage", output)
        status, output = self._run("equity", "--subject", "Math")
        self.assertEqual(status, 0)
        self.assertIn("FARMS", output)

    def test_export_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "report.json")
            status, output = self._run("export", "--out", out)
            self.assertEqual(status, 0)
            with open(out, encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertIn("summary", payload)
            self.assertIn("teachers", payload)
            self.assertIn("curriculum", payload)
            self.assertIn("equity", payload)

    def test_unknown_school_fails_cleanly(self) -> None:
        err = io.StringIO()
        import contextlib

        with contextlib.redirect_stderr(err):
            status = main(["school", "Hogwarts"])
        self.assertEqual(status, 1)
        self.assertIn("no school named", err.getvalue())


if __name__ == "__main__":
    unittest.main()
