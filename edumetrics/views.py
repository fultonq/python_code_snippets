"""
Presentation-ready rows for the CCPS dashboards.

Both front-ends (tkinter GUI and Textual TUI) render the same data.
These helpers turn metric dicts into (columns, rows) tuples so the
widget code stays thin and the table shapes are testable without
opening a window.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from edumetrics.metrics import (
    curriculum_audit,
    district_summary,
    equity_gaps,
    teacher_report,
)
from edumetrics.models import District, SUBJECTS

Columns = Tuple[str, ...]
Rows = List[Tuple[Any, ...]]


def school_names(district: District) -> List[str]:
    return sorted(school.name for school in district.schools.values())


def district_kpis(district: District) -> Dict[str, str]:
    """Headline numbers for the dashboard banner."""
    summary = district_summary(district)
    return {
        "District": summary["district"],
        "Schools": str(summary["schools"]),
        "Students": str(summary["students"]),
        "Teachers": str(summary["teachers"]),
        "Attendance": f"{summary['attendance_rate']:.1%}",
        "Chronic Absent": f"{summary['chronic_absentee_rate']:.1%}",
        "Avg GPA": f"{summary['average_gpa']:.2f}",
        "Certified": f"{summary['certified_teacher_rate']:.1%}",
    }


def school_table(district: District) -> Tuple[Columns, Rows]:
    """One row per school with attendance, GPA, and MCAP proficiency."""
    summary = district_summary(district)
    columns = (
        "School", "Level", "Enrolled", "Attendance",
        "Chronic", "GPA", "ELA", "Math", "Science",
    )
    rows: Rows = []
    for row in summary["schools_detail"]:
        prof = row["proficiency"]
        rows.append(
            (
                row["school"],
                row["level"],
                row["enrollment"],
                f"{row['attendance_rate']:.1%}",
                f"{row['chronic_absentee_rate']:.1%}",
                f"{row['average_gpa']:.2f}",
                f"{prof['ELA']:.0%}",
                f"{prof['Math']:.0%}",
                f"{prof['Science']:.0%}",
            )
        )
    return columns, rows


def teacher_table(
    district: District, school_name: Optional[str] = None
) -> Tuple[Columns, Rows]:
    """Effectiveness table, best composite first."""
    school_id = (
        district.school_by_name(school_name).school_id if school_name else None
    )
    columns = (
        "Teacher", "School", "Subject", "Yrs", "Cert",
        "Growth %ile", "Eval", "PD hrs", "Composite", "Rating",
    )
    rows: Rows = []
    for row in teacher_report(district, school_id):
        rows.append(
            (
                row["name"],
                district.schools[row["school_id"]].name,
                row["subject"],
                row["years_experience"],
                "Y" if row["certified"] else "N",
                f"{row['median_growth_percentile']:.1f}",
                f"{row['evaluation_score']:.2f}",
                f"{row['pd_hours']:.1f}",
                f"{row['composite']:.3f}",
                row["rating"],
            )
        )
    return columns, rows


def curriculum_table(district: District) -> Tuple[Columns, Rows]:
    columns = (
        "Course", "Subject", "Coverage", "Alignment",
        "Pacing (days)", "Pass Rate", "Untaught Standards",
    )
    rows: Rows = []
    for row in curriculum_audit(district):
        rows.append(
            (
                row["title"],
                row["subject"],
                f"{row['coverage']:.0%}",
                f"{row['assessment_alignment']:.0%}",
                f"{row['pacing_variance_days']:+d}",
                f"{row['pass_rate']:.1%}",
                ", ".join(row["gaps"]) or "—",
            )
        )
    return columns, rows


def equity_table(
    district: District, subjects: Sequence[str] = SUBJECTS
) -> Tuple[Columns, Rows]:
    """All subjects in one table so a scan spots flagged gaps quickly."""
    columns = (
        "Subject", "Subgroup", "Students", "Proficiency",
        "Gap (pts)", "Flagged",
    )
    rows: Rows = []
    for subject in subjects:
        report = equity_gaps(district, subject)
        for subgroup, detail in report["subgroups"].items():
            rows.append(
                (
                    subject,
                    subgroup,
                    detail["students"],
                    f"{detail['proficiency']:.1%}",
                    f"{detail['gap_points']:+.1f}",
                    "YES" if detail["flagged"] else "no",
                )
            )
    return columns, rows
