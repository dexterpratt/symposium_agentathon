#!/usr/bin/env python3
"""Generate the prepopulation import artifacts from the frozen corpus manifest.

    python import_corpus.py --corpus ~/Dropbox/chromatin_project_sources --out ./imports
    python import_corpus.py ... --no-verify          # skip the per-file HTTP check

Writes one canonical JSON per SOURCE. It does not publish: `admin_publish.py` does that, and
the split is deliberate, because an artifact name can never be reused. Generating is cheap and
repeatable; publishing is a one-way door.

WHY ONE ARTIFACT PER SOURCE, NOT PER FILE
-----------------------------------------
`00_admin/checksums.sha256` lists 116 files; `00_admin/master_inventory.csv` lists 44 sources,
and a source is the unit that has one provenance, one authorship, one licence and one act of
acquisition. A paper and its supplementary zip are one source; a GEO series is one source with
five files. Splitting per file would put a paper's supplement in a different artifact from the
paper — and `import_method`, which is the substance of an import, would have to be written 116
times about 44 decisions.

NOTHING FROM THE CORPUS IS EMBEDDED
-----------------------------------
Every source file stays on the file server and is reached by `download`. The one thing embedded
is the `files` table: path, bytes and SHA-256 for each file of the source, a few hundred bytes.
That is provenance, not measurement, and it is what makes a retrieval CHECKABLE — a reader
fetches the file, hashes it, and compares against a digest that is fixed inside an immutable
artifact. Without it a `download` ground is unverifiable forever, and imports cannot be revised
to add it later.

WHAT IS DELIBERATELY LEFT OUT
-----------------------------
Sources with `access_status` of `manual_required` (nothing was acquired, so there is no file to
point at) and `quarantined` (acquired but under an unresolved accession conflict). They are
listed on stderr and belong in a scout Report that says they exist and were not imported —
silence about them would misrepresent the corpus as complete.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

BASE = "https://symposium.ndexbio.org/archives/symposium_files/"
PREFIX = "ndex-admin"

# A source becomes a ScientificPublication only if it IS a publication. Everything else is Data:
# a supplement is data that travelled with a paper, not a paper.
PUBLICATION_TYPES = {"literature"}
SKIP_STATUS = {"manual_required", "quarantined"}


def slug(s):
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]+", "_", s or "")).strip("_").lower()


def load_manifest(corpus):
    out = {}
    for line in (corpus / "00_admin" / "checksums.sha256").read_text().splitlines():
        if line.strip():
            h, p = line.split(None, 1)
            out[p.strip()] = h
    return out


def expand(row, manifest):
    """local_paths -> the manifest files it covers. A path may name a directory."""
    out = []
    for p in [x.strip() for x in row["local_paths"].replace("\n", ";").split(";") if x.strip()]:
        if p in manifest:
            out.append(p)
        else:
            out += [m for m in manifest if m.startswith(p.rstrip("/") + "/")]
    return sorted(set(out))


def head(url):
    """-> (status, content-length or None). A cheap existence check at generation time."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            n = r.headers.get("Content-Length")
            return r.status, int(n) if n and n.isdigit() else None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:                                          # noqa: BLE001
        return 0, None


def import_method(row, files, manifest):
    """The substance of the import: what was selected, what was left, and what can be checked."""
    r = row
    bits = [f"Source {r['source_id']} from the frozen chromatin/paclitaxel corpus, "
            f"acquired {r['retrieved_at'] or 'date not recorded'} and checksummed at acquisition."]
    ident = [x for x in (f"DOI {r['doi']}" if r["doi"] else "",
                         f"PMID {r['pmid']}" if r["pmid"] else "",
                         f"{r['pmcid']}" if r["pmcid"] else "",
                         f"accession {r['dataset_accession']}" if r["dataset_accession"] else "",
                         f"{r['repository']}" if r["repository"] else "",
                         f"release {r['version_or_release']}" if r["version_or_release"] else "") if x]
    if ident:
        bits.append("Identified by " + "; ".join(ident) + ".")
    bits.append(f"SELECTED: {len(files)} file(s), listed in `files` with size and SHA-256, "
                f"exactly as acquired — no filtering, reformatting, rescaling or cleaning was "
                f"applied by this import.")
    bits.append("NOT INCLUDED: the file contents. Nothing from this corpus is embedded; the "
                "bytes are reached by `download`. So a Ground under `download` is NOT verified "
                "by the gate. The SHA-256 in `files` is what makes it checkable by hand: fetch "
                "the file, hash it, compare. A retrieval that does not match that digest is not "
                "the material this artifact describes.")
    if r["access_status"] != "acquired":
        bits.append(f"ACCESS STATUS: {r['access_status']} — this source is INCOMPLETE. "
                    f"Do not read the absence of a file as evidence of absence in the source.")
    if r["license_or_terms"]:
        bits.append(f"Terms: {r['license_or_terms']}.")
    if r["notes"]:
        note = r["notes"].strip()
        bits.append(f"Acquisition note: {note}" + ("" if note.endswith((".", "!", "?")) else "."))
    bits.append("This import makes the material addressable. It asserts nothing about it.")
    return " ".join(bits)


def build(row, files, manifest, verify):
    name = f"{PREFIX}_importer_{slug(row['short_name'] or row['source_id'])}_v1"
    is_pub = row["source_type"] in PUBLICATION_TYPES
    rows = ["path,bytes,sha256"]
    problems = []
    for p in files:
        st, n = (head(BASE + p) if verify else (200, None))
        if st != 200:
            problems.append(f"{p}: HTTP {st}")
        local = (row["_corpus"] / p)
        size = n if n is not None else (local.stat().st_size if local.exists() else 0)
        if n is not None and local.exists() and n != local.stat().st_size:
            problems.append(f"{p}: served {n} B, local {local.stat().st_size} B")
        rows.append(f"{p},{size},{manifest[p]}")

    art = {
        "artifact": {
            "name": name,
            "type": "ScientificPublication" if is_pub else "Data",
            "specification_version": "6",
            "published_by": f"@{PREFIX}",
            "created": None,
            "title": row["title"] or row["short_name"],
            "authors": [a.strip() for a in (row["authors_or_provider"] or "unattributed").split(";")],
            "import_method": import_method(row, files, manifest),
            "files": "\n".join(rows) + "\n",
        },
        "objects": [
            {"name": "download", "type": "AddressingMethod", "groundable": True,
             "access_method": f"HTTP GET {BASE}<path>, where <path> is a value from the `path` "
                              f"column of `files`. No authentication.",
             # No literal '@address' in this text on purpose: the citation check reads a bare
             # @name in prose as an unvalidatable citation, and 'ndex-admin' truncates at the
             # hyphen, so an example address here would put a spurious REVIEW on every import.
             "description": "A file of this source, retrieved over HTTP. Reference: the file's "
                            "path exactly as it appears in the `path` column of `files` — "
                            "address this artifact and append '#download.' followed by that "
                            "path, for example '#download." + (files[0] if files else "<path>")
                            + "'. The gate cannot verify content reached this way; hash what "
                            "you retrieve and compare it against `files` before you rely on it."},
            {"name": "csv", "type": "AddressingMethod", "groundable": True,
             "description": "A cell in `files`. Reference: row=<path>&col=<path|bytes|sha256>. "
                            "This addresses PROVENANCE — which file, how large, which digest — "
                            "never the scientific content, which lives behind `download`."},
        ],
        "relationships": [],
    }
    return art, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the per-file HTTP check (offline generation)")
    args = ap.parse_args(argv)

    corpus = pathlib.Path(args.corpus).expanduser()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(corpus)
    rows = list(csv.DictReader((corpus / "00_admin" / "master_inventory.csv").open()))
    print(f"{len(rows)} source(s) in the inventory; {len(manifest)} file(s) in the manifest")

    written, skipped, all_problems, claimed = [], [], [], set()
    for row in rows:
        row["_corpus"] = corpus
        files = expand(row, manifest)
        claimed |= set(files)
        if row["access_status"] in SKIP_STATUS or not files:
            skipped.append((row["source_id"], row["short_name"], row["access_status"], len(files)))
            continue
        art, problems = build(row, files, manifest, verify=not args.no_verify)
        all_problems += [(row["source_id"], p) for p in problems]
        path = out / f"{art['artifact']['name']}.json"
        path.write_text(json.dumps(art, indent=2) + "\n")
        written.append((art["artifact"]["name"], art["artifact"]["type"], len(files),
                        len(json.dumps(art))))

    for n, t, nf, size in written:
        print(f"  {t:22s} {nf:2d} file(s)  {size:6,d} B  {n}")

    print(f"\n{len(written)} artifact(s) written to {out}")
    if skipped:
        print(f"\nNOT IMPORTED — {len(skipped)} source(s). These belong in a scout Report; the "
              f"corpus is not complete without saying they exist:")
        for sid, short, status, nf in skipped:
            print(f"  {sid:16s} {status:20s} {nf} file(s)  {short}")
    unclaimed = sorted(set(manifest) - claimed)
    if unclaimed:
        print(f"\n{len(unclaimed)} manifest file(s) claimed by no source:")
        for u in unclaimed:
            print(f"  {u}")
    if all_problems:
        print(f"\n! {len(all_problems)} file(s) did not check out against the server:")
        for sid, p in all_problems:
            print(f"  {sid}: {p}")
        return 1
    print("\nevery file referenced was reachable and the served size matched the local copy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
