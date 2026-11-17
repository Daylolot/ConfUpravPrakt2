"""Offline checks for graph traversal, validation, and rendering."""

import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from graph import TestRepository, build_graph
from maven import Dependency, MavenRepository
from render import ascii_tree, mermaid


class GraphTests(unittest.TestCase):
    """Check cases used in the defense and version-specific POM requests."""

    def fixture(self, name):
        """Build a graph rooted at A from one repository fixture."""
        repo = TestRepository(ROOT / "examples" / (name + ".txt"))
        return build_graph("A", repo.direct)

    def test_shared_dependency_and_order(self):
        """Keep both edges to D and list each package once in postorder."""
        edges, cycles, order = self.fixture("diamond")
        self.assertEqual(edges, {"A": ["B", "C"], "B": ["D"], "D": [],
                                 "C": ["D"]})
        self.assertEqual(cycles, [])
        self.assertEqual(order, ["D", "B", "C", "A"])
        tree = list(ascii_tree("A", edges, str))
        self.assertIn("    `-- D [shared]", tree)

    def test_cycle(self):
        """Preserve the cycle edge and stop recursion on the active node."""
        edges, cycles, _ = self.fixture("cycle")
        self.assertEqual(cycles, [["A", "B", "C", "A"]])
        self.assertEqual(edges["C"], ["A", "D"])
        self.assertTrue(any("[cycle]" in line for line in
                            ascii_tree("A", edges, str)))

    def test_leaf(self):
        """Output an isolated node without unrelated packages."""
        edges, cycles, order = self.fixture("leaf")
        self.assertEqual((edges, cycles, order), ({"A": []}, [], ["A"]))
        self.assertEqual(list(mermaid(edges, str)),
                         ["flowchart TD", '    n0["A"]'])

    def test_version_and_managed_dependency(self):
        """Use the selected version and resolve a managed version."""
        root = ElementTree.fromstring("""
            <project>
              <properties><lib.version>2.5</lib.version></properties>
              <dependencyManagement><dependencies><dependency>
                <groupId>g</groupId><artifactId>lib</artifactId>
                <version>${lib.version}</version>
              </dependency></dependencies></dependencyManagement>
              <dependencies><dependency>
                <groupId>g</groupId><artifactId>lib</artifactId>
              </dependency></dependencies>
            </project>
        """)
        repo = MavenRepository("https://example.invalid")
        with patch("maven.read_pom", return_value=root) as read:
            deps = repo.direct(Dependency("g", "app", "7.0"))
        read.assert_called_once_with(repo.repo, "g", "app", "7.0")
        self.assertEqual(deps, [Dependency("g", "lib", "2.5")])
