#!/usr/bin/env python3
"""
Bubble, selection, insertion, and merge sort — campus bookstore demo.

Real-world setup
----------------
Riverside Campus Bookstore runs a flash sale. Students want textbooks
ordered from cheapest to most expensive. The staff picks shelf is only
a handful of titles (bubble / selection / insertion). The full catalog
has 15,335 SKUs, which is why the store uses merge sort (and why
Python's own sorted() is a merge/insertion hybrid).

    python3 sorting_algorithms.py
    python3 sorting_algorithms.py demo
    python3 sorting_algorithms.py interactive
    python3 sorting_algorithms.py sort --algorithm merge --by price
    python3 -m unittest test_sorting_algorithms.py -v
"""

from __future__ import annotations

import argparse
import random
import shlex
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Sequence, Tuple


CATALOG_SIZE = 15335
BENCHMARK_SIZE = 1200

HELP_TEXT = """
Commands (interactive mode)
---------------------------
  help                         Show this help text
  featured                     Load the 8-item flash-sale shelf
  catalog [N]                  Load N generated catalog items (default 40)
  show                         Print the current list
  bubble [price|title|stock]   Sort with bubble sort
  selection [price|title|stock]
  insertion [price|title|stock]
  merge [price|title|stock]
  compare                      Time all four algorithms on a copy
  reverse                      Toggle ascending / descending
  demo                         Run the scripted bookstore walkthrough
  quit                         Exit
""".strip()


class SortError(Exception):
    """Base exception for sorting failures in this program."""


class InvalidInputError(SortError, ValueError):
    """Raised when the collection or key cannot be sorted as requested."""


class CommandParseError(SortError):
    """Raised when an interactive or CLI command cannot be parsed."""


@dataclass(frozen=True)
class Product:
    """
    One item on a bookstore shelf.

    `arrival` is the order the box was unpacked. Stable sorts keep two
    $79.99 titles in that original arrival order; selection sort may not.
    """

    title: str
    price: float
    department: str
    stock: int
    arrival: int = 0
    sku: str = ""

    def __str__(self) -> str:
        return (
            f"{self.title:<36} ${self.price:7.2f}  "
            f"{self.department:<10} stock={self.stock:<4} #{self.arrival}"
        )


@dataclass
class SortStats:
    """Comparisons, data moves, and wall time for one sort run."""

    name: str
    comparisons: int = 0
    moves: int = 0
    seconds: float = 0.0
    extra: dict = field(default_factory=dict)


KeyFn = Callable[[Any], Any]


def _require_list(items: Any) -> List[Any]:
    if not isinstance(items, list):
        raise InvalidInputError(
            f"items must be a list, got {type(items).__name__}"
        )
    return items


def _resolve_key(key: Any) -> KeyFn:
    if key is None:
        return lambda item: item
    if not callable(key):
        raise InvalidInputError("key must be callable or None")
    return key


def _less(left: Any, right: Any, key: KeyFn, reverse: bool, stats: SortStats) -> bool:
    """
    Strict less-than on the sort key.

    Using `<` (never `<=`) keeps equal keys in their original order for
    bubble, insertion, and merge sort.
    """
    stats.comparisons += 1
    try:
        left_key = key(left)
        right_key = key(right)
        if reverse:
            return right_key < left_key
        return left_key < right_key
    except TypeError as exc:
        raise InvalidInputError(
            f"cannot compare {left!r} with {right!r}: {exc}"
        ) from exc


def bubble_sort(
    items: List[Any],
    *,
    key: Optional[KeyFn] = None,
    reverse: bool = False,
) -> SortStats:
    """
    Bubble sort: swap adjacent inversions until the list is clean.

    Bookstore analog: two clerks walk the shelf left to right. Whenever
    a pricier book sits to the left of a cheaper one, they swap those
    two. After a full pass the most expensive title has "bubbled" to
    the end. A pass with no swaps means the shelf is already in order,
    so we stop early — useful when overnight restocking only shuffled
    a few titles.
    """
    items = _require_list(items)
    key_fn = _resolve_key(key)
    stats = SortStats("bubble")
    started = time.perf_counter()
    try:
        n = len(items)
        for end in range(n - 1, 0, -1):
            swapped = False
            for index in range(end):
                if _less(items[index + 1], items[index], key_fn, reverse, stats):
                    items[index], items[index + 1] = items[index + 1], items[index]
                    stats.moves += 1
                    swapped = True
            if not swapped:
                break
    except SortError:
        raise
    except Exception as exc:
        raise SortError(f"bubble sort failed: {exc}") from exc
    stats.seconds = time.perf_counter() - started
    return stats


def selection_sort(
    items: List[Any],
    *,
    key: Optional[KeyFn] = None,
    reverse: bool = False,
) -> SortStats:
    """
    Selection sort: pull the next extreme item into place.

    Bookstore analog: the display manager repeatedly scans whatever is
    still in the back room, picks the cheapest remaining book, and puts
    it in the next empty slot on the sale table. Each pass does at most
    one swap, so this is attractive when writing a record is expensive
    (think EEPROM / flash) even though the scans are still quadratic.
    Selection sort is not stable: two titles with the same price may
    trade places.
    """
    items = _require_list(items)
    key_fn = _resolve_key(key)
    stats = SortStats("selection")
    started = time.perf_counter()
    try:
        n = len(items)
        for slot in range(n - 1):
            chosen = slot
            for index in range(slot + 1, n):
                if _less(items[index], items[chosen], key_fn, reverse, stats):
                    chosen = index
            if chosen != slot:
                items[slot], items[chosen] = items[chosen], items[slot]
                stats.moves += 1
    except SortError:
        raise
    except Exception as exc:
        raise SortError(f"selection sort failed: {exc}") from exc
    stats.seconds = time.perf_counter() - started
    return stats


def insertion_sort(
    items: List[Any],
    *,
    key: Optional[KeyFn] = None,
    reverse: bool = False,
) -> SortStats:
    """
    Insertion sort: insert each new item into the already-sorted prefix.

    Bookstore analog: a clerk unpacks boxes one book at a time onto a
    shelf that is already sorted by price. They slide the new book left
    until its neighbors are in order. That is exactly how a nearly
    sorted shelf (or a live queue of incoming shipments) should be
    maintained, and it is why Timsort — Python's sorted() — falls back
    to insertion sort on short runs.
    """
    items = _require_list(items)
    key_fn = _resolve_key(key)
    stats = SortStats("insertion")
    started = time.perf_counter()
    try:
        for index in range(1, len(items)):
            current = items[index]
            hole = index
            while hole > 0 and _less(current, items[hole - 1], key_fn, reverse, stats):
                items[hole] = items[hole - 1]
                stats.moves += 1
                hole -= 1
            items[hole] = current
            if hole != index:
                stats.moves += 1
    except SortError:
        raise
    except Exception as exc:
        raise SortError(f"insertion sort failed: {exc}") from exc
    stats.seconds = time.perf_counter() - started
    return stats


def merge_sort(
    items: List[Any],
    *,
    key: Optional[KeyFn] = None,
    reverse: bool = False,
) -> SortStats:
    """
    Merge sort: split the catalog, sort each half, then zip them together.

    Bookstore analog: two employees each sort half of the 15,335-SKU
    inventory, then walk the two sorted carts in lockstep, always taking
    the cheaper remaining title. Guaranteed O(n log n), stable, and the
    reason large storefronts (and databases) merge sorted runs instead
    of bubbling through millions of adjacent pairs.
    """
    items = _require_list(items)
    key_fn = _resolve_key(key)
    stats = SortStats("merge")
    started = time.perf_counter()
    try:
        scratch = [None] * len(items)
        _merge_sort_range(items, scratch, 0, len(items), key_fn, reverse, stats)
    except SortError:
        raise
    except Exception as exc:
        raise SortError(f"merge sort failed: {exc}") from exc
    stats.seconds = time.perf_counter() - started
    return stats


def _merge_sort_range(
    items: List[Any],
    scratch: List[Any],
    low: int,
    high: int,
    key_fn: KeyFn,
    reverse: bool,
    stats: SortStats,
) -> None:
    """Sort items[low:high] using scratch as a temporary buffer."""
    length = high - low
    if length <= 1:
        return
    mid = low + length // 2
    _merge_sort_range(items, scratch, low, mid, key_fn, reverse, stats)
    _merge_sort_range(items, scratch, mid, high, key_fn, reverse, stats)

    left, right = low, mid
    merged = low
    while left < mid and right < high:
        if _less(items[right], items[left], key_fn, reverse, stats):
            scratch[merged] = items[right]
            right += 1
        else:
            scratch[merged] = items[left]
            left += 1
        merged += 1
        stats.moves += 1
    while left < mid:
        scratch[merged] = items[left]
        left += 1
        merged += 1
        stats.moves += 1
    while right < high:
        scratch[merged] = items[right]
        right += 1
        merged += 1
        stats.moves += 1
    items[low:high] = scratch[low:high]


ALGORITHMS = {
    "bubble": bubble_sort,
    "selection": selection_sort,
    "insertion": insertion_sort,
    "merge": merge_sort,
}

PRODUCT_KEYS = {
    "price": lambda product: product.price,
    "title": lambda product: product.title.lower(),
    "stock": lambda product: product.stock,
    "arrival": lambda product: product.arrival,
    "department": lambda product: product.department.lower(),
}


def featured_shelf() -> List[Product]:
    """
    Eight real flash-sale titles, deliberately unsorted.

    Two Python books share the $79.99 price so stability is visible:
    "Intro to Python" arrived first (arrival=2) and should stay ahead
    of "Data Structures in Python" (arrival=7) after a stable sort.
    """
    raw = [
        ("Calculus: Early Transcendentals", 284.50, "Math", 11),
        ("Intro to Python Programming", 79.99, "CS", 24),
        ("Organic Chemistry", 312.00, "Chem", 6),
        ("Campus Hoodie (used)", 29.50, "Supplies", 18),
        ("Linear Algebra and Its Applications", 198.00, "Math", 9),
        ("The College Writer (used)", 24.99, "English", 14),
        ("Data Structures in Python", 79.99, "CS", 15),
        ("Lab Goggles", 12.49, "Supplies", 40),
    ]
    return [
        Product(title, price, department, stock, arrival=index + 1, sku=f"FS-{index + 1:03d}")
        for index, (title, price, department, stock) in enumerate(raw)
    ]


def generate_catalog(size: int = CATALOG_SIZE, seed: int = 42) -> List[Product]:
    """Build a deterministic warehouse catalog of `size` SKUs."""
    if isinstance(size, bool) or not isinstance(size, int):
        raise InvalidInputError(f"size must be an int, got {type(size).__name__}")
    if size < 0:
        raise InvalidInputError(f"size must be >= 0, got {size}")
    departments = ("Math", "CS", "Chem", "English", "History", "Supplies")
    adjectives = ("Intro", "Advanced", "Applied", "Essential", "Modern", "Campus")
    subjects = ("Algebra", "Biology", "Poetry", "Networks", "Physics", "Ethics")
    rng = random.Random(seed)
    catalog: List[Product] = []
    for index in range(size):
        title = f"{rng.choice(adjectives)} {rng.choice(subjects)} {index + 1}"
        catalog.append(
            Product(
                title=title,
                price=round(rng.uniform(4.99, 399.99), 2),
                department=rng.choice(departments),
                stock=rng.randint(0, 80),
                arrival=index + 1,
                sku=f"CAT-{index + 1:05d}",
            )
        )
    return catalog


def _print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _print_shelf(products: Sequence[Product], limit: int = 12) -> None:
    print(f"{'title':<36} {'price':>8}  {'dept':<10} stock  unpacked")
    print("-" * 72)
    for product in products[:limit]:
        print(product)
    if len(products) > limit:
        print(f"... ({len(products) - limit} more)")


def _is_sorted(items: Sequence[Any], key: KeyFn, reverse: bool = False) -> bool:
    for index in range(1, len(items)):
        left, right = key(items[index - 1]), key(items[index])
        if reverse:
            if left < right:
                return False
        elif right < left:
            return False
    return True


def _run_named_sort(
    name: str,
    items: List[Any],
    *,
    key: Optional[KeyFn] = None,
    reverse: bool = False,
) -> SortStats:
    if name not in ALGORITHMS:
        raise InvalidInputError(
            f"unknown algorithm {name!r}; choose from {sorted(ALGORITHMS)}"
        )
    return ALGORITHMS[name](items, key=key, reverse=reverse)


def demonstrate_sorts() -> int:
    """
    Walk the bookstore example: tiny shelf traces, stability, then
    a timed comparison and a full 15,335-SKU merge.
    """
    try:
        shelf = featured_shelf()
    except SortError as exc:
        print(f"Failed to build the flash-sale shelf: {exc}", file=sys.stderr)
        return 1

    _print_section("1. Flash-sale shelf (unsorted, as unpacked)")
    print("Students asked for 'price: low to high' on the website.")
    _print_shelf(shelf)

    _print_section("2. Each algorithm sorts a copy of that shelf")
    for name in ("bubble", "selection", "insertion", "merge"):
        copy = list(shelf)
        stats = _run_named_sort(name, copy, key=PRODUCT_KEYS["price"])
        cheapest = copy[0]
        priciest = copy[-1]
        print(
            f"{name:<10} {stats.comparisons:4} comparisons, "
            f"{stats.moves:4} moves, {stats.seconds * 1e6:7.1f} µs  |  "
            f"cheapest: {cheapest.title} (${cheapest.price:.2f}); "
            f"priciest: {priciest.title} (${priciest.price:.2f})"
        )
        if not _is_sorted(copy, PRODUCT_KEYS["price"]):
            print(f"  ERROR: {name} did not sort by price")
            return 1

    _print_section("3. Stability: two books both cost $79.99")
    """
    Intro to Python was unpacked before Data Structures in Python.
    A stable sort must keep that arrival order when prices tie.
    """
    print("Original arrival order among the $79.99 pair:")
    for product in shelf:
        if product.price == 79.99:
            print(f"  arrival #{product.arrival}: {product.title}")
    for name in ("bubble", "selection", "insertion", "merge"):
        copy = list(shelf)
        _run_named_sort(name, copy, key=PRODUCT_KEYS["price"])
        tied = [item for item in copy if item.price == 79.99]
        order = " -> ".join(item.title.split()[0] for item in tied)
        stable = [item.arrival for item in tied] == sorted(item.arrival for item in tied)
        print(
            f"{name:<10} $79.99 order: {order:28} "
            f"{'(stable)' if stable else '(not stable)'}"
        )

    _print_section("4. Timed bake-off on a 1,200-item restock cart")
    """
    Quadratic sorts are fine for a cart; they are not fine for the
    warehouse. This is the point of measuring them side by side.
    """
    cart = generate_catalog(BENCHMARK_SIZE, seed=7)
    print(f"restock cart: {len(cart)} titles, random prices")
    for name in ("bubble", "selection", "insertion", "merge"):
        copy = list(cart)
        stats = _run_named_sort(name, copy, key=PRODUCT_KEYS["price"])
        print(
            f"{name:<10} {stats.seconds * 1000:8.2f} ms   "
            f"{stats.comparisons:10} comparisons   {stats.moves:10} moves"
        )

    _print_section("5. Full warehouse: merge-sort 15,335 SKUs")
    warehouse = generate_catalog(CATALOG_SIZE, seed=42)
    stats = merge_sort(warehouse, key=PRODUCT_KEYS["price"])
    print(
        f"merge-sorted {len(warehouse)} SKUs in {stats.seconds * 1000:.2f} ms "
        f"({stats.comparisons} comparisons)"
    )
    print("five cheapest:")
    _print_shelf(warehouse, limit=5)
    print("five most expensive:")
    _print_shelf(warehouse[-5:], limit=5)

    _print_section("6. Exception handling (expected failures)")
    error_cases = [
        ("sort a tuple, not a list", lambda: bubble_sort((3, 2, 1))),
        ("incomparable mixed types", lambda: insertion_sort([1, "x", 3])),
        ("unknown algorithm", lambda: _run_named_sort("quick", [1, 2])),
        ("negative catalog size", lambda: generate_catalog(-4)),
        ("non-callable key", lambda: merge_sort([1, 2], key="price")),
    ]
    for label, action in error_cases:
        try:
            action()
            print(f"UNEXPECTED SUCCESS: {label}")
        except SortError as exc:
            print(f"caught {type(exc).__name__} for {label}: {exc}")
        except Exception as exc:
            print(f"caught unexpected {type(exc).__name__} for {label}: {exc}")

    _print_section("7. When the bookstore actually uses each sort")
    print("bubble     tiny shelf, almost-sorted overnight restock, teaching")
    print("selection  tiny shelf when swapping two books is the costly part")
    print("insertion  live unpacking onto an already-sorted display")
    print("merge      the 15,335-SKU website catalog and any stable price sort")
    return 0


def handle_repl_line(
    items: List[Product],
    reverse: List[bool],
    line: str,
) -> Tuple[str, bool, Optional[List[Product]]]:
    """
    Run one interactive command.

    reverse is a one-element list so the toggle can update the caller's
    flag. Returns (message, should_quit, replacement_list_or_None).
    """
    stripped = line.strip()
    if not stripped:
        return "", False, None
    try:
        tokens = shlex.split(stripped)
    except ValueError as exc:
        raise CommandParseError(f"could not parse command: {exc}") from exc

    command = tokens[0].lower()
    args = tokens[1:]

    if command in {"quit", "exit", "q"}:
        return "Goodbye.", True, None
    if command in {"help", "?"}:
        return HELP_TEXT, False, None
    if command == "featured":
        return f"loaded {len(featured_shelf())} flash-sale titles", False, featured_shelf()
    if command == "catalog":
        size = int(args[0], 10) if args else 40
        loaded = generate_catalog(size)
        return f"loaded {len(loaded)} catalog titles", False, loaded
    if command == "show":
        if not items:
            return "(list is empty)", False, None
        lines = [str(product) for product in items[:20]]
        extra = "" if len(items) <= 20 else f"\n... ({len(items) - 20} more)"
        return "\n".join(lines) + extra, False, None
    if command == "reverse":
        reverse[0] = not reverse[0]
        direction = "descending" if reverse[0] else "ascending"
        return f"direction is now {direction}", False, None
    if command in ALGORITHMS:
        field_name = args[0].lower() if args else "price"
        if field_name not in PRODUCT_KEYS:
            raise CommandParseError(
                f"unknown field {field_name!r}; choose from {sorted(PRODUCT_KEYS)}"
            )
        stats = _run_named_sort(
            command, items, key=PRODUCT_KEYS[field_name], reverse=reverse[0]
        )
        return (
            f"{command} by {field_name}: {stats.comparisons} comparisons, "
            f"{stats.moves} moves, {stats.seconds * 1000:.2f} ms"
        ), False, None
    if command == "compare":
        rows = []
        for name in ALGORITHMS:
            copy = list(items)
            stats = _run_named_sort(
                name, copy, key=PRODUCT_KEYS["price"], reverse=reverse[0]
            )
            rows.append(
                f"{name:<10} {stats.seconds * 1000:8.2f} ms  "
                f"{stats.comparisons:8} cmp  {stats.moves:8} moves"
            )
        return "\n".join(rows), False, None
    if command == "demo":
        demonstrate_sorts()
        return "demonstration finished (interactive list was not changed).", False, None

    raise CommandParseError(f"unknown command {command!r}; type 'help'")


def run_interactive(input_fn: Callable[[str], str] = input) -> int:
    items = featured_shelf()
    reverse = [False]
    print("Riverside Campus Bookstore sorter. Type 'help', 'quit' to exit.")
    print(f"starting with {len(items)} flash-sale titles")
    while True:
        try:
            line = input_fn("sort> ")
        except EOFError:
            print()
            print("Goodbye.")
            return 0
        except KeyboardInterrupt:
            print()
            print("Interrupted. Type 'quit' to exit.")
            continue
        try:
            message, should_quit, replacement = handle_repl_line(items, reverse, line)
        except SortError as exc:
            print(f"{type(exc).__name__}: {exc}")
            continue
        except Exception as exc:
            print(f"unexpected {type(exc).__name__}: {exc}")
            continue
        if replacement is not None:
            items = replacement
        if message:
            print(message)
        if should_quit:
            return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Bubble, selection, insertion, and merge sort "
            "on a campus bookstore inventory."
        )
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("demo", help="run the scripted bookstore walkthrough")
    sub.add_parser("interactive", help="open the command prompt")

    sort_parser = sub.add_parser("sort", help="sort featured or generated products")
    sort_parser.add_argument(
        "--algorithm",
        choices=sorted(ALGORITHMS),
        default="merge",
    )
    sort_parser.add_argument("--by", choices=sorted(PRODUCT_KEYS), default="price")
    sort_parser.add_argument("--size", type=int, default=0, help="0 = featured shelf")
    sort_parser.add_argument("--reverse", action="store_true")
    sort_parser.add_argument("--limit", type=int, default=8)
    return parser


def dispatch(args: argparse.Namespace) -> int:
    command = args.command or "demo"
    if command == "demo":
        return demonstrate_sorts()
    if command == "interactive":
        return run_interactive()
    if command == "sort":
        products = (
            featured_shelf() if args.size <= 0 else generate_catalog(args.size)
        )
        stats = _run_named_sort(
            args.algorithm,
            products,
            key=PRODUCT_KEYS[args.by],
            reverse=args.reverse,
        )
        print(
            f"{args.algorithm} by {args.by}: {len(products)} items, "
            f"{stats.comparisons} comparisons, {stats.seconds * 1000:.2f} ms"
        )
        _print_shelf(products, limit=max(args.limit, 1))
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
    except SortError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unhandled error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
