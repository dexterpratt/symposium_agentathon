"""Symposium admin gate — discover, validate, accept-or-reject on symposium.ndexbio.org.

The publication loop, exactly as smoke-tested 2026-08-05:

  member  : uploads CX2 (canonical JSON in the `symposium_canonical` network attribute),
            then grants ndex-admin READ.  Without the grant the admin cannot see it at all.
  admin   : polls granted networks -> extracts canonical -> validates (validate_v6)
            ACCEPT : stamp `created`, copy into the record, fan out READ to every member,
                     write canonical JSON to the mirror repo, index the name
            REJECT : upload a reply artifact naming the failures; the member polls for it

Four server facts this is built around, all established empirically on build ac3ee:
  * group-principal sharing is broken, so read access fans out as user->user grants
  * folders are navigation only, and the folder REST API is absent (every path 404s inside
    a 500) — bundling is declared by the artifacts, not by a folder
  * a freshly uploaded private network has `indexLevel: NONE` and never appears in
    /v2/search/network, so discovery uses the permission map, not search
  * NDEx search TOKENISES and cannot do exact-name matching, so name uniqueness lives in the
    mirror repo index, never in a server query

Credentials come from the environment; nothing is passed on the command line.

  NDEX_ADMIN_USER / NDEX_ADMIN_PASSWORD        the gate's own account
  SYMPOSIUM_MEMBERS=agent_lyra,agent_vega      members who receive read access

  python gate.py --once            one pass
  python gate.py --dry-run         validate and report; publish nothing
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import telemetry
from ndex_io import (BASE, CANONICAL_ATTR, RECORD_MARK, REPLY_MARK, auth, api as _api,
                     extract_canonical, grant_read as _grant, to_cx2, upload_cx2 as _upload,
                     user_uuid, load_canonical_dir)
from validate_v6 import validate, passed

MIRROR = Path(os.environ.get("SYMPOSIUM_MIRROR", "./record"))
DRY = "--dry-run" in sys.argv

ADMIN_USER, ADMIN_TOK = auth("ADMIN")
MEMBERS = [m.strip() for m in os.environ.get("SYMPOSIUM_MEMBERS", "").split(",") if m.strip()]


def api(method, path, body=None, raw=False, tok=None):
    return _api(method, path, tok or ADMIN_TOK, body=body, raw=raw)


def upload_cx2(aspects, tok=None):
    return _upload(aspects, tok or ADMIN_TOK)


def _extract(uuid):
    return extract_canonical(uuid, ADMIN_TOK)


# --------------------------------------------------------------------------- mirror repo
def load_record():
    MIRROR.mkdir(parents=True, exist_ok=True)
    return load_canonical_dir(MIRROR)


def write_record(canonical, uuid):
    p = MIRROR / f"{canonical['artifact']['name']}.json"
    p.write_text(json.dumps(canonical, indent=2) + "\n")
    (MIRROR / "index.jsonl").open("a").write(json.dumps(
        {"name": canonical["artifact"]["name"], "type": canonical["artifact"]["type"],
         "created": canonical["artifact"]["created"], "network": uuid}) + "\n")
    return p


# --------------------------------------------------------------------------- discovery
def discover():
    """Submissions the admin can see, driven by the grant itself.

    NOT by search: on this deployment a freshly uploaded private network has
    `indexLevel: NONE` and simply does not appear in /v2/search/network, so search-based
    discovery silently drops submissions. The permission map is exact and immediate — a
    member's grant IS the submission signal."""
    st, me = api("GET", "/v2/user?valid=true")
    if st != 200:
        print(f"  ! cannot resolve admin account: HTTP {st}")
        return []
    st, perms = api("GET", f"/v2/user/{me['externalId']}/permission?type=NETWORK&permission=READ")
    if st != 200 or not isinstance(perms, dict):
        print(f"  ! permission listing failed: HTTP {st}")
        return []
    subs = []
    for uuid, level in perms.items():
        if level != "READ":
            continue                       # ADMIN/WRITE = our own record copies and replies
        st, s = api("GET", f"/v2/network/{uuid}/summary")
        if st != 200 or not isinstance(s, dict):
            print(f"  ! summary {uuid[:8]} failed: HTTP {st}")
            continue
        if s.get("owner") == ADMIN_USER:
            continue
        subs.append({"uuid": uuid, "name": s.get("name"), "owner": s.get("owner")})
    return subs


def grant_read(uuid, member_uuid):
    return _grant(uuid, member_uuid, ADMIN_TOK)


def member_uuids():
    out = {}
    for m in MEMBERS:
        u = user_uuid(m, ADMIN_TOK)
        if u:
            out[m] = u
        else:
            print(f"  ! cannot resolve member '{m}'")
    return out


# --------------------------------------------------------------------------- accept / reject
def _root(addr):
    """Artifact name at the head of an address."""
    return str(addr).lstrip("@").split("#")[0].split(".")[0]


def form_bundles(subs, record_names):
    """Group submissions into publication units.

    An Analysis and the Artifacts it produces are published as a single act (spec 1.8) and
    must be validated and accepted together — neither can be validated alone, because their
    `outputs`/`produced_by` addresses refer to each other. The bundle is declared by the
    artifacts themselves; no folder or external grouping is needed.

    -> (bundles, deferred) where deferred are units still missing a member."""
    by_name = {s["canonical"]["artifact"]["name"]: s for s in subs}

    def leader_of(c):
        h = c["artifact"]
        if h.get("produced_by"):
            return _root(h["produced_by"])          # the Analysis leads the unit
        return h["name"]

    groups = {}
    for s in subs:
        groups.setdefault(leader_of(s["canonical"]), []).append(s)

    bundles, deferred = [], []
    for leader, members in groups.items():
        required = {m["canonical"]["artifact"]["name"] for m in members}
        lead_sub = by_name.get(leader)
        if lead_sub is not None and lead_sub["canonical"]["artifact"].get("type") == "Analysis":
            required |= {_root(a) for a in (lead_sub["canonical"]["artifact"].get("outputs") or [])}
            required.add(leader)
        elif leader not in record_names and leader not in by_name:
            deferred.append((members, [leader]))     # produced_by names an Analysis we cannot see
            continue
        missing = sorted(required - set(by_name) - set(record_names))
        if missing:
            deferred.append((members, missing))
            continue
        bundles.append([by_name[n] for n in sorted(required) if n in by_name])

    # Order bundles so one is accepted before any bundle that addresses it. Without this the
    # acceptance order follows the permission map, which is unordered, and `created` could be
    # stamped so that an Argument precedes the Data it grounds on.
    def refs(bundle):
        out = set()
        for m in bundle:
            c = m["canonical"]
            h = c["artifact"]
            for k in ("produced_by", "extracted_from"):
                if h.get(k):
                    out.add(_root(h[k]))
            for k in ("supersedes", "inputs", "used_models", "outputs", "recipients"):
                for v in (h.get(k) or []):
                    out.add(_root(v))
            for o in c.get("objects", []):
                if o.get("type") == "Ground":
                    out.add(_root(o.get("address", "")))
        return out - {m["canonical"]["artifact"]["name"] for m in bundle}

    ordered, placed, pending = [], set(record_names), list(bundles)
    while pending:
        ready = [b for b in pending if refs(b) <= placed | (set(by_name) - {
            m["canonical"]["artifact"]["name"] for bb in pending for m in bb})]
        ready = [b for b in pending if not (refs(b) & {
            m["canonical"]["artifact"]["name"] for bb in pending for m in bb} - placed)]
        if not ready:                      # a cycle among submissions; fall back to given order
            ready = pending[:1]
        for b in ready:
            ordered.append(b)
            placed |= {m["canonical"]["artifact"]["name"] for m in b}
            pending.remove(b)
    return ordered, deferred


def accept(canonical, record, muuids, stamp=None):
    name = canonical["artifact"]["name"]
    canonical["artifact"]["created"] = stamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    if DRY:
        print(f"    (dry-run) would accept {name}")
        return True
    st, uuid = upload_cx2(to_cx2(canonical, marks={RECORD_MARK: True}))
    if st not in (200, 201):
        print(f"    ! record copy failed: HTTP {st} {uuid}")
        return False
    for m, mu in muuids.items():
        if mu and not grant_read(uuid, mu):
            print(f"    ! could not grant READ to {m}")
    write_record(canonical, uuid)
    print(f"    ACCEPTED -> record {uuid}, {len(muuids)} read grants, mirrored")
    return True


def reject(canonical, submitted_name, findings, owner, muuids):
    fails = [f"{x['check']}: {x['msg']}" for x in findings if x["level"] == "FAIL"]
    reply_name = f"{ADMIN_USER}_REPLY_{submitted_name}"
    reply = {"artifact": {"name": reply_name.replace("-", "_"), "type": "Report",
                          "specification_version": "6", "published_by": f"@{ADMIN_USER}",
                          "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "text": "REJECTED\n\nin_reply_to: " + submitted_name + "\n\n"
                                  + "\n".join(f"- {x}" for x in fails)},
             "objects": [], "relationships": []}
    print(f"    REJECTED ({len(fails)} failures)")
    for x in fails[:6]:
        print(f"      - {x[:150]}")
    if DRY:
        return
    st, uuid = upload_cx2(to_cx2(reply, marks={REPLY_MARK: True,
                                                 "symposium_in_reply_to": submitted_name}))
    if st in (200, 201):
        mu = muuids.get(owner)
        if mu:
            grant_read(uuid, mu)
        print(f"    reply posted -> {uuid} (readable by {owner})")
    else:
        print(f"    ! reply upload failed: HTTP {st} {uuid}")


def run_once():
    record = load_record()
    names = {r["artifact"]["name"] for r in record if r.get("artifact", {}).get("name")}
    members = set(MEMBERS) | {ADMIN_USER}
    muuids = member_uuids()
    print(f"gate: record holds {len(record)} artifact(s); members {sorted(members)}"
          + ("  [DRY RUN]" if DRY else ""))

    raw = discover()
    print(f"gate: {len(raw)} visible submission(s)\n")

    subs = []
    for s in raw:
        if s["name"] in names:
            print(f"  {s['name']}: already in the record — skipping")
            continue
        canonical, err = _extract(s["uuid"])
        if err:
            print(f"  {s['name']}: ! {err}")
            continue
        declared = canonical.get("artifact", {}).get("name")
        if declared != s["name"]:
            print(f"  {s['name']}: ! network name != artifact.name '{declared}'")
            continue
        if not declared.startswith(f"{s['owner']}_"):
            print(f"  {declared}: ! name is not prefixed with the owner '{s['owner']}_'")
            continue
        s["canonical"] = canonical
        subs.append(s)

    bundles, deferred = form_bundles(subs, names)
    for members, missing in deferred:
        who = ", ".join(m["name"] for m in members)
        print(f"  DEFERRED {who}\n    waiting for: {', '.join(missing)} (single act, spec 1.8)")
        for m in members:
            telemetry.emit("gate", "gate_defer", "deferred", artifact=m["name"],
                           atype=m["canonical"]["artifact"].get("type"),
                           submitter=m["owner"], waiting_for=sorted(missing))

    for bundle in bundles:
        # one act -> one timestamp, so the record shows the single-act property directly
        # rather than requiring a reader to apply the ordering exception
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        label = " + ".join(m["canonical"]["artifact"]["name"] for m in bundle)
        print(f"  {label}" + ("   [bundle]" if len(bundle) > 1 else ""))
        for m in bundle:
            m["canonical"]["artifact"]["created"] = stamp

        # each member is validated against the record PLUS its siblings, so the mutual
        # outputs/produced_by addresses resolve
        results = []
        for m in bundle:
            sibs = [x["canonical"] for x in bundle if x is not m]
            results.append((m, validate(m["canonical"], record + sibs, members)))

        if all(passed(f) for _, f in results):
            for m, f in results:
                for x in f:
                    print(f"    [REVIEW {x['check']}] {x['msg'][:110]}")
            ok = all(accept(m["canonical"], record, muuids, stamp=stamp) for m, _ in results)
            if ok:
                for m, f in results:
                    record.append(m["canonical"])
                    names.add(m["canonical"]["artifact"]["name"])
                    # REVIEW findings are logged at the moment of acceptance because they
                    # are the validator signal that SURVIVES into the record — the same
                    # findings can be recomputed tomorrow, but not the fact that the gate
                    # saw them and accepted anyway.
                    telemetry.emit("gate", "gate_accept", "accepted",
                                   artifact=m["canonical"]["artifact"]["name"],
                                   atype=m["canonical"]["artifact"].get("type"),
                                   submitter=m["owner"], findings=f,
                                   bundle=len(bundle) if len(bundle) > 1 else None)
        else:
            # all-or-nothing: a bundle is one act, so a failure anywhere rejects the unit
            if len(bundle) > 1:
                print("    bundle rejected as a unit — an Analysis and its outputs are one act")
            for m, f in results:
                if not passed(f):
                    reject(m["canonical"], m["name"], f, m["owner"], muuids)
                    telemetry.emit("gate", "gate_reject", "rejected", artifact=m["name"],
                                   atype=m["canonical"]["artifact"].get("type"),
                                   submitter=m["owner"], findings=f, refusal=["spec"],
                                   bundle=len(bundle) if len(bundle) > 1 else None)
                else:
                    print(f"    {m['name']}: conformant, but withheld with its bundle")
                    # Conformant and still not in the record: an outcome with no equivalent
                    # on the member side, and invisible unless it is logged here.
                    telemetry.emit("gate", "gate_withhold", "withheld", artifact=m["name"],
                                   atype=m["canonical"]["artifact"].get("type"),
                                   submitter=m["owner"], findings=f, bundle=len(bundle))
    return 0


if __name__ == "__main__":
    sys.exit(run_once())
