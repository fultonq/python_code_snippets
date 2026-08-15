#!/usr/bin/env python3
"""
Graph ADT and algorithms, plus two campus application demos.

Algorithms
----------
BFS                 fewest shuttle hops between buildings
DFS                 explore every reachable stop / walk one branch
Dijkstra            fastest ride when edges are minutes
topological sort    legal order to take courses given prerequisites
connected components isolated shuttle networks (night vs day)
cycle detection     broken prerequisite catalog

Real-world demos
----------------
1. Riverside shuttle map — weighted undirected graph of campus stops.
2. Degree planner — directed course-prerequisite graph.

    python3 graph_algorithms.py
    python3 graph_algorithms.py demo
    python3 graph_algorithms.py path Union Stadium
    python3 graph_algorithms.py plan
    python3 -m unittest test_graph_algorithms.py -v
"""

from __future__ import annotations

import argparse
import heapq
import sys
from collections import deque
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


class GraphError(Exception):
    """Base exception for graph operations."""


class UnknownVertexError(GraphError, KeyError):
    """Raised when an algorithm is pointed at a stop / course that is not on the map."""


class Graph:
    """
    Adjacency-list graph.

    Edges are (neighbor, weight). Shuttle minutes use weight > 0.
    Course prerequisites use weight 1 and `directed=True`.
    """

    def __init__(self, directed: bool = False) -> None:
        self.directed = directed
        self._adj: Dict[Any, List[Tuple[Any, float]]] = {}

    def add_vertex(self, vertex: Any) -> None:
        self._adj.setdefault(vertex, [])

    def add_edge(self, source: Any, target: Any, weight: float = 1.0) -> None:
        if weight < 0:
            raise GraphError(f"weight must be >= 0, got {weight}")
        self.add_vertex(source)
        self.add_vertex(target)
        self._adj[source].append((target, float(weight)))
        if not self.directed:
            self._adj[target].append((source, float(weight)))

    def vertices(self) -> List[Any]:
        return list(self._adj)

    def neighbors(self, vertex: Any) -> List[Tuple[Any, float]]:
        if vertex not in self._adj:
            raise UnknownVertexError(f"unknown vertex {vertex!r}")
        return list(self._adj[vertex])

    def __contains__(self, vertex: Any) -> bool:
        return vertex in self._adj

    def __len__(self) -> int:
        return len(self._adj)

    def __repr__(self) -> str:
        kind = "directed" if self.directed else "undirected"
        return f"Graph({kind}, {len(self)} vertices)"

    def _require(self, vertex: Any) -> None:
        if vertex not in self._adj:
            raise UnknownVertexError(f"unknown vertex {vertex!r}")

    def bfs(self, start: Any) -> List[Any]:
        """
        Breadth-first search: visit by hop count.

        Shuttle analog: the fewest transfers from `start`, ignoring
        how long each leg takes.
        """
        self._require(start)
        seen: Set[Any] = {start}
        order: List[Any] = []
        queue: deque[Any] = deque([start])
        while queue:
            vertex = queue.popleft()
            order.append(vertex)
            for neighbor, _weight in self._adj[vertex]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return order

    def dfs(self, start: Any) -> List[Any]:
        """Depth-first search: walk one branch as far as it goes."""
        self._require(start)
        seen: Set[Any] = set()
        order: List[Any] = []

        def walk(vertex: Any) -> None:
            seen.add(vertex)
            order.append(vertex)
            for neighbor, _weight in self._adj[vertex]:
                if neighbor not in seen:
                    walk(neighbor)

        walk(start)
        return order

    def shortest_hops(self, start: Any, goal: Any) -> List[Any]:
        """BFS path with the fewest edges (unweighted)."""
        self._require(start)
        self._require(goal)
        if start == goal:
            return [start]
        previous: Dict[Any, Any] = {start: None}
        queue: deque[Any] = deque([start])
        while queue:
            vertex = queue.popleft()
            for neighbor, _weight in self._adj[vertex]:
                if neighbor in previous:
                    continue
                previous[neighbor] = vertex
                if neighbor == goal:
                    return _rebuild_path(previous, goal)
                queue.append(neighbor)
        raise GraphError(f"no path from {start!r} to {goal!r}")

    def dijkstra(
        self, start: Any, goal: Optional[Any] = None
    ) -> Tuple[Dict[Any, float], Dict[Any, Any]]:
        """
        Dijkstra: smallest total weight from `start`.

        Shuttle analog: fastest ride in minutes, not fewest stops.
        Returns (distance, previous) maps. Unreachable vertices are
        omitted from `distance`.
        """
        self._require(start)
        if goal is not None:
            self._require(goal)
        distance: Dict[Any, float] = {start: 0.0}
        previous: Dict[Any, Any] = {start: None}
        heap: List[Tuple[float, int, Any]] = [(0.0, 0, start)]
        tie = 1
        seen: Set[Any] = set()
        while heap:
            cost, _seq, vertex = heapq.heappop(heap)
            if vertex in seen:
                continue
            seen.add(vertex)
            if goal is not None and vertex == goal:
                break
            for neighbor, weight in self._adj[vertex]:
                candidate = cost + weight
                if neighbor not in distance or candidate < distance[neighbor]:
                    distance[neighbor] = candidate
                    previous[neighbor] = vertex
                    heapq.heappush(heap, (candidate, tie, neighbor))
                    tie += 1
        return distance, previous

    def shortest_weighted_path(self, start: Any, goal: Any) -> Tuple[List[Any], float]:
        distance, previous = self.dijkstra(start, goal)
        if goal not in distance:
            raise GraphError(f"no path from {start!r} to {goal!r}")
        return _rebuild_path(previous, goal), distance[goal]

    def connected_components(self) -> List[List[Any]]:
        """Undirected components. Night shuttles that never meet day routes."""
        if self.directed:
            raise GraphError("connected_components is for undirected graphs")
        remaining = set(self._adj)
        components: List[List[Any]] = []
        while remaining:
            start = next(iter(remaining))
            group = self.bfs(start)
            remaining.difference_update(group)
            components.append(group)
        return components

    def has_cycle(self) -> bool:
        """
        Directed: color DFS (white/gray/black).
        Undirected: DFS with parent tracking.
        """
        if self.directed:
            return self._directed_cycle()
        return self._undirected_cycle()

    def _directed_cycle(self) -> bool:
        white, gray, black = 0, 1, 2
        color = {vertex: white for vertex in self._adj}

        def walk(vertex: Any) -> bool:
            color[vertex] = gray
            for neighbor, _weight in self._adj[vertex]:
                if color[neighbor] == gray:
                    return True
                if color[neighbor] == white and walk(neighbor):
                    return True
            color[vertex] = black
            return False

        return any(walk(vertex) for vertex in self._adj if color[vertex] == white)

    def _undirected_cycle(self) -> bool:
        seen: Set[Any] = set()

        def walk(vertex: Any, parent: Any) -> bool:
            seen.add(vertex)
            for neighbor, _weight in self._adj[vertex]:
                if neighbor == parent:
                    continue
                if neighbor in seen or walk(neighbor, vertex):
                    return True
            return False

        return any(walk(vertex, None) for vertex in self._adj if vertex not in seen)

    def topological_sort(self) -> List[Any]:
        """
        Kahn's algorithm: a legal course order.

        Incoming-edge count is the number of unfinished prerequisites.
        A cycle means the catalog is inconsistent (A needs B needs A).
        """
        if not self.directed:
            raise GraphError("topological_sort requires a directed graph")
        indegree = {vertex: 0 for vertex in self._adj}
        for _source, edges in self._adj.items():
            for target, _weight in edges:
                indegree[target] += 1
        ready = sorted(vertex for vertex, degree in indegree.items() if degree == 0)
        queue: deque[Any] = deque(ready)
        order: List[Any] = []
        while queue:
            vertex = queue.popleft()
            order.append(vertex)
            unlocked: List[Any] = []
            for neighbor, _weight in self._adj[vertex]:
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    unlocked.append(neighbor)
            for neighbor in sorted(unlocked):
                queue.append(neighbor)
        if len(order) != len(self._adj):
            raise GraphError("graph has a cycle; no topological order exists")
        return order


def _rebuild_path(previous: Dict[Any, Any], goal: Any) -> List[Any]:
    path = []
    current: Any = goal
    while current is not None:
        path.append(current)
        current = previous[current]
    path.reverse()
    return path


def campus_shuttle() -> Graph:
    """
    Undirected shuttle map. Edge weight = scheduled minutes.

    Union --5-- Library --4-- Science
      | 7          | 8          | 6
    Dorms ------ Rec ------ Health
      | 10
    Stadium
    """
    graph = Graph(directed=False)
    legs = [
        ("Union", "Library", 5),
        ("Library", "Science", 4),
        ("Union", "Dorms", 7),
        ("Library", "Rec", 8),
        ("Science", "Health", 6),
        ("Dorms", "Rec", 9),
        ("Rec", "Health", 3),
        ("Dorms", "Stadium", 10),
        ("Union", "Health", 20),  # express: one hop, but traffic makes it slow
    ]
    for source, target, minutes in legs:
        graph.add_edge(source, target, minutes)
    return graph


def course_catalog() -> Graph:
    """
    Directed prerequisite graph.

    MATH101 -> CS201 -> CS301
    CS101  -> CS201 -> CS250 -> CS301
    CS101  -> CS150
    """
    graph = Graph(directed=True)
    edges = [
        ("CS101", "CS150"),
        ("CS101", "CS201"),
        ("MATH101", "CS201"),
        ("CS201", "CS250"),
        ("CS201", "CS301"),
        ("CS250", "CS301"),
    ]
    for source, target in edges:
        graph.add_edge(source, target, 1)
    return graph


def _print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def demonstrate_graphs() -> int:
    """Run the shuttle map and the degree planner side by side."""
    try:
        shuttle = campus_shuttle()
        catalog = course_catalog()
    except GraphError as exc:
        print(f"Failed to build campus graphs: {exc}", file=sys.stderr)
        return 1

    _print_section("1. Shuttle map (undirected, weighted)")
    print(shuttle)
    print("stops:", ", ".join(sorted(shuttle.vertices())))
    print("from Union:", shuttle.neighbors("Union"))

    _print_section("2. BFS — fewest hops from the Union")
    print("visit order:", " -> ".join(shuttle.bfs("Union")))
    hops = shuttle.shortest_hops("Union", "Stadium")
    print(f"fewest hops Union -> Stadium: {' -> '.join(hops)}  ({len(hops) - 1} rides)")
    hops_health = shuttle.shortest_hops("Union", "Health")
    print(f"fewest hops Union -> Health:  {' -> '.join(hops_health)}  ({len(hops_health) - 1} rides)")

    _print_section("3. DFS — one branch as far as it goes")
    print("visit order:", " -> ".join(shuttle.dfs("Union")))

    _print_section("4. Dijkstra — fastest Union -> Stadium")
    """
    Union -> Health is one express hop (20 min) but the three-hop
    local route Union -> Library -> Science -> Health is 15 minutes.
    BFS picks the express; Dijkstra picks the local.
    """
    path, minutes = shuttle.shortest_weighted_path("Union", "Health")
    print(f"fastest Union -> Health: {' -> '.join(path)}  ({minutes:.0f} minutes)")
    path_s, minutes_s = shuttle.shortest_weighted_path("Union", "Stadium")
    print(f"fastest Union -> Stadium: {' -> '.join(path_s)}  ({minutes_s:.0f} minutes)")
    distance, _previous = shuttle.dijkstra("Union")
    print("minutes from Union to every stop:")
    for stop in sorted(distance):
        print(f"  {stop:10} {distance[stop]:5.0f} min")

    _print_section("5. Connected components")
    print("day network:", shuttle.connected_components())
    night = Graph(directed=False)
    night.add_edge("Union", "Library", 12)
    night.add_vertex("Stadium")
    print("night network (Stadium isolated):", night.connected_components())

    _print_section("6. Course planner — topological sort")
    print(catalog)
    order = catalog.topological_sort()
    print("a legal semester order:")
    for index, course in enumerate(order, start=1):
        print(f"  {index}. {course}")
    print(f"catalog has a cycle? {catalog.has_cycle()}")

    _print_section("7. Broken catalog — CS301 requires CS201 which already leads to CS301")
    broken = course_catalog()
    broken.add_edge("CS301", "CS201", 1)
    try:
        broken.topological_sort()
        print("UNEXPECTED SUCCESS: cyclic catalog")
    except GraphError as exc:
        print(f"caught {type(exc).__name__}: {exc}")
    print(f"broken catalog has a cycle? {broken.has_cycle()}")

    _print_section("8. Expected errors")
    error_cases = [
        ("unknown stop", lambda: shuttle.bfs("Airport")),
        ("no path", lambda: night.shortest_hops("Union", "Stadium")),
        ("topo on shuttle", lambda: shuttle.topological_sort()),
        ("negative weight", lambda: shuttle.add_edge("Union", "Moon", -3)),
    ]
    for label, action in error_cases:
        try:
            action()
            print(f"UNEXPECTED SUCCESS: {label}")
        except GraphError as exc:
            print(f"caught {type(exc).__name__} for {label}: {exc}")
        except Exception as exc:
            print(f"caught unexpected {type(exc).__name__} for {label}: {exc}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Graph algorithms + campus demos")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("demo", help="shuttle map + course planner walkthrough")
    path_parser = sub.add_parser("path", help="fastest shuttle ride")
    path_parser.add_argument("start")
    path_parser.add_argument("goal")
    sub.add_parser("plan", help="print a legal course order")
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
        command = args.command or "demo"
        if command == "demo":
            return demonstrate_graphs()
        if command == "path":
            shuttle = campus_shuttle()
            hops = shuttle.shortest_hops(args.start, args.goal)
            path, minutes = shuttle.shortest_weighted_path(args.start, args.goal)
            print(f"fewest hops: {' -> '.join(hops)}")
            print(f"fastest:     {' -> '.join(path)}  ({minutes:.0f} min)")
            return 0
        order = course_catalog().topological_sort()
        print("legal course order:", " -> ".join(order))
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except GraphError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unhandled error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
