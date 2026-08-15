#!/usr/bin/env python3
"""Tests for the Riverside Student Swap advanced-Python marketplace."""

import io
import unittest
from contextlib import redirect_stdout

from campus_marketplace import (
    Listing,
    MarketplaceError,
    OutOfStockError,
    PercentageOff,
    PickRoute,
    UnknownSkuError,
    demonstrate_features,
    make_budget_filter,
    make_tax_calculator,
    seed_desk,
)


class ListingDunderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.item = Listing(
            "TB-CALC", "Used Calculus", 24.99, {"math", "used"}, 3, ("Union", 1, "A"), "maya"
        )

    def test_str_is_customer_facing(self) -> None:
        text = str(self.item)
        self.assertIn("Used Calculus", text)
        self.assertIn("24.99", text)
        self.assertNotIn("sku=", text)

    def test_repr_is_unambiguous(self) -> None:
        text = repr(self.item)
        self.assertIn("Listing(", text)
        self.assertIn("TB-CALC", text)
        self.assertIn("stock=3", text)

    def test_eq_and_hash_use_sku(self) -> None:
        other = Listing("TB-CALC", "Other Title", 1.0, set(), 0, ("X", 9, "Z"), "x")
        self.assertEqual(self.item, other)
        self.assertEqual(len({self.item, other}), 1)
        self.assertNotEqual(
            self.item,
            Listing("TB-PY", "Intro to Python", 18.5, set(), 1, ("Union", 1, "A"), "j"),
        )


class DataStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.desk = seed_desk()

    def test_tuple_location_is_dict_key(self) -> None:
        self.assertIn(("Union", 1, "A"), self.desk.bins)
        self.assertIn("TB-CALC", self.desk.bins[("Union", 1, "A")])

    def test_set_intersection_search(self) -> None:
        hits = self.desk.search(interests={"math", "used"})
        skus = {item.sku for item in hits}
        self.assertIn("TB-CALC", skus)
        self.assertIn("TB-ALG", skus)
        self.assertNotIn("HOOD-GR", skus)

    def test_list_comprehension_under_20(self) -> None:
        cheap = [
            listing.sku
            for listing in self.desk.by_sku.values()
            if listing.price < 20 and listing.stock > 0
        ]
        self.assertIn("TB-PY", cheap)
        self.assertIn("LAMP-01", cheap)

    def test_generator_streams_and_low_stock(self) -> None:
        first = next(self.desk.iter_catalog())
        self.assertIsInstance(first, Listing)
        alerts = list(self.desk.low_stock_alerts(1))
        self.assertTrue(all(item.stock == 1 for item in alerts))


class ClosureCallableDecoratorTests(unittest.TestCase):
    def test_tax_closure(self) -> None:
        add_tax = make_tax_calculator(0.0825)
        self.assertEqual(add_tax(100), 108.25)
        with self.assertRaises(MarketplaceError):
            make_tax_calculator(-0.1)

    def test_callable_coupon(self) -> None:
        coupon = PercentageOff(25, "FLASH25")
        self.assertEqual(coupon(40), 30.0)
        self.assertTrue(callable(coupon))
        self.assertIn("FLASH25", str(coupon))

    def test_budget_filter_closure_is_generator(self) -> None:
        desk = seed_desk()
        under_ten = make_budget_filter(10)
        titles = [item.title for item in under_ten(desk.iter_catalog())]
        self.assertEqual(titles, ["Desk Lamp"])

    def test_timed_and_audit_decorators(self) -> None:
        desk = seed_desk()
        desk.search(budget=50)
        self.assertGreaterEqual(desk.last_elapsed, 0)
        desk.reserve("USB-HUB", "maya")
        actions = [entry[0] for entry in desk.audit_log]
        self.assertIn("reserve", actions)


class IteratorTests(unittest.TestCase):
    def test_pick_route_iter_and_next(self) -> None:
        desk = seed_desk()
        desk.reserve("TB-CALC", "maya")
        desk.reserve("CALC-TI", "maya")
        route = desk.pick_route_for("maya")
        stops = []
        iterator = iter(route)
        try:
            while True:
                stops.append(next(iterator))
        except StopIteration:
            pass
        self.assertEqual(len(stops), 2)
        buildings = [stop[0][0] for stop in stops]
        self.assertEqual(buildings, sorted(buildings))
        with self.assertRaises(StopIteration):
            next(iterator)
        route.rewind()
        self.assertEqual(len(list(route)), 2)

    def test_exhausted_iterator_raises(self) -> None:
        route = PickRoute([])
        with self.assertRaises(StopIteration):
            next(iter(route))


class CheckoutTests(unittest.TestCase):
    def test_checkout_applies_coupons_and_tax(self) -> None:
        desk = seed_desk()
        desk.reserve("LAMP-01", "maya")
        receipt = desk.checkout(
            "maya",
            coupons=(PercentageOff(20, "MEMBER"),),
            add_tax=make_tax_calculator(0.10),
        )
        self.assertEqual(receipt["subtotal"], 8.75)
        self.assertEqual(receipt["discounted"], 7.00)
        self.assertEqual(receipt["total"], 7.70)
        self.assertIn("maya", desk.claimed)

    def test_reserve_errors(self) -> None:
        desk = seed_desk()
        with self.assertRaises(UnknownSkuError):
            desk.reserve("NOPE", "lee")
        with self.assertRaises(OutOfStockError):
            desk.reserve("CALC-TI", "lee", 9)

    def test_undo_stack(self) -> None:
        desk = seed_desk()
        before = desk.by_sku["HOOD-GR"].stock
        desk.reserve("HOOD-GR", "jordan", 1)
        self.assertEqual(desk.by_sku["HOOD-GR"].stock, before - 1)
        desk.undo_last()
        self.assertEqual(desk.by_sku["HOOD-GR"].stock, before)
        self.assertEqual(desk.carts["jordan"], [])


class DemonstrationTests(unittest.TestCase):
    def test_walkthrough_completes(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = demonstrate_features()
        output = buffer.getvalue()
        self.assertEqual(status, 0)
        self.assertIn("__str__ vs __repr__", output)
        self.assertIn("pick route", output)
        self.assertIn("STUDENT10", output)
        self.assertNotIn("UNEXPECTED SUCCESS", output)


if __name__ == "__main__":
    unittest.main()
