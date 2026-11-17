"""Build a directed dependency graph with recursive DFS."""

from pathlib import Path
import re


class TestRepository:
    """Load lines of the form A: B C from a test repository."""

    def __init__(self, filename):
        """Validate declarations and references before traversal."""
        self.rows = {}
        lines = Path(filename).read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            key, delimiter, values = line.partition(":")
            children = values.split()
            if (not delimiter or not re.fullmatch(r"[A-Z]", key)
                    or any(not re.fullmatch(r"[A-Z]", c) for c in children)
                    or key in self.rows):
                raise ValueError(f"{filename}:{number}: invalid declaration")
            self.rows[key] = list(dict.fromkeys(children))
        referenced = {c for row in self.rows.values() for c in row}
        missing = referenced - self.rows.keys()
        if missing:
            packages = ", ".join(sorted(missing))
            raise ValueError(f"undeclared packages: {packages}")

    def direct(self, node):
        """Return children of a named package from the fixture."""
        if node not in self.rows:
            raise ValueError(f"package not found: {node}")
        return self.rows[node]


def build_graph(root, direct):
    """Return reachable edges, cycle paths, and DFS finishing order."""
    edges, active, stack, cycles, finished = {}, set(), [], [], []

    def visit(node):
        """Follow each edge once and keep back edges in the graph."""
        if node in active:
            cycles.append(stack[stack.index(node):] + [node])
            return
        if node in edges:
            return
        active.add(node)
        stack.append(node)
        edges[node] = list(dict.fromkeys(direct(node)))
        for child in edges[node]:
            visit(child)
        stack.pop()
        active.remove(node)
        finished.append(node)

    visit(root)
    return edges, cycles, finished
