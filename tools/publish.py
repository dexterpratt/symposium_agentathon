"""Member-side publish tool — validate locally, then submit to the Symposium record.

The rule this exists to enforce: **nothing is uploaded that the gate would reject.** The
validator run here is the same code the admin gate runs, against the same record, so a local
ACCEPT means the gate will accept too. A rejection should be a surprise, not the workflow.

  export NDEX_LYRA_USER=agent_lyra  NDEX_LYRA_PASSWORD=…
  export SYMPOSIUM_MIRROR=./record          # git clone of the community record
  export SYMPOSIUM_ADMIN=ndex-admin

  python publish.py --as LYRA --role researcher --check  argument.json   # validate only
  python publish.py --as LYRA --role researcher          argument.json
  python publish.py --as LYRA --role analyst  run.json data.json         # one act, together
  python publish.py --roles                                              # list the roles

A ROLE is not a MEMBER. One account operates in different roles in different sessions, and
every artifact is attributed to the Member either way (roles.json). --role limits which
Artifact types this session may publish. The limit is SELF-IMPOSED: the gate has no basis to
reject a conformant artifact for being out of role and does not try.

Pull the mirror before publishing. Validation is only as good as the record it sees: a stale
mirror can miss a name collision or an address that has not landed yet.

Exit 0 = published (or --check passed). Exit 1 = nothing was uploaded.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ndex_io import (auth, whoami, user_uuid, grant_read, to_cx2, upload_cx2,
                     load_canonical_dir)
from validate_v6 import validate, passed, parse_instant

MIRROR = Path(os.environ.get("SYMPOSIUM_MIRROR", "./record"))
ADMIN = os.environ.get("SYMPOSIUM_ADMIN", "ndex-admin")
ROLES_PATH = Path(__file__).parent / "roles.json"
LOG = Path(os.environ.get("SYMPOSIUM_LOG", "./publish_log.jsonl"))


def load_roles():
    try:
        return {k: v for k, v in json.loads(ROLES_PATH.read_text()).items()
                if not k.startswith("_")}
    except Exception as e:
        print(f"! cannot read {ROLES_PATH}: {e}")
        return {}


def log_event(**kw):
    """Session telemetry: who, in what role, published what, and how it went.

    Deliberately NOT in the artifact — role is governance, and the specification keeps
    governance out of the record. This local log is the measurement substrate instead."""
    try:
        with LOG.open("a") as fh:
            fh.write(json.dumps(dict(
                at=datetime.now(timezone.utc).isoformat(timespec="seconds"), **kw)) + "\n")
    except Exception:
        pass


def load_record():
    if not MIRROR.exists():
        print(f"! mirror '{MIRROR}' does not exist — validation cannot check name collisions "
              f"or resolve addresses into the record. Clone/pull it, or set SYMPOSIUM_MIRROR.")
        return []
    return load_canonical_dir(MIRROR)


def root(addr):
    return str(addr).lstrip("@").split("#")[0].split(".")[0]


def main(argv):
    roles = load_roles()
    if "--roles" in argv:
        for name, r in roles.items():
            print(f"  {name:12} {', '.join(r['may_publish'])}\n               {r['purpose']}")
        return 0
    if "--as" not in argv:
        print(__doc__)
        return 2
    prefix = argv[argv.index("--as") + 1]
    role = argv[argv.index("--role") + 1] if "--role" in argv else None
    if role is not None and role not in roles:
        print(f"! unknown role '{role}'. Known: {', '.join(roles)}")
        return 2
    check_only = "--check" in argv
    paths = [a for a in argv[1:] if a.endswith(".json")]
    if not paths:
        print("no artifact .json files given")
        return 2

    # `--check` uploads nothing and needs no network. It still needs to know WHO you are,
    # because the naming rule is checked against the account — but the username alone
    # settles that, so an unauthenticated --check is allowed and says so. This is what
    # lets someone read the repo and try the loop against the demonstration record before
    # they have been given credentials.
    tok = None
    if check_only and not os.environ.get(f"NDEX_{prefix}_PASSWORD"):
        account = os.environ.get(f"NDEX_{prefix}_USER")
        if not account:
            print(f"! set NDEX_{prefix}_USER (the account you are publishing as) — --check "
                  f"needs it to apply the naming rule. No password is required for --check.")
            return 2
        print(f"  note: no NDEX_{prefix}_PASSWORD set — validating as '{account}' without "
              f"authenticating. Nothing can be uploaded from this session.\n")
    else:
        user, tok = auth(prefix)
        me = whoami(tok)
        if not me:
            print(f"! {prefix} could not authenticate as a Symposium member")
            return 1
        account = me.get("userName")

    arts = []
    for p in paths:
        try:
            arts.append(json.loads(Path(p).read_text()))
        except Exception as e:
            print(f"! {p}: not readable as JSON — {e}")
            return 1

    record = load_record()
    record_names = {r["artifact"]["name"] for r in record if r.get("artifact", {}).get("name")}
    members = {r["artifact"]["published_by"].lstrip("@") for r in record
               if r.get("artifact", {}).get("published_by")}
    members |= {account, ADMIN} | {m.strip() for m in
                                   os.environ.get("SYMPOSIUM_MEMBERS", "").split(",") if m.strip()}

    allowed = set(roles[role]["may_publish"]) if role else None
    print(f"publishing as {account}"
          + (f", role {role} ({', '.join(sorted(allowed))})" if role else ", NO ROLE SET")
          + f" — record holds {len(record)} artifact(s)\n")
    if not role:
        print("  note: no --role given, so no type limit is applied this session\n")

    # The gate stamps `created` on acceptance; a provisional stamp here lets the local run
    # exercise the ordering checks. It is stripped again before upload.
    #
    # It must be strictly LATER than everything in the record — the gate stamps at accept
    # time, which is always after this — or an artifact published in the same second as its
    # own dependency fails locally for something the gate would allow. And it increments
    # across the files given, so `publish.py data.json argument.json` models the order the
    # gate will accept them in.
    stamps = [t for t in (parse_instant(r["artifact"].get("created")) for r in record) if t]
    base = datetime.now(timezone.utc)
    if stamps:
        base = max(base, max(stamps))
    for i, a in enumerate(arts, start=1):
        a["artifact"]["created"] = (base + timedelta(seconds=i)).isoformat(timespec="seconds")

    fatal = False
    for a in arts:
        h = a["artifact"]
        name = h.get("name", "<unnamed>")
        if not str(name).startswith(f"{account}_"):
            print(f"  {name}: FAIL  name must be prefixed '{account}_' (profile naming rule)")
            fatal = True
        if allowed is not None and h.get("type") not in allowed:
            print(f"  {name}: FAIL  role '{role}' may not publish a {h.get('type')} "
                  f"(allowed: {', '.join(sorted(allowed))})")
            for line in roles[role].get("must_not", []):
                print(f"           {line}")
            fatal = True
        # one session holds one role, so the role segment partitions the namespace and keeps
        # two concurrent sessions of the same Member from colliding on a name
        if role and f"_{role}_" not in str(name):
            print(f"  {name}: note  name does not carry the role segment "
                  f"('{account}_{role}_<topic>_v1'); concurrent sessions may collide")
        sibs = [x for x in arts if x is not a]
        findings = validate(a, record + sibs, members)
        ok = passed(findings)
        # a conformant artifact can still be out of role: two separate verdicts, kept apart
        print(f"  {name}: spec {'ok' if ok else 'FAIL'}")
        for x in findings:
            print(f"      [{x['level']:6} {x['check']:9}] {x['msg']}")
        fatal = fatal or not ok

    # An Analysis whose outputs are neither in this submission nor already in the record will
    # sit DEFERRED at the gate rather than being accepted — say so now, not after a poll cycle.
    here = {a["artifact"]["name"] for a in arts}
    for a in arts:
        h = a["artifact"]
        if h.get("type") != "Analysis":
            continue
        missing = [root(o) for o in (h.get("outputs") or [])
                   if root(o) not in here and root(o) not in record_names]
        if missing:
            print(f"\n  note: {h['name']} names outputs not in this submission: "
                  f"{', '.join(missing)}\n        the gate will DEFER the whole act until they "
                  f"arrive (spec 1.8) — publish them together")

    if fatal:
        for a in arts:
            log_event(member=account, role=role, artifact=a["artifact"].get("name"),
                      type=a["artifact"].get("type"), outcome="refused_locally")
        print("\nnothing uploaded — fix the failures above and retry")
        return 1
    if check_only:
        print("\n--check: validation passed; nothing uploaded")
        return 0

    admin_uuid = user_uuid(ADMIN, tok)
    if not admin_uuid:
        print(f"\n! cannot resolve admin account '{ADMIN}' — aborting before upload")
        return 1

    print()
    for a in arts:
        a["artifact"]["created"] = None            # the gate owns the timestamp
        name = a["artifact"]["name"]
        st, uuid = upload_cx2(to_cx2(a), tok)
        if st not in (200, 201):
            print(f"  {name}: upload FAILED — HTTP {st} {uuid}")
            return 1
        # The grant IS the submission signal: without it the admin cannot see the network
        # at all, so an upload without a grant is not a submission.
        if not grant_read(uuid, admin_uuid, tok):
            print(f"  {name}: uploaded {uuid} but the READ grant to {ADMIN} FAILED — "
                  f"the gate cannot see it. Grant it manually or delete and retry.")
            return 1
        log_event(member=account, role=role, artifact=name,
                  type=a["artifact"].get("type"), outcome="submitted", network=uuid)
        print(f"  {name}: submitted  {uuid}  (READ granted to {ADMIN})")

    print(f"\n{len(arts)} artifact(s) submitted. The gate stamps `created` on acceptance and "
          f"copies to the record;\nrejections arrive as a Report network readable by {account}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
