#!/usr/bin/env python3
"""Add entries to the English-mode dictionary (desktop/resources/i18n/ko-en.json) — safe to run from
several recordings at once (file lock). Existing entries are never changed; a conflict is reported.

    python3 desktop/scripts/i18n-add.py '<Korean>' '<English>'              exact entry
    python3 desktop/scripts/i18n-add.py --pattern '<Korean {0}>' '<English {0}>'
    python3 desktop/scripts/i18n-add.py --replace '<Korean>' '<English>'    change an existing exact entry
    python3 desktop/scripts/i18n-add.py --context '<css selector>' '<Korean>' '<English>'
                                                where that Korean means something else
"""
import fcntl
import json
import os
import sys

DICT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources", "i18n", "ko-en.json")


def main():
    args = sys.argv[1:]
    mode = args[0] if args and args[0].startswith("--") else ""
    if mode:
        args = args[1:]
    if len(args) != (3 if mode == "--context" else 2):
        raise SystemExit(__doc__)
    pattern = mode == "--pattern"
    ko, en = args[-2:]
    with open(DICT + ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        d = json.load(open(DICT, encoding="utf-8"))
        if mode == "--context":
            entry = [args[0], ko, en]
            ctx = d.setdefault("context", [])
            if entry in ctx:
                print(f"exists: {entry}")
                return
            ctx.append(entry)
        elif mode == "--replace":
            print(f"replaced: {ko!r}: {d['exact'].get(ko)!r} → {en!r}")
            d["exact"][ko] = en
        elif pattern:
            have = {p[0]: p[1] for p in d["patterns"]}
            if ko in have:
                print(f"exists: {ko!r} → {have[ko]!r}")
                return
            lit = len(ko.replace("{0}", "").replace("{1}", "").replace("{2}", ""))
            # keep the order translate.js tries them in: most fixed text first
            at = next((i for i, p in enumerate(d["patterns"]) if len(p[0]) - p[0].count("{") * 3 < lit), len(d["patterns"]))
            d["patterns"].insert(at, [ko, en])
        else:
            if ko in d["exact"]:
                print(f"exists: {ko!r} → {d['exact'][ko]!r}")
                return
            d["exact"][ko] = en
        tmp = DICT + ".tmp"
        json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, DICT)
        print(f"added: {ko!r} → {en!r}")


if __name__ == "__main__":
    main()
