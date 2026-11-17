"""Render dependency graphs as Mermaid or ASCII."""


def mermaid(edges, label):
    """Yield Mermaid declarations, including isolated nodes and back edges."""
    ids = {node: f"n{i}" for i, node in enumerate(edges)}
    yield "flowchart TD"
    for node, ident in ids.items():
        name = label(node).replace("&", "&amp;").replace('"', "&quot;")
        yield f'    {ident}["{name}"]'
    for node, children in edges.items():
        for child in children:
            yield f"    {ids[node]} --> {ids[child]}"


def ascii_tree(root, edges, label):
    """Render shared dependencies once and mark cycles explicitly."""
    printed, active = set(), set()

    def visit(node, prefix, branch, continuation):
        """Emit one node and its children with the correct branch prefix."""
        repeated = node in printed
        cycle = node in active
        marker = " [cycle]" if cycle else " [shared]" if repeated else ""
        yield prefix + branch + label(node) + marker
        if repeated:
            return
        printed.add(node)
        active.add(node)
        children = edges[node]
        for index, child in enumerate(children):
            last = index == len(children) - 1
            yield from visit(child, prefix + continuation,
                             "`-- " if last else "|-- ",
                             "    " if last else "|   ")
        active.remove(node)

    yield from visit(root, "", "", "")
