"""Regression tests for inherited and managed Maven dependencies."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from xml.etree import ElementTree
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from maven import Dependency, MavenRepository, expand


def xml(source):
    """Parse an inline POM fixture."""
    return ElementTree.fromstring(source)


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
