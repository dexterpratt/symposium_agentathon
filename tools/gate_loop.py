#!/usr/bin/env python3
"""Run the admin gate on a cadence, and keep a log of what it did.

    python3 gate_loop.py                    # every 60s, until ctrl-c
    python3 gate_loop.py --every 120
    python3 gate_loop.py --once             # one pass, then exit
    python3 gate_loop.py --dry-run          # report what WOULD be accepted; publish nothing

Needs the same environment as gate.py: NDEX_ADMIN_*, SYMPOSIUM_MIRROR, SYMPOSIUM_MEMBERS.

WHAT THIS DOES AND DOES NOT DECIDE
----------------------------------
It accepts every submission that conforms, which is the gate's designed behaviour: the gate
judges CONFORMANCE, and has no basis to reject an artifact for being wrong, thin, or unwise.
Reading the science is a separate, human act that happens after publication, not a condition
of it — the record is the thing being measured, and a gate that quietly withheld work would
be measuring the admin instead.

So this is not an unattended-quality decision. It is the removal of a human from a mechanical
loop that was never exercising judgment in the first place.

Quiet by design: a pass with nothing new prints one short line. Every acceptance and every
rejection is appended to accepted.log beside the mirror, with a timestamp, so the day can be
read back afterwards without scrolling a terminal.

Each pass is a separate `gate.py` process. That is deliberate — gate.py reads credentials and
the member list at import time, and a long-lived process would hold a stale roster after an
account is added mid-day.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

TOOLS = pathlib.Path(__file__).resolve().parent
MIRROR = pathlib.Path(os.environ.get("SYMPOSIUM_MIRROR", "./record"))


def now():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def one_pass(dry):
    cmd = [sys.executable, str(TOOLS / "gate.py")] + (["--dry-run"] if dry else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--every", type=int, default=60, help="seconds between passes (default 60)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    log = MIRROR / "accepted.log"
    MIRROR.mkdir(parents=True, exist_ok=True)
    print(f"gate loop — every {args.every}s, mirror {MIRROR}"
          + ("  [DRY RUN]" if args.dry_run else "") + "\n  ctrl-c to stop\n", flush=True)

    passes = accepted = rejected = fails = 0
    while True:
        passes += 1
        code, out = one_pass(args.dry_run)
        acc = re.findall(r"ACCEPTED -> record", out)
        rej = re.findall(r"REJECTED \((\d+) failures?\)", out)
        if code != 0:
            fails += 1
            print(f"[{now()}] gate exited {code} — NOT publishing. Output:", flush=True)
            print("   " + "\n   ".join(out.strip().splitlines()[-8:]), flush=True)
        elif acc or rej:
            accepted += len(acc)
            rejected += len(rej)
            print(f"[{now()}] {len(acc)} accepted, {len(rej)} rejected", flush=True)
            for line in out.splitlines():
                if line.strip() and not line.startswith("gate:"):
                    print("   " + line.rstrip(), flush=True)
            if not args.dry_run:
                with log.open("a") as fh:
                    fh.write(f"\n===== {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
                    fh.write(out)
        else:
            held = re.search(r"record holds (\d+)", out)
            print(f"[{now()}] nothing new ({held.group(1) if held else '?'} artifacts)"
                  + (f"  [{accepted} accepted, {rejected} rejected, {fails} errors so far]"
                     if passes % 10 == 0 else ""), flush=True)

        if args.once:
            return 0 if code == 0 else 1
        try:
            time.sleep(args.every)
        except KeyboardInterrupt:
            print(f"\nstopped after {passes} pass(es): "
                  f"{accepted} accepted, {rejected} rejected, {fails} errors")
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nstopped")
        sys.exit(0)
