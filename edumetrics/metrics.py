"""
Metric computations for students, teachers, curriculum, and equity.

Every public function takes a validated District and returns plain
dicts/lists so reports can be rendered as text, JSON, or CSV without
touching the math.
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

from edumetrics.models import (
    CHRONIC_ABSENCE_THRESHOLD,
    District,
    EducationDataError,
    Student,
    SUBGROUPS,
    SUBJECTS,
)


class MetricsError(EducationDataError):
    """Raised when a metric cannot be computed from the given data."""


# --------------------------------------------------------------------------
# Student metrics
# --------------------------------------------------------------------------

def attendance_rate(students: Iterable[Student]) -> float:
    """Average daily attendance across `students` (0.0 - 1.0)."""
    students = list(students)
    if not students:
        raise MetricsError("attendance_rate needs at least one student")
    present = sum(s.days_present for s in students)
    enrolled = sum(s.days_enrolled for s in students)
    return present / enrolled


def chronic_absentee_rate(students: Iterable[Student]) -> float:
    """Share of students under the 90% attendance threshold."""
    students = list(students)
    if not students:
        raise MetricsError("chronic_absentee_rate needs at least one student")
    flagged = sum(1 for s in students if s.chronically_absent)
    return flagged / len(students)


def proficiency_rate(students: Iterable[Student], subject: str) -> float:
    """Share of tested students scoring MCAP level 3 or 4 in `subject`."""
    if subject not in SUBJECTS:
        raise MetricsError(f"unknown subject {subject!r}; choose from {SUBJECTS}")
    tested = [s for s in students if subject in s.assessments]
    if not tested:
        raise MetricsError(f"no assessment results for {subject}")
    proficient = sum(1 for s in tested if s.assessments[subject].proficient)
    return proficient / len(tested)


def growth_percentiles(district: District, subject: str) -> Dict[str, float]:
    """
    Rank each student's pre->post growth against district peers.

    Returns student_id -> percentile (0-100). Median growth is the 50th
    percentile, mirroring how Maryland reports student growth.
    """
    if subject not in SUBJECTS:
        raise MetricsError(f"unknown subject {subject!r}")
    deltas = [
        (student.student_id, student.assessments[subject].growth)
        for student in district.students.values()
        if subject in student.assessments
    ]
    if len(deltas) < 2:
        raise MetricsError(f"need at least two {subject} results for percentiles")
    deltas.sort(key=lambda pair: pair[1])
    last_index = len(deltas) - 1
    return {
        student_id: round(100.0 * position / last_index, 1)
        for position, (student_id, _growth) in enumerate(deltas)
    }


# --------------------------------------------------------------------------
# Teacher metrics
# --------------------------------------------------------------------------

def teacher_effectiveness(district: District, teacher_id: str) -> Dict[str, Any]:
    """
    Composite teacher score.

      50%  median growth percentile of the teacher's students
      30%  evaluation score (Danielson 1-4, normalized)
      20%  professional development hours (capped at 40)

    Returns the composite (0-1), the rating band, and each input.
    """
    if teacher_id not in district.teachers:
        raise MetricsError(f"unknown teacher {teacher_id!r}")
    teacher = district.teachers[teacher_id]
    percentiles = growth_percentiles(district, teacher.subject)

    student_ids = {
        enrollment.student_id
        for section in district.sections_taught_by(teacher_id)
        for enrollment in district.enrollments_in(section.section_id)
    }
    growth_values = [percentiles[sid] for sid in student_ids if sid in percentiles]
    if not growth_values:
        raise MetricsError(f"teacher {teacher_id} has no scored students")

    growth_values.sort()
    middle = len(growth_values) // 2
    if len(growth_values) % 2:
        median_growth = growth_values[middle]
    else:
        median_growth = (growth_values[middle - 1] + growth_values[middle]) / 2

    growth_component = median_growth / 100.0
    evaluation_component = (teacher.evaluation_score - 1.0) / 3.0
    pd_component = min(teacher.pd_hours, 40.0) / 40.0
    composite = round(
        0.5 * growth_component + 0.3 * evaluation_component + 0.2 * pd_component, 3
    )

    if composite >= 0.75:
        rating = "Highly Effective"
    elif composite >= 0.55:
        rating = "Effective"
    elif composite >= 0.40:
        rating = "Developing"
    else:
        rating = "Needs Improvement"

    return {
        "teacher_id": teacher_id,
        "name": teacher.name,
        "school_id": teacher.school_id,
        "subject": teacher.subject,
        "certified": teacher.certified,
        "years_experience": teacher.years_experience,
        "students_scored": len(growth_values),
        "median_growth_percentile": round(median_growth, 1),
        "evaluation_score": teacher.evaluation_score,
        "pd_hours": teacher.pd_hours,
        "composite": composite,
        "rating": rating,
    }


def teacher_report(district: District, school_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Effectiveness rows for every teacher (optionally one school), best first."""
    teachers = (
        district.teachers_at(school_id) if school_id else list(district.teachers.values())
    )
    if school_id is not None and not teachers:
        raise MetricsError(f"no teachers found for school {school_id!r}")
    rows = [teacher_effectiveness(district, teacher.teacher_id) for teacher in teachers]
    rows.sort(key=lambda row: row["composite"], reverse=True)
    return rows


# --------------------------------------------------------------------------
# Curriculum metrics
# --------------------------------------------------------------------------

def curriculum_audit(district: District) -> List[Dict[str, Any]]:
    """
    Per-course curriculum health.

      coverage   taught standards / required standards
      alignment  assessed standards that were actually taught / assessed
      pacing     actual days vs planned days across units
      pass_rate  enrollments earning >= 60 in sections of this course
    """
    rows: List[Dict[str, Any]] = []
    for course in district.courses.values():
        required = course.required_standards()
        taught = course.taught_standards()
        assessed = course.assessed_standards()
        if not required:
            raise MetricsError(f"course {course.course_id} has no required standards")
        coverage = len(taught & required) / len(required)
        alignment = (len(assessed & taught) / len(assessed)) if assessed else 0.0
        planned = sum(unit.planned_days for unit in course.units)
        actual = sum(unit.actual_days for unit in course.units)

        grades = [
            enrollment.final_grade
            for section in district.sections.values()
            if section.course_id == course.course_id
            for enrollment in district.enrollments_in(section.section_id)
        ]
        pass_rate = (sum(1 for g in grades if g >= 60) / len(grades)) if grades else 0.0

        rows.append(
            {
                "course_id": course.course_id,
                "title": course.title,
                "subject": course.subject,
                "standards_required": len(required),
                "standards_taught": len(taught & required),
                "coverage": round(coverage, 3),
                "assessment_alignment": round(alignment, 3),
                "planned_days": planned,
                "actual_days": actual,
                "pacing_variance_days": actual - planned,
                "enrollment_count": len(grades),
                "pass_rate": round(pass_rate, 3),
                "gaps": sorted(required - taught),
            }
        )
    rows.sort(key=lambda row: row["coverage"])
    return rows


# --------------------------------------------------------------------------
# Equity and rollups
# --------------------------------------------------------------------------

def equity_gaps(district: District, subject: str) -> Dict[str, Any]:
    """
    Proficiency for each subgroup vs the district overall.

    A positive gap means the subgroup trails the district. Anything
    over 10 points is flagged for the equity office.
    """
    students = list(district.students.values())
    overall = proficiency_rate(students, subject)
    subgroup_rows: Dict[str, Any] = {}
    for subgroup in SUBGROUPS:
        members = [s for s in students if subgroup in s.subgroups()]
        if not members:
            continue
        rate = proficiency_rate(members, subject)
        gap_points = round((overall - rate) * 100, 1)
        subgroup_rows[subgroup] = {
            "students": len(members),
            "proficiency": round(rate, 3),
            "gap_points": gap_points,
            "flagged": gap_points > 10.0,
        }
    return {
        "subject": subject,
        "overall_proficiency": round(overall, 3),
        "subgroups": subgroup_rows,
    }


def school_report(district: District, school_name: str) -> Dict[str, Any]:
    """Report card for one building."""
    school = district.school_by_name(school_name)
    students = district.students_at(school.school_id)
    if not students:
        raise MetricsError(f"{school.name} has no enrolled students")
    report: Dict[str, Any] = {
        "school": school.name,
        "level": school.level,
        "enrollment": len(students),
        "capacity": school.enrollment_capacity,
        "attendance_rate": round(attendance_rate(students), 3),
        "chronic_absentee_rate": round(chronic_absentee_rate(students), 3),
        "average_gpa": round(mean(s.gpa for s in students), 2),
        "proficiency": {},
        "teachers": len(district.teachers_at(school.school_id)),
    }
    for subject in SUBJECTS:
        report["proficiency"][subject] = round(proficiency_rate(students, subject), 3)
    return report


def district_summary(district: District) -> Dict[str, Any]:
    """District-wide rollup across all three pillars."""
    students = list(district.students.values())
    if not students:
        raise MetricsError("district has no students")
    teachers = list(district.teachers.values())
    summary: Dict[str, Any] = {
        "district": district.name,
        "schools": len(district.schools),
        "students": len(students),
        "teachers": len(teachers),
        "attendance_rate": round(attendance_rate(students), 3),
        "chronic_absentee_rate": round(chronic_absentee_rate(students), 3),
        "average_gpa": round(mean(s.gpa for s in students), 2),
        "certified_teacher_rate": round(
            sum(1 for t in teachers if t.certified) / len(teachers), 3
        ),
        "proficiency": {
            subject: round(proficiency_rate(students, subject), 3) for subject in SUBJECTS
        },
        "schools_detail": [
            school_report(district, school.name)
            for school in sorted(district.schools.values(), key=lambda s: s.name)
        ],
    }
    return summary
