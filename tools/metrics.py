#!/usr/bin/env python3
"""Measure the record and the event that produced it.

RUN THIS ON THE ADMIN MACHINE. It reads two inputs with very different properties:

  * **The record** — the gate's own `SYMPOSIUM_MIRROR`. This is the single source of truth:
    `gate.py` writes accepted artifacts there, and a Member's mirror is only a copy pulled
    down by `sync.py`. Point `--record` at the gate's mirror, never at a member's.

  * **The event log** — written by whichever process ran. **Participants share no
    filesystem**, so member-side refusals sit on member machines until somebody carries
    them across: each session hands over its log file at the end, alongside its session
    report, and the files are dropped into one directory here. `--events` takes a
    directory, a file or a glob and MERGES them, dropping duplicates, so re-running after
    each new file arrives is safe and the same file can be added twice without harm.

    python metrics.py --record ./record --events ./events/ --out ./metrics

    Run it before any logs are collected and it still works: the gate's own events are on
    this machine, so acceptances, rejections and deferrals are all present. What is missing
    until collection is the pre-submission half — the local refusals and the rounds — and
    the report will show it as a small `artifacts_attempted` beside a full record.

Why both. Every artifact in the record passed validation — that is what acceptance means —
so the record can say what the community built but cannot say what it cost, what was refused,
or how many rounds anything took. That half exists only in the log, and only if it was
captured at the time.

WHAT THIS IS NOT. One day, a handful of accounts, tens of artifacts. These numbers are
DESCRIPTIVE. They exist to point a reader at the artifacts worth opening and to put concrete
counts behind qualitative claims. They do not support significance testing or member-versus-
member comparison, and the report says so on its face.

Deliberately absent: any ranking of Arguments by quality. A metric that scored
`supported_for_purpose` above `insufficient` would invert the framework's own stance — the
member instructions tell agents to reach for `insufficient` often and say plainly it is not a
failure state — and, if it ever became visible to agents, would reward overclaiming. Value
ranking stays human and blind.
"""
from __future__ import annotations

import argparse
import glob as globlib
import json
import os
import pathlib
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import telemetry                                                       # noqa: E402
from browse_v6 import load_record, run_validator                       # noqa: E402
from validate_v6 import build_index, parse_address                     # noqa: E402

PRESERVED_TYPES = {"Data", "ScientificPublication", "Model"}
ARGUMENT = "Argument"
VERDICTS = ("supported_for_purpose", "insufficient", "falsified")

# Words an author reaches for when admitting that Grounds share a source. Used ONLY to
# triage: every hit and every miss is printed with the evaluation text so a human decides.
# A regex cannot read prose, and pretending otherwise would be the exact overclaim this
# whole framework exists to make visible.
_ACK_HINTS = re.compile(
    r"\b(independen\w*|corroborat\w*|same (study|source|paper|table|section|dataset|analysis)"
    r"|one (study|source|paper)|not .{0,20}independent|share[sd]?\b|shared)\b", re.I)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

def load_events(spec):
    """Merge every event log named by `spec` (a file, a directory, or a glob).

    Deduplicated on the whole event, so re-running over a directory that also holds a
    copied-in log from another machine does not double-count.
    """
    paths = []
    for s in (spec if isinstance(spec, (list, tuple)) else [spec]):
        p = pathlib.Path(s)
        if p.is_dir():
            paths += sorted(p.glob("*.jsonl"))
        elif any(ch in str(s) for ch in "*?["):
            paths += [pathlib.Path(x) for x in sorted(globlib.glob(str(s)))]
        elif p.exists():
            paths.append(p)
    seen, out = set(), []
    for p in paths:
        for e in telemetry.read(p):
            key = json.dumps(e, sort_keys=True)
            if key not in seen:
                seen.add(key)
                out.append(e)
    out.sort(key=lambda e: e.get("at") or "")
    return out, [str(p) for p in paths]


def argument_parts(doc):
    """-> (assertions, assessments, grounds, assumptions, out_edges) for an Argument."""
    objs = {o["name"]: o for o in doc.get("objects", []) if o.get("name")}
    kind = lambda t: {n: o for n, o in objs.items() if o.get("type") == t}   # noqa: E731
    out = defaultdict(list)
    for r in doc.get("relationships", []):
        out[r.get("source")].append((r.get("rel"), r.get("target")))
    return (kind("Assertion"), kind("Assessment"), kind("Ground"),
            kind("Assumption"), out)


# --------------------------------------------------------------------------- #
# M1 — basis composition
# --------------------------------------------------------------------------- #

def basis_composition(arguments):
    """What each Assertion actually rests on.

    An Assertion resting only on an Assumption is a different animal from one resting on a
    measurement, and the record does not distinguish them anywhere a reader can see at a
    glance. The gate guarantees every Assertion has SOME basis (spec 2.2); it says nothing
    about which.
    """
    combos, rows = Counter(), []
    for doc in arguments:
        name = doc["artifact"]["name"]
        assertions, _asm, grounds, assumptions, out = argument_parts(doc)
        for an in assertions:
            g = [t for rel, t in out.get(an, []) if rel == "grounded_by" and t in grounds]
            d = [t for rel, t in out.get(an, []) if rel == "depends_on" and t in assertions]
            u = [t for rel, t in out.get(an, []) if rel == "assumes" and t in assumptions]
            key = "+".join(k for k, v in
                           (("grounded", g), ("depends", d), ("assumes", u)) if v) or "NONE"
            combos[key] += 1
            rows.append({"argument": name, "assertion": an, "grounds": len(g),
                         "depends_on": len(d), "assumes": len(u), "basis": key})
    return {"by_combination": dict(combos.most_common()),
            "assertions": len(rows),
            "assumption_only": sum(1 for r in rows if r["basis"] == "assumes"),
            "no_basis": sum(1 for r in rows if r["basis"] == "NONE"),
            "rows": rows}


# --------------------------------------------------------------------------- #
# M2 — criterion rate
# --------------------------------------------------------------------------- #

def criterion_rate(arguments):
    """How often a Ground claims the material was used as a TEST.

    A `criterion` states what result would have counted against the claim, which is the
    strongest and most falsifiable thing an author asserts anywhere in the format. Both
    extremes are interesting and neither is good: near zero means nobody put a claim at
    risk, near one means the criterion has become decoration asserted where no test could
    have failed. Split by Member, because that separates a property of the framework from a
    property of one agent.
    """
    per_member, per_argument, total, with_c = Counter(), {}, 0, 0
    per_member_total = Counter()
    for doc in arguments:
        name = doc["artifact"]["name"]
        member = doc["artifact"].get("published_by", "").lstrip("@")
        _a, _s, grounds, _u, _o = argument_parts(doc)
        n = len(grounds)
        c = sum(1 for g in grounds.values() if g.get("criterion"))
        total += n
        with_c += c
        per_member[member] += c
        per_member_total[member] += n
        per_argument[name] = {"grounds": n, "with_criterion": c,
                              "rate": round(c / n, 3) if n else None}
    return {
        "grounds": total, "with_criterion": with_c,
        "rate": round(with_c / total, 3) if total else None,
        "by_member": {m: {"grounds": per_member_total[m], "with_criterion": per_member[m],
                          "rate": round(per_member[m] / per_member_total[m], 3)
                                  if per_member_total[m] else None}
                      for m in sorted(per_member_total)},
        "by_argument": per_argument,
    }


# --------------------------------------------------------------------------- #
# M3 — distance to a measurement, and how much of it is testimony
# --------------------------------------------------------------------------- #

def trust_chains(arguments, index):
    """For every Assertion: does its support terminate in preserved content, and how many
    times does the path pass through another author's conclusion to get there?

    This is the measure the framework exists for. Grounding on another Argument's Assertion
    takes that author's conclusion as testimony (spec 2.2.4) — legitimate, and materially
    different from reading a measurement, because the reader can only credit it rather than
    examine it. A claim three testimony hops from anything preserved may be perfectly sound
    and is certainly worth knowing about.

    Two numbers, kept apart on purpose:

      testimony_hops   times the path crosses into ANOTHER Argument's Assertion. 0 means
                       this author grounded on preserved content themselves.
      steps            total edges traversed, counting an author's own `depends_on`
                       decomposition, which adds distance but no second-hand trust.

    `terminates` false means no path reaches preserved content at all: the support rests
    entirely on assumptions, on a cycle, or on testimony that itself never lands. That is
    not a verdict on the claim — it is a statement about what a reader can check.
    """
    # global assertion table: (argument, assertion) -> its grounds and local dependencies
    node = {}
    for doc in arguments:
        aname = doc["artifact"]["name"]
        assertions, _s, grounds, _u, out = argument_parts(doc)
        for an in assertions:
            terminal, testimony, deps = [], [], []
            for rel, t in out.get(an, []):
                if rel == "depends_on" and t in assertions:
                    deps.append((aname, t))
                elif rel == "grounded_by" and t in grounds:
                    p = parse_address(grounds[t].get("address", ""))
                    if not p:
                        continue
                    root, rec = p["root"], index.get(p["root"])
                    if not rec:
                        continue
                    if rec["type"] in PRESERVED_TYPES:
                        terminal.append(grounds[t].get("address"))
                    elif rec["type"] == ARGUMENT and p["segs"]:
                        tgt = rec["objects"].get(p["segs"][0], {})
                        if tgt.get("type") == "Assertion":
                            testimony.append((root, p["segs"][0]))
            node[(aname, an)] = {"terminal": terminal, "testimony": testimony, "deps": deps}

    memo, rows = {}, []

    def solve(key, stack):
        """-> (terminates, testimony_hops, steps). Cycles resolve to no termination."""
        if key in memo:
            return memo[key]
        if key in stack or key not in node:
            return (False, None, None)
        n = node[key]
        best = (False, None, None)
        if n["terminal"]:
            best = (True, 0, 1)
        for tgt in n["testimony"]:                       # crossing to another author: +1 hop
            ok, hops, steps = solve(tgt, stack | {key})
            if ok and (not best[0] or (hops + 1, steps + 1) < (best[1], best[2])):
                best = (True, hops + 1, steps + 1)
        for tgt in n["deps"]:                            # own decomposition: distance only
            ok, hops, steps = solve(tgt, stack | {key})
            if ok and (not best[0] or (hops, steps + 1) < (best[1], best[2])):
                best = (True, hops, steps + 1)
        memo[key] = best
        return best

    for key in node:
        ok, hops, steps = solve(key, frozenset())
        rows.append({"argument": key[0], "assertion": key[1], "terminates": ok,
                     "testimony_hops": hops, "steps": steps,
                     "direct_grounds": len(node[key]["terminal"]),
                     "testimony_grounds": len(node[key]["testimony"])})

    term = [r for r in rows if r["terminates"]]
    return {
        "assertions": len(rows),
        "terminates_in_measurement": len(term),
        "does_not_terminate": len(rows) - len(term),
        "by_testimony_hops": dict(sorted(Counter(r["testimony_hops"] for r in term).items())),
        "max_testimony_hops": max((r["testimony_hops"] for r in term), default=None),
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# M4 — was non-independence acknowledged?
# --------------------------------------------------------------------------- #

def independence_acknowledgement(arguments, findings_by):
    """Where the validator saw Grounds sharing a source, did the author say so?

    Pure intent-compliance: the gate cannot enforce this and does not try (spec 2.2.4 makes
    it best practice), which is exactly why it is worth counting. A reader skimming a claim
    map sees several Grounds and reads corroboration unless the evaluation says otherwise.

    The verdict here is a TRIAGE, not a measurement. The evaluation text is carried into the
    output beside the finding so a human settles each case in seconds.
    """
    cases = []
    by_name = {d["artifact"]["name"]: d for d in arguments}
    for name, findings in findings_by.items():
        doc = by_name.get(name)
        if not doc:
            continue
        assertions, assessments, _g, _u, out = argument_parts(doc)
        for f in findings:
            if f.get("check") != "INDEPENDENCE":
                continue
            m = re.search(r"Assertion '([^']+)'", f.get("msg", ""))
            an = m.group(1) if m else None
            evals = [assessments[t].get("evaluation", "")
                     for rel, t in out.get(an, []) if rel == "assessed_by" and t in assessments]
            joined = "\n".join(evals)
            cases.append({
                "argument": name, "assertion": an,
                "finding": f.get("msg"),
                "evaluation": joined,
                "hint": bool(_ACK_HINTS.search(joined)),
            })
    return {"flagged": len(cases),
            "hint_present": sum(1 for c in cases if c["hint"]),
            "hint_absent": sum(1 for c in cases if not c["hint"]),
            "cases": cases}


# --------------------------------------------------------------------------- #
# Which sources carry load
# --------------------------------------------------------------------------- #

def load_bearing(arguments, artifacts, index):
    """How much of the record's weight each imported source actually carries.

    Answers the 'which evidence was most informative' question structurally, without any
    notion of a high-value Argument: count the distinct Assertions, Arguments and Members
    that ground on each source, and which addresses within it were used.

    The inverse matters as much. An import nobody grounded on is importer effort that did
    not become evidence — and since what an importer selects is the ceiling on what every
    downstream researcher can reach, the unused list is a direct read on the bottleneck.
    """
    use = defaultdict(lambda: {"grounds": 0, "assertions": set(), "arguments": set(),
                               "members": set(), "addresses": Counter()})
    for doc in arguments:
        aname = doc["artifact"]["name"]
        member = doc["artifact"].get("published_by", "").lstrip("@")
        assertions, _s, grounds, _u, out = argument_parts(doc)
        for an in assertions:
            for rel, t in out.get(an, []):
                if rel != "grounded_by" or t not in grounds:
                    continue
                p = parse_address(grounds[t].get("address", ""))
                if not p or p["root"] not in index:
                    continue
                u = use[p["root"]]
                u["grounds"] += 1
                u["assertions"].add(f"{aname}.{an}")
                u["arguments"].add(aname)
                u["members"].add(member)
                u["addresses"][grounds[t].get("address")] += 1

    rows = []
    for a in artifacts:
        h = a["artifact"]
        if h["type"] not in PRESERVED_TYPES:
            continue
        u = use.get(h["name"])
        rows.append({
            "artifact": h["name"], "type": h["type"],
            "published_by": h.get("published_by", "").lstrip("@"),
            "grounds": u["grounds"] if u else 0,
            "assertions": len(u["assertions"]) if u else 0,
            "arguments": len(u["arguments"]) if u else 0,
            "members": len(u["members"]) if u else 0,
            "distinct_addresses": len(u["addresses"]) if u else 0,
            "top_address": (u["addresses"].most_common(1)[0][0] if u and u["addresses"]
                            else None),
        })
    rows.sort(key=lambda r: (-r["grounds"], r["artifact"]))
    return {"rows": rows,
            "unused": [r["artifact"] for r in rows if r["grounds"] == 0],
            "groundable_artifacts": len(rows)}


# --------------------------------------------------------------------------- #
# The event log: what the record cannot show
# --------------------------------------------------------------------------- #

def effort(events):
    """Attempts, refusals and rounds — derived, never stored.

    `rounds_to_pass` counts the attempts an artifact took before its first clean result in
    a session. It is the closest thing to a direct answer to 'how hard is this framework to
    work in', and it exists only because passing checks are logged too.
    """
    attempts = defaultdict(list)
    for e in events:
        if e.get("action") in ("check", "publish") and e.get("artifact"):
            attempts[(e.get("session"), e["artifact"])].append(e)

    rounds, never = [], []
    for (sess, art), evs in attempts.items():
        evs.sort(key=lambda e: e.get("at") or "")
        first_ok = next((i for i, e in enumerate(evs)
                         if e.get("outcome") in ("passed", "submitted")), None)
        if first_ok is None:
            never.append({"session": sess, "artifact": art, "attempts": len(evs)})
        else:
            rounds.append({"session": sess, "artifact": art, "rounds": first_ok + 1,
                           "attempts": len(evs)})
    rounds.sort(key=lambda r: -r["rounds"])

    refusal_kinds, fail_checks = Counter(), Counter()
    for e in events:
        for k in e.get("refusal") or []:
            refusal_kinds[k] += 1
        for f in e.get("fail") or []:
            fail_checks[f.get("check")] += 1

    gate = Counter(e.get("outcome") for e in events if str(e.get("action", "")).startswith("gate"))
    n = [r["rounds"] for r in rounds]
    return {
        "events": len(events),
        "sessions": len(sorted({e.get("session") for e in events if e.get("session")})),
        "artifacts_attempted": len(attempts),
        "reached_a_clean_result": len(rounds),
        "never_passed": never,
        "rounds_mean": round(sum(n) / len(n), 2) if n else None,
        "rounds_max": max(n) if n else None,
        "rounds_first_time": sum(1 for x in n if x == 1),
        "hardest": rounds[:10],
        # naming/role are the TOOLING declining; only `spec` is the specification declining
        "refusal_kinds": dict(refusal_kinds.most_common()),
        "which_rules_bite": dict(fail_checks.most_common()),
        "gate_outcomes": dict(gate.most_common()),
    }


# --------------------------------------------------------------------------- #
# Per-type tables
# --------------------------------------------------------------------------- #

def type_tables(artifacts, arguments, index, findings_by, chains):
    """One table per Artifact type, with columns that mean something for that type."""
    chain_by = defaultdict(list)
    for r in chains["rows"]:
        chain_by[r["argument"]].append(r)

    tables = defaultdict(list)
    for a in artifacts:
        h = a["artifact"]
        t, name = h["type"], h["name"]
        base = {"artifact": name, "member": h.get("published_by", "").lstrip("@"),
                "created": h.get("created"), "title": h.get("title"),
                "findings": len(findings_by.get(name, [])),
                "reviews": sum(1 for f in findings_by.get(name, [])
                               if f.get("level") == "REVIEW")}
        methods = [o for o in a.get("objects", []) if o.get("type") == "AddressingMethod"]
        if t == ARGUMENT:
            assertions, assessments, grounds, assumptions, _o = argument_parts(a)
            verd = Counter(x.get("verdict") for x in assessments.values())
            ch = chain_by.get(name, [])
            base.update({
                "assertions": len(assertions), "assessments": len(assessments),
                "grounds": len(grounds), "assumptions": len(assumptions),
                "with_criterion": sum(1 for g in grounds.values() if g.get("criterion")),
                **{v: verd.get(v, 0) for v in VERDICTS},
                "unterminated": sum(1 for r in ch if not r["terminates"]),
                "max_testimony_hops": max((r["testimony_hops"] for r in ch
                                           if r["terminates"]), default=None),
            })
        elif t in PRESERVED_TYPES:
            base.update({
                "methods": len(methods),
                "groundable_methods": sum(1 for m in methods if m.get("groundable")),
                "imported": bool(h.get("import_method")),
                "produced_by": h.get("produced_by"),
            })
        elif t == "Analysis":
            base.update({"inputs": len(h.get("inputs") or []),
                         "outputs": len(h.get("outputs") or []),
                         "used_models": len(h.get("used_models") or [])})
        else:                                            # Report, Message
            base.update({"text_chars": len(h.get("text") or ""),
                         "recipients": len(h.get("recipients") or [])})
        tables[t].append(base)
    for t in tables:
        tables[t].sort(key=lambda r: r["created"] or "")
    return dict(tables)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #

def md_table(rows, columns=None):
    if not rows:
        return "_(none)_\n"
    cols = columns or list(rows[0])
    head = "| " + " | ".join(cols) + " |\n| " + " | ".join("---" for _ in cols) + " |\n"
    body = ""
    for r in rows:
        cells = []
        for c in cols:
            v = r.get(c)
            v = "" if v is None else ("yes" if v is True else "no" if v is False else str(v))
            cells.append(v.replace("|", "\\|")[:90])
        body += "| " + " | ".join(cells) + " |\n"
    return head + body


def render(m):
    o = []
    w = o.append
    c = m["counts"]
    w(f"# Symposium record — measurement snapshot\n")
    w(f"`{m['generated_from']['record']}` · {c['artifacts']} artifacts · "
      f"{c['arguments']} Arguments · {c['members']} Members · "
      f"{m['effort']['events']} logged events from {m['effort']['sessions']} session(s)\n")
    w("> These numbers are **descriptive**. One day, a handful of accounts, tens of "
      "artifacts — enough to point a reader at the artifacts worth opening and to put "
      "counts behind a qualitative claim, not enough for significance testing or for "
      "comparing Members against one another. Nothing here ranks Arguments by quality: "
      "`insufficient` is not a worse verdict than `supported_for_purpose`, and a metric "
      "that treated it as one would reward overclaiming.\n")

    w("\n## 1. What claims rest on\n")
    b = m["basis"]
    w(f"{b['assertions']} Assertions. **{b['assumption_only']}** rest on an assumption and "
      f"nothing else.\n")
    w(md_table([{"basis": k, "assertions": v} for k, v in b["by_combination"].items()]))

    w("\n## 2. How often a Ground claims a test\n")
    cr = m["criterion"]
    w(f"**{cr['with_criterion']} of {cr['grounds']} Grounds carry a `criterion`** "
      f"(rate {cr['rate']}). A criterion asserts the material could have counted against "
      f"the claim and did not — the strongest thing an author states anywhere in the "
      f"format. Near zero means nothing was put at risk; near one means the criterion has "
      f"become decoration.\n")
    w(md_table([{"member": k, **v} for k, v in cr["by_member"].items()]))

    w("\n## 3. Distance to a measurement\n")
    t = m["chains"]
    w(f"Of {t['assertions']} Assertions, **{t['terminates_in_measurement']} reach preserved "
      f"content** and **{t['does_not_terminate']} do not** — resting entirely on "
      f"assumptions, on a cycle, or on testimony that never lands. Not a verdict on those "
      f"claims: a statement about what a reader can check.\n")
    w(f"\nTestimony hops (times the path crosses into another author's conclusion; "
      f"0 = grounded on preserved content directly):\n\n")
    w(md_table([{"testimony_hops": k, "assertions": v}
                for k, v in t["by_testimony_hops"].items()]))
    unterm = [r for r in t["rows"] if not r["terminates"]]
    if unterm:
        w("\nAssertions not reaching a measurement — worth reading:\n\n")
        w(md_table(unterm, ["argument", "assertion", "direct_grounds", "testimony_grounds"]))

    w("\n## 4. Was non-independence acknowledged?\n")
    i = m["independence"]
    w(f"The validator flagged **{i['flagged']}** Assertion(s) whose Grounds share a source. "
      f"A keyword triage finds language of independence in {i['hint_present']} and not in "
      f"{i['hint_absent']}. **The triage is not the measurement** — a regex cannot read "
      f"prose. Each case is below with its evaluation; settle them by reading.\n")
    for case in i["cases"]:
        w(f"\n**{case['argument']} · {case['assertion']}** "
          f"— triage: {'language present' if case['hint'] else 'NO language found'}\n")
        w(f"\n> {case['finding']}\n")
        ev = (case["evaluation"] or "(no evaluation)").strip().replace("\n", "\n> ")
        w(f"\n> _evaluation:_ {ev[:1200]}\n")

    w("\n## 5. Which sources carry load\n")
    lb = m["load_bearing"]
    w(f"{lb['groundable_artifacts']} groundable artifacts; **{len(lb['unused'])} carry no "
      f"Grounds at all**. What an importer selects is the ceiling on what every downstream "
      f"researcher can reach, so the unused list is a direct read on that bottleneck.\n")
    w(md_table(lb["rows"], ["artifact", "type", "published_by", "grounds", "assertions",
                            "arguments", "members", "distinct_addresses"]))
    if lb["unused"]:
        w("\nGrounded on by nobody: " + ", ".join(f"`{x}`" for x in lb["unused"]) + "\n")

    w("\n## 6. What it cost — from the event log\n")
    e = m["effort"]
    w(f"{e['artifacts_attempted']} artifacts attempted across {e['sessions']} session(s). "
      f"**{e['rounds_first_time']} passed first time**; mean rounds to a clean result "
      f"{e['rounds_mean']}, worst {e['rounds_max']}.\n")
    w(f"\nRefusal kinds — `naming` and `role` are the tooling declining, only `spec` is the "
      f"specification declining:\n\n")
    w(md_table([{"kind": k, "n": v} for k, v in e["refusal_kinds"].items()]))
    w("\nWhich rules bite:\n\n")
    w(md_table([{"check": k, "failures": v} for k, v in e["which_rules_bite"].items()]))
    if e["hardest"]:
        w("\nArtifacts that took the most rounds:\n\n")
        w(md_table(e["hardest"], ["artifact", "rounds", "attempts", "session"]))
    if e["never_passed"]:
        w("\nNever reached a clean result:\n\n")
        w(md_table(e["never_passed"], ["artifact", "attempts", "session"]))
    if e["gate_outcomes"]:
        w("\nGate outcomes:\n\n")
        w(md_table([{"outcome": k, "n": v} for k, v in e["gate_outcomes"].items()]))

    w("\n## 7. Per type\n")
    for t, rows in sorted(m["tables"].items()):
        w(f"\n### {t} ({len(rows)})\n")
        w(md_table(rows))
    return "\n".join(o)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def compute(record_dir, events_spec):
    artifacts = load_record(record_dir)
    arguments = [a for a in artifacts if a["artifact"]["type"] == ARGUMENT]
    members = sorted({a["artifact"].get("published_by", "").lstrip("@") for a in artifacts})
    index = build_index(artifacts)
    findings_by = run_validator(artifacts, set(members))
    events, log_paths = load_events(events_spec)

    chains = trust_chains(arguments, index)
    m = {
        "generated_from": {"record": str(record_dir), "event_logs": log_paths},
        "counts": {"artifacts": len(artifacts), "arguments": len(arguments),
                   "members": len(members),
                   "by_type": dict(Counter(a["artifact"]["type"] for a in artifacts)),
                   "by_member": dict(Counter(a["artifact"].get("published_by", "").lstrip("@")
                                             for a in artifacts))},
        "basis": basis_composition(arguments),
        "criterion": criterion_rate(arguments),
        "chains": chains,
        "independence": independence_acknowledgement(arguments, findings_by),
        "load_bearing": load_bearing(arguments, artifacts, index),
        "effort": effort(events),
        "tables": type_tables(artifacts, arguments, index, findings_by, chains),
    }
    return m


def snapshot(m):
    """The few numbers worth a trend line. The interesting question is not the end state
    but whether the criterion rate decays through the afternoon and whether testimony
    depth climbs as people build on each other instead of returning to data."""
    return {
        "artifacts": m["counts"]["artifacts"],
        "arguments": m["counts"]["arguments"],
        "assertions": m["basis"]["assertions"],
        "assumption_only": m["basis"]["assumption_only"],
        "grounds": m["criterion"]["grounds"],
        "criterion_rate": m["criterion"]["rate"],
        "unterminated": m["chains"]["does_not_terminate"],
        "max_testimony_hops": m["chains"]["max_testimony_hops"],
        "independence_flagged": m["independence"]["flagged"],
        "unused_sources": len(m["load_bearing"]["unused"]),
        "rounds_mean": m["effort"]["rounds_mean"],
        "refusal_spec": m["effort"]["refusal_kinds"].get("spec", 0),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--record", default=os.environ.get("SYMPOSIUM_MIRROR", "../demo_record"),
                    help="the GATE's mirror — the authoritative record")
    ap.add_argument("--events", default=os.environ.get("SYMPOSIUM_LOG", "./events"),
                    help="event log file, directory, or glob (merged)")
    ap.add_argument("--out", default="./metrics", help="output directory")
    ap.add_argument("--at", default=None,
                    help="timestamp to label this snapshot with (default: none)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    m = compute(args.record, args.events)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(m, indent=2, default=str))
    (out / "metrics.md").write_text(render(m))
    snap = snapshot(m)
    if args.at:
        snap = {"at": args.at, **snap}
    with (out / "metrics_series.jsonl").open("a") as fh:
        fh.write(json.dumps(snap) + "\n")

    if not args.quiet:
        e, ch, cr = m["effort"], m["chains"], m["criterion"]
        print(f"record  {m['counts']['artifacts']} artifacts, {m['counts']['arguments']} Arguments, "
              f"{m['basis']['assertions']} Assertions")
        print(f"ground  {cr['with_criterion']}/{cr['grounds']} Grounds carry a criterion "
              f"(rate {cr['rate']})")
        print(f"chains  {ch['terminates_in_measurement']} reach a measurement, "
              f"{ch['does_not_terminate']} do not; max testimony hops "
              f"{ch['max_testimony_hops']}")
        print(f"basis   {m['basis']['assumption_only']} Assertion(s) rest on an assumption alone")
        print(f"sources {len(m['load_bearing']['unused'])} groundable artifact(s) unused")
        print(f"effort  {e['artifacts_attempted']} attempted, {e['rounds_first_time']} first time, "
              f"mean {e['rounds_mean']} round(s); refusals {e['refusal_kinds'] or '{}'}")
        print(f"\n-> {out}/metrics.md   {out}/metrics.json   {out}/metrics_series.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
