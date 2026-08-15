#!/usr/bin/env python3
"""Unit tests for the binary tree ADT, CLI commands, and interactive REPL."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from tree_operations import (
    TREE_SIZE,
    CommandParseError,
    EmptyTreeError,
    InvalidIndexError,
    InvalidValueError,
    OccupiedSlotError,
    TreeManager,
    TreeOperationError,
    handle_repl_line,
    main,
    run_interactive,
)


class TreeInitTests(unittest.TestCase):
    def test_default_size_is_15335(self) -> None:
        manager = TreeManager()
        self.assertEqual(len(manager), TREE_SIZE)
        self.assertEqual(TREE_SIZE, 15335)
        self.assertEqual(manager.height(), 13)

    def test_complete_layout(self) -> None:
        manager = TreeManager(values=[4, 2, 6, 1, 3, 5, 7])
        self.assertEqual(manager.level_order(), [4, 2, 6, 1, 3, 5, 7])
        self.assertEqual(manager.inorder(), [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(manager.get(0), 4)
        self.assertEqual(manager.get(-1), 7)

    def test_seed_is_deterministic(self) -> None:
        a = TreeManager(size=50, seed=7)
        b = TreeManager(size=50, seed=7)
        self.assertEqual(a.level_order(), b.level_order())

    def test_negative_and_bool_size_raise(self) -> None:
        with self.assertRaises(InvalidValueError):
            TreeManager(size=-3)
        with self.assertRaises(InvalidValueError):
            TreeManager(size=True)


class InsertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = TreeManager(values=[4, 2, 6])

    def test_append_keeps_tree_complete(self) -> None:
        index = self.manager.append(1)
        self.assertEqual(index, 3)
        self.assertEqual(self.manager.level_order(), [4, 2, 6, 1])

    def test_insert_left_and_right_on_leaf(self) -> None:
        left_index = self.manager.insert_left(1, 1)
        right_index = self.manager.insert_right(1, 3)
        self.assertEqual(left_index, 3)
        self.assertEqual(right_index, 4)
        self.assertEqual(self.manager.level_order(), [4, 2, 6, 1, 3])

    def test_insert_prefers_left_then_right(self) -> None:
        self.manager.insert(2, "L")
        self.manager.insert(2, "R")
        self.assertEqual(self.manager.level_order(), [4, 2, 6, "L", "R"])
        with self.assertRaises(OccupiedSlotError):
            self.manager.insert(2, "X")

    def test_insert_on_empty_tree(self) -> None:
        empty = TreeManager(size=0)
        self.assertEqual(empty.insert(0, "root"), 0)
        self.assertEqual(empty.get(0), "root")
        with self.assertRaises(InvalidIndexError):
            TreeManager(size=0).insert(5, "x")

    def test_occupied_left_child(self) -> None:
        with self.assertRaises(OccupiedSlotError):
            self.manager.insert_left(0, "x")

    def test_insert_many_rolls_back(self) -> None:
        original = self.manager.level_order()
        with self.assertRaises(OccupiedSlotError):
            self.manager.insert_many([(1, "A"), (0, "B")])
        self.assertEqual(self.manager.level_order(), original)


class DeleteTests(unittest.TestCase):
    def test_delete_leaf(self) -> None:
        manager = TreeManager(values=[4, 2, 6, 1, 3, 5, 7])
        removed = manager.delete(-1)
        self.assertEqual(removed, 7)
        self.assertEqual(manager.level_order(), [4, 2, 6, 1, 3, 5])

    def test_delete_one_child(self) -> None:
        manager = TreeManager(values=[4, 2, 6])
        manager.insert_left(1, 1)
        removed = manager.delete(1)
        self.assertEqual(removed, 2)
        self.assertEqual(manager.level_order(), [4, 1, 6])

    def test_delete_two_children_uses_inorder_successor(self) -> None:
        manager = TreeManager(values=[4, 2, 6, 1, 3, 5, 7])
        removed = manager.delete(0)
        self.assertEqual(removed, 4)
        self.assertEqual(manager.level_order(), [5, 2, 6, 1, 3, 7])
        self.assertEqual(manager.inorder(), [1, 2, 3, 5, 6, 7])

    def test_delete_internal_with_two_children(self) -> None:
        manager = TreeManager(values=[4, 2, 6, 1, 3, 5, 7])
        removed = manager.delete(1)
        self.assertEqual(removed, 2)
        self.assertEqual(manager.level_order(), [4, 3, 6, 1, 5, 7])

    def test_delete_empty_raises(self) -> None:
        with self.assertRaises(EmptyTreeError):
            TreeManager(size=0).delete(0)

    def test_delete_subtree(self) -> None:
        manager = TreeManager(values=[4, 2, 6, 1, 3, 5, 7])
        removed = manager.delete_subtree(1)
        self.assertEqual(removed, 2)
        self.assertEqual(manager.level_order(), [4, 6, 5, 7])
        self.assertEqual(len(manager), 4)

    def test_delete_many_deepest_first(self) -> None:
        manager = TreeManager(values=[4, 2, 6, 1, 3, 5, 7])
        removed = manager.delete_many([3, 4])
        self.assertEqual(sorted(removed), [1, 3])
        self.assertEqual(len(manager), 5)


class ReplaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = TreeManager(values=["a", "b", "c"])

    def test_replace_returns_previous(self) -> None:
        previous = self.manager.replace(0, "A")
        self.assertEqual(previous, "a")
        self.assertEqual(self.manager.get(0), "A")
        self.assertEqual(len(self.manager), 3)

    def test_replace_out_of_range(self) -> None:
        with self.assertRaises(InvalidIndexError):
            self.manager.replace(9, "z")

    def test_get_and_find(self) -> None:
        self.assertEqual(self.manager.get(1), "b")
        self.assertEqual(self.manager.find("c"), 2)
        with self.assertRaises(InvalidValueError):
            self.manager.find("missing")

    def test_replace_many_rejects_bad_pair(self) -> None:
        original = self.manager.level_order()
        with self.assertRaises(InvalidValueError):
            self.manager.replace_many([(0, "A"), (1,)])
        self.assertEqual(self.manager.level_order(), original)


class LargeTreeTests(unittest.TestCase):
    def test_mixed_operations_on_full_size_tree(self) -> None:
        manager = TreeManager(size=TREE_SIZE, seed=1)
        original_root = manager.get(0)
        original_mid = manager.get(7000)

        appended = manager.append("LEAF")
        self.assertEqual(appended, TREE_SIZE)
        previous = manager.replace(7000, 99999)
        self.assertEqual(previous, original_mid)
        removed_leaf = manager.delete(-1)
        self.assertEqual(removed_leaf, "LEAF")
        removed_root = manager.delete(0)
        self.assertEqual(removed_root, original_root)
        self.assertIn(99999, manager.level_order())
        self.assertEqual(len(manager), TREE_SIZE - 1)


class DemonstrationTests(unittest.TestCase):
    def test_walkthrough_completes(self) -> None:
        from tree_operations import demonstrate_operations

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = demonstrate_operations()
        output = buffer.getvalue()
        self.assertEqual(status, 0)
        self.assertIn("Initial tree_nums", output)
        self.assertIn("caught", output)
        self.assertNotIn("UNEXPECTED SUCCESS", output)


class ReplTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = TreeManager(values=[10, 20, 30])

    def test_insert_replace_delete_and_quit(self) -> None:
        message, done = handle_repl_line(self.manager, "insert 1 15")
        self.assertFalse(done)
        self.assertIn("15", message)
        message, done = handle_repl_line(self.manager, "replace 0 99")
        self.assertIn("99", message)
        message, done = handle_repl_line(self.manager, "delete -1")
        self.assertIn("15", message)
        message, done = handle_repl_line(self.manager, "quit")
        self.assertTrue(done)
        self.assertEqual(self.manager.level_order(), [99, 20, 30])

    def test_unknown_command(self) -> None:
        with self.assertRaises(CommandParseError):
            handle_repl_line(self.manager, "explode 1")

    def test_run_interactive(self) -> None:
        commands = iter(["append TAIL", "quit"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = run_interactive(
                self.manager, input_fn=lambda _prompt: next(commands)
            )
        self.assertEqual(status, 0)
        self.assertEqual(self.manager.level_order()[-1], "TAIL")
        self.assertIn("Goodbye.", buffer.getvalue())


class CliTests(unittest.TestCase):
    def test_append_subcommand(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = main(["--values", "1,2,3", "append", "4"])
        self.assertEqual(status, 0)
        self.assertIn("appended 4 at 3", buffer.getvalue())

    def test_delete_out_of_range_is_nonzero(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            status = main(["--size", "3", "delete", "99"])
        self.assertEqual(status, 1)
        self.assertIn("InvalidIndexError", err.getvalue())

    def test_get(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = main(["--values", "1,2,3", "get", "0"])
        self.assertEqual(status, 0)
        self.assertIn("tree_nums[0] = 1", buffer.getvalue())


class ErrorHierarchyTests(unittest.TestCase):
    def test_custom_errors_are_tree_operation_errors(self) -> None:
        self.assertTrue(issubclass(InvalidIndexError, TreeOperationError))
        self.assertTrue(issubclass(OccupiedSlotError, TreeOperationError))
        self.assertTrue(issubclass(EmptyTreeError, TreeOperationError))


if __name__ == "__main__":
    unittest.main()
