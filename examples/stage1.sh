#!/bin/sh
set -eu
python3 src/main.py --package A --repo examples/diamond.txt --test \
    --version 1.0 --ascii
bad() {
    if python3 src/main.py "$@"; then
        echo "Expected an option error" >&2
        exit 1
    else
        test "$?" -eq 2
    fi
}
bad --package A --repo https://repo.maven.apache.org/maven2 --version 1.0
bad --package A --repo missing.txt --test --version 1.0
bad --package A --repo examples/diamond.txt --test --version ../1
bad --package A --repo examples/diamond.txt --test false --version 1.0
bad --package A --repo examples/diamond.txt --test --version 1.0 --ascii no
