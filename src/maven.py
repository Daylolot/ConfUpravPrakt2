"""Read Maven POM files directly using the Python standard library."""

from dataclasses import dataclass
import re
from urllib.request import urlopen
from xml.etree import ElementTree


@dataclass(frozen=True)
class Dependency:
    """Store a Maven coordinate and its dependency flags."""

    group: str
    artifact: str
    version: str
    scope: str = "compile"
    optional: bool = False

    @property
    def label(self):
        """Return a printable Maven coordinate."""
        return f"{self.group}:{self.artifact}:{self.version}"


def read_pom(repo, group, artifact, version):
    """Download one versioned POM and remove XML namespaces."""
    name = r"[A-Za-z0-9_][A-Za-z0-9_.+-]*"
    if not all(re.fullmatch(name, value) for value in
               (group, artifact, version)):
        raise ValueError("invalid or unsupported Maven coordinate")
    path = f"{group.replace('.', '/')}/{artifact}/{version}"
    url = f"{repo.rstrip('/')}/{path}/{artifact}-{version}.pom"
    with urlopen(url, timeout=20) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError(f"POM is too large: {url}")
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        raise ValueError(f"invalid POM: {url}") from error
    for node in root.iter():
        node.tag = node.tag.rsplit("}", 1)[-1]
    return root


def expand(value, properties):
    """Substitute POM properties, including nested references."""
    for _ in range(32):
        result = re.sub(
            r"\$\{([^}]+)\}",
            lambda match: properties.get(match[1], match[0]),
            value,
        )
        if result == value:
            return result
        value = result
    raise ValueError("POM properties exceed the expansion limit")


class MavenRepository:
    """Read direct dependency declarations and basic inherited settings."""

    def __init__(self, repo):
        """Keep the URL and cache parsed POM models."""
        self.repo = repo
        self.cache = {}

    def model(self, dep, parents=()):
        """Merge parent properties, managed versions, and declarations."""
        if dep in parents or len(parents) >= 32:
            raise ValueError(f"invalid POM inheritance chain: {dep.label}")
        if dep in self.cache:
            return self.cache[dep]
        root = read_pom(self.repo, dep.group, dep.artifact, dep.version)
        props, managed, rows = {}, {}, {}
        parent = root.find("parent")
        if parent is not None:
            coordinates = ("groupId", "artifactId", "version")
            parent_dep = Dependency(*(parent.findtext(field, "").strip()
                                      for field in coordinates))
            inherited = self.model(parent_dep, parents + (dep,))
            props, managed, rows = (item.copy() for item in inherited)
        props.update({node.tag: (node.text or "").strip()
                      for node in root.findall("properties/*")})
        for prefix in ("project", "pom"):
            props.update({f"{prefix}.groupId": dep.group,
                          f"{prefix}.artifactId": dep.artifact,
                          f"{prefix}.version": dep.version})

        def fields(node):
            """Collect and expand the fields used by this analyzer."""
            return {child.tag: expand((child.text or "").strip(), props)
                    for child in node}

        def identity(item):
            """Distinguish ordinary and test JAR declarations."""
            return (item.get("groupId"), item.get("artifactId"),
                    item.get("type", "jar"), item.get("classifier", ""))

        management = "dependencyManagement/dependencies/dependency"
        for node in root.findall(management):
            item = fields(node)
            if item.get("scope") != "import":
                managed[identity(item)] = item
        for node in root.findall("dependencies/dependency"):
            item = fields(node)
            rows[identity(item)] = item
        self.cache[dep] = props, managed, rows
        return self.cache[dep]

    def direct(self, dep, scopes=None):
        """Return dependencies for the requested version and scopes."""
        props, managed, rows = self.model(dep)
        result = []
        for key, row in rows.items():
            item = managed.get(key, {}) | row
            scope = expand(item.get("scope", "compile"), props)
            if scopes is not None and scope not in scopes:
                continue
            group, artifact = (item.get(field, "") for field in
                               ("groupId", "artifactId"))
            version = expand(item.get("version", ""), props)
            if not group or not artifact or not version or "${" in version:
                raise ValueError(f"unresolved dependency {key} in {dep.label}")
            optional = item.get("optional", "false").lower() == "true"
            result.append(Dependency(group, artifact, version, scope, optional))
        return result
