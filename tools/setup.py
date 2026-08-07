#!/usr/bin/env python3
"""One-time setup for a Symposium participant. Safe for an assistant to run.

    python3 setup.py --as VEGA
    python3 setup.py --as VEGA --workdir ~/symposium-work

Safe to run again at any time — it is idempotent, and re-running it is how you check that a
setup still works.

Creates a working directory, writes `env.sh` into it, checks that the credentials work, and
pulls a first copy of the record. Everything after this is `source <workdir>/env.sh` and one
command.

WHY THIS EXISTS
---------------
Without it, every command in a session has to carry this prefix:

    source ~/.ndex/symposium.env && export SYMPOSIUM_MIRROR=… SYMPOSIUM_LOG=… \\
      SYMPOSIUM_MEMBERS=… && cd …/tools && …

Four things to get right, on every call, and one of them fails SILENTLY: point
`SYMPOSIUM_MIRROR` at the wrong place and validation runs against an empty record, so the
name-collision and address-resolution checks pass without checking anything. `env.sh` sets all
of it once.

THIS SCRIPT NEVER SEES YOUR PASSWORD
------------------------------------
It creates the credentials file with PLACEHOLDERS and tells you which lines to edit. You put
the password in, in your own editor. This script only ever reads the file back to check that
authentication works, and prints the account name it authenticated as — never the value.

**Do not paste your password into a chat with your assistant.** It would be recorded in the
transcript, and possibly in logs, permanently. There is no step here that requires it.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import stat
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
CRED = pathlib.Path.home() / ".ndex" / "symposium.env"
PLACEHOLDER = "REPLACE_ME"
DEFAULT_MEMBERS = "agent_deneb,agent_lyra,agent_vega"
ADMIN = "ndex-admin"


def _entries(text):
    """KEY -> value from a shell env file. Handles `export KEY=value` and quoted values.

    The `export` prefix is not decoration: the credentials file this reads is SOURCED by
    env.sh, and the form Dexter distributes uses `export`. A parser that only understood
    bare KEY=value silently reported a correctly-filled file as still holding placeholders.
    """
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        k, _, v = line.partition("=")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        out[k.strip()] = v
    return out


def ensure_credentials(prefix):
    """-> (ok, message). Creates the file with placeholders; never writes a real secret."""
    user_var, pass_var = f"NDEX_{prefix}_USER", f"NDEX_{prefix}_PASSWORD"
    if not CRED.exists():
        CRED.parent.mkdir(parents=True, exist_ok=True)
        CRED.write_text(f"# Symposium credentials. Readable only by you.\n"
                        f"# Replace {PLACEHOLDER} with the values you were given.\n"
                        f"export {user_var}={PLACEHOLDER}\nexport {pass_var}={PLACEHOLDER}\n")
        CRED.chmod(stat.S_IRUSR | stat.S_IWUSR)
        return False, f"created {CRED} with placeholders"

    CRED.chmod(stat.S_IRUSR | stat.S_IWUSR)          # tighten it whatever it was
    have = _entries(CRED.read_text())
    missing = [v for v in (user_var, pass_var) if v not in have]
    if missing:
        with CRED.open("a") as fh:
            for v in missing:
                fh.write(f"export {v}={PLACEHOLDER}\n")
        return False, f"added {', '.join(missing)} to {CRED} as placeholders"
    if any(have[v] in ("", PLACEHOLDER) for v in (user_var, pass_var)):
        return False, f"{CRED} still contains placeholders"
    return True, f"{CRED} has {user_var} and {pass_var}"


def load_credentials(prefix):
    """Load the credentials file into os.environ, OVERRIDING what is already there.

    Overriding, not setdefault. The whole documented recovery loop is "edit the file and run
    this again" — and a participant does that in the terminal they are already in, which has
    very often already sourced the old file. With setdefault, the stale value in the shell wins,
    the edit appears to do nothing, and the error tells them to check a file that is now
    correct. That is a loop with no exit, hit at the exact moment someone is already unsure
    whether they typed their password right.

    -> a note if the shell disagreed with the file, so the participant knows their CURRENT
    shell is stale even though this run succeeded. Values are never printed.
    """
    if not CRED.exists():
        return None
    stale = []
    for k, v in _entries(CRED.read_text()).items():
        if k in os.environ and os.environ[k] != v:
            stale.append(k)
        os.environ[k] = v
    mine = [k for k in stale if k.startswith(f"NDEX_{prefix}_")]
    if mine:
        return (f"note: {', '.join(mine)} already had a DIFFERENT value in this shell; the "
                f"file wins here, but that shell is stale — open a new terminal, or re-source "
                f"the file, before running anything else")
    return None


def whoami(prefix):
    """-> (account, error). Authenticates. Prints nothing."""
    sys.path.insert(0, str(TOOLS))
    try:
        import ndex_io
    except Exception as e:                                     # noqa: BLE001
        return None, f"cannot import the toolchain from {TOOLS}: {e}"
    try:
        _, tok = ndex_io.auth(prefix)
    except SystemExit as e:
        return None, str(e)
    me = ndex_io.whoami(tok)
    if not me or not me.get("userName"):
        return None, ("the server did not accept those credentials — check the username and "
                      "password in the file, then run this again")
    return me["userName"], None


def write_env(workdir, prefix, account, members):
    env = workdir / "env.sh"
    env.write_text(f"""# Symposium session environment for {account}. Written by setup.py.
# Use it at the start of every shell command:
#
#     source {env}
#     python3 "$SYMPOSIUM_TOOLS/publish.py" --as {prefix} --role importer --check my_artifact.json
#
# Do not edit SYMPOSIUM_MIRROR to point somewhere else. Validation is only as good as the
# record it can see: aimed at an empty directory it approves duplicate names and unresolvable
# addresses without complaint.

set -a
. "{CRED}"
set +a

export SYMPOSIUM_TOOLS="{TOOLS}"
export SYMPOSIUM_MIRROR="{workdir / 'record'}"
export SYMPOSIUM_LOG="{workdir / 'events.jsonl'}"
export SYMPOSIUM_MEMBERS="{members}"
export SYMPOSIUM_ADMIN="{ADMIN}"
export SYMPOSIUM_PREFIX="{prefix}"
export SYMPOSIUM_ACCOUNT="{account}"
""")
    env.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return env


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--as", dest="prefix", required=True,
                    help="your credential prefix, e.g. VEGA (not your account name)")
    ap.add_argument("--workdir", default="~/symposium-work",
                    help="where your artifacts, mirror and log live (default: ~/symposium-work)")
    ap.add_argument("--members", default=DEFAULT_MEMBERS)
    args = ap.parse_args(argv)
    prefix = args.prefix.upper()

    print(f"Symposium setup — credential prefix {prefix}\n")

    # 1. credentials --------------------------------------------------------------------
    ok, msg = ensure_credentials(prefix)
    print(f"  credentials  {msg}")
    if not ok:
        print(f"""
  ---------------------------------------------------------------------------
  STOP HERE. This is the one step that is yours, not your assistant's.

  Open this file in an editor:

      {CRED}

  Replace {PLACEHOLDER} on these two lines with the values you were given:

      export NDEX_{prefix}_USER={PLACEHOLDER}
      export NDEX_{prefix}_PASSWORD={PLACEHOLDER}

  Save it, then run this command again.

  Do NOT paste your password into the chat. Nothing here needs it, and a chat
  transcript keeps it.
  ---------------------------------------------------------------------------""")
        return 2

    # 2. authenticate -------------------------------------------------------------------
    note = load_credentials(prefix)
    if note:
        print(f"  environment  {note}")
    account, err = whoami(prefix)
    if err:
        print(f"  account      ! {err}")
        print(f"               The file itself parses and contains both values, so if you have\n"
              f"               just corrected it, the correction WAS read — the server rejected\n"
              f"               what it now says. Check for a typo in the password, and that the\n"
              f"               username is the account name (e.g. agent_deneb) and not the\n"
              f"               prefix ({prefix}).")
        return 1
    print(f"  account      authenticated as {account}")

    # 3. working directory --------------------------------------------------------------
    workdir = pathlib.Path(args.workdir).expanduser().resolve()
    (workdir / "record").mkdir(parents=True, exist_ok=True)
    print(f"  workdir      {workdir}")

    env = write_env(workdir, prefix, account, args.members)
    print(f"  env.sh       {env}")

    # 4. first sync ---------------------------------------------------------------------
    r = subprocess.run([sys.executable, str(TOOLS / "sync.py"), "--as", prefix],
                       env={**os.environ,
                            "SYMPOSIUM_MIRROR": str(workdir / "record"),
                            "SYMPOSIUM_ADMIN": ADMIN},
                       capture_output=True, text=True)
    # Structural count, not a glob: the mirror also holds manifest.json and .sync_state.json,
    # and reporting "48 artifacts" for a 46-artifact record is a number someone will later try
    # to reconcile.
    import ndex_io
    held = len(ndex_io.load_canonical_dir(workdir / "record"))
    if r.returncode != 0:
        print(f"  record       ! sync failed:\n{(r.stdout + r.stderr).strip()[:400]}")
        return 1
    print(f"  record       {held} artifact(s) in {workdir / 'record'}")

    print(f"""
Done. From now on, every command starts the same way:

    source {env}

Then, from {workdir}:

    python3 "$SYMPOSIUM_TOOLS/sync.py"    --as {prefix}
    python3 "$SYMPOSIUM_TOOLS/publish.py" --as {prefix} --roles

To see the record in a browser:

    python3 "$SYMPOSIUM_TOOLS/serve.py" "$SYMPOSIUM_MIRROR" --port 8760

Next: read QUICKSTART.md, part 2.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
