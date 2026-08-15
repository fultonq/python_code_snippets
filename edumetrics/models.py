"""
Domain models for Charles County Public Schools metrics.

Every model validates on construction so bad rows fail at load time,
not in the middle of a report. IDs are strings; scores use Maryland
conventions (MCAP performance levels 1-4, GPA 0.0-4.0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


MCAP_LEVELS = (1, 2, 3, 4)  # Beginning, Developing, Proficient, Distinguished
PROFICIENT_LEVEL = 3
CHRONIC_ABSENCE_THRESHOLD = 0.90
SUBJECTS = ("ELA", "Math", "Science")
SUBGROUPS = ("FARMS", "ELL", "IEP")


class EducationDataError(Exception):
    """Base exception for the edumetrics package."""


class ValidationError(EducationDataError, ValueError):
    """Raised when a record fails validation at construction."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


@dataclass(frozen=True)
class School:
    """One CCPS school building."""

    school_id: str
    name: str
    level: str  # "ES", "MS", "HS"
    enrollment_capacity: int

    def __post_init__(self) -> None:
        _require(bool(self.school_id), "school_id is required")
        _require(bool(self.name), "school name is required")
        _require(self.level in {"ES", "MS", "HS"}, f"level must be ES/MS/HS, got {self.level!r}")
        _require(self.enrollment_capacity > 0, "enrollment_capacity must be positive")


@dataclass
class Teacher:
    """A certificated teacher with evaluation and PD records."""

    teacher_id: str
    name: str
    school_id: str
    subject: str
    years_experience: int
    certified: bool
    evaluation_score: float  # Danielson-style composite, 1.0 - 4.0
    pd_hours: float  # professional development hours this year

    def __post_init__(self) -> None:
        _require(bool(self.teacher_id), "teacher_id is required")
        _require(self.subject in SUBJECTS, f"subject must be one of {SUBJECTS}, got {self.subject!r}")
        _require(self.years_experience >= 0, "years_experience must be >= 0")
        _require(
            1.0 <= self.evaluation_score <= 4.0,
            f"evaluation_score must be 1.0-4.0, got {self.evaluation_score}",
        )
        _require(self.pd_hours >= 0, "pd_hours must be >= 0")


@dataclass
class AssessmentResult:
    """Pre/post scale scores and an MCAP performance level for one subject."""

    subject: str
    pre_score: float
    post_score: float
    level: int

    def __post_init__(self) -> None:
        _require(self.subject in SUBJECTS, f"unknown subject {self.subject!r}")
        _require(0 <= self.pre_score <= 100, f"pre_score out of range: {self.pre_score}")
        _require(0 <= self.post_score <= 100, f"post_score out of range: {self.post_score}")
        _require(self.level in MCAP_LEVELS, f"MCAP level must be 1-4, got {self.level}")

    @property
    def growth(self) -> float:
        return self.post_score - self.pre_score

    @property
    def proficient(self) -> bool:
        return self.level >= PROFICIENT_LEVEL


@dataclass
class Student:
    """One enrolled student with attendance, GPA, and assessment results."""

    student_id: str
    name: str
    school_id: str
    grade_level: int
    days_enrolled: int
    days_present: int
    gpa: float
    farms: bool = False  # Free and Reduced-price Meals
    ell: bool = False  # English Language Learner
    iep: bool = False  # Individualized Education Program
    assessments: Dict[str, AssessmentResult] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require(bool(self.student_id), "student_id is required")
        _require(0 <= self.grade_level <= 12, f"grade_level must be 0-12, got {self.grade_level}")
        _require(self.days_enrolled > 0, "days_enrolled must be positive")
        _require(
            0 <= self.days_present <= self.days_enrolled,
            f"days_present must be 0..{self.days_enrolled}, got {self.days_present}",
        )
        _require(0.0 <= self.gpa <= 4.0, f"gpa must be 0.0-4.0, got {self.gpa}")

    @property
    def attendance_rate(self) -> float:
        return self.days_present / self.days_enrolled

    @property
    def chronically_absent(self) -> bool:
        return self.attendance_rate < CHRONIC_ABSENCE_THRESHOLD

    def subgroups(self) -> Set[str]:
        active = set()
        if self.farms:
            active.add("FARMS")
        if self.ell:
            active.add("ELL")
        if self.iep:
            active.add("IEP")
        return active


@dataclass
class Unit:
    """One curriculum unit: the standards it must teach and assess."""

    unit_id: str
    title: str
    required_standards: Tuple[str, ...]
    taught_standards: Tuple[str, ...]
    assessed_standards: Tuple[str, ...]
    planned_days: int
    actual_days: int

    def __post_init__(self) -> None:
        _require(bool(self.unit_id), "unit_id is required")
        _require(len(self.required_standards) > 0, "a unit needs at least one required standard")
        _require(self.planned_days > 0, "planned_days must be positive")
        _require(self.actual_days >= 0, "actual_days must be >= 0")
        extra = set(self.taught_standards) - set(self.required_standards)
        _require(
            not extra,
            f"taught standards not in the required list: {sorted(extra)}",
        )


@dataclass
class Course:
    """A course of study (e.g. Algebra I) made of ordered units."""

    course_id: str
    title: str
    subject: str
    grade_level: int
    units: List[Unit] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require(bool(self.course_id), "course_id is required")
        _require(self.subject in SUBJECTS, f"unknown subject {self.subject!r}")
        _require(0 <= self.grade_level <= 12, "grade_level must be 0-12")

    def required_standards(self) -> Set[str]:
        return {std for unit in self.units for std in unit.required_standards}

    def taught_standards(self) -> Set[str]:
        return {std for unit in self.units for std in unit.taught_standards}

    def assessed_standards(self) -> Set[str]:
        return {std for unit in self.units for std in unit.assessed_standards}


@dataclass
class Section:
    """One scheduled class: a teacher delivering a course at a school."""

    section_id: str
    course_id: str
    teacher_id: str
    school_id: str

    def __post_init__(self) -> None:
        _require(bool(self.section_id), "section_id is required")


@dataclass
class Enrollment:
    """A student seat in a section with the earned course grade (0-100)."""

    student_id: str
    section_id: str
    final_grade: float

    def __post_init__(self) -> None:
        _require(
            0 <= self.final_grade <= 100,
            f"final_grade must be 0-100, got {self.final_grade}",
        )


@dataclass
class District:
    """
    The whole district: lookup tables plus referential-integrity checks.

    `validate()` cross-checks every foreign key so a report never dies
    on a dangling ID halfway through.
    """

    name: str
    schools: Dict[str, School] = field(default_factory=dict)
    teachers: Dict[str, Teacher] = field(default_factory=dict)
    students: Dict[str, Student] = field(default_factory=dict)
    courses: Dict[str, Course] = field(default_factory=dict)
    sections: Dict[str, Section] = field(default_factory=dict)
    enrollments: List[Enrollment] = field(default_factory=list)

    def add_school(self, school: School) -> None:
        _require(school.school_id not in self.schools, f"duplicate school {school.school_id}")
        self.schools[school.school_id] = school

    def add_teacher(self, teacher: Teacher) -> None:
        _require(teacher.teacher_id not in self.teachers, f"duplicate teacher {teacher.teacher_id}")
        self.teachers[teacher.teacher_id] = teacher

    def add_student(self, student: Student) -> None:
        _require(student.student_id not in self.students, f"duplicate student {student.student_id}")
        self.students[student.student_id] = student

    def add_course(self, course: Course) -> None:
        _require(course.course_id not in self.courses, f"duplicate course {course.course_id}")
        self.courses[course.course_id] = course

    def add_section(self, section: Section) -> None:
        _require(section.section_id not in self.sections, f"duplicate section {section.section_id}")
        self.sections[section.section_id] = section

    def enroll(self, enrollment: Enrollment) -> None:
        self.enrollments.append(enrollment)

    def students_at(self, school_id: str) -> List[Student]:
        return [s for s in self.students.values() if s.school_id == school_id]

    def teachers_at(self, school_id: str) -> List[Teacher]:
        return [t for t in self.teachers.values() if t.school_id == school_id]

    def school_by_name(self, name: str) -> School:
        for school in self.schools.values():
            if school.name.lower() == name.lower():
                return school
        raise EducationDataError(f"no school named {name!r}")

    def sections_taught_by(self, teacher_id: str) -> List[Section]:
        return [sec for sec in self.sections.values() if sec.teacher_id == teacher_id]

    def enrollments_in(self, section_id: str) -> List[Enrollment]:
        return [e for e in self.enrollments if e.section_id == section_id]

    def validate(self) -> None:
        """Cross-check foreign keys across the whole district."""
        for teacher in self.teachers.values():
            _require(
                teacher.school_id in self.schools,
                f"teacher {teacher.teacher_id} references unknown school {teacher.school_id}",
            )
        for student in self.students.values():
            _require(
                student.school_id in self.schools,
                f"student {student.student_id} references unknown school {student.school_id}",
            )
        for section in self.sections.values():
            _require(
                section.course_id in self.courses,
                f"section {section.section_id} references unknown course {section.course_id}",
            )
            _require(
                section.teacher_id in self.teachers,
                f"section {section.section_id} references unknown teacher {section.teacher_id}",
            )
            _require(
                section.school_id in self.schools,
                f"section {section.section_id} references unknown school {section.school_id}",
            )
        for enrollment in self.enrollments:
            _require(
                enrollment.student_id in self.students,
                f"enrollment references unknown student {enrollment.student_id}",
            )
            _require(
                enrollment.section_id in self.sections,
                f"enrollment references unknown section {enrollment.section_id}",
            )
