"""Fixture suite for validate_v6.

Every scenario mutates a known-good corpus and asserts which check fires. A validator that
accepts everything passes no test here; a validator that rejects everything fails the first.

  python validate_v6.py --selftest
"""
from __future__ import annotations

import copy
import json

from validate_v6 import validate, passed

MEMBERS = {"agent_lyra", "agent_vega", "ndex-admin"}

DATA = {
    "artifact": {
        "name": "agent_lyra_gdsc_v1", "type": "Data", "specification_version": "6",
        "published_by": "@agent_lyra", "created": "2026-08-01T10:00:00Z",
        "authors": ["GDSC consortium"],
        "import_method": "GDSC2 release 8.5, paclitaxel, filtered to breast lines.",
        "measurements": "cell_line,arid1a_status,ic50_z\nMCF7,WT,-0.34\nHCC1143,MUT,-1.21\n",
    },
    "objects": [{"name": "csv", "type": "AddressingMethod", "groundable": True,
                 "description": "A cell in measurements. Reference: row=<cell_line>&col=<column>."}],
    "relationships": [],
}

PAPER = {
    "artifact": {
        "name": "agent_lyra_chen2025_v1", "type": "ScientificPublication",
        "specification_version": "6", "published_by": "@agent_lyra",
        "created": "2026-08-01T11:00:00Z", "authors": ["Chen, Y.", "Okafor, N."],
        "import_method": "Extracted the Results section as plain text from the publisher PDF.",
        "results_text": "ARID1A knockdown raised CHK1 levels across all lines tested.",
    },
    "objects": [{"name": "text_span", "type": "AddressingMethod", "groundable": True,
                 "description": 'A passage in results_text. Reference: quote="…".'}],
    "relationships": [],
}

REPORT = {
    "artifact": {"name": "agent_vega_plan_v1", "type": "Report", "specification_version": "6",
                 "published_by": "@agent_vega", "created": "2026-08-01T09:00:00Z",
                 "text": "Proposed screening plan."},
    "objects": [], "relationships": [],
}

ARG = {
    "artifact": {
        "name": "agent_lyra_arid1a_v1", "type": "Argument", "specification_version": "6",
        "published_by": "@agent_lyra", "created": "2026-08-02T09:00:00Z",
        "authors": ["agent_lyra"], "primary_assertion": "a_primary",
        "description": "Revisits [the earlier plan](@agent_vega_plan_v1).",
    },
    "objects": [
        {"name": "a_primary", "type": "Assertion",
         "claim": "ARID1A-mutant breast lines are more paclitaxel-sensitive.",
         "scope": "GDSC2 breast carcinoma lines; in vitro viability."},
        {"name": "a_sub", "type": "Assertion",
         "claim": "ARID1A loss raises CHK1.", "scope": "Cell lines in Chen 2025."},
        {"name": "as_primary", "type": "Assessment", "verdict": "insufficient",
         "purpose": "Whether to commit wet-lab resource.", "evaluation": "Direction right, n small."},
        {"name": "as_sub", "type": "Assessment", "verdict": "supported_for_purpose",
         "evaluation": "Direct perturbation across all lines."},
        {"name": "g_csv", "type": "Ground",
         "address": "@agent_lyra_gdsc_v1.measurements#csv.row=HCC1143&col=ic50_z",
         "rationale": "HCC1143 is ARID1A-mutant and sits below the WT median.",
         "criterion": "An ic50_z at or above the WT median counts against."},
        {"name": "g_quote", "type": "Ground",
         "address": '@agent_lyra_chen2025_v1.results_text#text_span.quote="raised CHK1 levels"',
         "rationale": "The authors report the mechanism directly."},
    ],
    "relationships": [
        {"rel": "assessed_by", "source": "a_primary", "target": "as_primary"},
        {"rel": "assessed_by", "source": "a_sub", "target": "as_sub"},
        {"rel": "grounded_by", "source": "a_primary", "target": "g_csv"},
        {"rel": "grounded_by", "source": "a_sub", "target": "g_quote"},
        {"rel": "depends_on", "source": "a_primary", "target": "a_sub"},
    ],
}

MODEL = {
    "artifact": {"name": "agent_vega_nest_v1", "type": "Model", "specification_version": "6",
                 "published_by": "@agent_vega", "created": "2026-08-01T07:00:00Z",
                 "authors": ["agent_vega"],
                 "modeling_choices": "Hierarchy cut at resolution 0.4; clusters under 3 members pruned.",
                 "clusters": "cluster,members\nNEST_0042,ARID1A;SMARCA4;SMARCB1\n"},
    "objects": [{"name": "csv", "type": "AddressingMethod", "groundable": True,
                 "description": "A cell in clusters. Reference: row=<cluster>&col=<column>."}],
    "relationships": [],
}

ANALYSIS = {
    "artifact": {"name": "agent_vega_clusterrun_v1", "type": "Analysis", "specification_version": "6",
                 "published_by": "@agent_vega", "created": "2026-08-01T06:00:00Z",
                 "procedure": "Louvain at resolution 0.4 over the STRING network.",
                 "outputs": ["@agent_vega_nest_v1"]},
    "objects": [], "relationships": [],
}

RECORD = [DATA, PAPER, REPORT, MODEL, ANALYSIS]


def mut(fn):
    a = copy.deepcopy(ARG)
    fn(a)
    return a


def obj(a, name):
    return next(o for o in a["objects"] if o["name"] == name)


# (label, artifact, expect_pass, expected_check_or_None)
CASES = [
    ("baseline conformant Argument", ARG, True, None),
    ("conformant Data", DATA, True, None),
    ("conformant non-groundable Report", REPORT, True, None),

    ("missing basis on an Assertion", mut(lambda a: a["relationships"].remove(
        {"rel": "grounded_by", "source": "a_sub", "target": "g_quote"})), False, "C-ARG"),
    ("two Assessments on one Assertion", mut(lambda a: a["relationships"].append(
        {"rel": "assessed_by", "source": "a_primary", "target": "as_sub"})), False, "C-ARG"),
    ("primary_assertion names a non-Assertion", mut(lambda a: a["artifact"].update(
        primary_assertion="as_primary")), False, "C-ARG"),
    ("something depends on the primary", mut(lambda a: a["relationships"].append(
        {"rel": "depends_on", "source": "a_sub", "target": "a_primary"})), False, "C-ARG"),
    ("depends_on cycle", mut(lambda a: a["relationships"].append(
        {"rel": "depends_on", "source": "a_sub", "target": "a_primary"})), False, "C-ARG"),
    ("primary Assessment lacks purpose", mut(lambda a: obj(a, "as_primary").pop("purpose")), False, "C-ARG"),
    ("bad verdict value", mut(lambda a: obj(a, "as_primary").update(verdict="supported-for-purpose")),
     False, "TYPE"),
    ("Ground bearing on two Assertions", mut(lambda a: a["relationships"].append(
        {"rel": "grounded_by", "source": "a_sub", "target": "g_csv"})), False, "C-ARG"),
    ("relationship leaves the Artifact", mut(lambda a: a["relationships"].append(
        {"rel": "depends_on", "source": "a_primary", "target": "@other.x"})), False, "STRUCT"),

    ("Ground addresses its own Argument", mut(lambda a: obj(a, "g_csv").update(
        address="@agent_lyra_arid1a_v1.a_sub")), False, "GROUND"),
    ("Ground on a non-groundable Report", mut(lambda a: obj(a, "g_csv").update(
        address="@agent_vega_plan_v1.text")), False, "GROUND"),
    ("Ground on an Analysis is still refused", mut(lambda a: obj(a, "g_csv").update(
        address="@agent_vega_clusterrun_v1.procedure")), False, "GROUND"),
    # spec 2.6 change: Model is groundable; evidential weight is the author's judgment
    ("Ground on a Model is permitted", mut(lambda a: obj(a, "g_csv").update(
        address="@agent_vega_nest_v1.clusters#csv.row=NEST_0042&col=members")), True, None),
    ("Ground on a Model still checks the address", mut(lambda a: obj(a, "g_csv").update(
        address="@agent_vega_nest_v1.clusters#csv.row=NEST_9999&col=members")), False, "ADDRESS"),
    ("conformant groundable Model", MODEL, True, None),
    ("conformant Analysis", ANALYSIS, True, None),
    ("Ground on a Member", mut(lambda a: obj(a, "g_csv").update(address="@agent_vega")), False, "GROUND"),
    ("Ground on an AddressingMethod", mut(lambda a: obj(a, "g_csv").update(
        address="@agent_lyra_gdsc_v1.csv")), False, "GROUND"),

    ("csv col does not exist", mut(lambda a: obj(a, "g_csv").update(
        address="@agent_lyra_gdsc_v1.measurements#csv.row=HCC1143&col=nope")), False, "ADDRESS"),
    ("csv row does not exist", mut(lambda a: obj(a, "g_csv").update(
        address="@agent_lyra_gdsc_v1.measurements#csv.row=NOSUCHLINE&col=ic50_z")), False, "ADDRESS"),
    ("fabricated quote", mut(lambda a: obj(a, "g_quote").update(
        address='@agent_lyra_chen2025_v1.results_text#text_span.quote="lowered CHK1"')), False, "ADDRESS"),
    ("undeclared AddressingMethod", mut(lambda a: obj(a, "g_csv").update(
        address="@agent_lyra_gdsc_v1.measurements#tsv.row=HCC1143&col=ic50_z")), False, "ADDRESS"),
    ("address to unknown artifact", mut(lambda a: obj(a, "g_csv").update(
        address="@nobody_nothing_v1.measurements#csv.row=x&col=y")), False, "ADDRESS"),

    ("future-dated source (ordering)", mut(lambda a: a["artifact"].update(
        created="2026-07-01T00:00:00Z")), False, "ORDER"),
    ("name already in the record", mut(lambda a: a["artifact"].update(
        name="agent_lyra_gdsc_v1")), False, "UNIQUE"),
    ("missing agent name prefix", mut(lambda a: a["artifact"].update(name="arid1a")), False, "NAMING"),
    # An NDEx account name may contain a hyphen (`ndex-admin`), and the admin publishes the
    # end-of-day metrics under its own account. The prefix rule is structural; matching the
    # name to the publishing account is enforced where the account is known.
    ("hyphenated member prefix is accepted",
     mut(lambda a: a["artifact"].update(name="ndex-admin_metrics_v1")), True, None),
    ("wrong spec version", mut(lambda a: a["artifact"].update(specification_version="5")), False, "STRUCT"),
    ("supersedes without rationale", mut(lambda a: a["artifact"].update(
        supersedes=["@agent_lyra_chen2025_v1"])), False, "STRUCT"),
    ("Argument without authors", mut(lambda a: a["artifact"].pop("authors")), False, "TYPE"),
    ("Object name collides with a property", mut(lambda a: obj(a, "a_sub").update(name="authors")
                                                 or a["relationships"].clear()), False, "STRUCT"),

    ("groundable as a string not a boolean",
     {**copy.deepcopy(DATA), "objects": [{"name": "csv", "type": "AddressingMethod",
                                          "groundable": "True", "description": "x"}]}, False, "TYPE"),
    ("non-groundable type declaring a groundable method",
     {**copy.deepcopy(REPORT), "objects": [{"name": "csv", "type": "AddressingMethod",
                                            "groundable": True, "description": "x"}]}, False, "TYPE"),
    ("rest method without access_method",
     {**copy.deepcopy(DATA), "objects": [{"name": "rest", "type": "AddressingMethod",
                                          "groundable": True, "description": "x"}]}, False, "TYPE"),
]

# --- independence: two Data artifacts derived from ONE source, via declared provenance ---
SRC = {"artifact": {"name": "agent_lyra_gdscraw_v1", "type": "Data", "specification_version": "6",
                    "published_by": "@agent_lyra", "created": "2026-08-01T05:00:00Z",
                    "authors": ["GDSC consortium"], "import_method": "GDSC2 8.5 raw.",
                    "raw": "cell_line,ic50\nMCF7,-0.34\n"},
       "objects": [{"name": "csv", "type": "AddressingMethod", "groundable": True,
                    "description": "A cell in raw."}], "relationships": []}
RUN_A = {"artifact": {"name": "agent_lyra_runa_v1", "type": "Analysis", "specification_version": "6",
                      "published_by": "@agent_lyra", "created": "2026-08-01T05:10:00Z",
                      "procedure": "Z-score by tissue.", "inputs": ["@agent_lyra_gdscraw_v1"],
                      "outputs": ["@agent_lyra_derivA_v1"]}, "objects": [], "relationships": []}
DERIV_A = {"artifact": {"name": "agent_lyra_derivA_v1", "type": "Data", "specification_version": "6",
                        "published_by": "@agent_lyra", "created": "2026-08-01T05:10:00Z",
                        "authors": ["agent_lyra"], "produced_by": "@agent_lyra_runa_v1",
                        "z": "cell_line,z\nMCF7,-0.34\n"},
           "objects": [{"name": "csv", "type": "AddressingMethod", "groundable": True,
                        "description": "A cell in z."}], "relationships": []}
RUN_B = {"artifact": {"name": "agent_lyra_runb_v1", "type": "Analysis", "specification_version": "6",
                      "published_by": "@agent_lyra", "created": "2026-08-01T05:20:00Z",
                      "procedure": "Rank within panel.", "inputs": ["@agent_lyra_gdscraw_v1"],
                      "outputs": ["@agent_lyra_derivB_v1"]}, "objects": [], "relationships": []}
DERIV_B = {"artifact": {"name": "agent_lyra_derivB_v1", "type": "Data", "specification_version": "6",
                        "published_by": "@agent_lyra", "created": "2026-08-01T05:20:00Z",
                        "authors": ["agent_lyra"], "produced_by": "@agent_lyra_runb_v1",
                        "r": "cell_line,rank\nMCF7,3\n"},
           "objects": [{"name": "csv", "type": "AddressingMethod", "groundable": True,
                        "description": "A cell in r."}], "relationships": []}
# an INDEPENDENT dataset: same shape, no shared provenance
INDEP = {"artifact": {"name": "agent_lyra_ctrp_v1", "type": "Data", "specification_version": "6",
                      "published_by": "@agent_lyra", "created": "2026-08-01T05:30:00Z",
                      "authors": ["CTRP"], "import_method": "CTRPv2, independent of GDSC.",
                      "c": "cell_line,auc\nMCF7,0.71\n"},
         "objects": [{"name": "csv", "type": "AddressingMethod", "groundable": True,
                      "description": "A cell in c."}], "relationships": []}

RECORD += [SRC, RUN_A, DERIV_A, RUN_B, DERIV_B, INDEP]


def two_ground_arg(name, addr1, addr2):
    return {"artifact": {"name": name, "type": "Argument", "specification_version": "6",
                         "published_by": "@agent_lyra", "created": "2026-08-03T09:00:00Z",
                         "authors": ["agent_lyra"], "primary_assertion": "a1"},
            "objects": [
                {"name": "a1", "type": "Assertion", "claim": "c", "scope": "s"},
                {"name": "s1", "type": "Assessment", "verdict": "insufficient",
                 "purpose": "p", "evaluation": "e"},
                {"name": "gx", "type": "Ground", "address": addr1, "rationale": "r1"},
                {"name": "gy", "type": "Ground", "address": addr2, "rationale": "r2"}],
            "relationships": [{"rel": "assessed_by", "source": "a1", "target": "s1"},
                              {"rel": "grounded_by", "source": "a1", "target": "gx"},
                              {"rel": "grounded_by", "source": "a1", "target": "gy"}]}


INDEPENDENCE_CASES = [
    ("same carrier: two Grounds on one artifact are flagged",
     two_ground_arg("agent_lyra_samecarrier_v1",
                    "@agent_lyra_gdscraw_v1.raw#csv.row=MCF7&col=ic50",
                    "@agent_lyra_gdscraw_v1.raw#csv.row=MCF7&col=cell_line"), True),
    ("shared ancestor: distinct artifacts from one source are flagged",
     two_ground_arg("agent_lyra_sharedanc_v1",
                    "@agent_lyra_derivA_v1.z#csv.row=MCF7&col=z",
                    "@agent_lyra_derivB_v1.r#csv.row=MCF7&col=rank"), True),
    ("genuinely independent sources are NOT flagged",
     two_ground_arg("agent_lyra_indep_v1",
                    "@agent_lyra_derivA_v1.z#csv.row=MCF7&col=z",
                    "@agent_lyra_ctrp_v1.c#csv.row=MCF7&col=auc"), False),
    ("BLIND SPOT: undeclared shared source is not detectable and is NOT flagged",
     two_ground_arg("agent_lyra_blindspot_v1",
                    "@agent_lyra_gdscraw_v1.raw#csv.row=MCF7&col=ic50",
                    "@agent_lyra_ctrp_v1.c#csv.row=MCF7&col=auc"), False),
]

REVIEW_CASES = [
    ("bare @name in prose is flagged, not failed",
     mut(lambda a: a["artifact"].update(description="See @agent_vega_plan_v1 for context.")), "CITATION"),
    ("rest grounding is accepted but reviewed",
     mut(lambda a: (obj(a, "g_csv").update(address="@agent_lyra_depmap_v1#rest.gene=ARID1A"),)), "GROUND"),
]

DEPMAP = {"artifact": {"name": "agent_lyra_depmap_v1", "type": "Data", "specification_version": "6",
                       "published_by": "@agent_lyra", "created": "2026-08-01T08:00:00Z",
                       "authors": ["DepMap"], "import_method": "REST."},
          "objects": [{"name": "rest", "type": "AddressingMethod", "groundable": True,
                       "description": "A DepMap REST query.", "access_method": "https://depmap.org/api"}],
          "relationships": []}


def run():
    fails = 0
    print("validate_v6 fixture suite\n")
    for label, art, want_pass, want_check in CASES:
        # exclude by IDENTITY, not by name — a mutated copy that reuses a record name must
        # still see the original in the record, or the uniqueness test cannot fire
        record = [r for r in RECORD if r is not art]
        got = validate(art, record, MEMBERS)
        ok = passed(got)
        checks = {x["check"] for x in got if x["level"] == "FAIL"}
        good = (ok == want_pass) and (want_check is None or want_check in checks)
        fails += not good
        print(f"  [{'ok ' if good else 'BAD'}] {label}"
              + ("" if good else f"  -> pass={ok} (want {want_pass}), checks={sorted(checks)} (want {want_check})"))
        if not good:
            for x in got:
                print(f"          {x['level']:6} {x['check']:8} {x['msg'][:100]}")

    for label, art, want_check in REVIEW_CASES:
        got = validate(art, RECORD + [DEPMAP], MEMBERS)
        revs = {x["check"] for x in got if x["level"] == "REVIEW"}
        good = passed(got) and want_check in revs
        fails += not good
        print(f"  [{'ok ' if good else 'BAD'}] {label}"
              + ("" if good else f"  -> pass={passed(got)}, reviews={sorted(revs)} (want {want_check})"))
        if not good:
            for x in got:
                print(f"          {x['level']:6} {x['check']:8} {x['msg'][:100]}")

    for label, art, want_flag in INDEPENDENCE_CASES:
        got = validate(art, RECORD, MEMBERS)
        flagged = [x for x in got if x["check"] == "INDEPENDENCE"]
        # must always stay conformant: independence is a REVIEW, never a gate
        good = passed(got) and bool(flagged) == want_flag
        fails += not good
        print(f"  [{'ok ' if good else 'BAD'}] {label}"
              + ("" if good else f"  -> pass={passed(got)}, flagged={len(flagged)} (want {want_flag})"))
        if not good:
            for x in got:
                print(f"          {x['level']:6} {x['check']:12} {x['msg'][:110]}")
        elif flagged:
            print(f"          -> {flagged[0]['msg'][:104]}")

    total = len(CASES) + len(REVIEW_CASES) + len(INDEPENDENCE_CASES)
    print(f"\n{total - fails}/{total} scenarios behaved as specified")
    return 1 if fails else 0
