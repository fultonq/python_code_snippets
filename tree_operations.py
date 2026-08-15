#!/usr/bin/env python3
"""
Binary tree ADT with insert, delete, and replace at index positions.

This program builds a complete binary tree named `tree_nums` with 15,335
nodes by default. Nodes are addressed by level-order (breadth-first)
indexes, the same numbering a heap uses:

    parent(i) = (i - 1) // 2
    left(i)   = 2 * i + 1
    right(i)  = 2 * i + 2

Insert adds a child of an existing node. Delete removes one node
(promoting a child, or the inorder successor when there are two).
Replace changes a node's value and leaves the shape alone.

Modes:
    python3 tree_operations.py
    python3 tree_operations.py demo
    python3 tree_operations.py interactive
    python3 tree_operations.py insert 7667 HEAD
    python3 tree_operations.py delete -- -1
    python3 tree_operations.py replace 100 42
    python3 tree_operations.py get 0
    python3 tree_operations.py show
    python3 tree_operations.py append 99
    python3 tree_operations.py find 654

Tests:
    python3 -m unittest test_tree_operations.py -v
"""

from __future__ import annotations

import argparse
import random
import shlex
import sys
from collections import deque
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Iterator, List, Optional, Sequence, Tuple


TREE_SIZE = 15335

HELP_TEXT = """
Commands (interactive mode)
---------------------------
  help                         Show this help text
  size                         Print node count, height, and root value
  show [start] [count]         Print a level-order window (default 0 10)
  get INDEX                    Print the value at level-order INDEX
  insert INDEX VALUE           Add VALUE as the next free child of INDEX
  insert-left INDEX VALUE      Add VALUE as the left child of INDEX
  insert-right INDEX VALUE     Add VALUE as the right child of INDEX
  append VALUE                 Add VALUE in the next complete-tree slot
  delete INDEX                 Remove the node at INDEX (see notes)
  delete-subtree INDEX         Remove INDEX and every descendant
  replace INDEX VALUE          Overwrite the value at INDEX
  find VALUE                   Print the first level-order index of VALUE
  inorder | preorder | postorder | level
                               Print the first 20 values of a traversal
  history [count]              Print recent mutation history (default 12)
  demo                         Run the scripted demonstration on a copy
  quit                         Exit interactive mode

INDEX is a level-order position (0 is the root; -1 is the last node).
Insert on an empty tree is allowed only at index 0. Delete of a leaf
unlinks it. One child is promoted. Two children: the inorder successor
moves up and that successor node is removed.
""".strip()


class TreeOperationError(Exception):
    """
    Base exception for every tree_nums mutation failure.

    Catch this type when a caller wants insert, delete, and replace
    errors as a single family of problems.
    """


class InvalidIndexError(TreeOperationError, IndexError):
    """Raised when a level-order index does not identify a live node."""


class InvalidValueError(TreeOperationError, ValueError):
    """Raised when a value, side, or count argument cannot be used."""


class EmptyTreeError(TreeOperationError):
    """Raised when get / delete / replace needs a node but the tree is empty."""


class OccupiedSlotError(TreeOperationError, ValueError):
    """Raised when inserting into a child pointer that is already set."""


class CommandParseError(TreeOperationError):
    """Raised when an interactive or CLI command cannot be parsed."""


def parse_cli_value(raw: str) -> Any:
    """
    Convert a user-supplied token into a stored node value.

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
        raise InvalidIndexError(f"index must be an int, got {raw!r}") from exc


class TreeNode:
    """One node in the binary tree ADT: a value and two optional children."""

    def __init__(self, value: Any) -> None:
        self.value = value
        self.left: Optional[TreeNode] = None
        self.right: Optional[TreeNode] = None
        self.parent: Optional[TreeNode] = None

    def __repr__(self) -> str:
        return f"TreeNode({self.value!r})"


class TreeManager:
    """
    Binary tree ADT addressed by level-order indexes.

    The structure is a real linked tree (not a disguised list). Index 0
    is always the root of the live tree. After a delete, remaining nodes
    are re-numbered in breadth-first order, the same way an array shifts
    after a pop.
    """

    def __init__(
        self,
        size: int = TREE_SIZE,
        seed: Optional[int] = None,
        values: Optional[Iterable[Any]] = None,
    ) -> None:
        """
        Build a complete binary tree.

        If `values` is given, those items become the level-order contents.
        Otherwise the tree is filled with `size` deterministic integers
        in the range [0, 999] using `seed` (default 42).
        """
        if values is not None:
            items = list(values)
        else:
            if isinstance(size, bool) or not isinstance(size, int):
                raise InvalidValueError(
                    f"size must be an integer, got {type(size).__name__}"
                )
            if size < 0:
                raise InvalidValueError(f"size must be >= 0, got {size}")
            rng = random.Random(42 if seed is None else seed)
            items = [rng.randint(0, 999) for _ in range(size)]

        self.root: Optional[TreeNode] = self._build_complete(items)
        self._size = len(items)
        self.history: List[str] = [
            f"initialized tree_nums with {self._size} node(s)"
        ]

    @staticmethod
    def _build_complete(items: Sequence[Any]) -> Optional[TreeNode]:
        """
        Link `items` into a complete binary tree in level order.

        Index i gets left child 2*i+1 and right child 2*i+2 when those
        positions fall inside the list. Parent pointers are set so
        delete can unlink a node in O(1) after it has been located.
        """
        if not items:
            return None
        nodes = [TreeNode(value) for value in items]
        for index, node in enumerate(nodes):
            left = 2 * index + 1
            right = 2 * index + 2
            if left < len(nodes):
                node.left = nodes[left]
                nodes[left].parent = node
            if right < len(nodes):
                node.right = nodes[right]
                nodes[right].parent = node
        return nodes[0]

    def __len__(self) -> int:
        return self._size

    def __repr__(self) -> str:
        preview = self.snapshot(0, 8)
        suffix = "..." if self._size > 8 else ""
        return (
            f"TreeManager(size={self._size}, height={self.height()}, "
            f"level_order={preview}{suffix})"
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

    def _nodes(self) -> List[TreeNode]:
        """Return every live node in level order."""
        if self.root is None:
            return []
        ordered: List[TreeNode] = []
        queue: deque[TreeNode] = deque([self.root])
        while queue:
            node = queue.popleft()
            ordered.append(node)
            if node.left is not None:
                queue.append(node.left)
            if node.right is not None:
                queue.append(node.right)
        return ordered

    def _node_at(self, index: Any, operation: str = "access") -> Tuple[TreeNode, int]:
        """Resolve a level-order index to a live node and its normalized index."""
        nodes = self._nodes()
        if not nodes:
            raise EmptyTreeError(f"cannot {operation}: tree_nums is empty")
        index = self._require_int("index", index)
        if index < 0:
            index += len(nodes)
        if index < 0 or index >= len(nodes):
            raise InvalidIndexError(
                f"{operation} index is out of range for size {len(nodes)}; "
                f"valid range is 0..{len(nodes) - 1}"
            )
        return nodes[index], index

    def _clone(self, node: Optional[TreeNode], parent: Optional[TreeNode] = None) -> Optional[TreeNode]:
        """Deep-copy a subtree, preserving parent links."""
        if node is None:
            return None
        copied = TreeNode(node.value)
        copied.parent = parent
        copied.left = self._clone(node.left, copied)
        copied.right = self._clone(node.right, copied)
        return copied

    @contextmanager
    def _atomic(self) -> Iterator[None]:
        """
        Restore the tree and history if a bulk operation fails.

        Single-node insert / delete / replace stay eager. Bulk helpers
        either fully apply or leave tree_nums unchanged.
        """
        backup_root = self._clone(self.root)
        backup_size = self._size
        backup_hist = len(self.history)
        try:
            yield
        except Exception:
            self.root = backup_root
            self._size = backup_size
            del self.history[backup_hist:]
            raise

    def _depth(self, node: TreeNode) -> int:
        depth = 0
        while node.parent is not None:
            node = node.parent
            depth += 1
        return depth

    def _subtree_size(self, node: Optional[TreeNode]) -> int:
        if node is None:
            return 0
        return 1 + self._subtree_size(node.left) + self._subtree_size(node.right)

    def height(self) -> int:
        """Return the number of edges on the longest root-to-leaf path, or -1 if empty."""

        def _height(node: Optional[TreeNode]) -> int:
            if node is None:
                return -1
            return 1 + max(_height(node.left), _height(node.right))

        return _height(self.root)

    def get(self, index: Any) -> Any:
        """Return the value at level-order `index` without changing the tree."""
        try:
            node, _normalized = self._node_at(index, "get")
            return node.value
        except TreeOperationError:
            raise
        except Exception as exc:
            raise TreeOperationError(
                f"unexpected failure during get at {index!r}: {exc}"
            ) from exc

    def find(self, value: Any) -> int:
        """Return the first level-order index of `value`."""
        for index, node in enumerate(self._nodes()):
            if node.value == value:
                return index
        raise InvalidValueError(f"value {value!r} not found in tree_nums")

    def snapshot(self, start: int = 0, count: int = 10) -> List[Any]:
        """Return a copy of a short level-order window."""
        start = self._require_int("start", start)
        count = self._require_int("count", count)
        if start < 0:
            raise InvalidIndexError(f"snapshot start must be >= 0, got {start}")
        if count < 0:
            raise InvalidValueError(f"snapshot count must be >= 0, got {count}")
        values = [node.value for node in self._nodes()]
        return values[start : start + count]

    def level_order(self) -> List[Any]:
        return [node.value for node in self._nodes()]

    def preorder(self) -> List[Any]:
        result: List[Any] = []

        def walk(node: Optional[TreeNode]) -> None:
            if node is None:
                return
            result.append(node.value)
            walk(node.left)
            walk(node.right)

        walk(self.root)
        return result

    def inorder(self) -> List[Any]:
        result: List[Any] = []

        def walk(node: Optional[TreeNode]) -> None:
            if node is None:
                return
            walk(node.left)
            result.append(node.value)
            walk(node.right)

        walk(self.root)
        return result

    def postorder(self) -> List[Any]:
        result: List[Any] = []

        def walk(node: Optional[TreeNode]) -> None:
            if node is None:
                return
            walk(node.left)
            walk(node.right)
            result.append(node.value)

        walk(self.root)
        return result

    def _index_of_node(self, target: TreeNode) -> int:
        for index, node in enumerate(self._nodes()):
            if node is target:
                return index
        raise InvalidIndexError("node is no longer in tree_nums")

    def _attach(self, parent: TreeNode, side: str, value: Any) -> int:
        child = TreeNode(value)
        child.parent = parent
        if side == "left":
            if parent.left is not None:
                raise OccupiedSlotError("left child is already occupied")
            parent.left = child
        elif side == "right":
            if parent.right is not None:
                raise OccupiedSlotError("right child is already occupied")
            parent.right = child
        else:
            raise InvalidValueError(f"side must be 'left' or 'right', got {side!r}")
        self._size += 1
        new_index = self._index_of_node(child)
        self.history.append(
            f"insert {value!r} as {side} child of parent value={parent.value!r} "
            f"(new index={new_index}, size now {self._size})"
        )
        return new_index

    def insert_left(self, parent_index: Any, value: Any) -> int:
        """Insert `value` as the left child of the node at `parent_index`."""
        try:
            parent, _idx = self._node_at(parent_index, "insert-left")
            return self._attach(parent, "left", value)
        except TreeOperationError:
            raise
        except Exception as exc:
            raise TreeOperationError(
                f"unexpected failure during insert-left at {parent_index!r}: {exc}"
            ) from exc

    def insert_right(self, parent_index: Any, value: Any) -> int:
        """Insert `value` as the right child of the node at `parent_index`."""
        try:
            parent, _idx = self._node_at(parent_index, "insert-right")
            return self._attach(parent, "right", value)
        except TreeOperationError:
            raise
        except Exception as exc:
            raise TreeOperationError(
                f"unexpected failure during insert-right at {parent_index!r}: {exc}"
            ) from exc

    def insert(self, parent_index: Any, value: Any) -> int:
        """
        Insert `value` as the next free child of `parent_index`.

        Left is preferred when both slots are open. On an empty tree the
        only valid parent index is 0, which creates the root.
        """
        try:
            if self.root is None:
                index = self._require_int("index", parent_index)
                if index not in (0, -1):
                    raise InvalidIndexError(
                        "empty tree only accepts insert at index 0"
                    )
                self.root = TreeNode(value)
                self._size = 1
                self.history.append(f"insert root value={value!r}")
                return 0
            parent, pidx = self._node_at(parent_index, "insert")
            if parent.left is None:
                return self._attach(parent, "left", value)
            if parent.right is None:
                return self._attach(parent, "right", value)
            raise OccupiedSlotError(
                f"node {pidx} already has left and right children"
            )
        except TreeOperationError:
            raise
        except Exception as exc:
            raise TreeOperationError(
                f"unexpected failure during insert at {parent_index!r}: {exc}"
            ) from exc

    def append(self, value: Any) -> int:
        """
        Insert `value` in the next slot that keeps the tree complete.

        That is the left child of the first node in level order that is
        missing a left child, otherwise that node's right child.
        """
        try:
            if self.root is None:
                return self.insert(0, value)
            for node in self._nodes():
                if node.left is None:
                    return self._attach(node, "left", value)
                if node.right is None:
                    return self._attach(node, "right", value)
            raise TreeOperationError("complete tree had no free child slot")
        except TreeOperationError:
            raise
        except Exception as exc:
            raise TreeOperationError(
                f"unexpected failure during append: {exc}"
            ) from exc

    def replace(self, index: Any, value: Any) -> Any:
        """Overwrite the value at `index` and return the previous value."""
        try:
            node, normalized = self._node_at(index, "replace")
            previous = node.value
            node.value = value
            self.history.append(
                f"replace index={normalized} {previous!r} -> {value!r}"
            )
            return previous
        except TreeOperationError:
            raise
        except Exception as exc:
            raise TreeOperationError(
                f"unexpected failure during replace at {index!r}: {exc}"
            ) from exc

    def _transplant(self, old: TreeNode, new: Optional[TreeNode]) -> None:
        """Replace subtree `old` with `new` in `old`'s parent (or as root)."""
        if old.parent is None:
            self.root = new
        elif old is old.parent.left:
            old.parent.left = new
        else:
            old.parent.right = new
        if new is not None:
            new.parent = old.parent

    def _minimum(self, node: TreeNode) -> TreeNode:
        while node.left is not None:
            node = node.left
        return node

    def _delete_node(self, node: TreeNode) -> Any:
        """
        Remove `node` using standard binary-tree deletion.

        Zero children: unlink. One child: the child takes this place.
        Two children: the inorder successor (leftmost node of the right
        subtree) is lifted into this place, then the successor node is
        removed. This is the CLRS transplant algorithm and does not
        require the tree to be a BST.
        """
        removed = node.value
        if node.left is None:
            self._transplant(node, node.right)
        elif node.right is None:
            self._transplant(node, node.left)
        else:
            successor = self._minimum(node.right)
            if successor.parent is not node:
                self._transplant(successor, successor.right)
                successor.right = node.right
                successor.right.parent = successor
            self._transplant(node, successor)
            successor.left = node.left
            successor.left.parent = successor
        node.left = node.right = node.parent = None
        self._size -= 1
        return removed

    def delete(self, index: Any) -> Any:
        """Remove the node at level-order `index` and return its value."""
        try:
            node, normalized = self._node_at(index, "delete")
            removed = self._delete_node(node)
            self.history.append(
                f"delete index={normalized} removed={removed!r} "
                f"(size now {self._size})"
            )
            return removed
        except TreeOperationError:
            raise
        except Exception as exc:
            raise TreeOperationError(
                f"unexpected failure during delete at {index!r}: {exc}"
            ) from exc

    def delete_subtree(self, index: Any) -> Any:
        """Remove the node at `index` and every descendant; return the root value."""
        try:
            node, normalized = self._node_at(index, "delete-subtree")
            removed = node.value
            count = self._subtree_size(node)
            self._transplant(node, None)
            node.left = node.right = node.parent = None
            self._size -= count
            self.history.append(
                f"delete-subtree index={normalized} removed={removed!r} "
                f"and {count - 1} descendant(s) (size now {self._size})"
            )
            return removed
        except TreeOperationError:
            raise
        except Exception as exc:
            raise TreeOperationError(
                f"unexpected failure during delete-subtree at {index!r}: {exc}"
            ) from exc

    def insert_many(self, pairs: Sequence[Tuple[Any, Any]]) -> int:
        """
        Insert several (parent_index, value) pairs in order.

        Each parent index is resolved against the tree as it exists just
        before that pair runs. Failure rolls back the whole batch.
        """
        if not isinstance(pairs, (list, tuple)):
            raise InvalidValueError(
                "insert_many expects a sequence of (parent_index, value) pairs"
            )
        with self._atomic():
            applied = 0
            for item in pairs:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    raise InvalidValueError(
                        f"each insert pair must be (parent_index, value), got {item!r}"
                    )
                self.insert(item[0], item[1])
                applied += 1
            return applied

    def delete_many(self, indexes: Sequence[Any]) -> List[Any]:
        """
        Delete several nodes, deepest first.

        Indexes are resolved up front. Descendants are removed before
        ancestors so a parent delete does not yank a still-pending child
        out from under the caller. Duplicates are rejected.
        """
        if not isinstance(indexes, (list, tuple)):
            raise InvalidValueError("delete_many expects a sequence of indexes")
        if len(indexes) == 0:
            return []
        located = [self._node_at(index, "delete") for index in indexes]
        nodes = [item[0] for item in located]
        if len({id(node) for node in nodes}) != len(nodes):
            raise InvalidValueError(
                f"delete_many received duplicate indexes: {indexes!r}"
            )
        ranked = sorted(nodes, key=self._depth, reverse=True)
        with self._atomic():
            removed: List[Any] = []
            for node in ranked:
                removed.append(self._delete_node(node))
                self.history.append(
                    f"delete (bulk) removed={removed[-1]!r} (size now {self._size})"
                )
            return removed

    def replace_many(self, pairs: Sequence[Tuple[Any, Any]]) -> List[Any]:
        """Replace several (index, value) pairs; return previous values."""
        if not isinstance(pairs, (list, tuple)):
            raise InvalidValueError(
                "replace_many expects a sequence of (index, value) pairs"
            )
        prepared: List[Tuple[TreeNode, Any]] = []
        for item in pairs:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise InvalidValueError(
                    f"each replace pair must be (index, value), got {item!r}"
                )
            node, _idx = self._node_at(item[0], "replace")
            prepared.append((node, item[1]))
        with self._atomic():
            previous_values: List[Any] = []
            for node, value in prepared:
                previous_values.append(node.value)
                node.value = value
                self.history.append(
                    f"replace (bulk) {previous_values[-1]!r} -> {value!r}"
                )
            return previous_values


def _print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _run_step(label: str, action: Callable[[], None]) -> bool:
    """Run one demonstration step and keep going if it fails."""
    try:
        action()
        return True
    except TreeOperationError as exc:
        print(f"operation error during {label}: {type(exc).__name__}: {exc}")
        return False
    except Exception as exc:
        print(f"unexpected error during {label}: {type(exc).__name__}: {exc}")
        return False


def demonstrate_operations(manager: Optional[TreeManager] = None) -> int:
    """
    Walk through insert, delete, and replace on tree_nums.

    Valid mutations and expected failures are both shown. Returns 0 when
    the demonstration finishes without an unexpected crash.
    """
    try:
        if manager is None:
            manager = TreeManager(size=TREE_SIZE, seed=42)
    except TreeOperationError as exc:
        print(f"Failed to create tree_nums: {exc}", file=sys.stderr)
        return 1

    _print_section("1. Initial tree_nums")
    print(f"size: {len(manager)}")
    print(f"height: {manager.height()}")
    print(f"root: {manager.get(0)!r}")
    print(f"first 10 (level order): {manager.snapshot(0, 10)}")
    print(f"object: {manager}")

    _print_section("2. Insert at several positions")
    """
    A complete tree of 15,335 nodes has no free child under the root.
    append() fills the next complete-tree hole. insert() is also used
    on a node that still has an open child slot after those appends.
    """
    insert_plan = [
        ("append", None, "LEAF-A"),
        ("append", None, "LEAF-B"),
        ("insert", 0, None),
        ("insert-left", -1, "LEFT-OF-LAST"),
        ("insert-right", -2, "RIGHT-NEAR-LAST"),
    ]
    for kind, index, value in insert_plan:
        def _insert(kind=kind, index=index, value=value) -> None:
            before = len(manager)
            if kind == "append":
                new_index = manager.append(value)
                print(
                    f"appended {value!r:16} at index {new_index} "
                    f"-> size {before} to {len(manager)}"
                )
                return
            if kind == "insert":
                """Try the root first; if both children exist, append instead."""
                try:
                    new_index = manager.insert(0, "CHILD-OF-ROOT")
                    print(
                        f"inserted 'CHILD-OF-ROOT' under index 0 "
                        f"at new index {new_index}"
                    )
                except OccupiedSlotError as exc:
                    new_index = manager.append("CHILD-FALLBACK")
                    print(
                        f"root children occupied ({exc}); "
                        f"appended 'CHILD-FALLBACK' at {new_index}"
                    )
                return
            if kind == "insert-left":
                new_index = manager.insert_left(index, value)
                print(
                    f"insert-left {value!r} under {index!r} "
                    f"-> new index {new_index}; size {len(manager)}"
                )
                return
            new_index = manager.insert_right(index, value)
            print(
                f"insert-right {value!r} under {index!r} "
                f"-> new index {new_index}; size {len(manager)}"
            )

        _run_step(f"{kind} {value!r}", _insert)

    _print_section("3. Replace at several positions")
    replace_plan = [
        (0, "REPLACED-ROOT"),
        (100, 100001),
        (5000, 500001),
        (len(manager) - 1, "REPLACED-LAST"),
        (-2, "REPLACED-NEAR-LAST"),
    ]
    for index, value in replace_plan:
        def _replace(index=index, value=value) -> None:
            previous = manager.replace(index, value)
            print(f"replaced index {index!r:>6}: {previous!r} -> {value!r}")

        _run_step(f"replace at {index!r}", _replace)

    _print_section("4. Delete at several positions")
    """
    Delete a leaf (last node), a middle internal node, and then a node
    that still has two children. Indexes are resolved at call time so
    they stay valid after earlier deletes.
    """
    delete_plan = ["LAST", 50, 1000, 0]
    for requested in delete_plan:
        def _delete(requested=requested) -> None:
            index = len(manager) - 1 if requested == "LAST" else requested
            removed = manager.delete(index)
            print(
                f"deleted index {index!r:>6}: removed {removed!r}; "
                f"size now {len(manager)}"
            )

        _run_step(f"delete {requested!r}", _delete)

    _print_section("5. Bulk insert / replace / delete")

    def _bulk() -> None:
        """
        Bulk insert uses parent indexes that still have a free child.
        After appends above, the tree may not be complete, so append
        three times first, then replace and delete known live indexes.
        """
        for label in ("BULK-A", "BULK-B", "BULK-C"):
            manager.append(label)
        print(f"bulk appends done; size {len(manager)}")
        previous = manager.replace_many([(1, "BULK-LEFT"), (2, "BULK-RIGHT")])
        print(f"bulk replace previous values: {previous}")
        removed = manager.delete_many([len(manager) - 1, len(manager) - 2])
        print(f"bulk delete removed: {removed}")
        print(f"size after bulk work: {len(manager)}")

    _run_step("bulk mutations", _bulk)

    _print_section("6. Exception handling (expected failures)")
    error_cases = [
        ("insert under a full internal node", lambda: manager.insert(0, "X")),
        ("insert-left with a float index", lambda: manager.insert_left(3.14, "X")),
        ("insert with a bool index", lambda: manager.insert(True, "X")),
        ("delete far past the end", lambda: manager.delete(10**7)),
        ("delete with a string index", lambda: manager.delete("root")),
        ("replace with None as index", lambda: manager.replace(None, 1)),
        ("replace on empty tree", lambda: TreeManager(size=0).replace(0, 1)),
        ("delete on empty tree", lambda: TreeManager(size=0).delete(0)),
        ("insert on empty tree at 5", lambda: TreeManager(size=0).insert(5, "X")),
        ("insert_many bad pair", lambda: manager.insert_many([(0,)])),
        ("negative size", lambda: TreeManager(size=-1)),
    ]
    for label, action in error_cases:
        try:
            action()
            print(f"UNEXPECTED SUCCESS: {label}")
        except TreeOperationError as exc:
            print(f"caught {type(exc).__name__} for {label}: {exc}")
        except Exception as exc:
            print(f"caught unexpected {type(exc).__name__} for {label}: {exc}")

    _print_section("7. Final state")
    print(f"final size: {len(manager)}")
    print(f"final height: {manager.height()}")
    print(f"first 10 (level order): {manager.snapshot(0, 10)}")
    print(f"first 10 (inorder):     {manager.inorder()[:10]}")
    print(f"history entries: {len(manager.history)}")
    print("last 8 history lines:")
    for line in manager.history[-8:]:
        print(f"  - {line}")

    return 0


def handle_repl_line(manager: TreeManager, line: str) -> Tuple[str, bool]:
    """
    Execute one interactive command against `manager`.

    Returns (message, should_quit). Blank lines produce an empty message
    and do not exit.
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
    if command in {"size", "length", "len"}:
        root = "empty" if manager.root is None else repr(manager.get(0))
        return (
            f"size: {len(manager)}; height: {manager.height()}; root: {root}"
        ), False
    if command == "show":
        start = parse_index_token(args[0]) if len(args) >= 1 else 0
        count = parse_index_token(args[1]) if len(args) >= 2 else 10
        window = manager.snapshot(start, count)
        return (
            f"level_order[{start}:{start + count}] ({len(window)} item(s)): {window}"
        ), False
    if command == "get":
        if len(args) != 1:
            raise CommandParseError("usage: get INDEX")
        index = parse_index_token(args[0])
        return f"tree_nums[{index}] = {manager.get(index)!r}", False
    if command in {"insert-left", "insert_left"}:
        if len(args) < 2:
            raise CommandParseError("usage: insert-left INDEX VALUE")
        index = parse_index_token(args[0])
        value = parse_cli_value(" ".join(args[1:]))
        new_index = manager.insert_left(index, value)
        return (
            f"inserted {value!r} as left child; new index {new_index}; "
            f"size {len(manager)}"
        ), False
    if command in {"insert-right", "insert_right"}:
        if len(args) < 2:
            raise CommandParseError("usage: insert-right INDEX VALUE")
        index = parse_index_token(args[0])
        value = parse_cli_value(" ".join(args[1:]))
        new_index = manager.insert_right(index, value)
        return (
            f"inserted {value!r} as right child; new index {new_index}; "
            f"size {len(manager)}"
        ), False
    if command == "insert":
        if len(args) < 2:
            raise CommandParseError("usage: insert INDEX VALUE")
        index = parse_index_token(args[0])
        value = parse_cli_value(" ".join(args[1:]))
        new_index = manager.insert(index, value)
        return (
            f"inserted {value!r} under {index}; new index {new_index}; "
            f"size {len(manager)}"
        ), False
    if command == "append":
        if len(args) < 1:
            raise CommandParseError("usage: append VALUE")
        value = parse_cli_value(" ".join(args))
        new_index = manager.append(value)
        return (
            f"appended {value!r} at {new_index}; size {len(manager)}"
        ), False
    if command == "delete":
        if len(args) != 1:
            raise CommandParseError("usage: delete INDEX")
        index = parse_index_token(args[0])
        removed = manager.delete(index)
        return (
            f"deleted {removed!r} from {index}; size {len(manager)}"
        ), False
    if command in {"delete-subtree", "delete_subtree"}:
        if len(args) != 1:
            raise CommandParseError("usage: delete-subtree INDEX")
        index = parse_index_token(args[0])
        removed = manager.delete_subtree(index)
        return (
            f"deleted subtree rooted at {removed!r}; size {len(manager)}"
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
    if command in {"inorder", "preorder", "postorder", "level"}:
        walker = {
            "inorder": manager.inorder,
            "preorder": manager.preorder,
            "postorder": manager.postorder,
            "level": manager.level_order,
        }[command]
        values = walker()[:20]
        return f"{command} (first {len(values)}): {values}", False
    if command == "history":
        count = parse_index_token(args[0]) if args else 12
        if count < 0:
            raise InvalidValueError(f"history count must be >= 0, got {count}")
        lines = manager.history[-count:]
        if not lines:
            return "(history is empty)", False
        return "\n".join(f"  - {entry}" for entry in lines), False
    if command == "demo":
        demo_manager = TreeManager(values=manager.level_order())
        demonstrate_operations(demo_manager)
        return "demonstration finished (interactive tree was not changed).", False

    raise CommandParseError(
        f"unknown command {command!r}; type 'help' for a list"
    )


def run_interactive(
    manager: TreeManager,
    input_fn: Callable[[str], str] = input,
) -> int:
    """Read commands until the user quits or stdin closes."""
    print("tree_nums interactive mode. Type 'help' for commands, 'quit' to exit.")
    print(f"starting size: {len(manager)}; height: {manager.height()}")
    while True:
        try:
            line = input_fn(f"tree_nums[{len(manager)}]> ")
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
        except TreeOperationError as exc:
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
            "Insert, delete, and replace values in tree_nums, "
            "a binary tree of 15,335 nodes by default."
        )
    )
    parser.add_argument(
        "--size",
        type=int,
        default=TREE_SIZE,
        help=f"initial node count when --values is not set (default {TREE_SIZE})",
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
        help="comma-separated level-order starting values; overrides --size",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("demo", help="run the scripted insert/delete/replace walkthrough")
    sub.add_parser("interactive", help="open the command prompt")

    insert_parser = sub.add_parser("insert", help="insert VALUE under parent INDEX")
    insert_parser.add_argument("index", help="parent index (use -- before a negative)")
    insert_parser.add_argument("value", nargs="+", help="value to insert")

    left_parser = sub.add_parser("insert-left", help="insert VALUE as left child")
    left_parser.add_argument("index")
    left_parser.add_argument("value", nargs="+")

    right_parser = sub.add_parser("insert-right", help="insert VALUE as right child")
    right_parser.add_argument("index")
    right_parser.add_argument("value", nargs="+")

    delete_parser = sub.add_parser("delete", help="delete the node at INDEX")
    delete_parser.add_argument("index")

    subtree_parser = sub.add_parser("delete-subtree", help="delete INDEX and descendants")
    subtree_parser.add_argument("index")

    replace_parser = sub.add_parser("replace", help="replace INDEX with VALUE")
    replace_parser.add_argument("index")
    replace_parser.add_argument("value", nargs="+")

    get_parser = sub.add_parser("get", help="print the node at INDEX")
    get_parser.add_argument("index")

    show_parser = sub.add_parser("show", help="print a level-order window")
    show_parser.add_argument("start", nargs="?", default="0")
    show_parser.add_argument("count", nargs="?", default="10")

    append_parser = sub.add_parser("append", help="insert VALUE in the next complete slot")
    append_parser.add_argument("value", nargs="+")

    find_parser = sub.add_parser("find", help="print the first index of VALUE")
    find_parser.add_argument("value", nargs="+")

    return parser


def _manager_from_args(args: argparse.Namespace) -> TreeManager:
    if args.values is not None:
        raw_items = [item.strip() for item in args.values.split(",")]
        parsed = [parse_cli_value(item) for item in raw_items if item != ""]
        return TreeManager(values=parsed)
    return TreeManager(size=args.size, seed=args.seed)


def dispatch(args: argparse.Namespace) -> int:
    """Run the selected CLI command against a freshly built tree_nums."""
    command = args.command or "demo"
    manager = _manager_from_args(args)

    if command == "demo":
        return demonstrate_operations(manager)
    if command == "interactive":
        return run_interactive(manager)
    if command == "insert":
        index = parse_index_token(args.index)
        value = parse_cli_value(" ".join(args.value))
        new_index = manager.insert(index, value)
        print(
            f"inserted {value!r} under {index} at new index {new_index}; "
            f"size {len(manager)}"
        )
        return 0
    if command == "insert-left":
        index = parse_index_token(args.index)
        value = parse_cli_value(" ".join(args.value))
        new_index = manager.insert_left(index, value)
        print(f"inserted {value!r} as left child at {new_index}; size {len(manager)}")
        return 0
    if command == "insert-right":
        index = parse_index_token(args.index)
        value = parse_cli_value(" ".join(args.value))
        new_index = manager.insert_right(index, value)
        print(f"inserted {value!r} as right child at {new_index}; size {len(manager)}")
        return 0
    if command == "delete":
        index = parse_index_token(args.index)
        removed = manager.delete(index)
        print(f"deleted {removed!r} from {index}; size {len(manager)}")
        return 0
    if command == "delete-subtree":
        index = parse_index_token(args.index)
        removed = manager.delete_subtree(index)
        print(f"deleted subtree rooted at {removed!r}; size {len(manager)}")
        return 0
    if command == "replace":
        index = parse_index_token(args.index)
        value = parse_cli_value(" ".join(args.value))
        previous = manager.replace(index, value)
        print(f"replaced {previous!r} with {value!r} at {index}")
        return 0
    if command == "get":
        index = parse_index_token(args.index)
        print(f"tree_nums[{index}] = {manager.get(index)!r}")
        return 0
    if command == "show":
        start = parse_index_token(args.start)
        count = parse_index_token(args.count)
        window = manager.snapshot(start, count)
        print(f"size: {len(manager)}; height: {manager.height()}")
        print(f"level_order[{start}:{start + count}] = {window}")
        return 0
    if command == "append":
        value = parse_cli_value(" ".join(args.value))
        new_index = manager.append(value)
        print(f"appended {value!r} at {new_index}; size {len(manager)}")
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
    except TreeOperationError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unhandled error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
