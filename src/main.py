"""Command-line entry point for the dependency graph tool."""

import argparse
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


def parse_options():
    """Read and validate the five user-configurable options."""
    parser = argparse.ArgumentParser(description="Maven dependency graph")
    parser.add_argument("--package", required=True, help="group:artifact or A")
    parser.add_argument("--repo", required=True,
                        help="HTTP(S) URL or graph file")
    parser.add_argument("--test", action="store_true", help="use a graph file")
    parser.add_argument("--version", required=True,
                        help="exact package version")
    parser.add_argument("--ascii", action="store_true", help="print ASCII tree")
    config = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*", config.version):
        parser.error("--version: expected a fixed version, such as 1.0")
    name_pattern = r"[A-Z]" if config.test else (
        r"[A-Za-z0-9_][A-Za-z0-9_.-]*:[A-Za-z0-9_][A-Za-z0-9_.-]*"
    )
    if not re.fullmatch(name_pattern, config.package):
        parser.error("--package: expected A-Z in test mode or group:artifact")
    if config.test:
        if not Path(config.repo).is_file():
            parser.error("--repo: --test requires an existing graph file")
    else:
        try:
            url = urlsplit(config.repo)
            valid = (url.scheme in ("https", "http") and url.hostname
                     and url.username is None and not url.query
                     and not url.fragment and not re.search(r"\s", config.repo))
            _ = url.port
        except ValueError:
            valid = False
        if not valid:
            parser.error("--repo: expected an HTTP(S) repository URL")
    return config


def run(config):
    """Print the prototype configuration as key-value pairs."""
    for key, value in vars(config).items():
        print(f"{key}={value}")


def main():
    """Run the selected mode and report data errors without a traceback."""
    config = parse_options()
    try:
        run(config)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
