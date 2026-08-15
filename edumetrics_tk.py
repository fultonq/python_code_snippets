#!/usr/bin/env python3
"""
CCPS Metrics — Tcl/Tk desktop dashboard.

A native windowed front-end over the edumetrics engine using tkinter
(Tcl/Tk). All widgets take mouse input; keyboard shortcuts cover every
action. Requires a display (X11 / Wayland / Windows / macOS).

    python3 edumetrics_tk.py
    python3 edumetrics_tk.py --seed 7

Keys:  Ctrl+1..4 switch tabs   Ctrl+R reload   Ctrl+E export   Ctrl+Q quit
Mouse: click a column header to sort; pick a school in the dropdown to
       filter the Teachers tab; scroll wheel works in every table.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional, Sequence, Tuple

import tkinter as tk
from tkinter import messagebox, ttk

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
    school_names,
    school_table,
    teacher_table,
)


class SortableTable(ttk.Frame):
    """A Treeview table with scrollbars and click-to-sort headers."""

    def __init__(self, parent: tk.Misc, columns: Tuple[str, ...]) -> None:
        super().__init__(parent)
        self.columns = columns
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=18)
        for column in columns:
            self.tree.heading(
                column, text=column, command=lambda c=column: self.sort_by(c)
            )
            self.tree.column(column, width=110, anchor="w")
        y_scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self._sort_reverse = False

    def load(self, rows: List[Tuple]) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert("", "end", values=row)

    def sort_by(self, column: str) -> None:
        """Sort rows by a column; numbers sort numerically, text lexically."""
        index = self.columns.index(column)
        entries = [
            (self.tree.set(item, column), item) for item in self.tree.get_children()
        ]

        def key(pair):
            value = pair[0].rstrip("%").replace("+", "")
            try:
                return (0, float(value))
            except ValueError:
                return (1, pair[0].lower())

        entries.sort(key=key, reverse=self._sort_reverse)
        for position, (_value, item) in enumerate(entries):
            self.tree.move(item, "", position)
        self._sort_reverse = not self._sort_reverse
        del index  # column position not needed once values are read


class MetricsApp(tk.Tk):
    """Main window: KPI banner, notebook of tables, status bar."""

    def __init__(self, seed: int = 2026) -> None:
        super().__init__()
        self.title("Charles County Public Schools — Metrics")
        self.geometry("1150x640")
        self.seed = seed
        self.district = build_ccps_district(seed=seed)

        self.kpi_var = tk.StringVar()
        ttk.Label(self, textvariable=self.kpi_var, padding=8).pack(fill="x")

        toolbar = ttk.Frame(self, padding=(8, 0))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Teachers at:").pack(side="left")
        self.school_var = tk.StringVar(value="(all schools)")
        self.school_pick = ttk.Combobox(
            toolbar, textvariable=self.school_var, state="readonly", width=30
        )
        self.school_pick.pack(side="left", padx=6)
        self.school_pick.bind("<<ComboboxSelected>>", lambda _e: self.reload_teachers())
        ttk.Button(toolbar, text="Reload (Ctrl+R)", command=self.reload).pack(
            side="left", padx=6
        )
        ttk.Button(toolbar, text="Export JSON (Ctrl+E)", command=self.export).pack(
            side="left"
        )

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tables = {}
        for name, columns in (
            ("Schools", school_table(self.district)[0]),
            ("Teachers", teacher_table(self.district)[0]),
            ("Curriculum", curriculum_table(self.district)[0]),
            ("Equity", equity_table(self.district)[0]),
        ):
            table = SortableTable(self.notebook, columns)
            self.notebook.add(table, text=name)
            self.tables[name] = table

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, padding=4, relief="sunken").pack(
            fill="x"
        )

        for key, index in (("1", 0), ("2", 1), ("3", 2), ("4", 3)):
            self.bind_all(
                f"<Control-Key-{key}>",
                lambda _e, i=index: self.notebook.select(i),
            )
        self.bind_all("<Control-r>", lambda _e: self.reload())
        self.bind_all("<Control-e>", lambda _e: self.export())
        self.bind_all("<Control-q>", lambda _e: self.destroy())

        self.refresh_all()

    def refresh_all(self) -> None:
        kpis = district_kpis(self.district)
        self.kpi_var.set("   |   ".join(f"{k}: {v}" for k, v in kpis.items()))
        self.school_pick["values"] = ["(all schools)"] + school_names(self.district)
        self.tables["Schools"].load(school_table(self.district)[1])
        self.reload_teachers()
        self.tables["Curriculum"].load(curriculum_table(self.district)[1])
        self.tables["Equity"].load(equity_table(self.district)[1])
        self.status_var.set(
            f"seed {self.seed} — {len(self.district.students)} students, "
            f"{len(self.district.teachers)} teachers, "
            f"{len(self.district.schools)} schools"
        )

    def reload_teachers(self) -> None:
        chosen = self.school_var.get()
        name = None if chosen == "(all schools)" else chosen
        self.tables["Teachers"].load(teacher_table(self.district, name)[1])

    def reload(self) -> None:
        self.seed += 1
        self.district = build_ccps_district(seed=self.seed)
        self.refresh_all()

    def export(self) -> None:
        out_path = f"ccps_report_seed{self.seed}.json"
        payload = {
            "summary": district_summary(self.district),
            "teachers": teacher_report(self.district),
            "curriculum": curriculum_audit(self.district),
            "equity": {s: equity_gaps(self.district, s) for s in SUBJECTS},
        }
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        self.status_var.set(f"wrote {out_path}")
        messagebox.showinfo("Export", f"Report written to {out_path}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CCPS metrics desktop dashboard")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        app = MetricsApp(seed=args.seed)
    except tk.TclError as exc:
        print(
            f"Could not open a display ({exc}). "
            "Run on a desktop session, or use edumetrics_tui.py in the terminal.",
            file=sys.stderr,
        )
        return 1
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
