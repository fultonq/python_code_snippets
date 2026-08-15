"""
edumetrics — education metrics for Charles County (MD) Public Schools.

Measures three pillars:
  curriculum  standards coverage, pacing, assessment alignment
  teachers    student growth, evaluation, professional development
  students    attendance, GPA, MCAP proficiency, growth, equity gaps

Entry points:
    python3 -m edumetrics district
    python3 -m edumetrics school "North Point High"
    python3 -m edumetrics teachers --school "La Plata High"
    python3 -m edumetrics curriculum
    python3 -m edumetrics equity
    python3 -m edumetrics export --out district_report.json
"""

from edumetrics.models import (
    Course,
    District,
    EducationDataError,
    Enrollment,
    School,
    Section,
    Student,
    Teacher,
    Unit,
    ValidationError,
)
from edumetrics.data import build_ccps_district
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
    teacher_report,
)

__all__ = [
    "Course",
    "District",
    "EducationDataError",
    "Enrollment",
    "School",
    "Section",
    "Student",
    "Teacher",
    "Unit",
    "ValidationError",
    "MetricsError",
    "build_ccps_district",
    "attendance_rate",
    "chronic_absentee_rate",
    "curriculum_audit",
    "district_summary",
    "equity_gaps",
    "growth_percentiles",
    "proficiency_rate",
    "school_report",
    "teacher_report",
]

__version__ = "1.0.0"
