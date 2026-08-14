#!/usr/bin/env python3
"""
Array mutation application for arr_nums (15,335 elements).

This program builds a large list named arr_nums and lets you insert,
delete, and replace values at arbitrary index locations. Indexes are
checked before every mutation. Failures raise typed exceptions instead
of crashing with a raw IndexError.

Modes:
    python3 array_operations.py                 # scripted demonstration
    python3 array_operations.py demo
    python3 array_operations.py interactive     # menu / REPL application
    python3 array_operations.py insert 0 HEAD
    python3 array_operations.py delete -- -1
    python3 array_operations.py replace 100 42
    python3 array_operations.py get 0
    python3 array_operations.py show
    python3 array_operations.py append 99
    python3 array_operations.py find 654

Tests:
    python3 -m unittest test_array_operations.py -v
"""

from __future__ import annotations

import argparse
import random
import shlex
import sys
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Iterator, List, Optional, Sequence, Tuple


ARRAY_SIZE = 15335

HELP_TEXT = """
Commands (interactive mode)
---------------------------
  help                         Show this help text
  length                       Print the current length of arr_nums
  show [start] [count]         Print a window of values (default 0 10)
  get INDEX                    Print the value at INDEX
  insert INDEX VALUE           Insert VALUE so it occupies INDEX
  append VALUE                 Insert VALUE at the end
  delete INDEX                 Remove and print the value at INDEX
  replace INDEX VALUE          Overwrite INDEX and print the old value
  find VALUE                   Print the first index of VALUE
  history [count]              Print recent mutation history (default 12)
  demo                         Run the scripted demonstration on a copy
  quit                         Exit interactive mode

Negative indexes count from the end. Insert also accepts INDEX equal to
the current length, which appends. Values that look like integers or
floats are stored as numbers; everything else is kept as text.
""".strip()


class ArrayOperationError(Exception):
    """
    Base exception for every arr_nums mutation failure.

    Catch this type when a caller wants to treat insert, delete, and
    replace errors as a single family of problems.
    """


class InvalidIndexError(ArrayOperationError, IndexError):
    """Raised when an index is not a valid integer position in arr_nums."""


class InvalidValueError(ArrayOperationError, ValueError):
    """Raised when a value or count argument cannot be used as requested."""


class EmptyArrayError(ArrayOperationError):
    """Raised when a delete, replace, or get is attempted on an empty array."""


class CommandParseError(ArrayOperationError):
    """Raised when an interactive or CLI command cannot be parsed."""


def parse_cli_value(raw: str) -> Any:
    """
    Convert a user-supplied token into a stored array value.

    Integer and float literals become numbers. The words true / false /
    none (any case) become bool or None. Every other token stays a str.
    """
    if not isinstance(raw, str):
        raise InvalidValueError(
            f"value token must be a string, got {type(raw).__name__}"
        )
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"none", "null"}:
        return None
    try:
        return int(raw, 10)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def parse_index_token(raw: str) -> int:
    """Parse a decimal index token, including negative indexes."""
    if not isinstance(raw, str):
        raise InvalidIndexError(
            f"index must be text that looks like an int, got {type(raw).__name__}"
        )
    try:
        return int(raw, 10)
    except ValueError as exc:
        raise InvalidIndexError(
            f"index must be an int, got {raw!r}"
        ) from exc


class ArrayManager:
    """
    Manage a mutable list named arr_nums and apply guarded mutations.

    Python lists already support insert, pop, and item assignment. This
    wrapper adds:
      * bounds and type checks before each mutation
      * a small operation history for later inspection
      * helpers for bulk insert / delete / replace work
      * atomic bulk updates that roll back if any step fails
    """

    def __init__(
        self,
        size: int = ARRAY_SIZE,
        seed: Optional[int] = None,
        values: Optional[Iterable[Any]] = None,
    ) -> None:
        """
        Build arr_nums.

        If `values` is given, those items become the starting array.
        Otherwise the array is filled with `size` deterministic integers
        in the range [0, 999] using `seed` (default 42).
        """
        if values is not None:
            self.arr_nums: List[Any] = list(values)
        else:
            if isinstance(size, bool) or not isinstance(size, int):
                raise InvalidValueError(
                    f"size must be an integer, got {type(size).__name__}"
                )
            if size < 0:
                raise InvalidValueError(f"size must be >= 0, got {size}")
            rng = random.Random(42 if seed is None else seed)
            self.arr_nums = [rng.randint(0, 999) for _ in range(size)]

        self.history: List[str] = [
            f"initialized arr_nums with {len(self.arr_nums)} element(s)"
        ]

    def __len__(self) -> int:
        return len(self.arr_nums)

    def __repr__(self) -> str:
        preview = self.arr_nums[:8]
        suffix = "..." if len(self.arr_nums) > 8 else ""
        return (
            f"ArrayManager(length={len(self.arr_nums)}, "
            f"preview={preview}{suffix})"
        )

    def _require_int(self, name: str, value: Any) -> int:
        """
        Accept only real integers for indexes and counts.

        bool is a subclass of int in Python, so True/False are rejected
        explicitly to avoid treating them as 1 and 0.
        """
        error_cls: type = (
            InvalidIndexError if name in {"index", "start"} else InvalidValueError
        )
        if isinstance(value, bool) or not isinstance(value, int):
            raise error_cls(
                f"{name} must be an int, got {type(value).__name__}: {value!r}"
            )
        return value

    def _normalize_index(
        self,
        index: Any,
        *,
        allow_end: bool = False,
        operation: str = "access",
    ) -> int:
        """
        Convert a caller index into a non-negative list index.

        Negative indexes count from the end, matching list semantics.
        When allow_end is True (insert only), index == len(arr_nums) is
        valid and means "append at the end".
        """
        index = self._require_int("index", index)
        length = len(self.arr_nums)
        upper = length if allow_end else length - 1

        if length == 0 and not allow_end:
            raise EmptyArrayError(
                f"cannot {operation}: arr_nums is empty"
            )

        if index < 0:
            index += length

        if allow_end:
            if index < 0 or index > length:
                raise InvalidIndexError(
                    f"insert index {index} is out of range for length {length}; "
                    f"valid range is 0..{length} (inclusive end)"
                )
        else:
            if length == 0 or index < 0 or index > upper:
                raise InvalidIndexError(
                    f"{operation} index is out of range for length {length}; "
                    f"valid range is 0..{max(upper, 0)}"
                )
        return index

    @contextmanager
    def _atomic(self) -> Iterator[None]:
        """
        Restore arr_nums and history if the wrapped bulk operation fails.

        Single-item insert / delete / replace stay eager. Bulk helpers
        should either fully apply or leave the array unchanged.
        """
        backup_nums = self.arr_nums[:]
        backup_hist = len(self.history)
        try:
            yield
        except Exception:
            self.arr_nums = backup_nums
            del self.history[backup_hist:]
            raise

    def get(self, index: Any) -> Any:
        """Return the value at `index` without changing arr_nums."""
        try:
            normalized = self._normalize_index(index, operation="get")
            return self.arr_nums[normalized]
        except ArrayOperationError:
            raise
        except Exception as exc:
            raise ArrayOperationError(
                f"unexpected failure during get at {index!r}: {exc}"
            ) from exc

    def append(self, value: Any) -> int:
        """
        Insert `value` at the end of arr_nums.

        Returns the index where the value was stored.
        """
        index = len(self.arr_nums)
        self.insert(index, value)
        return index

    def find(self, value: Any) -> int:
        """Return the first index of `value`, or raise InvalidValueError."""
        try:
            return self.arr_nums.index(value)
        except ValueError as exc:
            raise InvalidValueError(
                f"value {value!r} not found in arr_nums"
            ) from exc

    def insert(self, index: Any, value: Any) -> None:
        """
        Insert `value` so it occupies `index` after the call.

        Valid indexes are 0 .. len(arr_nums) inclusive. Passing
        len(arr_nums) appends. Existing items from `index` onward shift
        one position to the right.
        """
        try:
            normalized = self._normalize_index(
                index, allow_end=True, operation="insert"
            )
            self.arr_nums.insert(normalized, value)
            self.history.append(
                f"insert value={value!r} at index={normalized} "
                f"(length now {len(self.arr_nums)})"
            )
        except ArrayOperationError:
            raise
        except Exception as exc:
            raise ArrayOperationError(
                f"unexpected failure during insert at {index!r}: {exc}"
            ) from exc

    def delete(self, index: Any) -> Any:
        """
        Remove and return the item at `index`.

        Items after `index` shift one position to the left. Valid
        indexes are 0 .. len(arr_nums)-1, including negative indexes.
        """
        try:
            if len(self.arr_nums) == 0:
                raise EmptyArrayError("cannot delete: arr_nums is empty")
            normalized = self._normalize_index(index, operation="delete")
            removed = self.arr_nums.pop(normalized)
            self.history.append(
                f"delete index={normalized} removed={removed!r} "
                f"(length now {len(self.arr_nums)})"
            )
            return removed
        except ArrayOperationError:
            raise
        except Exception as exc:
            raise ArrayOperationError(
                f"unexpected failure during delete at {index!r}: {exc}"
            ) from exc

    def replace(self, index: Any, value: Any) -> Any:
        """
        Overwrite the item at `index` and return the previous value.

        Length is unchanged. Valid indexes are 0 .. len(arr_nums)-1.
        """
        try:
            if len(self.arr_nums) == 0:
                raise EmptyArrayError("cannot replace: arr_nums is empty")
            normalized = self._normalize_index(index, operation="replace")
            previous = self.arr_nums[normalized]
            self.arr_nums[normalized] = value
            self.history.append(
                f"replace index={normalized} {previous!r} -> {value!r}"
            )
            return previous
        except ArrayOperationError:
            raise
        except Exception as exc:
            raise ArrayOperationError(
                f"unexpected failure during replace at {index!r}: {exc}"
            ) from exc

    def insert_many(self, pairs: Sequence[Tuple[Any, Any]]) -> int:
        """
        Insert several (index, value) pairs in the given order.

        Because each insert changes later indexes, callers should pass
        indexes relative to the array state just before that pair runs.
        If any pair fails, earlier inserts in this call are rolled back.
        Returns the number of successful inserts.
        """
        if not isinstance(pairs, (list, tuple)):
            raise InvalidValueError(
                "insert_many expects a sequence of (index, value) pairs"
            )
        with self._atomic():
            applied = 0
            for item in pairs:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    raise InvalidValueError(
                        f"each insert pair must be (index, value), got {item!r}"
                    )
                self.insert(item[0], item[1])
                applied += 1
            return applied

    def delete_many(self, indexes: Sequence[Any]) -> List[Any]:
        """
        Delete several indexes from highest to lowest.

        Sorting descending avoids shifting still-pending indexes. Duplicate
        indexes after that sort are rejected so a caller cannot silently
        delete the wrong neighbor. The array is unchanged if validation
        fails.
        """
        if not isinstance(indexes, (list, tuple)):
            raise InvalidValueError("delete_many expects a sequence of indexes")
        if len(indexes) == 0:
            return []

        normalized = [
            self._normalize_index(index, operation="delete") for index in indexes
        ]
        unique_sorted = sorted(set(normalized), reverse=True)
        if len(unique_sorted) != len(normalized):
            raise InvalidValueError(
                f"delete_many received duplicate indexes: {indexes!r}"
            )

        with self._atomic():
            removed: List[Any] = []
            for index in unique_sorted:
                removed.append(self.delete(index))
            return removed

    def replace_many(self, pairs: Sequence[Tuple[Any, Any]]) -> List[Any]:
        """Replace several (index, value) pairs; return previous values."""
        if not isinstance(pairs, (list, tuple)):
            raise InvalidValueError(
                "replace_many expects a sequence of (index, value) pairs"
            )
        prepared: List[Tuple[int, Any]] = []
        for item in pairs:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise InvalidValueError(
                    f"each replace pair must be (index, value), got {item!r}"
                )
            prepared.append(
                (self._normalize_index(item[0], operation="replace"), item[1])
            )
        with self._atomic():
            previous_values: List[Any] = []
            for index, value in prepared:
                previous_values.append(self.replace(index, value))
            return previous_values

    def snapshot(self, start: int = 0, count: int = 10) -> List[Any]:
        """Return a copy of a short window of arr_nums for display."""
        start = self._require_int("start", start)
        count = self._require_int("count", count)
        if start < 0:
            raise InvalidIndexError(f"snapshot start must be >= 0, got {start}")
        if count < 0:
            raise InvalidValueError(f"snapshot count must be >= 0, got {count}")
        return list(self.arr_nums[start : start + count])


def _print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _run_step(label: str, action: Callable[[], None]) -> bool:
    """
    Execute one demonstration step and keep going if it fails.

    Returns True when the step succeeded. ArrayOperationError and any
    unexpected exception are printed instead of aborting the walkthrough.
    """
    try:
        action()
        return True
    except ArrayOperationError as exc:
        print(f"operation error during {label}: {type(exc).__name__}: {exc}")
        return False
    except Exception as exc:
        print(f"unexpected error during {label}: {type(exc).__name__}: {exc}")
        return False


def demonstrate_operations(manager: Optional[ArrayManager] = None) -> int:
    """
    Run a scripted walkthrough of insert, delete, and replace.

    Successful operations and intentionally invalid calls are both shown
    so the exception paths are exercised in a normal run. Returns 0 when
    the demonstration finishes without an unexpected crash.
    """
    try:
        if manager is None:
            manager = ArrayManager(size=ARRAY_SIZE, seed=42)
    except ArrayOperationError as exc:
        print(f"Failed to create arr_nums: {exc}", file=sys.stderr)
        return 1

    _print_section("1. Initial arr_nums")
    print(f"length: {len(manager)}")
    print(f"first 10 values: {manager.snapshot(0, 10)}")
    print(f"last 10 values:  {manager.arr_nums[-10:]}")
    print(f"object: {manager}")

    _print_section("2. Insert at several positions")
    insert_plan = [
        (0, "HEAD"),
        (1, "NEAR-HEAD"),
        (len(manager) // 2, "MID"),
        (len(manager), "TAIL"),
        (-1, "BEFORE-LAST"),
    ]
    for index, value in insert_plan:
        def _insert(index=index, value=value) -> None:
            before = len(manager)
            manager.insert(index, value)
            print(
                f"inserted {value!r:12} using index {index!r:>6} "
                f"-> length {before} to {len(manager)}"
            )

        _run_step(f"insert {value!r} at {index!r}", _insert)

    _print_section("3. Replace at several positions")
    replace_plan = [
        (0, "REPLACED-HEAD"),
        (100, 100001),
        (5000, 500001),
        (len(manager) - 1, "REPLACED-TAIL"),
        (-2, "REPLACED-NEAR-TAIL"),
    ]
    for index, value in replace_plan:
        def _replace(index=index, value=value) -> None:
            previous = manager.replace(index, value)
            print(
                f"replaced index {index!r:>6}: {previous!r} -> {value!r}"
            )

        _run_step(f"replace at {index!r}", _replace)

    _print_section("4. Delete at several positions")
    """
    Delete indexes are resolved at the moment of each call. Using a
    precomputed len(arr_nums)-1 would go stale after earlier deletes
    shift the tail left.
    """
    delete_plan = [0, 50, 1000, "LAST", -3]
    for requested in delete_plan:
        def _delete(requested=requested) -> None:
            index = len(manager) - 1 if requested == "LAST" else requested
            removed = manager.delete(index)
            print(
                f"deleted index {index!r:>6}: removed {removed!r}; "
                f"length now {len(manager)}"
            )

        _run_step(f"delete {requested!r}", _delete)

    _print_section("5. Bulk insert / replace / delete")

    def _bulk() -> None:
        bulk_inserts = [(10, "BULK-A"), (20, "BULK-B"), (30, "BULK-C")]
        print(f"bulk inserts applied: {manager.insert_many(bulk_inserts)}")
        previous = manager.replace_many([(10, "BULK-A*"), (20, "BULK-B*")])
        print(f"bulk replace previous values: {previous}")
        removed = manager.delete_many([10, 20, len(manager) - 1])
        print(f"bulk delete removed: {removed}")
        print(f"length after bulk work: {len(manager)}")

    _run_step("bulk mutations", _bulk)

    _print_section("6. Exception handling (expected failures)")
    error_cases = [
        ("insert beyond end", lambda: manager.insert(len(manager) + 5, "X")),
        ("insert with a float index", lambda: manager.insert(3.14, "X")),
        ("insert with a bool index", lambda: manager.insert(True, "X")),
        ("delete far past the end", lambda: manager.delete(10**7)),
        ("delete with a string index", lambda: manager.delete("first")),
        ("replace with None as index", lambda: manager.replace(None, 1)),
        ("replace on empty array", lambda: ArrayManager(size=0).replace(0, 1)),
        ("delete on empty array", lambda: ArrayManager(size=0).delete(0)),
        ("delete_many duplicates", lambda: manager.delete_many([1, 1])),
        ("insert_many bad pair", lambda: manager.insert_many([(0,)])),
        ("negative size", lambda: ArrayManager(size=-1)),
    ]
    for label, action in error_cases:
        try:
            action()
            print(f"UNEXPECTED SUCCESS: {label}")
        except ArrayOperationError as exc:
            print(f"caught {type(exc).__name__} for {label}: {exc}")
        except Exception as exc:
            print(f"caught unexpected {type(exc).__name__} for {label}: {exc}")

    _print_section("7. Final state")
    print(f"final length: {len(manager)}")
    print(f"first 10 values: {manager.snapshot(0, 10)}")
    print(f"history entries: {len(manager.history)}")
    print("last 8 history lines:")
    for line in manager.history[-8:]:
        print(f"  - {line}")

    return 0


def handle_repl_line(manager: ArrayManager, line: str) -> Tuple[str, bool]:
    """
    Execute one interactive command against `manager`.

    Returns (message, should_quit). Blank lines produce an empty message
    and do not exit. Unknown commands raise CommandParseError.
    """
    stripped = line.strip()
    if not stripped:
        return "", False

    try:
        tokens = shlex.split(stripped)
    except ValueError as exc:
        raise CommandParseError(f"could not parse command: {exc}") from exc

    command = tokens[0].lower()
    args = tokens[1:]

    if command in {"quit", "exit", "q"}:
        return "Goodbye.", True
    if command in {"help", "?"}:
        return HELP_TEXT, False
    if command in {"length", "len"}:
        return f"length: {len(manager)}", False
    if command == "show":
        start = parse_index_token(args[0]) if len(args) >= 1 else 0
        count = parse_index_token(args[1]) if len(args) >= 2 else 10
        window = manager.snapshot(start, count)
        return f"arr_nums[{start}:{start + count}] ({len(window)} item(s)): {window}", False
    if command == "get":
        if len(args) != 1:
            raise CommandParseError("usage: get INDEX")
        index = parse_index_token(args[0])
        return f"arr_nums[{index}] = {manager.get(index)!r}", False
    if command == "insert":
        if len(args) < 2:
            raise CommandParseError("usage: insert INDEX VALUE")
        index = parse_index_token(args[0])
        value = parse_cli_value(" ".join(args[1:]))
        manager.insert(index, value)
        return (
            f"inserted {value!r} at {index}; length is now {len(manager)}"
        ), False
    if command == "append":
        if len(args) < 1:
            raise CommandParseError("usage: append VALUE")
        value = parse_cli_value(" ".join(args))
        index = manager.append(value)
        return f"appended {value!r} at {index}; length is now {len(manager)}", False
    if command == "delete":
        if len(args) != 1:
            raise CommandParseError("usage: delete INDEX")
        index = parse_index_token(args[0])
        removed = manager.delete(index)
        return (
            f"deleted {removed!r} from {index}; length is now {len(manager)}"
        ), False
    if command == "replace":
        if len(args) < 2:
            raise CommandParseError("usage: replace INDEX VALUE")
        index = parse_index_token(args[0])
        value = parse_cli_value(" ".join(args[1:]))
        previous = manager.replace(index, value)
        return f"replaced {previous!r} with {value!r} at {index}", False
    if command == "find":
        if len(args) < 1:
            raise CommandParseError("usage: find VALUE")
        value = parse_cli_value(" ".join(args))
        index = manager.find(value)
        return f"{value!r} first occurs at index {index}", False
    if command == "history":
        count = parse_index_token(args[0]) if args else 12
        if count < 0:
            raise InvalidValueError(f"history count must be >= 0, got {count}")
        lines = manager.history[-count:]
        if not lines:
            return "(history is empty)", False
        return "\n".join(f"  - {entry}" for entry in lines), False
    if command == "demo":
        demo_manager = ArrayManager(values=list(manager.arr_nums))
        demonstrate_operations(demo_manager)
        return "demonstration finished (interactive array was not changed).", False

    raise CommandParseError(
        f"unknown command {command!r}; type 'help' for a list"
    )


def run_interactive(
    manager: ArrayManager,
    input_fn: Callable[[str], str] = input,
) -> int:
    """
    Read commands until the user quits or stdin closes.

    `input_fn` is injectable so tests can drive the loop without a
    real terminal. Returns 0 on a clean exit.
    """
    print("arr_nums interactive mode. Type 'help' for commands, 'quit' to exit.")
    print(f"starting length: {len(manager)}")
    while True:
        try:
            line = input_fn(f"arr_nums[{len(manager)}]> ")
        except EOFError:
            print()
            print("Goodbye.")
            return 0
        except KeyboardInterrupt:
            print()
            print("Interrupted. Type 'quit' to exit.")
            continue
        try:
            message, should_quit = handle_repl_line(manager, line)
        except ArrayOperationError as exc:
            print(f"{type(exc).__name__}: {exc}")
            continue
        except Exception as exc:
            print(f"unexpected {type(exc).__name__}: {exc}")
            continue
        if message:
            print(message)
        if should_quit:
            return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level CLI parser, including mutation subcommands."""
    parser = argparse.ArgumentParser(
        description=(
            "Insert, delete, and replace values in arr_nums, "
            "a list of 15,335 elements by default."
        )
    )
    parser.add_argument(
        "--size",
        type=int,
        default=ARRAY_SIZE,
        help=f"initial length when --values is not set (default {ARRAY_SIZE})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for the generated starting values (default 42)",
    )
    parser.add_argument(
        "--values",
        metavar="ITEMS",
        help="comma-separated starting values; overrides --size",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("demo", help="run the scripted insert/delete/replace walkthrough")
    sub.add_parser("interactive", help="open the command prompt")

    insert_parser = sub.add_parser("insert", help="insert VALUE at INDEX")
    insert_parser.add_argument("index", help="index (use -- before a negative index)")
    insert_parser.add_argument("value", nargs="+", help="value to insert")

    delete_parser = sub.add_parser("delete", help="delete the item at INDEX")
    delete_parser.add_argument("index", help="index (use -- before a negative index)")

    replace_parser = sub.add_parser("replace", help="replace INDEX with VALUE")
    replace_parser.add_argument("index", help="index (use -- before a negative index)")
    replace_parser.add_argument("value", nargs="+", help="replacement value")

    get_parser = sub.add_parser("get", help="print the item at INDEX")
    get_parser.add_argument("index", help="index (use -- before a negative index)")

    show_parser = sub.add_parser("show", help="print a window of arr_nums")
    show_parser.add_argument("start", nargs="?", default="0")
    show_parser.add_argument("count", nargs="?", default="10")

    append_parser = sub.add_parser("append", help="insert VALUE at the end")
    append_parser.add_argument("value", nargs="+", help="value to append")

    find_parser = sub.add_parser("find", help="print the first index of VALUE")
    find_parser.add_argument("value", nargs="+", help="value to search for")

    return parser


def _manager_from_args(args: argparse.Namespace) -> ArrayManager:
    """Build arr_nums from CLI flags, including optional --values."""
    if args.values is not None:
        raw_items = [item.strip() for item in args.values.split(",")]
        parsed = [parse_cli_value(item) for item in raw_items if item != ""]
        return ArrayManager(values=parsed)
    return ArrayManager(size=args.size, seed=args.seed)


def dispatch(args: argparse.Namespace) -> int:
    """Run the selected CLI command against a freshly built arr_nums."""
    command = args.command or "demo"
    manager = _manager_from_args(args)

    if command == "demo":
        return demonstrate_operations(manager)
    if command == "interactive":
        return run_interactive(manager)
    if command == "insert":
        index = parse_index_token(args.index)
        value = parse_cli_value(" ".join(args.value))
        manager.insert(index, value)
        print(f"inserted {value!r} at {index}; length is now {len(manager)}")
        print(f"window: {manager.snapshot(max(index, 0), 5)}")
        return 0
    if command == "delete":
        index = parse_index_token(args.index)
        removed = manager.delete(index)
        print(f"deleted {removed!r} from {index}; length is now {len(manager)}")
        return 0
    if command == "replace":
        index = parse_index_token(args.index)
        value = parse_cli_value(" ".join(args.value))
        previous = manager.replace(index, value)
        print(f"replaced {previous!r} with {value!r} at {index}")
        return 0
    if command == "get":
        index = parse_index_token(args.index)
        print(f"arr_nums[{index}] = {manager.get(index)!r}")
        return 0
    if command == "show":
        start = parse_index_token(args.start)
        count = parse_index_token(args.count)
        window = manager.snapshot(start, count)
        print(f"length: {len(manager)}")
        print(f"arr_nums[{start}:{start + count}] = {window}")
        return 0
    if command == "append":
        value = parse_cli_value(" ".join(args.value))
        index = manager.append(value)
        print(f"appended {value!r} at {index}; length is now {len(manager)}")
        return 0
    if command == "find":
        value = parse_cli_value(" ".join(args.value))
        index = manager.find(value)
        print(f"{value!r} first occurs at index {index}")
        return 0

    print(f"unknown command: {command}", file=sys.stderr)
    return 2


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
        return dispatch(args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except ArrayOperationError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unhandled error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
