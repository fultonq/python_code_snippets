#!/usr/bin/env python3
"""
Hash map from scratch, plus a campus ID-card application demo.

This is not Python's dict. `HashMap` uses separate chaining: each
bucket is a list of (key, value) pairs. When the load factor crosses
0.75 the table doubles so lookups stay close to O(1).

Real-world demo
---------------
Riverside Campus ID office. A student taps their card; the reader
hashes the SID and jumps to the locker / meal-plan record. Colliding
SIDs share a bucket chain the same way two students can share a
hallway but still have unique lockers.

    python3 hashmap.py
    python3 hashmap.py demo
    python3 hashmap.py lookup R1002341
    python3 -m unittest test_hashmap.py -v
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Iterator, List, Optional, Sequence, Tuple


class HashMapError(Exception):
    """Base exception for HashMap failures."""


class MissingKeyError(HashMapError, KeyError):
    """Raised when get/delete is asked for a key that is not stored."""


class UnhashableKeyError(HashMapError, TypeError):
    """Raised when a key cannot be hashed."""


class HashMap:
    """
    Open hash table with separate chaining and automatic resize.

    Application: SID -> student record (name, meal plan, locker).
    """

    def __init__(self, capacity: int = 8, load_factor: float = 0.75) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise HashMapError(f"capacity must be an int >= 1, got {capacity!r}")
        if not 0.1 <= load_factor <= 1.0:
            raise HashMapError(f"load_factor must be in 0.1..1.0, got {load_factor}")
        self._capacity = capacity
        self._load_factor = load_factor
        self._buckets: List[List[Tuple[Any, Any]]] = [[] for _ in range(capacity)]
        self._size = 0

    def _index(self, key: Any) -> int:
        try:
            return hash(key) % self._capacity
        except TypeError as exc:
            raise UnhashableKeyError(f"key {key!r} is not hashable") from exc

    def _resize(self, new_capacity: int) -> None:
        """
        Re-hash every pair into a larger (or smaller) table.

        Required after many inserts so chains do not grow into linear
        scans — the ID office would otherwise thumb through a whole
        drawer for every tap.
        """
        old = self._buckets
        self._capacity = new_capacity
        self._buckets = [[] for _ in range(new_capacity)]
        self._size = 0
        for chain in old:
            for key, value in chain:
                self.put(key, value)

    def put(self, key: Any, value: Any) -> None:
        """Insert or overwrite `key`. Grows the table when it is too full."""
        index = self._index(key)
        chain = self._buckets[index]
        for offset, (stored_key, _stored_value) in enumerate(chain):
            if stored_key == key:
                chain[offset] = (key, value)
                return
        chain.append((key, value))
        self._size += 1
        if self._size / self._capacity > self._load_factor:
            self._resize(self._capacity * 2)

    def get(self, key: Any, default: Any = None) -> Any:
        """Return the value for `key`, or `default` if it is missing."""
        chain = self._buckets[self._index(key)]
        for stored_key, stored_value in chain:
            if stored_key == key:
                return stored_value
        return default

    def pop(self, key: Any) -> Any:
        """Remove `key` and return its value."""
        chain = self._buckets[self._index(key)]
        for offset, (stored_key, stored_value) in enumerate(chain):
            if stored_key == key:
                del chain[offset]
                self._size -= 1
                return stored_value
        raise MissingKeyError(f"key {key!r} is not in the map")

    def contains(self, key: Any) -> bool:
        return self.get(key, default=_MISSING) is not _MISSING

    def keys(self) -> Iterator[Any]:
        for chain in self._buckets:
            for key, _value in chain:
                yield key

    def values(self) -> Iterator[Any]:
        for chain in self._buckets:
            for _key, value in chain:
                yield value

    def items(self) -> Iterator[Tuple[Any, Any]]:
        for chain in self._buckets:
            yield from chain

    def bucket_lengths(self) -> List[int]:
        """How long each chain is — used to show collisions in the demo."""
        return [len(chain) for chain in self._buckets]

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: Any) -> bool:
        return self.contains(key)

    def __getitem__(self, key: Any) -> Any:
        value = self.get(key, default=_MISSING)
        if value is _MISSING:
            raise MissingKeyError(f"key {key!r} is not in the map")
        return value

    def __setitem__(self, key: Any, value: Any) -> None:
        self.put(key, value)

    def __delitem__(self, key: Any) -> None:
        self.pop(key)

    def __iter__(self) -> Iterator[Any]:
        return self.keys()

    def __repr__(self) -> str:
        pairs = ", ".join(f"{key!r}: {value!r}" for key, value in self.items())
        return f"HashMap({{{pairs}}})"


_MISSING = object()


def seed_id_office() -> HashMap:
    """
    Load the campus ID office: SID -> student record.

    Records are ordinary dicts stored as values. The HashMap only
    hashes the SID string.
    """
    office = HashMap(capacity=8)
    roster = [
        ("R1002341", {"name": "Maya Chen", "plan": "Unlimited", "locker": "U-114"}),
        ("R1002342", {"name": "Jordan Blake", "plan": "Block 150", "locker": "U-115"}),
        ("R1008810", {"name": "Sam Ortiz", "plan": "Block 80", "locker": "S-022"}),
        ("R1001107", {"name": "Priya Shah", "plan": "Unlimited", "locker": "L-440"}),
        ("R1005520", {"name": "Lee Park", "plan": "None", "locker": "—"}),
        ("R1007781", {"name": "Chris Adeyemi", "plan": "Block 150", "locker": "U-201"}),
        ("R1009902", {"name": "Ava Nguyen", "plan": "Unlimited", "locker": "R-018"}),
        ("R1003344", {"name": "Noah Kim", "plan": "Block 80", "locker": "S-107"}),
        ("R1006677", {"name": "Riley Cole", "plan": "Unlimited", "locker": "L-119"}),
    ]
    for sid, record in roster:
        office[sid] = record
    return office


def _print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def demonstrate_hashmap() -> int:
    """Walk a card-tap at the ID office and show collisions / resize."""
    try:
        office = seed_id_office()
    except HashMapError as exc:
        print(f"Failed to open the ID office: {exc}", file=sys.stderr)
        return 1

    _print_section("1. Campus ID tap — HashMap get by SID")
    print(f"office holds {len(office)} cards; table capacity {office._capacity}")
    sid = "R1002341"
    record = office[sid]
    print(f"tap {sid} -> {record['name']}, meal={record['plan']}, locker={record['locker']}")

    _print_section("2. Insert, overwrite, delete (lost card / new locker)")
    office["R1002341"] = {**record, "locker": "U-220"}
    print(f"Maya moved lockers: {office['R1002341']}")
    office["R1999999"] = {"name": "Guest Pass", "plan": "Day", "locker": "G-001"}
    print(f"issued guest pass; size now {len(office)}")
    removed = office.pop("R1999999")
    print(f"guest expired, popped {removed['name']}; size now {len(office)}")

    _print_section("3. Collisions — more than one SID in a bucket")
    """
    hash(SID) % capacity can land two students in the same chain.
    That is expected. The chain is a short list, not a second table.
    """
    lengths = office.bucket_lengths()
    print(f"bucket lengths: {lengths}")
    print(f"longest chain: {max(lengths)}  (0 means an empty slot)")
    print("occupied buckets:")
    for index, chain in enumerate(office._buckets):
        if chain:
            keys = [key for key, _value in chain]
            print(f"  bucket {index}: {keys}")

    _print_section("4. Membership and iteration")
    print(f"'R1008810' in office? {('R1008810' in office)}")
    print(f"'R0000000' in office? {('R0000000' in office)}")
    print("all SIDs:", ", ".join(sorted(office)))

    _print_section("5. Resize — load factor crossed 0.75")
    print("inserting 20 more SIDs to force a grow...")
    before = office._capacity
    for number in range(20):
        office[f"R2{number:06d}"] = {
            "name": f"Student {number}",
            "plan": "Block 80",
            "locker": "T",
        }
    print(f"capacity {before} -> {office._capacity}; size {len(office)}")
    print(f"bucket lengths after resize: {office.bucket_lengths()}")

    _print_section("6. Expected errors")
    error_cases = [
        ("missing SID", lambda: office["NO-SUCH"]),
        ("unhashable key", lambda: office.put(["list-key"], 1)),
        ("pop missing", lambda: office.pop("NO-SUCH")),
        ("bad capacity", lambda: HashMap(capacity=0)),
    ]
    for label, action in error_cases:
        try:
            action()
            print(f"UNEXPECTED SUCCESS: {label}")
        except HashMapError as exc:
            print(f"caught {type(exc).__name__} for {label}: {exc}")
        except Exception as exc:
            print(f"caught unexpected {type(exc).__name__} for {label}: {exc}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="HashMap ADT + campus ID office demo")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("demo", help="run the ID-office walkthrough")
    lookup = sub.add_parser("lookup", help="look up one SID in the seed roster")
    lookup.add_argument("sid")
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
        command = args.command or "demo"
        if command == "demo":
            return demonstrate_hashmap()
        office = seed_id_office()
        if args.sid not in office:
            print(f"unknown SID {args.sid}", file=sys.stderr)
            return 1
        record = office[args.sid]
        print(f"{args.sid}: {record['name']}  meal={record['plan']}  locker={record['locker']}")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except HashMapError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unhandled error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
