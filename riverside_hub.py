#!/usr/bin/env python3
"""
Riverside Campus Hub — one application built from every snippet.

Maya Chen's morning uses the modules in this repo together:

  hashmap.py              tap SID -> locker / meal plan
  array_operations.py     advising waitlist insert / delete / replace
  tree_operations.py      campus directory (level-order tree)
  sorting_algorithms.py   flash-sale shelf sorted by price
  campus_marketplace.py   used-book search, pick route, coupons, tax
  graph_algorithms.py     shuttle hops vs minutes, course prerequisites

    python3 riverside_hub.py
    python3 riverside_hub.py demo
    python3 riverside_hub.py tap R1002341
    python3 riverside_hub.py ride Union Health
    python3 riverside_hub.py interactive
    python3 -m unittest test_riverside_hub.py -v
"""

from __future__ import annotations

import argparse
import shlex
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from array_operations import ArrayManager
from campus_marketplace import (
    PercentageOff,
    make_tax_calculator,
    seed_desk,
)
from graph_algorithms import campus_shuttle, course_catalog
from hashmap import HashMap, MissingKeyError, seed_id_office
from sorting_algorithms import PRODUCT_KEYS, featured_shelf, merge_sort
from tree_operations import TreeManager


HELP_TEXT = """
Riverside Campus Hub
--------------------
  help                 Show this help
  tap SID              HashMap ID lookup (example: tap R1002341)
  waitlist             Show / bump the advising waitlist (array)
  directory            Show the campus directory tree
  sale                 Merge-sort the flash-sale shelf by price
  swap                 Maya buys used books (marketplace)
  ride START GOAL      Shuttle: fewest hops vs fastest minutes
  plan                 Legal CS course order (topological sort)
  demo                 Run Maya's whole morning
  quit                 Exit
""".strip()


class HubError(Exception):
    """Base exception for the campus hub."""


class CampusHub:
    """
    Facade over every campus system we have implemented.

    Keeping one object means the interactive prompt and the scripted
    day-in-the-life demo share the same seeded state.
    """

    MAYA = "R1002341"

    def __init__(self) -> None:
        self.ids: HashMap = seed_id_office()
        self.waitlist = ArrayManager(values=["Jordan", "Sam", "Priya", "Lee"])
        self.directory = TreeManager(
            values=[
                "Riverside",
                "Academic",
                "StudentLife",
                "CS",
                "Math",
                "Union",
                "Rec",
            ]
        )
        self.shelf = featured_shelf()
        self.desk = seed_desk()
        self.shuttle = campus_shuttle()
        self.courses = course_catalog()
        self.tax = make_tax_calculator(0.0825)
        self.member = PercentageOff(10, "STUDENT10")

    def tap(self, sid: str) -> Dict[str, Any]:
        """HashMap: card reader lookup."""
        try:
            record = self.ids[sid]
        except MissingKeyError as exc:
            raise HubError(f"unknown SID {sid}") from exc
        return {"sid": sid, **record}

    def bump_waitlist(self, name: str = "Maya") -> List[Any]:
        """
        Array ADT: advising line.

        Maya has a priority hold so she is inserted at index 0. Lee
        no-shows (delete last). The front slot is replaced with a
        walk-in after Maya is called.
        """
        self.waitlist.insert(0, name)
        if len(self.waitlist) > 0:
            self.waitlist.delete(-1)
        if len(self.waitlist) > 1:
            self.waitlist.replace(1, "Walk-in")
        return list(self.waitlist.arr_nums)

    def directory_preview(self) -> Dict[str, Any]:
        """Tree ADT: campus org chart in level order."""
        return {
            "root": self.directory.get(0),
            "level_order": self.directory.level_order(),
            "size": len(self.directory),
            "height": self.directory.height(),
        }

    def flash_sale(self) -> List[str]:
        """Merge sort: cheapest flash-sale titles first."""
        shelf = list(self.shelf)
        merge_sort(shelf, key=PRODUCT_KEYS["price"])
        return [f"{item.title} ${item.price:.2f}" for item in shelf]

    def buy_used_books(self, student: str = "maya") -> Dict[str, Any]:
        """Marketplace: search, reserve, iterate the pick route, checkout."""
        hits = self.desk.search(budget=30, interests={"math", "cs", "used"})
        for listing in hits[:2]:
            if listing.stock > 0:
                self.desk.reserve(listing.sku, student, 1)
        route = self.desk.pick_route_for(student)
        stops = []
        iterator = iter(route)
        try:
            while True:
                location, listing, qty = next(iterator)
                stops.append((location, listing.sku, qty))
        except StopIteration:
            pass
        receipt = self.desk.checkout(
            student, coupons=(self.member,), add_tax=self.tax
        )
        return {"hits": [item.sku for item in hits], "picks": stops, "receipt": receipt}

    def ride(self, start: str, goal: str) -> Dict[str, Any]:
        """Graph: fewest shuttle hops vs fastest minutes (Dijkstra)."""
        hops = self.shuttle.shortest_hops(start, goal)
        path, minutes = self.shuttle.shortest_weighted_path(start, goal)
        return {
            "hops": hops,
            "hop_count": len(hops) - 1,
            "fastest": path,
            "minutes": minutes,
        }

    def degree_plan(self) -> List[str]:
        """Directed graph: a legal order to take CS / MATH courses."""
        return self.courses.topological_sort()


def _print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def mayas_morning(hub: Optional[CampusHub] = None) -> int:
    """Scripted day that touches every module once."""
    hub = hub or CampusHub()
    try:
        _print_section("1. HashMap — Maya taps R1002341 at the Union gate")
        card = hub.tap(CampusHub.MAYA)
        print(
            f"{card['sid']}: {card['name']}  "
            f"meal={card['plan']}  locker={card['locker']}"
        )

        _print_section("2. Array — advising waitlist insert / delete / replace")
        line = hub.bump_waitlist("Maya")
        print("waitlist after Maya's priority insert:", line)

        _print_section("3. Tree — campus directory (level order)")
        directory = hub.directory_preview()
        print(f"root={directory['root']!r}  height={directory['height']}")
        print("level order:", " / ".join(str(name) for name in directory["level_order"]))

        _print_section("4. Merge sort — flash-sale shelf, cheapest first")
        for row in hub.flash_sale():
            print(f"  {row}")

        _print_section("5. Marketplace — used books, pick route, 10% + tax")
        swap = hub.buy_used_books("maya")
        print("search hits:", swap["hits"])
        for location, sku, qty in swap["picks"]:
            building, aisle, bin_id = location
            print(f"  pick {qty} x {sku} at {building} aisle {aisle} bin {bin_id}")
        receipt = swap["receipt"]
        print(
            f"paid ${receipt['total']:.2f}  "
            f"(subtotal ${receipt['subtotal']:.2f}, coupons {receipt['coupons']})"
        )

        _print_section("6. Graph — shuttle Union -> Health")
        trip = hub.ride("Union", "Health")
        print(f"fewest hops: {' -> '.join(trip['hops'])}  ({trip['hop_count']} rides)")
        print(
            f"fastest:     {' -> '.join(trip['fastest'])}  "
            f"({trip['minutes']:.0f} min)"
        )

        _print_section("7. Graph — degree plan (topological sort)")
        print(" -> ".join(hub.degree_plan()))
        return 0
    except Exception as exc:
        print(f"Hub error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def handle_line(hub: CampusHub, line: str) -> Tuple[str, bool]:
    stripped = line.strip()
    if not stripped:
        return "", False
    try:
        tokens = shlex.split(stripped)
    except ValueError as exc:
        raise HubError(f"could not parse command: {exc}") from exc
    command = tokens[0].lower()
    args = tokens[1:]

    if command in {"quit", "exit", "q"}:
        return "Goodbye.", True
    if command in {"help", "?"}:
        return HELP_TEXT, False
    if command == "tap":
        if len(args) != 1:
            raise HubError("usage: tap SID")
        card = hub.tap(args[0])
        return (
            f"{card['sid']}: {card['name']}  meal={card['plan']}  "
            f"locker={card['locker']}"
        ), False
    if command == "waitlist":
        line_now = hub.bump_waitlist()
        return "waitlist: " + ", ".join(str(item) for item in line_now), False
    if command == "directory":
        preview = hub.directory_preview()
        return " / ".join(str(name) for name in preview["level_order"]), False
    if command == "sale":
        return "\n".join(hub.flash_sale()), False
    if command == "swap":
        result = hub.buy_used_books()
        receipt = result["receipt"]
        return (
            f"bought {receipt['titles']} total=${receipt['total']:.2f}"
        ), False
    if command == "ride":
        if len(args) != 2:
            raise HubError("usage: ride START GOAL")
        trip = hub.ride(args[0], args[1])
        return (
            f"hops: {' -> '.join(trip['hops'])}\n"
            f"fastest: {' -> '.join(trip['fastest'])} ({trip['minutes']:.0f} min)"
        ), False
    if command == "plan":
        return " -> ".join(hub.degree_plan()), False
    if command == "demo":
        mayas_morning(hub)
        return "morning demo finished.", False
    raise HubError(f"unknown command {command!r}; type 'help'")


def run_interactive(
    hub: Optional[CampusHub] = None,
    input_fn: Callable[[str], str] = input,
) -> int:
    hub = hub or CampusHub()
    print("Riverside Campus Hub. Type 'help' or 'demo'.")
    while True:
        try:
            line = input_fn("hub> ")
        except EOFError:
            print()
            print("Goodbye.")
            return 0
        except KeyboardInterrupt:
            print()
            print("Interrupted. Type 'quit' to exit.")
            continue
        try:
            message, done = handle_line(hub, line)
        except HubError as exc:
            print(f"HubError: {exc}")
            continue
        except Exception as exc:
            print(f"{type(exc).__name__}: {exc}")
            continue
        if message:
            print(message)
        if done:
            return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Riverside Campus Hub")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("demo", help="Maya's morning through every module")
    sub.add_parser("interactive", help="command prompt")
    tap = sub.add_parser("tap", help="look up a student ID")
    tap.add_argument("sid")
    ride = sub.add_parser("ride", help="shuttle route")
    ride.add_argument("start")
    ride.add_argument("goal")
    sub.add_parser("plan", help="print a legal course order")
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
        command = args.command or "demo"
        hub = CampusHub()
        if command == "demo":
            return mayas_morning(hub)
        if command == "interactive":
            return run_interactive(hub)
        if command == "tap":
            card = hub.tap(args.sid)
            print(
                f"{card['sid']}: {card['name']}  "
                f"meal={card['plan']}  locker={card['locker']}"
            )
            return 0
        if command == "ride":
            trip = hub.ride(args.start, args.goal)
            print(f"fewest hops: {' -> '.join(trip['hops'])}")
            print(
                f"fastest:     {' -> '.join(trip['fastest'])}  "
                f"({trip['minutes']:.0f} min)"
            )
            return 0
        print(" -> ".join(hub.degree_plan()))
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except HubError as exc:
        print(f"HubError: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unhandled error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
