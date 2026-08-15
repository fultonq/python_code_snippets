#!/usr/bin/env python3
"""Tests for campus shuttle / course-planner graph algorithms."""

import io
import unittest
from contextlib import redirect_stdout

from graph_algorithms import (
    Graph,
    GraphError,
    UnknownVertexError,
    campus_shuttle,
    course_catalog,
    demonstrate_graphs,
    main,
)


class ShuttleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.shuttle = campus_shuttle()

    def test_bfs_starts_at_union(self) -> None:
        order = self.shuttle.bfs("Union")
        self.assertEqual(order[0], "Union")
        self.assertEqual(set(order), set(self.shuttle.vertices()))

    def test_fewest_hops_prefers_express_to_health(self) -> None:
        path = self.shuttle.shortest_hops("Union", "Health")
        self.assertEqual(path, ["Union", "Health"])

    def test_dijkstra_prefers_local_legs_to_health(self) -> None:
        path, minutes = self.shuttle.shortest_weighted_path("Union", "Health")
        self.assertEqual(path, ["Union", "Library", "Science", "Health"])
        self.assertEqual(minutes, 15)

    def test_stadium_path(self) -> None:
        hops = self.shuttle.shortest_hops("Union", "Stadium")
        self.assertEqual(hops, ["Union", "Dorms", "Stadium"])
        path, minutes = self.shuttle.shortest_weighted_path("Union", "Stadium")
        self.assertEqual(path, ["Union", "Dorms", "Stadium"])
        self.assertEqual(minutes, 17)

    def test_connected_components_night_network(self) -> None:
        night = Graph(directed=False)
        night.add_edge("Union", "Library", 12)
        night.add_vertex("Stadium")
        parts = {frozenset(group) for group in night.connected_components()}
        self.assertEqual(parts, {frozenset({"Union", "Library"}), frozenset({"Stadium"})})

    def test_unknown_stop(self) -> None:
        with self.assertRaises(UnknownVertexError):
            self.shuttle.bfs("Airport")


class CoursePlannerTests(unittest.TestCase):
    def test_topological_order_respects_prereqs(self) -> None:
        catalog = course_catalog()
        order = catalog.topological_sort()
        index = {course: position for position, course in enumerate(order)}
        self.assertLess(index["CS101"], index["CS201"])
        self.assertLess(index["MATH101"], index["CS201"])
        self.assertLess(index["CS201"], index["CS301"])
        self.assertLess(index["CS250"], index["CS301"])
        self.assertFalse(catalog.has_cycle())

    def test_cycle_is_detected(self) -> None:
        catalog = course_catalog()
        catalog.add_edge("CS301", "CS201")
        self.assertTrue(catalog.has_cycle())
        with self.assertRaises(GraphError):
            catalog.topological_sort()

    def test_topo_rejected_on_undirected_graph(self) -> None:
        with self.assertRaises(GraphError):
            campus_shuttle().topological_sort()


class DemoTests(unittest.TestCase):
    def test_walkthrough_completes(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = demonstrate_graphs()
        self.assertEqual(status, 0)
        output = buffer.getvalue()
        self.assertIn("Dijkstra", output)
        self.assertIn("topological sort", output)
        self.assertNotIn("UNEXPECTED SUCCESS", output)

    def test_path_cli(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = main(["path", "Union", "Health"])
        self.assertEqual(status, 0)
        text = buffer.getvalue()
        self.assertIn("fewest hops: Union -> Health", text)
        self.assertIn("Library -> Science -> Health", text)


if __name__ == "__main__":
    unittest.main()
