#!/usr/bin/env python3
"""Admin-side: pull the event logs Members have pushed, into one directory.

    python collect_logs.py --out ./events        # then: metrics.py --events ./events

Discovery is the permission map, not search — the same reason the gate uses it: a freshly
uploaded private network has `indexLevel: NONE` and never appears in `/v2/search/network`, so
search-based discovery would silently drop logs exactly as it once silently dropped
submissions. A member's grant IS the signal.

Only networks marked `symposium_telemetry` are touched. Anything else granted to the admin is
a submission and belongs to the gate; this tool never validates, never accepts, and never
writes to the record.

Files are written as `<owner>__<uuid>.jsonl`, one per push. That is deliberately redundant:
`metrics.py` de-duplicates on the whole event, so three pushes from one session produce three
files whose overlapping events count once. Re-running is safe, collecting the same push twice
is safe, and a log handed over on a memory stick can simply be dropped into the same
directory alongside the pulled ones.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from ndex_io import (TELEMETRY_ATTR, TELEMETRY_MARK, TELEMETRY_SEGMENT, api, auth,
                     extract_blob)

ADMIN_USER, ADMIN_TOK = auth("ADMIN")


def granted_networks():
    """Every network readable by the admin, with owner and name."""
    st, me = api("GET", "/v2/user?valid=true", ADMIN_TOK)
    if st != 200 or not isinstance(me, dict):
        print(f"! cannot resolve admin account: HTTP {st}")
        return []
    st, perms = api("GET",
                    f"/v2/user/{me['externalId']}/permission?type=NETWORK&permission=READ",
                    ADMIN_TOK)
    if st != 200 or not isinstance(perms, dict):
        print(f"! permission listing failed: HTTP {st}")
        return []
    out = []
    for uuid, level in perms.items():
        if level != "READ":
            continue
        st, s = api("GET", f"/v2/network/{uuid}/summary", ADMIN_TOK)
        if st != 200 or not isinstance(s, dict):
            continue
        if s.get("owner") == ADMIN_USER:
            continue
        out.append({"uuid": uuid, "name": s.get("name") or "", "owner": s.get("owner")})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="./events", help="directory to write logs into")
    ap.add_argument("--dry-run", action="store_true", help="list what would be pulled")
    args = ap.parse_args(argv)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    nets = granted_networks()
    # The name segment is the cheap filter, applied to the summary already in hand; the mark
    # is the guarantee, checked after the download. A log named oddly is still collected.
    candidates = [n for n in nets if TELEMETRY_SEGMENT in n["name"]]
    others = [n for n in nets if TELEMETRY_SEGMENT not in n["name"]]
    print(f"{len(nets)} network(s) readable; {len(candidates)} look like event logs, "
          f"{len(others)} are for the gate\n")

    pulled = skipped = 0
    for n in candidates:
        if args.dry_run:
            print(f"  would pull {n['name']}  ({n['owner']})")
            continue
        payload, na, err = extract_blob(n["uuid"], ADMIN_TOK, attr=TELEMETRY_ATTR)
        if err:
            print(f"  {n['name']}: ! {err}")
            skipped += 1
            continue
        if not (na or {}).get(TELEMETRY_MARK):
            print(f"  {n['name']}: ! not marked {TELEMETRY_MARK} — leaving it for the gate")
            skipped += 1
            continue
        path = out / f"{n['owner']}__{n['uuid']}.jsonl"
        path.write_text(payload)
        n_events = sum(1 for line in payload.splitlines() if line.strip())
        pulled += 1
        print(f"  {n['name']}: {n_events} event(s) -> {path.name}")

    if not args.dry_run:
        files = sorted(out.glob("*.jsonl"))
        total = 0
        seen = set()
        for f in files:
            for line in f.read_text().splitlines():
                if line.strip():
                    try:
                        seen.add(json.dumps(json.loads(line), sort_keys=True))
                        total += 1
                    except json.JSONDecodeError:
                        pass
        print(f"\n{pulled} pulled, {skipped} skipped. {out}/ holds {len(files)} file(s), "
              f"{total} event line(s), {len(seen)} distinct after de-duplication.")
        print(f"next: python metrics.py --record <gate mirror> --events {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
