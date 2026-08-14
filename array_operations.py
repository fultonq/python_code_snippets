#!/usr/bin/env python3
"""
Array mutation exercise for arr_nums (15,335 elements).

This module demonstrates insert, delete, and replace operations at many
index locations, with explicit validation and exception handling.

Run the walkthrough:
    python3 array_operations.py

Run the tests:
    python3 -m unittest test_array_operations.py -v
"""

from __future__ import annotations

import random
import sys
from typing import Any, Iterable, List, Optional, Sequence, Tuple


ARRAY_SIZE = 15335


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
    """Raised when a delete is attempted on an empty array."""


class ArrayManager:
    """
    Manage a mutable list named arr_nums and apply guarded mutations.

    Python lists already support insert, pop, and item assignment. This
    wrapper adds:
      * bounds and type checks before each mutation
      * a small operation history for later inspection
      * helpers for bulk insert / delete / replace work
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
            if not isinstance(size, int):
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
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidIndexError(
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
        Returns the number of successful inserts.
        """
        if not isinstance(pairs, (list, tuple)):
            raise InvalidValueError(
                "insert_many expects a sequence of (index, value) pairs"
            )
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
        delete the wrong neighbor.
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
        previous_values: List[Any] = []
        for item in pairs:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise InvalidValueError(
                    f"each replace pair must be (index, value), got {item!r}"
                )
            previous_values.append(self.replace(item[0], item[1]))
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


def _run_step(label: str, action) -> bool:
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


def demonstrate_operations() -> int:
    """
    Run a scripted walkthrough of insert, delete, and replace.

    Successful operations and intentionally invalid calls are both shown
    so the exception paths are exercised in a normal run. Returns 0 when
    the demonstration finishes without an unexpected crash.
    """
    try:
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


def main() -> int:
    try:
        return demonstrate_operations()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Unhandled error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
