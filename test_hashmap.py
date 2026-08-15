#!/usr/bin/env python3
"""Tests for the separate-chaining HashMap and ID-office demo."""

import io
import unittest
from contextlib import redirect_stdout

from hashmap import (
    HashMap,
    HashMapError,
    MissingKeyError,
    UnhashableKeyError,
    demonstrate_hashmap,
    main,
    seed_id_office,
)


class HashMapCoreTests(unittest.TestCase):
    def test_put_get_overwrite(self) -> None:
        table = HashMap()
        table.put("R1", "Maya")
        self.assertEqual(table.get("R1"), "Maya")
        table.put("R1", "Maya Chen")
        self.assertEqual(table["R1"], "Maya Chen")
        self.assertEqual(len(table), 1)

    def test_pop_and_contains(self) -> None:
        table = HashMap()
        table["a"] = 1
        table["b"] = 2
        self.assertTrue("a" in table)
        self.assertEqual(table.pop("a"), 1)
        self.assertFalse("a" in table)
        with self.assertRaises(MissingKeyError):
            table.pop("a")

    def test_missing_get_default(self) -> None:
        table = HashMap()
        self.assertIsNone(table.get("missing"))
        self.assertEqual(table.get("missing", "n/a"), "n/a")
        with self.assertRaises(MissingKeyError):
            _ = table["missing"]

    def test_unhashable_key(self) -> None:
        table = HashMap()
        with self.assertRaises(UnhashableKeyError):
            table.put(["sid"], "x")

    def test_resize_keeps_all_keys(self) -> None:
        table = HashMap(capacity=4, load_factor=0.75)
        for number in range(50):
            table[f"k{number}"] = number
        self.assertGreater(table._capacity, 4)
        self.assertEqual(len(table), 50)
        self.assertEqual(table["k42"], 42)
        self.assertEqual(set(table), {f"k{n}" for n in range(50)})

    def test_collision_chain_can_hold_several_keys(self) -> None:
        table = HashMap(capacity=2, load_factor=1.0)
        for number in range(4):
            table[number] = str(number)
        self.assertEqual(len(table), 4)
        self.assertTrue(max(table.bucket_lengths()) >= 1)
        for number in range(4):
            self.assertEqual(table[number], str(number))

    def test_bad_capacity(self) -> None:
        with self.assertRaises(HashMapError):
            HashMap(capacity=0)


class IdOfficeTests(unittest.TestCase):
    def test_seed_lookup(self) -> None:
        office = seed_id_office()
        self.assertEqual(office["R1002341"]["name"], "Maya Chen")
        self.assertIn("R1008810", office)

    def test_cli_lookup(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = main(["lookup", "R1001107"])
        self.assertEqual(status, 0)
        self.assertIn("Priya Shah", buffer.getvalue())

    def test_demo_completes(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = demonstrate_hashmap()
        self.assertEqual(status, 0)
        output = buffer.getvalue()
        self.assertIn("Campus ID tap", output)
        self.assertNotIn("UNEXPECTED SUCCESS", output)


if __name__ == "__main__":
    unittest.main()
