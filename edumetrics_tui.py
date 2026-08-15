#!/usr/bin/env python3
"""
CCPS Metrics — Textual/Rich terminal dashboard.

Runs entirely in the terminal with full keyboard and mouse support
(Textual reads OS terminal events: clicks, wheel scroll, and keys).

    python3 edumetrics_tui.py
    python3 edumetrics_tui.py --seed 7

Keys: 1-4 switch tabs, r reload data, x export JSON, q quit.
Mouse: click tabs, click column headers, wheel-scroll tables.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane

from edumetrics.data import build_ccps_district
from edumetrics.metrics import (
    curriculum_audit,
    district_summary,
    equity_gaps,
    teacher_report,
)
from edumetrics.models import SUBJECTS
from edumetrics.views import (
    curriculum_table,
    district_kpis,
    equity_table,
    school_table,
    teacher_table,
)


class KpiBar(Static):
    """One-line banner of district headline numbers."""

    def update_kpis(self, kpis: dict) -> None:
        text = "  |  ".join(f"[b]{key}[/b] {value}" for key, value in kpis.items())
        self.update(text)


class CCPSDashboard(App):
    """Four-tab dashboard over the edumetrics engine."""

    TITLE = "Charles County Public Schools — Metrics"
    CSS = """
    KpiBar {
        height: 3;
        padding: 1 2;
        background: $primary-darken-2;
        color: $text;
    }
    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("1", "show_tab('schools')", "Schools"),
        Binding("2", "show_tab('teachers')", "Teachers"),
        Binding("3", "show_tab('curriculum')", "Curriculum"),
        Binding("4", "show_tab('equity')", "Equity"),
        Binding("r", "reload", "Reload"),
        Binding("x", "export", "Export JSON"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, seed: int = 2026) -> None:
        super().__init__()
        self.seed = seed
        self.district = build_ccps_district(seed=seed)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield KpiBar(id="kpis")
        with TabbedContent(initial="schools"):
            with TabPane("Schools", id="schools"):
                yield DataTable(id="schools-table", zebra_stripes=True, cursor_type="row")
            with TabPane("Teachers", id="teachers"):
                yield DataTable(id="teachers-table", zebra_stripes=True, cursor_type="row")
            with TabPane("Curriculum", id="curriculum"):
                yield DataTable(id="curriculum-table", zebra_stripes=True, cursor_type="row")
            with TabPane("Equity", id="equity"):
                yield DataTable(id="equity-table", zebra_stripes=True, cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        """(Re)build the district and repopulate every table."""
        self.query_one("#kpis", KpiBar).update_kpis(district_kpis(self.district))
        fills = (
            ("#schools-table", school_table(self.district)),
            ("#teachers-table", teacher_table(self.district)),
            ("#curriculum-table", curriculum_table(self.district)),
            ("#equity-table", equity_table(self.district)),
        )
        for selector, (columns, rows) in fills:
            table = self.query_one(selector, DataTable)
            table.clear(columns=True)
            table.add_columns(*columns)
            table.add_rows(rows)

    def action_show_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active = tab_id

    def action_reload(self) -> None:
        self.seed += 1
        self.district = build_ccps_district(seed=self.seed)
        self.refresh_data()
        self.notify(f"reloaded with seed {self.seed}")

    def action_export(self) -> None:
        out_path = f"ccps_report_seed{self.seed}.json"
        payload = {
            "summary": district_summary(self.district),
            "teachers": teacher_report(self.district),
            "curriculum": curriculum_audit(self.district),
            "equity": {s: equity_gaps(self.district, s) for s in SUBJECTS},
        }
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        self.notify(f"wrote {out_path}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CCPS metrics terminal dashboard")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args(list(argv) if argv is not None else None)
    CCPSDashboard(seed=args.seed).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
