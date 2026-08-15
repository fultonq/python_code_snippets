#!/usr/bin/env python3
"""Tests for the comprehensive Riverside Campus Hub."""

import io
import unittest
from contextlib import redirect_stdout

from riverside_hub import CampusHub, HubError, handle_line, main, mayas_morning, run_interactive


class HubWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hub = CampusHub()

    def test_tap_hashmap(self) -> None:
        card = self.hub.tap("R1002341")
        self.assertEqual(card["name"], "Maya Chen")
        self.assertEqual(card["locker"], "U-114")
        with self.assertRaises(HubError):
            self.hub.tap("NOPE")

    def test_waitlist_array_mutations(self) -> None:
        line = self.hub.bump_waitlist("Maya")
        self.assertEqual(line[0], "Maya")
        self.assertIn("Walk-in", line)
        self.assertNotIn("Lee", line)

    def test_directory_tree(self) -> None:
        preview = self.hub.directory_preview()
        self.assertEqual(preview["root"], "Riverside")
        self.assertEqual(preview["level_order"][0], "Riverside")
        self.assertIn("CS", preview["level_order"])

    def test_flash_sale_is_sorted(self) -> None:
        rows = self.hub.flash_sale()
        self.assertIn("Lab Goggles", rows[0])
        self.assertIn("Organic Chemistry", rows[-1])

    def test_marketplace_checkout(self) -> None:
        result = self.hub.buy_used_books("maya")
        self.assertTrue(result["receipt"]["titles"])
        self.assertGreater(result["receipt"]["total"], 0)
        self.assertIn("maya", self.hub.desk.claimed)

    def test_shuttle_union_health(self) -> None:
        trip = self.hub.ride("Union", "Health")
        self.assertEqual(trip["hops"], ["Union", "Health"])
        self.assertEqual(trip["fastest"], ["Union", "Library", "Science", "Health"])
        self.assertEqual(trip["minutes"], 15)

    def test_degree_plan_orders_prereqs(self) -> None:
        order = self.hub.degree_plan()
        self.assertLess(order.index("CS101"), order.index("CS301"))
        self.assertLess(order.index("MATH101"), order.index("CS201"))


class DemoAndCliTests(unittest.TestCase):
    def test_morning_demo_completes(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = mayas_morning()
        self.assertEqual(status, 0)
        output = buffer.getvalue()
        self.assertIn("Maya Chen", output)
        self.assertIn("HashMap", output)
        self.assertIn("Merge sort", output)
        self.assertIn("topological sort", output)

    def test_repl_tap_and_quit(self) -> None:
        hub = CampusHub()
        message, done = handle_line(hub, "tap R1002341")
        self.assertFalse(done)
        self.assertIn("Maya Chen", message)
        message, done = handle_line(hub, "quit")
        self.assertTrue(done)

    def test_interactive_session(self) -> None:
        commands = iter(["plan", "quit"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = run_interactive(
                CampusHub(), input_fn=lambda _prompt: next(commands)
            )
        self.assertEqual(status, 0)
        self.assertIn("CS101", buffer.getvalue())

    def test_cli_tap(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = main(["tap", "R1002341"])
        self.assertEqual(status, 0)
        self.assertIn("Maya Chen", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
