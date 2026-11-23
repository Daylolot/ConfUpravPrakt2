"""Regression checks for the cases found during the project review."""

from contextlib import redirect_stderr
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from graph import TestRepository, build_graph
from main import main
from maven import Dependency, MavenRepository, expand, read_pom
from render import ascii_tree, mermaid


def xml(source):
    """Parse an inline POM fixture."""
    return ElementTree.fromstring(source)


class SilentHandler(SimpleHTTPRequestHandler):
    """Serve fixture POMs without writing request logs."""

    def log_message(self, *_):
        """Suppress the default request log."""


class MavenModelTests(unittest.TestCase):
    """Check model inheritance, management, and invalid input."""

    def test_child_overrides_inherited_property(self):
        """Resolve inherited version expressions in the child context."""
        child = xml("""
          <project>
            <parent><groupId>g</groupId><artifactId>parent</artifactId>
              <version>1</version></parent>
            <properties><v>2.0</v></properties>
            <dependencies><dependency><groupId>g</groupId>
              <artifactId>lib</artifactId></dependency></dependencies>
          </project>
        """)
        parent = xml("""
          <project><properties><v>1.0</v></properties>
            <dependencyManagement><dependencies><dependency>
              <groupId>g</groupId><artifactId>lib</artifactId>
              <version>${v}</version>
            </dependency></dependencies></dependencyManagement>
          </project>
        """)
        with patch("maven.read_pom", side_effect=[child, parent]):
            actual = MavenRepository("https://example.invalid").direct(
                Dependency("g", "app", "1"))
        self.assertEqual(actual, [Dependency("g", "lib", "2.0")])

    def test_inherited_dependency_keeps_version_on_partial_override(self):
        """Keep a parent's version when the child changes only its scope."""
        child = xml("""
          <project><parent><groupId>g</groupId><artifactId>parent</artifactId>
            <version>1</version></parent>
            <dependencies><dependency><groupId>g</groupId>
              <artifactId>lib</artifactId><scope>runtime</scope>
            </dependency></dependencies></project>
        """)
        parent = xml("""
          <project><dependencies><dependency><groupId>g</groupId>
            <artifactId>lib</artifactId><version>2</version>
          </dependency></dependencies></project>
        """)
        with patch("maven.read_pom", side_effect=[child, parent]):
            actual = MavenRepository("https://example.invalid").direct(
                Dependency("g", "app", "1"))
        self.assertEqual(actual, [Dependency("g", "lib", "2", "runtime")])

    def test_import_bom_resolves_version(self):
        """Import managed versions without adding a BOM as a graph edge."""
        app = xml("""
          <project><dependencyManagement><dependencies><dependency>
            <groupId>g</groupId><artifactId>bom</artifactId>
            <version>1</version><type>pom</type><scope>import</scope>
          </dependency></dependencies></dependencyManagement>
          <dependencies><dependency><groupId>g</groupId>
            <artifactId>lib</artifactId>
          </dependency></dependencies></project>
        """)
        bom = xml("""
          <project><properties><v>3</v></properties>
          <dependencyManagement><dependencies><dependency>
            <groupId>g</groupId><artifactId>lib</artifactId>
            <version>${v}</version>
          </dependency></dependencies></dependencyManagement></project>
        """)
        with patch("maven.read_pom", side_effect=[app, bom]):
            actual = MavenRepository("https://example.invalid").direct(
                Dependency("g", "app", "1"))
        self.assertEqual(actual, [Dependency("g", "lib", "3")])

    def test_test_jar_does_not_hide_compile_jar(self):
        """Keep declarations with different Maven types independent."""
        app = xml("""
          <project><dependencies>
            <dependency><groupId>g</groupId><artifactId>lib</artifactId>
              <version>1</version></dependency>
            <dependency><groupId>g</groupId><artifactId>lib</artifactId>
              <version>1</version><type>test-jar</type><scope>test</scope>
            </dependency>
          </dependencies></project>
        """)
        with patch("maven.read_pom", return_value=app):
            actual = MavenRepository("https://example.invalid").direct(
                Dependency("g", "app", "1"), {"compile", "runtime"})
        self.assertEqual(actual, [Dependency("g", "lib", "1")])

    def test_unused_test_version_is_not_resolved(self):
        """Skip test dependencies before resolving their unused properties."""
        app = xml("""
          <project><dependencies><dependency>
            <groupId>g</groupId><artifactId>tests</artifactId>
            <version>${test.only}</version><scope>test</scope>
          </dependency></dependencies></project>
        """)
        with patch("maven.read_pom", return_value=app):
            actual = MavenRepository("https://example.invalid").direct(
                Dependency("g", "app", "1"), {"compile", "runtime"})
        self.assertEqual(actual, [])

    def test_recursive_parent_is_reported(self):
        """Stop recursive POM inheritance with a useful data error."""
        app = xml("""
          <project><parent><groupId>g</groupId><artifactId>app</artifactId>
          <version>1</version></parent></project>
        """)
        with patch("maven.read_pom", return_value=app):
            with self.assertRaisesRegex(ValueError, "inheritance"):
                MavenRepository("https://example.invalid").direct(
                    Dependency("g", "app", "1"))

    def test_properties_unknown_and_cyclic(self):
        """Reject unknown and self-referential properties."""
        for props in ({}, {"x": "${x}"}, {"x": "${y}", "y": "${x}"}):
            with self.subTest(props=props):
                with self.assertRaises(ValueError):
                    expand("${x}", props)
        self.assertEqual(expand("${a}", {"a": "${b}", "b": "2"}), "2")

    def test_parent_coordinate_alias(self):
        """Resolve a version through project.parent.version."""
        child = xml("""
          <project><parent><groupId>g</groupId><artifactId>parent</artifactId>
            <version>9</version></parent>
            <dependencies><dependency><groupId>g</groupId>
              <artifactId>lib</artifactId>
              <version>${project.parent.version}</version>
            </dependency></dependencies></project>
        """)
        with patch("maven.read_pom", side_effect=[child, xml("<project/>")]):
            actual = MavenRepository("https://example.invalid").direct(
                Dependency("g", "app", "1"))
        self.assertEqual(actual[0].version, "9")

    def test_fixed_version_and_scope_validation(self):
        """Reject unresolved versions, ranges, and invalid scopes."""
        for version, scope in (("", "compile"), ("[1,2)", "compile"),
                               ("LATEST", "compile"), ("1", "wrong")):
            app = xml(f"""
              <project><dependencies><dependency><groupId>g</groupId>
                <artifactId>lib</artifactId><version>{version}</version>
                <scope>{scope}</scope>
              </dependency></dependencies></project>
            """)
            with self.subTest(version=version, scope=scope):
                with patch("maven.read_pom", return_value=app):
                    with self.assertRaises(ValueError):
                        MavenRepository("https://example.invalid").direct(
                            Dependency("g", "app", "1"))


class CliTests(unittest.TestCase):
    """Exercise the public entry point and genuine local HTTP transfers."""

    def run_cli(self, *options):
        """Run the executable interface without external network access."""
        return subprocess.run(
            [sys.executable, "src/main.py", *options], cwd=ROOT,
            text=True, capture_output=True, timeout=10)

    def test_each_cli_option_error(self):
        """Reject invalid names, URLs, versions, and flag values."""
        valid = ["--package", "g:a", "--version", "1",
                 "--repo", "https://example.invalid"]
        cases = [
            [],
            ["--package", "bad"],
            ["--repo", "ftp://example.invalid"],
            ["--repo", "https://example.invalid:wrong"],
            ["--version", "../1"],
            ["--version", "LATEST"],
            ["--test", "false"],
            ["--ascii", "no"],
            ["--test", "--repo", "missing.txt", "--package", "A"],
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                result = self.run_cli(*(valid + extra if extra else []))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_fixture_cli_outputs(self):
        """Render shared dependencies and cycles without hanging."""
        for name, marker in (("diamond", "[shared]"), ("cycle", "[cycle]")):
            with self.subTest(name=name):
                result = self.run_cli(
                    "--package", "A", "--version", "1.0", "--test",
                    "--repo", f"examples/{name}.txt", "--ascii")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(marker, result.stdout)

    def test_test_version_and_missing_package(self):
        """Reject a missing test package and a nonexistent test version."""
        for package, version in (("Z", "1.0"), ("A", "2")):
            result = self.run_cli(
                "--package", package, "--version", version, "--test",
                "--repo", "examples/diamond.txt")
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)

    def test_network_error_has_no_traceback(self):
        """Report network failures as ordinary application errors."""
        args = ["app", "--package", "g:a", "--version", "1",
                "--repo", "https://example.invalid"]
        error_output = io.StringIO()
        with patch.object(sys, "argv", args):
            with patch("maven.urlopen", side_effect=OSError("offline")):
                with redirect_stderr(error_output):
                    self.assertEqual(main(), 1)
        self.assertIn("offline", error_output.getvalue())

    def test_real_http_version_and_bad_pom(self):
        """Fetch the exact requested POM and reject non-POM XML or 404."""
        with tempfile.TemporaryDirectory() as folder:
            pom = Path(folder) / "g/app/2/app-2.pom"
            pom.parent.mkdir(parents=True)
            pom.write_text("""
              <project xmlns="http://maven.apache.org/POM/4.0.0">
                <dependencies><dependency><groupId>g</groupId>
                  <artifactId>lib</artifactId><version>3</version>
                </dependency></dependencies>
              </project>
            """, encoding="utf-8")
            handler = partial(SilentHandler, directory=folder)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            repo = f"http://127.0.0.1:{server.server_port}"
            try:
                actual = MavenRepository(repo).direct(
                    Dependency("g", "app", "2"))
                self.assertEqual(actual, [Dependency("g", "lib", "3")])
                for content in ("<html/>", "<project>"):
                    pom.write_text(content, encoding="utf-8")
                    result = self.run_cli(
                        "--package", "g:app", "--version", "2",
                        "--repo", repo)
                    self.assertEqual(result.returncode, 1)
                    self.assertNotIn("Traceback", result.stderr)
                with self.assertRaises(OSError):
                    read_pom(repo, "g", "app", "404")
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


class FixtureValidationTests(unittest.TestCase):
    """Check invalid graph files and all rendered edges."""

    def test_invalid_graph_descriptions(self):
        """Reject duplicate names, lowercase names, and undeclared nodes."""
        for content in ("A: B", "A:\nA:", "a:", "AA:", "A B"):
            with self.subTest(content=content):
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / "graph.txt"
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        TestRepository(path)

    def test_self_cycle(self):
        """Retain a self-loop and produce finite text output."""
        edges, cycles, _ = build_graph("A", lambda node: ["A"])
        self.assertEqual(cycles, [["A", "A"]])
        self.assertEqual(list(mermaid(edges, str)),
                         ["flowchart TD", '    n0["A"]', "    n0 --> n0"])
        self.assertEqual(list(ascii_tree("A", edges, str)),
                         ["A", "`-- A [cycle]"])

    def test_mermaid_diamond_preserves_both_incoming_edges(self):
        """Print each node once but keep both references to a shared node."""
        repo = TestRepository(ROOT / "examples/diamond.txt")
        edges, _, _ = build_graph("A", repo.direct)
        lines = list(mermaid(edges, str))
        self.assertEqual(sum("[" in line for line in lines), 4)
        self.assertEqual(sum("-->" in line for line in lines), 4)


if __name__ == "__main__":
    unittest.main()
