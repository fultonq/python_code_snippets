"""
Faker-powered synthetic data for Charles County Public Schools.

Uses the `faker` package for realistic student and teacher names,
emails, and demographics across the real CCPS building list —
elementary, middle, and high schools. Seeded, so a given seed always
produces the same district (safe for tests and reproducible reports).

    pip install faker
    python3 -m edumetrics --faker district
"""

from __future__ import annotations

import random
from typing import List, Tuple

try:
    from faker import Faker
except ModuleNotFoundError as _exc:  # pragma: no cover - exercised via ImportError path
    Faker = None
    _FAKER_IMPORT_ERROR = _exc
else:
    _FAKER_IMPORT_ERROR = None

from edumetrics.data import _make_courses
from edumetrics.models import (
    AssessmentResult,
    District,
    EducationDataError,
    Enrollment,
    School,
    Section,
    Student,
    Teacher,
    SUBJECTS,
)


# Real CCPS buildings: (id, name, level, capacity)
CCPS_ALL_SCHOOLS: Tuple[Tuple[str, str, str, int], ...] = (
    # High schools
    ("HS-NP", "North Point High", "HS", 2200),
    ("HS-SC", "St. Charles High", "HS", 1900),
    ("HS-LP", "La Plata High", "HS", 1500),
    ("HS-TS", "Thomas Stone High", "HS", 1450),
    ("HS-WL", "Westlake High", "HS", 1550),
    ("HS-MM", "Maurice J. McDonough High", "HS", 1300),
    ("HS-HL", "Henry E. Lackey High", "HS", 1250),
    # Middle schools
    ("MS-JH", "John Hanson Middle", "MS", 900),
    ("MS-MW", "Mattawoman Middle", "MS", 950),
    ("MS-SO", "Milton M. Somers Middle", "MS", 850),
    ("MS-PW", "Piccowaxen Middle", "MS", 700),
    ("MS-MH", "Matthew Henson Middle", "MS", 750),
    ("MS-GS", "General Smallwood Middle", "MS", 800),
    ("MS-BS", "Benjamin Stoddert Middle", "MS", 820),
    ("MS-TD", "Theodore G. Davis Middle", "MS", 880),
    # Elementary schools (subset)
    ("ES-BB", "C. Paul Barnhart Elementary", "ES", 600),
    ("ES-BY", "Berry Elementary", "ES", 580),
    ("ES-ET", "Eva Turner Elementary", "ES", 560),
    ("ES-JP", "J.C. Parks Elementary", "ES", 620),
    ("ES-MM", "Mary H. Matula Elementary", "ES", 540),
    ("ES-WM", "Walter J. Mitchell Elementary", "ES", 590),
    ("ES-WD", "William A. Diggs Elementary", "ES", 640),
    ("ES-SM", "Dr. Samuel A. Mudd Elementary", "ES", 520),
    ("ES-GB", "Dr. Gustavus Brown Elementary", "ES", 550),
)

_GRADES_BY_LEVEL = {"ES": (3, 4, 5), "MS": (6, 7, 8), "HS": (9, 10, 11, 12)}


def build_ccps_district_faker(
    seed: int = 2026,
    students_per_school: int = 30,
    teachers_per_school: int = 5,
    locale: str = "en_US",
) -> District:
    """
    Build a validated CCPS district with Faker-generated people.

    Names come from Faker (seeded); scores, attendance, and curriculum
    follow the same distributions as the built-in generator so metric
    outputs stay in realistic Maryland ranges.
    """
    if Faker is None:
        raise EducationDataError(
            "the 'faker' package is required for build_ccps_district_faker; "
            "install it with: pip install faker"
        ) from _FAKER_IMPORT_ERROR

    fake = Faker(locale)
    fake.seed_instance(seed)
    rng = random.Random(seed)

    district = District(name="Charles County Public Schools")
    for school_id, name, level, capacity in CCPS_ALL_SCHOOLS:
        district.add_school(School(school_id, name, level, capacity))
    for course in _make_courses(rng):
        district.add_course(course)

    section_counter = 0
    for school_id, _name, level, _capacity in CCPS_ALL_SCHOOLS:
        for slot in range(teachers_per_school):
            subject = SUBJECTS[slot % len(SUBJECTS)]
            district.add_teacher(
                Teacher(
                    teacher_id=f"T-{school_id}-{slot:02d}",
                    name=fake.name(),
                    school_id=school_id,
                    subject=subject,
                    years_experience=rng.randint(0, 30),
                    certified=rng.random() > 0.05,
                    evaluation_score=round(rng.uniform(2.0, 4.0), 2),
                    pd_hours=round(rng.uniform(4, 48), 1),
                )
            )
            section_counter += 1
            district.add_section(
                Section(
                    section_id=f"SEC-{section_counter:04d}",
                    course_id=f"C-{subject[:3].upper()}",
                    teacher_id=f"T-{school_id}-{slot:02d}",
                    school_id=school_id,
                )
            )

        sections_here = [
            sec for sec in district.sections.values() if sec.school_id == school_id
        ]
        grade_pool = _GRADES_BY_LEVEL[level]
        for number in range(students_per_school):
            days_enrolled = 180
            if rng.random() < 0.70:
                days_present = int(days_enrolled * rng.uniform(0.92, 1.0))
            else:
                days_present = int(days_enrolled * rng.uniform(0.70, 0.92))
            base_ability = rng.uniform(35, 88)
            student = Student(
                student_id=f"S-{school_id}-{number:03d}",
                name=fake.name(),
                school_id=school_id,
                grade_level=rng.choice(grade_pool),
                days_enrolled=days_enrolled,
                days_present=days_present,
                gpa=round(min(4.0, max(0.0, base_ability / 22.0 + rng.uniform(-0.4, 0.4))), 2),
                farms=rng.random() < 0.38,
                ell=rng.random() < 0.09,
                iep=rng.random() < 0.12,
            )
            for subject in SUBJECTS:
                pre = min(100.0, max(0.0, base_ability + rng.uniform(-8, 8)))
                attendance_boost = (student.attendance_rate - 0.85) * 40
                post = min(100.0, max(0.0, pre + rng.uniform(-3, 9) + attendance_boost))
                if post >= 75:
                    mcap_level = 4
                elif post >= 60:
                    mcap_level = 3
                elif post >= 45:
                    mcap_level = 2
                else:
                    mcap_level = 1
                student.assessments[subject] = AssessmentResult(
                    subject=subject,
                    pre_score=round(pre, 1),
                    post_score=round(post, 1),
                    level=mcap_level,
                )
            district.add_student(student)
            for section in sections_here:
                course = district.courses[section.course_id]
                result = student.assessments[course.subject]
                grade = min(100.0, max(0.0, result.post_score + rng.uniform(-6, 10)))
                district.enroll(
                    Enrollment(
                        student_id=student.student_id,
                        section_id=section.section_id,
                        final_grade=round(grade, 1),
                    )
                )

    district.validate()
    return district


def roster_preview(district: District, count: int = 8) -> List[str]:
    """A few Faker-generated names for a quick eyeball check."""
    students = sorted(district.students.values(), key=lambda s: s.student_id)
    return [
        f"{student.student_id}  {student.name}  "
        f"({district.schools[student.school_id].name}, grade {student.grade_level})"
        for student in students[:count]
    ]
