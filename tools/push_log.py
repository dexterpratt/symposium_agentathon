#!/usr/bin/env python3
"""Send this session's event log to the admin.

    python push_log.py --as VEGA          # push
    python push_log.py --as VEGA --check  # show what would be sent; upload nothing

Participants share no filesystem, so a session's log — what was attempted, what was refused,
and how many rounds it took — otherwise stays on the machine that ran it. This pushes it
through the one channel that already connects every Member to the admin: upload a network,
grant the admin READ. Exactly how a submission travels, because the grant IS the channel; a
freshly uploaded private network never appears in search.

**This is not a publication.** The network carries no canonical JSON, is marked
`symposium_telemetry`, and is named with the reserved `_TELEMETRY_` segment. The gate skips
it on both counts. Nothing here enters the CommunityRecord, and nothing here is visible to
other Members: the grant goes to the admin alone.

Three properties worth keeping if this is ever changed:

  * **The local file stays authoritative and is never deleted.** The push is a mirror. If
    NDEx is down — which is exactly when you most want to know what agents were hitting —
    the log is still on disk and can be handed over by other means. Measurement riding on
    the system under test is acceptable only while that remains true.
  * **The whole log is sent every time.** `metrics.py` de-duplicates on the whole event, so
    repeated pushes are idempotent by construction: no append protocol, no update semantics,
    no way for two pushes to interleave wrongly. Push as often as you like.
  * **A failed push is reported and changes nothing else.** It never fails a publish and
    never touches the record.

Run it when a session ends, and any time you want the admin's mid-day metrics to include
your session — until your log arrives, their numbers see only the gate's half.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import telemetry
from ndex_io import (TELEMETRY_MARK, TELEMETRY_SEGMENT, auth, grant_read, to_cx2_blob,
                     upload_cx2, user_uuid, whoami)

ADMIN = os.environ.get("SYMPOSIUM_ADMIN", "ndex-admin")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--as", dest="prefix", required=True,
                    help="credential prefix, e.g. VEGA (NDEX_VEGA_USER / _PASSWORD)")
    ap.add_argument("--log", default=None, help="log file (default: $SYMPOSIUM_LOG)")
    ap.add_argument("--check", action="store_true", help="report only; upload nothing")
    args = ap.parse_args(argv)

    log = Path(args.log) if args.log else telemetry.LOG
    if not log.exists():
        print(f"! no event log at {log}\n"
              f"  Nothing has been logged from this session yet, or SYMPOSIUM_LOG points "
              f"somewhere else.")
        return 1

    events = telemetry.read(log)
    payload = log.read_text()
    sessions = sorted({e.get("session") for e in events if e.get("session")})
    print(f"{log}: {len(events)} event(s), {len(payload)} bytes, "
          f"{len(sessions)} session(s)")
    for s in sessions:
        n = sum(1 for e in events if e.get("session") == s)
        print(f"  {s}  ({n} event(s))")
    if not events:
        print("! the log is empty — nothing to send")
        return 1

    if args.check:
        print("\n--check: nothing uploaded. The local file is unchanged either way.")
        return 0

    user, tok = auth(args.prefix)
    me = whoami(tok)
    account = (me or {}).get("userName")
    if not account:
        print(f"! {args.prefix} could not authenticate")
        return 1
    admin_uuid = user_uuid(ADMIN, tok)
    if not admin_uuid:
        print(f"! cannot resolve admin account '{ADMIN}' — nothing uploaded")
        return 1

    # A distinct name per push, so successive pushes do not look like one network being
    # rewritten and a partial upload never overwrites a complete one. The admin merges and
    # de-duplicates, so several pushes from one session cost nothing but a little clutter.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{account}{TELEMETRY_SEGMENT}{stamp}"
    desc = (f"Symposium event log from {account}: {len(events)} event(s) across "
            f"{len(sessions)} session(s). Not an Artifact; not part of the record.")

    st, uuid = upload_cx2(to_cx2_blob(name, desc, payload, {TELEMETRY_MARK: True}), tok)
    if st not in (200, 201):
        print(f"! upload FAILED — HTTP {st} {uuid}\n"
              f"  The local log at {log} is untouched. Hand it over instead.")
        return 1
    if not grant_read(uuid, admin_uuid, tok):
        print(f"! uploaded {uuid} but the READ grant to {ADMIN} FAILED — the admin cannot "
              f"see it.\n  Grant it manually, or hand over {log} instead.")
        return 1

    print(f"\nsent {name}  {uuid}  (READ granted to {ADMIN})")
    print(f"the local log at {log} is unchanged — it stays the authoritative copy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
