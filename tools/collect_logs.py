#!/usr/bin/env python3
"""Admin-side: pull what Members have pushed — event logs and session reports.

    python collect_logs.py --out ./events        # then: metrics.py --events ./events

Logs land as `<owner>__<uuid>.jsonl`; session reports land as `<owner>__<uuid>.md` in a
`reports/` subdirectory beside them. `metrics.py` reads the logs. The reports are for reading:
the fourth thing every session is asked — what it wanted to express scientifically and could
not — has no substitute anywhere else in the measurement, and no statistic will produce it.

Discovery is the permission map, not search — the same reason the gate uses it: a freshly
uploaded private network has `indexLevel: NONE` and never appears in `/v2/search/network`, so
search-based discovery would silently drop logs exactly as it once silently dropped
submissions. A member's grant IS the signal.

Only networks marked `symposium_telemetry` or `symposium_report` are touched. Anything else
granted to the admin is a submission and belongs to the gate; this tool never validates, never
accepts, and never writes to the record.

One file per push, which is deliberately redundant: `metrics.py` de-duplicates on the whole
event, so three pushes from one session produce three files whose overlapping events count
once. Re-running is safe, collecting the same push twice is safe, and a log handed over on a
memory stick can simply be dropped into the same directory alongside the pulled ones.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from ndex_io import (REPORT_ATTR, REPORT_MARK, REPORT_SEGMENT, TELEMETRY_ATTR,
                     TELEMETRY_MARK, TELEMETRY_SEGMENT, api, auth, extract_blob)

ADMIN_USER, ADMIN_TOK = auth("ADMIN")


def collected_uuids(out, reports_dir):
    """UUIDs already on disk, read off the filenames. No state file: the collection IS the state.

    Every push is a new network carrying the whole cumulative log, so without this the pull
    cost grows quadratically over a day — and on this deployment a network summary carries all
    of its attributes, which means the log is paid for once just to find out it is a log.
    """
    seen = set()
    for p in list(out.glob("*.jsonl")) + list(reports_dir.glob("*.md")):
        part = p.stem.split("__")[-1]
        if len(part) == 36:
            seen.add(part)
    return seen


def granted_networks(skip=()):
    """Every network readable by the admin, with owner and name.

    `skip` is applied BEFORE the summary fetch, which is the whole point: the permission map
    costs ~47 bytes per network and a summary costs the entire network.
    """
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
        if level != "READ" or uuid in skip:
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
    ap.add_argument("--refresh", action="store_true",
                    help="re-pull everything, including networks already collected")
    args = ap.parse_args(argv)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    reports_dir = out / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    already = set() if args.refresh else collected_uuids(out, reports_dir)
    if already:
        print(f"{len(already)} network(s) already collected — not re-fetched "
              f"(--refresh to override)")
    nets = granted_networks(skip=already)
    # The name segment is the cheap filter, applied to the summary already in hand; the mark
    # is the guarantee, checked after the download. Something named oddly is still collected.
    KINDS = [(TELEMETRY_SEGMENT, TELEMETRY_MARK, TELEMETRY_ATTR, "event log", out, ".jsonl"),
             (REPORT_SEGMENT, REPORT_MARK, REPORT_ATTR, "session report", reports_dir, ".md")]
    logs = [n for n in nets if TELEMETRY_SEGMENT in n["name"]]
    reps = [n for n in nets if REPORT_SEGMENT in n["name"]]
    others = [n for n in nets if n not in logs and n not in reps]
    print(f"{len(nets)} network(s) readable; {len(logs)} event log(s), "
          f"{len(reps)} session report(s), {len(others)} for the gate\n")

    pulled = skipped = 0
    for seg, mark, attr, label, dest, ext in KINDS:
        for n in [x for x in nets if seg in x["name"]]:
            if args.dry_run:
                print(f"  would pull {label}: {n['name']}  ({n['owner']})")
                continue
            payload, na, err = extract_blob(n["uuid"], ADMIN_TOK, attr=attr)
            if err:
                print(f"  {n['name']}: ! {err}")
                skipped += 1
                continue
            if not (na or {}).get(mark):
                print(f"  {n['name']}: ! not marked {mark} — leaving it for the gate")
                skipped += 1
                continue
            path = dest / f"{n['owner']}__{n['uuid']}{ext}"
            path.write_text(payload)
            pulled += 1
            size = (f"{sum(1 for l in payload.splitlines() if l.strip())} event(s)"
                    if ext == ".jsonl" else f"{len(payload)} chars")
            print(f"  {label}: {n['name']}: {size} -> {path.relative_to(out)}")

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
        n_reports = len(list(reports_dir.glob("*.md")))
        print(f"\n{pulled} pulled, {skipped} skipped. {out}/ holds {len(files)} log file(s), "
              f"{total} event line(s), {len(seen)} distinct after de-duplication; "
              f"{n_reports} session report(s) in {reports_dir.name}/.")
        print(f"next: python metrics.py --record <gate mirror> --events {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
