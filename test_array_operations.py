#!/usr/bin/env python3
"""Unit tests for ArrayManager, CLI commands, and the interactive REPL."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from array_operations import (
    ARRAY_SIZE,
    ArrayManager,
    ArrayOperationError,
    CommandParseError,
    EmptyArrayError,
    InvalidIndexError,
    InvalidValueError,
    handle_repl_line,
    main,
    parse_cli_value,
    run_interactive,
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

    def test_bool_size_raises(self) -> None:
        with self.assertRaises(InvalidValueError):
            ArrayManager(size=True)


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

    def test_insert_many_rolls_back_on_failure(self) -> None:
        original = list(self.manager.arr_nums)
        with self.assertRaises(InvalidValueError):
            self.manager.insert_many([(0, "A"), (0,)])
        self.assertEqual(self.manager.arr_nums, original)

    def test_append_returns_new_index(self) -> None:
        index = self.manager.append("T")
        self.assertEqual(index, 5)
        self.assertEqual(self.manager.arr_nums[-1], "T")


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

    def test_get_and_find(self) -> None:
        self.assertEqual(self.manager.get(1), "b")
        self.assertEqual(self.manager.find("c"), 2)
        with self.assertRaises(InvalidValueError):
            self.manager.find("missing")

    def test_replace_many_rejects_bad_pair_before_mutating(self) -> None:
        original = list(self.manager.arr_nums)
        with self.assertRaises(InvalidValueError):
            self.manager.replace_many([(0, "A"), (1,)])
        self.assertEqual(self.manager.arr_nums, original)


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
        self.assertTrue(issubclass(CommandParseError, ArrayOperationError))


class ParseValueTests(unittest.TestCase):
    def test_parses_int_float_bool_none_and_text(self) -> None:
        self.assertEqual(parse_cli_value("42"), 42)
        self.assertEqual(parse_cli_value("-3"), -3)
        self.assertEqual(parse_cli_value("3.5"), 3.5)
        self.assertEqual(parse_cli_value("true"), True)
        self.assertEqual(parse_cli_value("NONE"), None)
        self.assertEqual(parse_cli_value("HEAD"), "HEAD")


class ReplTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = ArrayManager(values=[10, 20, 30])

    def test_insert_delete_replace_and_quit(self) -> None:
        message, done = handle_repl_line(self.manager, "insert 0 HEAD")
        self.assertFalse(done)
        self.assertIn("HEAD", message)
        message, done = handle_repl_line(self.manager, "replace 1 99")
        self.assertIn("99", message)
        message, done = handle_repl_line(self.manager, "delete -1")
        self.assertIn("30", message)
        message, done = handle_repl_line(self.manager, "quit")
        self.assertTrue(done)
        self.assertEqual(self.manager.arr_nums, ["HEAD", 99, 20])

    def test_unknown_command(self) -> None:
        with self.assertRaises(CommandParseError):
            handle_repl_line(self.manager, "explode 1")

    def test_run_interactive_reads_commands(self) -> None:
        commands = iter(["append TAIL", "quit"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = run_interactive(
                self.manager, input_fn=lambda _prompt: next(commands)
            )
        self.assertEqual(status, 0)
        self.assertEqual(self.manager.arr_nums[-1], "TAIL")
        self.assertIn("Goodbye.", buffer.getvalue())


class CliTests(unittest.TestCase):
    def test_insert_subcommand(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = main(["--size", "5", "--seed", "1", "insert", "0", "HEAD"])
        self.assertEqual(status, 0)
        self.assertIn("inserted 'HEAD' at 0", buffer.getvalue())

    def test_delete_out_of_range_is_nonzero(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            status = main(["--size", "3", "delete", "99"])
        self.assertEqual(status, 1)
        self.assertIn("InvalidIndexError", err.getvalue())

    def test_show_and_get(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = main(["--values", "1,2,3", "get", "1"])
        self.assertEqual(status, 0)
        self.assertIn("arr_nums[1] = 2", buffer.getvalue())

    def test_demo_command_completes(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = main(["demo"])
        self.assertEqual(status, 0)
        self.assertIn("Initial arr_nums", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
