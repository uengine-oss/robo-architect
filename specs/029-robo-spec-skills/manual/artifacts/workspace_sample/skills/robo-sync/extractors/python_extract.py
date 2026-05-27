#!/usr/bin/env python3
"""Python AST extractor for /robo-sync (skeleton — feature 029 T018).

Full implementation lands in T044 (US5 phase). When invoked, this stub
exits with a non-zero status and a clear "not yet implemented" message
so /robo-sync's flow surface treats it as an unimplemented dependency
rather than silently producing empty extracts (which the diff service
would then misinterpret as "every field was removed").

Final contract (T044): given a path to a `.py` file on argv[1], walk
class definitions / dataclass fields / type annotations and emit one
JSON document per element on stdout, of shape:

    {
        "kind": "Aggregate" | "Command" | "Event" | "ReadModel",
        "name": "<element name in source>",
        "fields": [ { "name": "...", "type": "..." }, ... ]
    }

The calling skill resolves each `name` to an `elementId` via
`get_bc_design` (T2) before sending the extract to `propose_sync` (T6).
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "usage: python_extract.py <path-to-python-file>",
            file=sys.stderr,
        )
        return 2

    print(
        "python_extract.py is a skeleton (feature 029 T018). "
        "Full AST extraction lands in T044 (US5).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
