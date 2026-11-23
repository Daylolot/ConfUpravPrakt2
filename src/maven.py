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
    if root.tag != "project":
        raise ValueError(f"expected a Maven project POM: {url}")
    return root


def expand(value, properties, strict=True):
    """Substitute POM properties, including nested references."""
    for _ in range(32):
        result = re.sub(
            r"\$\{([^}]+)\}",
            lambda match: properties.get(match[1], match[0]),
            value,
        )
        if result == value:
            if strict and "${" in result:
                raise ValueError(f"unresolved POM property in {result}")
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
            for prefix in ("project.parent", "parent"):
                props.update({f"{prefix}.groupId": parent_dep.group,
                              f"{prefix}.artifactId": parent_dep.artifact,
                              f"{prefix}.version": parent_dep.version})
        props.update({node.tag: (node.text or "").strip()
                      for node in root.findall("properties/*")})
        for prefix in ("project", "pom"):
            props.update({f"{prefix}.groupId": dep.group,
                          f"{prefix}.artifactId": dep.artifact,
                          f"{prefix}.version": dep.version})
        props.update({"groupId": dep.group, "artifactId": dep.artifact,
                      "version": dep.version})

        def fields(node):
            """Keep expressions until properties of the child are known."""
            return {child.tag: (child.text or "").strip()
                    for child in node if not len(child)}

        def identity(item):
            """Distinguish ordinary and test JAR declarations."""
            return (item.get("groupId"), item.get("artifactId"),
                    item.get("type", "jar"), item.get("classifier", ""))

        management = "dependencyManagement/dependencies/dependency"
        local, imports = {}, {}
        for node in root.findall(management):
            item = fields(node)
            if expand(item.get("scope", "compile"), props) == "import":
                if item.get("type") != "pom":
                    raise ValueError("an imported BOM must have type pom")
                bom = Dependency(*(expand(item.get(field, ""), props)
                                   for field in
                                   ("groupId", "artifactId", "version")))
                bom_props, bom_managed, _ = self.model(bom, parents + (dep,))
                for row in bom_managed.values():
                    resolved = {key: expand(value, bom_props, strict=False)
                                for key, value in row.items()}
                    imports.setdefault(identity(resolved), resolved)
            else:
                local[identity(item)] = item
        managed.update(imports)
        managed.update(local)
        for node in root.findall("dependencies/dependency"):
            item = fields(node)
            key = identity(item)
            rows[key] = rows.get(key, {}) | item
        self.cache[dep] = props, managed, rows
        return self.cache[dep]

    def direct(self, dep, scopes=None):
        """Return dependencies for the requested version and scopes."""
        props, managed, rows = self.model(dep)
        resolved_managed = {}
        for row in managed.values():
            values = {key: expand(value, props, strict=False)
                      for key, value in row.items()}
            key = (values.get("groupId"), values.get("artifactId"),
                   values.get("type", "jar"), values.get("classifier", ""))
            resolved_managed[key] = values
        result = []
        for row in rows.values():
            row = {key: expand(value, props) for key, value in row.items()}
            key = (row.get("groupId"), row.get("artifactId"),
                   row.get("type", "jar"), row.get("classifier", ""))
            item = {name: expand(value, props) for name, value in
                    (resolved_managed.get(key, {}) | row).items()}
            scope = expand(item.get("scope", "compile"), props)
            scopes_known = {"compile", "runtime", "provided", "test", "system"}
            if scope not in scopes_known:
                raise ValueError(f"unsupported dependency scope: {scope}")
            if scopes is not None and scope not in scopes:
                continue
            group, artifact = (item.get(field, "") for field in
                               ("groupId", "artifactId"))
            version = expand(item.get("version", ""), props)
            if not group or not artifact or not version or "${" in version:
                raise ValueError(f"unresolved dependency {key} in {dep.label}")
            if version in {"LATEST", "RELEASE"}:
                raise ValueError("dependency version must be fixed")
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*", version):
                raise ValueError(f"unsupported dependency version: {version}")
            if scopes is not None and (
                    item.get("type", "jar") != "jar"
                    or item.get("classifier", "")):
                raise ValueError("the graph supports unclassified JARs only")
            optional = item.get("optional", "false").lower() == "true"
            result.append(Dependency(group, artifact, version, scope, optional))
        return result
