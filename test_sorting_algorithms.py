#!/usr/bin/env python3
"""Unit tests for bubble, selection, insertion, and merge sort."""

import io
import random
import unittest
from contextlib import redirect_stderr, redirect_stdout

from sorting_algorithms import (
    ALGORITHMS,
    CATALOG_SIZE,
    InvalidInputError,
    CommandParseError,
    bubble_sort,
    featured_shelf,
    generate_catalog,
    handle_repl_line,
    insertion_sort,
    main,
    merge_sort,
    selection_sort,
    demonstrate_sorts,
)


def _sorted_like(items, *, key=None, reverse=False):
    return sorted(items, key=key, reverse=reverse)


class CorrectnessTests(unittest.TestCase):
    def test_matches_builtin_sorted_on_random_ints(self) -> None:
        rng = random.Random(0)
        samples = [
            [],
            [7],
            [1, 2, 3, 4],
            [4, 3, 2, 1],
            [5, 1, 5, 2, 5],
            rng.sample(range(200), 80),
        ]
        for name, sort_fn in ALGORITHMS.items():
            for sample in samples:
                with self.subTest(algorithm=name, sample=sample[:8]):
                    data = list(sample)
                    sort_fn(data)
                    self.assertEqual(data, _sorted_like(sample))

    def test_reverse(self) -> None:
        original = [3, 1, 4, 1, 5, 9]
        for sort_fn in ALGORITHMS.values():
            data = list(original)
            sort_fn(data, reverse=True)
            self.assertEqual(data, [9, 5, 4, 3, 1, 1])

    def test_key_function(self) -> None:
        words = ["pear", "Apple", "fig"]
        for sort_fn in ALGORITHMS.values():
            data = list(words)
            sort_fn(data, key=str.lower)
            self.assertEqual(data, ["Apple", "fig", "pear"])


class StabilityTests(unittest.TestCase):
    def test_stable_algorithms_keep_equal_key_order(self) -> None:
        pairs = [("a", 2), ("b", 2), ("c", 1)]
        expected = [("c", 1), ("a", 2), ("b", 2)]
        for sort_fn in (bubble_sort, insertion_sort, merge_sort):
            data = list(pairs)
            sort_fn(data, key=lambda pair: pair[1])
            self.assertEqual(data, expected)

    def test_selection_can_reorder_equal_keys(self) -> None:
        pairs = [("a", 2), ("b", 2), ("c", 1)]
        data = list(pairs)
        selection_sort(data, key=lambda pair: pair[1])
        self.assertEqual([pair[1] for pair in data], [1, 2, 2])
        self.assertEqual(data[1][0], "b")
        self.assertEqual(data[2][0], "a")


class ProductTests(unittest.TestCase):
    def test_featured_shelf_cheapest_is_goggles(self) -> None:
        shelf = featured_shelf()
        merge_sort(shelf, key=lambda product: product.price)
        self.assertEqual(shelf[0].title, "Lab Goggles")
        self.assertEqual(shelf[-1].title, "Organic Chemistry")

    def test_stable_price_sort_keeps_python_book_arrival_order(self) -> None:
        shelf = featured_shelf()
        insertion_sort(shelf, key=lambda product: product.price)
        tied = [item for item in shelf if item.price == 79.99]
        self.assertEqual(tied[0].title, "Intro to Python Programming")
        self.assertEqual(tied[1].title, "Data Structures in Python")

    def test_catalog_size(self) -> None:
        catalog = generate_catalog(CATALOG_SIZE)
        self.assertEqual(len(catalog), 15335)
        merge_sort(catalog, key=lambda product: product.price)
        prices = [item.price for item in catalog]
        self.assertEqual(prices, sorted(prices))


class ErrorTests(unittest.TestCase):
    def test_rejects_non_list(self) -> None:
        with self.assertRaises(InvalidInputError):
            bubble_sort((3, 2, 1))

    def test_rejects_mixed_types(self) -> None:
        with self.assertRaises(InvalidInputError):
            insertion_sort([1, "x"])

    def test_rejects_bad_catalog_size(self) -> None:
        with self.assertRaises(InvalidInputError):
            generate_catalog(-1)
        with self.assertRaises(InvalidInputError):
            generate_catalog(True)


class DemonstrationTests(unittest.TestCase):
    def test_walkthrough_completes(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = demonstrate_sorts()
        output = buffer.getvalue()
        self.assertEqual(status, 0)
        self.assertIn("Flash-sale shelf", output)
        self.assertIn("15,335 SKUs", output)
        self.assertNotIn("UNEXPECTED SUCCESS", output)


class ReplTests(unittest.TestCase):
    def test_bubble_then_show(self) -> None:
        items = featured_shelf()
        reverse = [False]
        message, done, replacement = handle_repl_line(items, reverse, "bubble price")
        self.assertFalse(done)
        self.assertIsNone(replacement)
        self.assertIn("bubble", message)
        self.assertEqual(items[0].title, "Lab Goggles")

    def test_unknown_command(self) -> None:
        with self.assertRaises(CommandParseError):
            handle_repl_line(featured_shelf(), [False], "heapsort")


class CliTests(unittest.TestCase):
    def test_sort_featured_with_insertion(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = main(["sort", "--algorithm", "insertion", "--by", "price"])
        self.assertEqual(status, 0)
        self.assertIn("Lab Goggles", buffer.getvalue())

    def test_bad_algorithm_is_nonzero(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            try:
                status = main(["sort", "--algorithm", "bogosort"])
            except SystemExit as exc:
                status = exc.code
        self.assertNotEqual(status, 0)


if __name__ == "__main__":
    unittest.main()
