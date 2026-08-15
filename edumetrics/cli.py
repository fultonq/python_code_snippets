"""
Command-line interface for CCPS education metrics.

    python3 -m edumetrics district
    python3 -m edumetrics school "North Point High"
    python3 -m edumetrics teachers --school "La Plata High" --top 5
    python3 -m edumetrics curriculum
    python3 -m edumetrics equity --subject Math
    python3 -m edumetrics export --out district_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional, Sequence

from edumetrics.data import build_ccps_district
from edumetrics.metrics import (
    MetricsError,
    curriculum_audit,
    district_summary,
    equity_gaps,
    school_report,
    teacher_report,
)
from edumetrics.models import District, EducationDataError, SUBJECTS


def _print_header(title: str) -> None:
    print(title)
    print("=" * len(title))


def _show_district(district: District) -> None:
    summary = district_summary(district)
    _print_header(summary["district"])
    print(
        f"schools={summary['schools']}  students={summary['students']}  "
        f"teachers={summary['teachers']}"
    )
    print(
        f"attendance {summary['attendance_rate']:.1%}   "
        f"chronic absenteeism {summary['chronic_absentee_rate']:.1%}   "
        f"avg GPA {summary['average_gpa']:.2f}"
    )
    print(f"certified teachers {summary['certified_teacher_rate']:.1%}")
    print("MCAP proficiency:", {k: f"{v:.1%}" for k, v in summary["proficiency"].items()})
    print()
    print(f"{'school':32} {'enr':>5} {'attend':>7} {'chronic':>8} {'GPA':>5}  ELA / Math / Sci")
    for row in summary["schools_detail"]:
        prof = row["proficiency"]
        print(
            f"{row['school']:32} {row['enrollment']:5} "
            f"{row['attendance_rate']:7.1%} {row['chronic_absentee_rate']:8.1%} "
            f"{row['average_gpa']:5.2f}  "
            f"{prof['ELA']:.0%} / {prof['Math']:.0%} / {prof['Science']:.0%}"
        )


def _show_school(district: District, name: str) -> None:
    report = school_report(district, name)
    _print_header(f"{report['school']} ({report['level']})")
    print(f"enrollment {report['enrollment']} / capacity {report['capacity']}")
    print(f"teachers on staff: {report['teachers']}")
    print(
        f"attendance {report['attendance_rate']:.1%}   "
        f"chronic absenteeism {report['chronic_absentee_rate']:.1%}   "
        f"avg GPA {report['average_gpa']:.2f}"
    )
    for subject, rate in report["proficiency"].items():
        print(f"  {subject:8} proficiency {rate:.1%}")


def _show_teachers(district: District, school_name: Optional[str], top: int) -> None:
    school_id = district.school_by_name(school_name).school_id if school_name else None
    rows = teacher_report(district, school_id)
    scope = school_name or "district"
    _print_header(f"Teacher effectiveness — {scope}")
    print(f"{'teacher':22} {'subject':8} {'yrs':>4} {'growth':>7} {'eval':>5} {'PD':>5} {'score':>6}  rating")
    for row in rows[:top]:
        print(
            f"{row['name']:22} {row['subject']:8} {row['years_experience']:4} "
            f"{row['median_growth_percentile']:7.1f} {row['evaluation_score']:5.2f} "
            f"{row['pd_hours']:5.1f} {row['composite']:6.3f}  {row['rating']}"
        )


def _show_curriculum(district: District) -> None:
    _print_header("Curriculum audit — coverage, alignment, pacing, pass rate")
    for row in curriculum_audit(district):
        print(
            f"{row['title']:12} [{row['subject']:7}] "
            f"coverage {row['coverage']:.0%}  alignment {row['assessment_alignment']:.0%}  "
            f"pacing {row['pacing_variance_days']:+d}d  pass {row['pass_rate']:.1%}"
        )
        if row["gaps"]:
            print(f"  untaught standards: {', '.join(row['gaps'])}")


def _show_equity(district: District, subject: str) -> None:
    report = equity_gaps(district, subject)
    _print_header(f"Equity — {subject} proficiency gaps")
    print(f"district overall: {report['overall_proficiency']:.1%}")
    for name, row in report["subgroups"].items():
        flag = "  << FLAGGED" if row["flagged"] else ""
        print(
            f"  {name:6} n={row['students']:4}  proficiency {row['proficiency']:.1%}  "
            f"gap {row['gap_points']:+.1f} pts{flag}"
        )


def _export(district: District, out_path: str) -> None:
    payload: Dict[str, Any] = {
        "summary": district_summary(district),
        "teachers": teacher_report(district),
        "curriculum": curriculum_audit(district),
        "equity": {subject: equity_gaps(district, subject) for subject in SUBJECTS},
    }
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"wrote {out_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edumetrics",
        description="Education metrics for Charles County Public Schools (MD)",
    )
    parser.add_argument("--seed", type=int, default=2026, help="data seed (default 2026)")
    parser.add_argument(
        "--faker",
        action="store_true",
        help="generate people with the faker package (all 24 CCPS buildings)",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("district", help="district-wide rollup")
    sub.add_parser("roster", help="preview generated student names (faker demo)")
    school = sub.add_parser("school", help="one school's report card")
    school.add_argument("name")
    teachers = sub.add_parser("teachers", help="teacher effectiveness table")
    teachers.add_argument("--school", default=None)
    teachers.add_argument("--top", type=int, default=15)
    sub.add_parser("curriculum", help="curriculum coverage / alignment / pacing")
    equity = sub.add_parser("equity", help="subgroup proficiency gaps")
    equity.add_argument("--subject", choices=SUBJECTS, default="Math")
    export = sub.add_parser("export", help="write the full report as JSON")
    export.add_argument("--out", default="ccps_report.json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
        if args.faker:
            from edumetrics.faker_data import build_ccps_district_faker

            district = build_ccps_district_faker(seed=args.seed)
        else:
            district = build_ccps_district(seed=args.seed)
        command = args.command or "district"
        if command == "district":
            _show_district(district)
        elif command == "roster":
            from edumetrics.faker_data import roster_preview

            _print_header("Roster preview")
            for line in roster_preview(district, count=10):
                print(line)
        elif command == "school":
            _show_school(district, args.name)
        elif command == "teachers":
            _show_teachers(district, args.school, args.top)
        elif command == "curriculum":
            _show_curriculum(district)
        elif command == "equity":
            _show_equity(district, args.subject)
        elif command == "export":
            _export(district, args.out)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except (MetricsError, EducationDataError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unhandled error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
