#!/usr/bin/env python3
"""Unit tests for ArrayManager insert, delete, replace, and error paths."""

import unittest

from array_operations import (
    ARRAY_SIZE,
    ArrayManager,
    ArrayOperationError,
    EmptyArrayError,
    InvalidIndexError,
    InvalidValueError,
)


class ArrayManagerInitTests(unittest.TestCase):
    def test_default_size_is_15335(self) -> None:
        manager = ArrayManager()
        self.assertEqual(len(manager), ARRAY_SIZE)
        self.assertEqual(ARRAY_SIZE, 15335)

    def test_seed_is_deterministic(self) -> None:
        a = ArrayManager(size=50, seed=7)
        b = ArrayManager(size=50, seed=7)
        self.assertEqual(a.arr_nums, b.arr_nums)

    def test_custom_values(self) -> None:
        manager = ArrayManager(values=[10, 20, 30])
        self.assertEqual(manager.arr_nums, [10, 20, 30])

    def test_negative_size_raises(self) -> None:
        with self.assertRaises(InvalidValueError):
            ArrayManager(size=-3)


class InsertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = ArrayManager(values=[1, 2, 3, 4, 5])

    def test_insert_at_head(self) -> None:
        self.manager.insert(0, "H")
        self.assertEqual(self.manager.arr_nums[0], "H")
        self.assertEqual(len(self.manager), 6)

    def test_insert_at_end_appends(self) -> None:
        self.manager.insert(len(self.manager), "T")
        self.assertEqual(self.manager.arr_nums[-1], "T")

    def test_insert_negative_index(self) -> None:
        self.manager.insert(-1, "X")
        self.assertEqual(self.manager.arr_nums, [1, 2, 3, 4, "X", 5])

    def test_insert_out_of_range(self) -> None:
        with self.assertRaises(InvalidIndexError):
            self.manager.insert(99, "X")

    def test_insert_rejects_bool_index(self) -> None:
        with self.assertRaises(InvalidIndexError):
            self.manager.insert(True, "X")

    def test_insert_many(self) -> None:
        applied = self.manager.insert_many([(0, "A"), (2, "B")])
        self.assertEqual(applied, 2)
        self.assertEqual(self.manager.arr_nums[0], "A")
        self.assertEqual(self.manager.arr_nums[2], "B")


class DeleteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = ArrayManager(values=[10, 20, 30, 40, 50])

    def test_delete_middle(self) -> None:
        removed = self.manager.delete(2)
        self.assertEqual(removed, 30)
        self.assertEqual(self.manager.arr_nums, [10, 20, 40, 50])

    def test_delete_negative_index(self) -> None:
        removed = self.manager.delete(-1)
        self.assertEqual(removed, 50)
        self.assertEqual(self.manager.arr_nums[-1], 40)

    def test_delete_empty_raises(self) -> None:
        empty = ArrayManager(size=0)
        with self.assertRaises(EmptyArrayError):
            empty.delete(0)

    def test_delete_many_highest_first(self) -> None:
        removed = self.manager.delete_many([1, 3])
        self.assertEqual(removed, [40, 20])
        self.assertEqual(self.manager.arr_nums, [10, 30, 50])

    def test_delete_many_rejects_duplicates(self) -> None:
        with self.assertRaises(InvalidValueError):
            self.manager.delete_many([1, 1])


class ReplaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = ArrayManager(values=["a", "b", "c"])

    def test_replace_returns_previous(self) -> None:
        previous = self.manager.replace(1, "B")
        self.assertEqual(previous, "b")
        self.assertEqual(self.manager.arr_nums[1], "B")
        self.assertEqual(len(self.manager), 3)

    def test_replace_out_of_range(self) -> None:
        with self.assertRaises(InvalidIndexError):
            self.manager.replace(-4, "z")

    def test_replace_many(self) -> None:
        previous = self.manager.replace_many([(0, "A"), (2, "C")])
        self.assertEqual(previous, ["a", "c"])
        self.assertEqual(self.manager.arr_nums, ["A", "b", "C"])


class LargeArrayTests(unittest.TestCase):
    def test_mixed_operations_on_full_size_array(self) -> None:
        manager = ArrayManager(size=ARRAY_SIZE, seed=1)
        original_at_6999 = manager.arr_nums[6999]
        original_tail = manager.arr_nums[-1]

        manager.insert(0, "HEAD")
        manager.insert(ARRAY_SIZE, "NEAR-TAIL")
        previous = manager.replace(7000, 99999)
        removed_head = manager.delete(0)
        removed_tail = manager.delete(-1)

        self.assertEqual(removed_head, "HEAD")
        self.assertEqual(removed_tail, original_tail)
        self.assertEqual(previous, original_at_6999)
        self.assertEqual(manager.arr_nums[6999], 99999)
        self.assertEqual(manager.arr_nums[-1], "NEAR-TAIL")
        self.assertEqual(len(manager), ARRAY_SIZE)


class DemonstrationTests(unittest.TestCase):
    def test_walkthrough_completes(self) -> None:
        import io
        from contextlib import redirect_stdout

        from array_operations import demonstrate_operations

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = demonstrate_operations()
        output = buffer.getvalue()
        self.assertEqual(status, 0)
        self.assertIn("Initial arr_nums", output)
        self.assertIn("caught InvalidIndexError", output)
        self.assertNotIn("UNEXPECTED SUCCESS", output)


class ErrorHierarchyTests(unittest.TestCase):
    def test_custom_errors_are_array_operation_errors(self) -> None:
        self.assertTrue(issubclass(InvalidIndexError, ArrayOperationError))
        self.assertTrue(issubclass(InvalidValueError, ArrayOperationError))
        self.assertTrue(issubclass(EmptyArrayError, ArrayOperationError))


if __name__ == "__main__":
    unittest.main()
