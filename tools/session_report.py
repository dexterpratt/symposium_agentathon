#!/usr/bin/env python3
"""A session's closing report — sent to the admin, and kept as the Member's own memory.

    python session_report.py --as VEGA --send report.md   # send it
    python session_report.py --as VEGA --list             # my earlier reports
    python session_report.py --as VEGA --read 1           # read one back

The report is the four things the session prompt asks for at the end: what was published,
every error and rejection with its actual text, what in the instructions was unclear or
wrong, and — the one with no substitute anywhere else — **what you wanted to express
scientifically but could not express in the format.** No validator can produce that
sentence and nothing in the record implies it.

Travels the same way the event log does: upload a network, grant the admin READ. Marked
`symposium_report`, named with the reserved `_REPORT_` segment, carrying no canonical JSON,
so the gate skips it and it never enters the record.

MEMORY, AND ITS LIMITS
----------------------
The network is owned by the Member who sent it, so a Member can read its own earlier reports
back — the continuity a scientist gets from their own notebook. `--list` and `--read` show
**only networks this account owns**, which is also all NDEx would show it: reports are granted
to the admin and to nobody else, so one Member cannot read another's.

That restriction is deliberate and worth keeping. The record is the medium of exchange between
Members; if one agent could read another's private report, work would start flowing through a
back channel the record does not account for, which is the one thing the whole design exists
to prevent.

Two consequences to be honest about:

  * A report is **not evidence and cannot be grounded on.** It is not an Artifact, has no
    address, and the validator will reject any attempt to reach it. If something in a report
    matters as evidence, publish it properly.
  * Reading your own past reports makes your later work depend on something outside the
    record. That is exactly as true of a human scientist's lab notebook, and it is worth
    saying out loud: the record accounts for what you claimed and what it rests on, not for
    everything that shaped your thinking.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import telemetry
from ndex_io import (REPORT_ATTR, REPORT_MARK, REPORT_SEGMENT, api, auth, extract_blob,
                     grant_read, to_cx2_blob, upload_cx2, user_uuid, whoami)

ADMIN = os.environ.get("SYMPOSIUM_ADMIN", "ndex-admin")


def my_reports(tok):
    """This account's own report networks, newest first. Ownership is the filter: NDEx will
    not show one Member another Member's reports, and this does not ask it to."""
    st, me = api("GET", "/v2/user?valid=true", tok)
    if st != 200 or not isinstance(me, dict):
        print(f"! cannot resolve account: HTTP {st}")
        return None, []
    st, nets = api("GET", f"/v2/user/{me['externalId']}/networksummary", tok)
    if st != 200 or not isinstance(nets, list):
        print(f"! cannot list networks: HTTP {st}")
        return me, []
    rs = [n for n in nets if REPORT_SEGMENT in (n.get("name") or "")]
    rs.sort(key=lambda n: n.get("name") or "", reverse=True)
    return me, rs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--as", dest="prefix", required=True, help="credential prefix, e.g. VEGA")
    ap.add_argument("--send", metavar="FILE", help="a report file to send (markdown or text)")
    ap.add_argument("--list", action="store_true", help="list my earlier reports")
    ap.add_argument("--read", metavar="N_OR_NAME", help="print one of my earlier reports")
    ap.add_argument("--check", action="store_true", help="report only; upload nothing")
    args = ap.parse_args(argv)
    if not (args.send or args.list or args.read):
        ap.error("give one of --send, --list or --read")

    user, tok = auth(args.prefix)
    me = whoami(tok)
    account = (me or {}).get("userName")
    if not account:
        print(f"! {args.prefix} could not authenticate")
        return 1

    # ---- read back: the memory path ---------------------------------------
    if args.list or args.read:
        me, rs = my_reports(tok)
        if not rs:
            print(f"no earlier reports owned by {account}")
            return 0
        if args.list:
            print(f"{len(rs)} report(s) owned by {account}, newest first:\n")
            for i, n in enumerate(rs, 1):
                print(f"  {i}. {n['name']}")
                if n.get("description"):
                    print(f"     {n['description'][:110]}")
            print(f"\nread one with: --read <number or name>")
            return 0
        pick = None
        if args.read.isdigit() and 1 <= int(args.read) <= len(rs):
            pick = rs[int(args.read) - 1]
        else:
            pick = next((n for n in rs if n.get("name") == args.read), None)
        if not pick:
            print(f"! no report matching '{args.read}' — try --list")
            return 1
        text, na, err = extract_blob(pick["externalId"], tok, attr=REPORT_ATTR)
        if err:
            print(f"! {pick['name']}: {err}")
            return 1
        print(f"===== {pick['name']} =====\n")
        print(text)
        return 0

    # ---- send -------------------------------------------------------------
    path = Path(args.send)
    if not path.exists():
        print(f"! no such file: {path}")
        return 1
    body = path.read_text()
    if not body.strip():
        print(f"! {path} is empty — nothing to send")
        return 1
    print(f"{path}: {len(body)} characters, {len(body.splitlines())} line(s)")

    if args.check:
        print("\n--check: nothing uploaded. The local file is unchanged either way.")
        return 0

    admin_uuid = user_uuid(ADMIN, tok)
    if not admin_uuid:
        print(f"! cannot resolve admin account '{ADMIN}' — nothing uploaded")
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{account}{REPORT_SEGMENT}{stamp}"
    session = telemetry.session_id(account)
    desc = f"Session report from {account} ({session}). Not an Artifact; not part of the record."

    st, uuid = upload_cx2(
        to_cx2_blob(name, desc, body, {REPORT_MARK: True}, attr=REPORT_ATTR), tok)
    if st not in (200, 201):
        print(f"! upload FAILED — HTTP {st} {uuid}\n  {path} is untouched. Hand it over instead.")
        return 1
    if not grant_read(uuid, admin_uuid, tok):
        print(f"! uploaded {uuid} but the READ grant to {ADMIN} FAILED.\n"
              f"  Grant it manually, or hand over {path} instead.")
        return 1

    print(f"\nsent {name}  {uuid}  (READ granted to {ADMIN})")
    print(f"{path} is unchanged. Read it back later with: "
          f"python session_report.py --as {args.prefix} --list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
