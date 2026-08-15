#!/usr/bin/env python3
"""
Advanced Python features in one real-world app: Riverside Student Swap.

Students list used textbooks and dorm gear. The desk indexes bins by
(building, aisle, bin) tuples, matches buyer tags with listing tags,
streams search hits, applies member/tax closures and callable coupons,
then walks a pick route with a custom iterator.

Feature map
-----------
list                 cart, undo stack, pick queue
dict                 SKU -> listing, location tuple -> bin contents
tuple                immutable warehouse coordinate; dict key
set                  tags, claimed student IDs, set algebra for matches
list comprehension   affordable listings, receipt lines, flatten bins
generator            stream catalog / low-stock alerts (yield)
decorator            @timed, @audit, @require_sku
iterator             PickRoute: __iter__ + __next__
callable             PercentageOff / MemberPrice via __call__
closure              make_tax_calculator, make_budget_filter
__repr__             debugger view of a Listing
__str__              customer-facing shelf label
__eq__               two listings are the same SKU
__iter__ / __next__  aisle-by-aisle pick walk

    python3 campus_marketplace.py
    python3 campus_marketplace.py demo
    python3 -m unittest test_campus_marketplace.py -v
"""

from __future__ import annotations

import argparse
import functools
import sys
import time
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple


Location = Tuple[str, int, str]  # (building, aisle, bin) — hashable dict key


class MarketplaceError(Exception):
    """Base exception for the student swap desk."""


class UnknownSkuError(MarketplaceError, KeyError):
    """Raised when a SKU is not in the warehouse index."""


class OutOfStockError(MarketplaceError):
    """Raised when a reserve/pick would go below zero stock."""


def timed(fn: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator: record wall time on the wrapped function as `.last_elapsed`.

    The swap desk uses this on search and checkout so staff can see which
    step is slow during rush week.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - started
            wrapper.last_elapsed = elapsed  # type: ignore[attr-defined]
            if args and hasattr(args[0], "__dict__"):
                args[0].last_elapsed = elapsed

    wrapper.last_elapsed = 0.0  # type: ignore[attr-defined]
    return wrapper


def audit(action: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator factory: append (action, result-summary) onto an audit list
    stored on the Marketplace instance (`self.audit_log`).
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(self: "Marketplace", *args: Any, **kwargs: Any) -> Any:
            result = fn(self, *args, **kwargs)
            summary = result if not isinstance(result, (list, dict, set)) else type(result).__name__
            self.audit_log.append((action, str(summary)[:80]))
            return result

        return wrapper

    return decorator


def require_sku(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: the first argument after self must be a known SKU."""

    @functools.wraps(fn)
    def wrapper(self: "Marketplace", sku: str, *args: Any, **kwargs: Any) -> Any:
        if sku not in self.by_sku:
            raise UnknownSkuError(f"unknown SKU {sku!r}")
        return fn(self, sku, *args, **kwargs)

    return wrapper


def make_tax_calculator(rate: float) -> Callable[[float], float]:
    """
    Closure: capture a campus tax rate and return an adder.

    Riverside city tax is 8.25%. The inner function keeps using that
    rate even after this factory returns — that captured binding is
    the closure.
    """
    if rate < 0:
        raise MarketplaceError(f"tax rate must be >= 0, got {rate}")

    def add_tax(subtotal: float) -> float:
        return round(subtotal * (1.0 + rate), 2)

    return add_tax


def make_budget_filter(budget: float) -> Callable[[Iterable["Listing"]], Iterator["Listing"]]:
    """
    Closure: capture a student's budget and yield only listings they
    can afford. Returns a generator function, not a list.
    """

    def affordable(listings: Iterable[Listing]) -> Iterator[Listing]:
        for listing in listings:
            if listing.price <= budget:
                yield listing

    return affordable


class PercentageOff:
    """
    Callable discount: `coupon(amount)` returns the discounted price.

    Staff can stack several of these (member 10% off, then FLASH25)
    because each object is a function-shaped value.
    """

    def __init__(self, percent: float, label: str) -> None:
        if not 0 <= percent <= 100:
            raise MarketplaceError(f"percent must be 0..100, got {percent}")
        self.percent = percent
        self.label = label

    def __call__(self, amount: float) -> float:
        return round(amount * (1.0 - self.percent / 100.0), 2)

    def __repr__(self) -> str:
        return f"PercentageOff({self.percent!r}, {self.label!r})"

    def __str__(self) -> str:
        return f"{self.label} ({self.percent:.0f}% off)"


class Listing:
    """One item a student listed at the swap desk."""

    def __init__(
        self,
        sku: str,
        title: str,
        price: float,
        tags: Iterable[str],
        stock: int,
        location: Location,
        seller: str,
    ) -> None:
        if stock < 0:
            raise MarketplaceError(f"stock must be >= 0, got {stock}")
        if price < 0:
            raise MarketplaceError(f"price must be >= 0, got {price}")
        self.sku = sku
        self.title = title
        self.price = float(price)
        self.tags: Set[str] = set(tags)
        self.stock = stock
        self.location = location
        self.seller = seller

    def __repr__(self) -> str:
        """Debugger / REPL view: unambiguous constructor-style dump."""
        return (
            f"Listing(sku={self.sku!r}, title={self.title!r}, "
            f"price={self.price!r}, stock={self.stock!r}, "
            f"location={self.location!r})"
        )

    def __str__(self) -> str:
        """Shelf label a student reads on the website."""
        tag_text = ", ".join(sorted(self.tags)) or "untagged"
        return (
            f"{self.title} (${self.price:.2f}) — {tag_text}; "
            f"{self.stock} left in {self.location[0]} aisle {self.location[1]}"
        )

    def __eq__(self, other: object) -> bool:
        """
        Two listings are the same marketplace item when the SKU matches.

        Price and stock can change; identity is the sticker on the bin.
        """
        if not isinstance(other, Listing):
            return NotImplemented
        return self.sku == other.sku

    def __hash__(self) -> int:
        return hash(self.sku)


class PickRoute:
    """
    Iterator over warehouse stops, sorted by building / aisle / bin.

    `for stop in route` calls __iter__, which returns self, then
    __next__ until StopIteration. Staff walk this instead of bouncing
    between buildings.
    """

    def __init__(self, stops: Sequence[Tuple[Location, Listing, int]]) -> None:
        self._stops: List[Tuple[Location, Listing, int]] = sorted(
            stops, key=lambda stop: (stop[0][0], stop[0][1], stop[0][2], stop[1].sku)
        )
        self._index = 0

    def __iter__(self) -> "PickRoute":
        """
        Return this route as its own iterator.

        Rewind is explicit (`rewind`) so a partially consumed iterator is
        not reset when `list()` calls `iter()` again.
        """
        return self

    def rewind(self) -> "PickRoute":
        self._index = 0
        return self

    def __next__(self) -> Tuple[Location, Listing, int]:
        if self._index >= len(self._stops):
            raise StopIteration
        stop = self._stops[self._index]
        self._index += 1
        return stop

    def __len__(self) -> int:
        return len(self._stops)

    def __repr__(self) -> str:
        return f"PickRoute({len(self._stops)} stop(s), next={self._index})"


class Marketplace:
    """
    In-memory swap desk: listings, bins, carts, and a checkout pipeline.

    Data layout
    -----------
    by_sku:     dict[str, Listing]
    bins:       dict[Location, list[str]]   # tuple keys
    claimed:    set[str]                    # student IDs who already checked out
    carts:      dict[str, list[str]]        # student -> SKUs
    undo:       list[tuple]                 # stack of reversible actions
    """

    def __init__(self) -> None:
        self.by_sku: Dict[str, Listing] = {}
        self.bins: Dict[Location, List[str]] = {}
        self.claimed: Set[str] = set()
        self.carts: Dict[str, List[str]] = {}
        self.undo: List[Tuple[str, Any]] = []
        self.audit_log: List[Tuple[str, str]] = []

    def stock(self, listing: Listing) -> None:
        """Put a listing in its bin. List append + dict index + tuple key."""
        if listing.sku in self.by_sku:
            raise MarketplaceError(f"duplicate SKU {listing.sku!r}")
        self.by_sku[listing.sku] = listing
        self.bins.setdefault(listing.location, []).append(listing.sku)

    def seed_riverside(self) -> None:
        """Load the current semester's desk with a handful of real listings."""
        samples = [
            Listing("TB-CALC", "Used Calculus", 24.99, {"math", "textbook", "used"}, 3, ("Union", 1, "A"), "maya"),
            Listing("TB-PY", "Intro to Python", 18.50, {"cs", "textbook", "used"}, 2, ("Union", 1, "A"), "jordan"),
            Listing("TB-CHEM", "Organic Chemistry", 40.00, {"chem", "textbook"}, 1, ("Union", 2, "C"), "sam"),
            Listing("CALC-TI", "TI-84 Calculator", 55.00, {"math", "gear"}, 1, ("Science", 4, "B"), "priya"),
            Listing("HOOD-GR", "Green Hoodie M", 12.00, {"dorm", "apparel"}, 4, ("Union", 3, "D"), "lee"),
            Listing("LAMP-01", "Desk Lamp", 8.75, {"dorm", "gear"}, 2, ("Science", 1, "A"), "maya"),
            Listing("TB-ALG", "Linear Algebra", 22.00, {"math", "textbook", "used"}, 1, ("Union", 1, "B"), "chris"),
            Listing("USB-HUB", "USB-C Hub", 15.99, {"cs", "gear"}, 5, ("Science", 2, "F"), "jordan"),
        ]
        for listing in samples:
            self.stock(listing)

    @timed
    def search(
        self,
        *,
        budget: Optional[float] = None,
        interests: Optional[Iterable[str]] = None,
        in_stock_only: bool = True,
    ) -> List[Listing]:
        """
        List comprehension + set intersection.

        A student who cares about math AND used books sees listings
        whose tag set overlaps their interest set, optionally capped
        by budget.
        """
        wanted = set(interests) if interests is not None else None
        """
        The comprehension below is the desk's public search: one pass,
        no extra lists until the result is built.
        """
        hits = [
            listing
            for listing in self.by_sku.values()
            if (not in_stock_only or listing.stock > 0)
            and (budget is None or listing.price <= budget)
            and (wanted is None or bool(listing.tags & wanted))
        ]
        hits.sort(key=lambda listing: (listing.price, listing.sku))
        return hits

    def iter_catalog(self) -> Iterator[Listing]:
        """Generator: stream listings without copying the dict values list."""
        for sku in sorted(self.by_sku):
            yield self.by_sku[sku]

    def low_stock_alerts(self, threshold: int = 1) -> Iterator[Listing]:
        """Generator: yield only SKUs at or below the restock threshold."""
        yield from (
            listing
            for listing in self.iter_catalog()
            if 0 < listing.stock <= threshold
        )

    @require_sku
    @audit("reserve")
    def reserve(self, sku: str, student: str, qty: int = 1) -> Listing:
        """Move `qty` units of `sku` into a student's cart (a list)."""
        if qty < 1:
            raise MarketplaceError(f"qty must be >= 1, got {qty}")
        listing = self.by_sku[sku]
        if listing.stock < qty:
            raise OutOfStockError(
                f"{listing.title} has {listing.stock} left, requested {qty}"
            )
        listing.stock -= qty
        cart = self.carts.setdefault(student, [])
        for _ in range(qty):
            cart.append(sku)
        self.undo.append(("reserve", student, sku, qty))
        return listing

    def undo_last(self) -> str:
        """List-as-stack: pop the last reserve and put stock back."""
        if not self.undo:
            raise MarketplaceError("nothing to undo")
        action, student, sku, qty = self.undo.pop()
        if action != "reserve":
            raise MarketplaceError(f"cannot undo {action}")
        listing = self.by_sku[sku]
        listing.stock += qty
        cart = self.carts.get(student, [])
        for _ in range(qty):
            if sku in cart:
                cart.remove(sku)
        return f"undid reserve of {qty} x {sku} for {student}"

    def pick_route_for(self, student: str) -> PickRoute:
        """
        Build an iterator of (location, listing, qty) from a cart.

        Qty is counted with a dict comprehension over the cart list.
        """
        cart = self.carts.get(student, [])
        counts: Dict[str, int] = {sku: cart.count(sku) for sku in set(cart)}
        stops = [
            (self.by_sku[sku].location, self.by_sku[sku], qty)
            for sku, qty in counts.items()
        ]
        return PickRoute(stops)

    def checkout(
        self,
        student: str,
        *,
        coupons: Sequence[Callable[[float], float]] = (),
        add_tax: Optional[Callable[[float], float]] = None,
    ) -> Dict[str, Any]:
        """
        Apply callable coupons in order, then a tax closure.

        Returns a receipt dict. Marks the student in the `claimed` set
        so a bundle deal cannot be used twice.
        """
        cart = self.carts.get(student, [])
        if not cart:
            raise MarketplaceError(f"{student} has an empty cart")
        lines = [self.by_sku[sku] for sku in cart]
        subtotal = round(sum(item.price for item in lines), 2)
        discounted = subtotal
        applied = []
        for coupon in coupons:
            discounted = coupon(discounted)
            applied.append(getattr(coupon, "label", repr(coupon)))
        total = add_tax(discounted) if add_tax is not None else discounted
        self.claimed.add(student)
        receipt = {
            "student": student,
            "titles": [item.title for item in lines],
            "subtotal": subtotal,
            "coupons": applied,
            "discounted": discounted,
            "total": total,
            "locations": {item.sku: item.location for item in lines},
        }
        self.carts[student] = []
        self.audit_log.append(("checkout", f"{student} total={total}"))
        return receipt


def seed_desk() -> Marketplace:
    desk = Marketplace()
    desk.seed_riverside()
    return desk


def _print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def demonstrate_features() -> int:
    """Walk Maya's used-book run so each language feature shows up on the job."""
    try:
        desk = seed_desk()
    except MarketplaceError as exc:
        print(f"Failed to open the desk: {exc}", file=sys.stderr)
        return 1

    _print_section("1. tuple + dict — warehouse bins keyed by location")
    """
    A location is (building, aisle, bin). Tuples are immutable and
    hashable, so they can be dictionary keys. A list of SKUs lives in
    each bin.
    """
    print("bins (tuple keys):")
    for location, skus in sorted(desk.bins.items()):
        building, aisle, bin_id = location  # tuple unpacking
        print(f"  {building:8} aisle {aisle} bin {bin_id}: {skus}")

    _print_section("2. set — tag matching for Maya's interests")
    interests = {"math", "used", "cs"}
    print(f"Maya's interests: {sorted(interests)}")
    matches = desk.search(interests=interests)
    for listing in matches:
        overlap = listing.tags & interests
        print(f"  {listing.sku:8} overlap={str(sorted(overlap)):<28} {listing}")

    listed = {listing.sku for listing in desk.by_sku.values()}
    in_stock = {sku for sku, listing in desk.by_sku.items() if listing.stock > 0}
    print(f"sold-out SKUs (set difference): {sorted(listed - in_stock) or 'none'}")

    _print_section("3. list comprehension — everything under $20 still in stock")
    cheap = [
        (listing.title, listing.price)
        for listing in desk.by_sku.values()
        if listing.stock > 0 and listing.price < 20
    ]
    for title, price in cheap:
        print(f"  ${price:6.2f}  {title}")

    _print_section("4. generator — stream the catalog; low-stock alerts")
    print("first four catalog rows (generator, not a copied list):")
    stream = desk.iter_catalog()
    for _ in range(4):
        print(f"  {next(stream)}")
    print("low-stock alerts (yield from generator expression):")
    for listing in desk.low_stock_alerts(threshold=1):
        print(f"  restock {listing.sku}: {listing.title} ({listing.stock} left)")

    _print_section("5. __str__ vs __repr__ vs __eq__")
    calc = desk.by_sku["TB-CALC"]
    same_sku = Listing("TB-CALC", "Different Title", 99.0, set(), 0, ("X", 0, "Z"), "ghost")
    print(f"str  : {calc}")
    print(f"repr : {calc!r}")
    print(f"eq   : Listing with same SKU but other fields == calc? {same_sku == calc}")
    print(f"hash set size for [calc, same_sku]: {len({calc, same_sku})}")

    _print_section("6. decorator — timed search and audited reserve")
    hits = desk.search(budget=30, interests={"math"})
    elapsed_ms = getattr(desk, "last_elapsed", 0.0) * 1000
    print(f"search(budget=30, math) -> {len(hits)} hit(s) in {elapsed_ms:.3f} ms")
    desk.reserve("TB-CALC", "maya", 1)
    desk.reserve("TB-PY", "maya", 1)
    desk.reserve("TB-ALG", "maya", 1)
    print("audit_log:")
    for action, summary in desk.audit_log:
        print(f"  {action}: {summary}")

    _print_section("7. closure + callable — member coupon then campus tax")
    add_tax = make_tax_calculator(0.0825)
    member = PercentageOff(10, "STUDENT10")
    flash = PercentageOff(25, "FLASH25")
    print(f"callable coupons: {member}, {flash}")
    print(f"$20 after 10% off: ${member(20):.2f}  (closure tax on $18: ${add_tax(18):.2f})")
    under_25 = make_budget_filter(25.00)
    print("Maya's $25 budget stream:")
    for listing in under_25(desk.iter_catalog()):
        print(f"  {listing.title} ${listing.price:.2f}")

    _print_section("8. iterator __iter__/__next__ — pick route for Maya")
    route = desk.pick_route_for("maya")
    print(f"{route!r}")
    iterator = iter(route)
    while True:
        try:
            location, listing, qty = next(iterator)
        except StopIteration:
            break
        building, aisle, bin_id = location
        print(
            f"  pick {qty} x {listing.sku} ({listing.title}) "
            f"at {building} / aisle {aisle} / bin {bin_id}"
        )

    _print_section("9. checkout receipt (list of titles, dict of locations)")
    receipt = desk.checkout("maya", coupons=(member, flash), add_tax=add_tax)
    for key, value in receipt.items():
        print(f"  {key}: {value}")
    print(f"claimed students (set): {desk.claimed}")

    _print_section("10. list-as-stack undo + expected errors")
    desk.reserve("HOOD-GR", "jordan", 1)
    print(desk.undo_last())
    error_cases = [
        ("unknown SKU", lambda: desk.reserve("NOPE", "lee")),
        ("out of stock", lambda: desk.reserve("CALC-TI", "lee", 9)),
        ("empty cart checkout", lambda: desk.checkout("ghost")),
        ("bad tax closure", lambda: make_tax_calculator(-0.1)),
        ("duplicate SKU", lambda: desk.stock(desk.by_sku["HOOD-GR"])),
    ]
    for label, action in error_cases:
        try:
            action()
            print(f"UNEXPECTED SUCCESS: {label}")
        except MarketplaceError as exc:
            print(f"caught {type(exc).__name__} for {label}: {exc}")
        except Exception as exc:
            print(f"caught unexpected {type(exc).__name__} for {label}: {exc}")

    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Riverside Student Swap — advanced Python features demo"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="demo",
        choices=("demo",),
        help="run the scripted marketplace walkthrough",
    )
    try:
        parser.parse_args(list(argv) if argv is not None else None)
        return demonstrate_features()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except MarketplaceError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unhandled error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
