"""
Deterministic synthetic data for Charles County Public Schools.

Real CCPS school names are used; every number is generated from a
seed so reports are reproducible run to run (and in tests). Swap
`build_ccps_district` for a CSV/SIS loader in production — the models
and metrics do not care where rows come from.
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

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
    SUBJECTS,
)


CCPS_SCHOOLS: Tuple[Tuple[str, str, str, int], ...] = (
    ("HS-NP", "North Point High", "HS", 2200),
    ("HS-SC", "St. Charles High", "HS", 1900),
    ("HS-LP", "La Plata High", "HS", 1500),
    ("HS-TS", "Thomas Stone High", "HS", 1450),
    ("HS-WL", "Westlake High", "HS", 1550),
    ("HS-MM", "Maurice J. McDonough High", "HS", 1300),
    ("HS-HL", "Henry E. Lackey High", "HS", 1250),
    ("MS-JH", "John Hanson Middle", "MS", 900),
    ("MS-MW", "Mattawoman Middle", "MS", 950),
    ("MS-SO", "Milton M. Somers Middle", "MS", 850),
)

FIRST_NAMES = (
    "Ava", "Liam", "Maya", "Noah", "Zoe", "Ethan", "Nia", "Owen",
    "Ruth", "Caleb", "Ivy", "Jonah", "Lena", "Marcus", "Tara", "Devon",
)
LAST_NAMES = (
    "Chen", "Johnson", "Okafor", "Reyes", "Nguyen", "Brooks", "Patel",
    "Washington", "Kim", "Lopez", "Grant", "Hayes", "Osei", "Turner",
)

MD_STANDARDS: Dict[str, Tuple[str, ...]] = {
    "ELA": ("RL.1", "RL.2", "RI.4", "W.1", "W.2", "SL.1", "L.3", "L.4"),
    "Math": ("A-SSE.1", "A-REI.3", "F-IF.4", "G-CO.9", "S-ID.6", "N-RN.2"),
    "Science": ("HS-PS1-1", "HS-PS2-1", "HS-LS1-2", "HS-LS3-1", "HS-ESS2-2"),
}


def _make_courses(rng: random.Random) -> List[Course]:
    """Three courses per subject-ish; each course splits standards into units."""
    titles = {
        "ELA": "English 10",
        "Math": "Algebra I",
        "Science": "Biology",
    }
    courses: List[Course] = []
    for subject in SUBJECTS:
        standards = list(MD_STANDARDS[subject])
        midpoint = len(standards) // 2
        chunks = [tuple(standards[:midpoint]), tuple(standards[midpoint:])]
        units: List[Unit] = []
        for index, chunk in enumerate(chunks, start=1):
            planned = rng.randint(15, 25)
            slip = rng.randint(-2, 6)
            taught = tuple(std for std in chunk if rng.random() > 0.12)
            assessed_pool = taught if taught else chunk
            assessed = tuple(std for std in assessed_pool if rng.random() > 0.25)
            units.append(
                Unit(
                    unit_id=f"{subject[:2].upper()}-U{index}",
                    title=f"{titles[subject]} Unit {index}",
                    required_standards=chunk,
                    taught_standards=taught,
                    assessed_standards=assessed or (assessed_pool[0],),
                    planned_days=planned,
                    actual_days=max(planned + slip, 1),
                )
            )
        courses.append(
            Course(
                course_id=f"C-{subject[:3].upper()}",
                title=titles[subject],
                subject=subject,
                grade_level=9,
                units=units,
            )
        )
    return courses


def build_ccps_district(
    seed: int = 2026,
    students_per_school: int = 40,
    teachers_per_school: int = 6,
) -> District:
    """
    Build and validate a full district.

    Sizes are intentionally small enough for tests but every entity and
    relationship a real export would carry is present.
    """
    rng = random.Random(seed)
    district = District(name="Charles County Public Schools")

    for school_id, name, level, capacity in CCPS_SCHOOLS:
        district.add_school(School(school_id, name, level, capacity))

    for course in _make_courses(rng):
        district.add_course(course)

    section_counter = 0
    for school_id, _name, _level, _capacity in CCPS_SCHOOLS:
        school_teachers: List[Teacher] = []
        for slot in range(teachers_per_school):
            subject = SUBJECTS[slot % len(SUBJECTS)]
            teacher = Teacher(
                teacher_id=f"T-{school_id}-{slot:02d}",
                name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                school_id=school_id,
                subject=subject,
                years_experience=rng.randint(0, 28),
                certified=rng.random() > 0.06,
                evaluation_score=round(rng.uniform(2.0, 4.0), 2),
                pd_hours=round(rng.uniform(4, 48), 1),
            )
            district.add_teacher(teacher)
            school_teachers.append(teacher)

            section_counter += 1
            district.add_section(
                Section(
                    section_id=f"SEC-{section_counter:04d}",
                    course_id=f"C-{subject[:3].upper()}",
                    teacher_id=teacher.teacher_id,
                    school_id=school_id,
                )
            )

        sections_here = [
            sec for sec in district.sections.values() if sec.school_id == school_id
        ]
        for number in range(students_per_school):
            days_enrolled = 180
            """
            Roughly 70% of students attend 92-100% of days; the rest
            fall in a 70-92% band. This lands district chronic
            absenteeism in the 25-30% range Maryland actually reports.
            """
            if rng.random() < 0.70:
                days_present = int(days_enrolled * rng.uniform(0.92, 1.0))
            else:
                days_present = int(days_enrolled * rng.uniform(0.70, 0.92))
            base_ability = rng.uniform(35, 88)
            student = Student(
                student_id=f"S-{school_id}-{number:03d}",
                name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                school_id=school_id,
                grade_level=rng.choice((9, 10)) if school_id.startswith("HS") else rng.choice((6, 7, 8)),
                days_enrolled=days_enrolled,
                days_present=days_present,
                gpa=round(min(4.0, max(0.0, base_ability / 22.0 + rng.uniform(-0.4, 0.4))), 2),
                farms=rng.random() < 0.38,
                ell=rng.random() < 0.09,
                iep=rng.random() < 0.12,
            )
            for subject in SUBJECTS:
                pre = min(100.0, max(0.0, base_ability + rng.uniform(-8, 8)))
                """
                Attendance feeds growth: students in class most days gain
                more between the fall and spring administrations.
                """
                attendance_boost = (student.attendance_rate - 0.85) * 40
                post = min(100.0, max(0.0, pre + rng.uniform(-3, 9) + attendance_boost))
                if post >= 75:
                    level = 4
                elif post >= 60:
                    level = 3
                elif post >= 45:
                    level = 2
                else:
                    level = 1
                student.assessments[subject] = AssessmentResult(
                    subject=subject, pre_score=round(pre, 1), post_score=round(post, 1), level=level
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
