#!/usr/bin/env python3
"""Check that THIS machine can talk to the Symposium server. No account needed.

    python3 tools/preflight.py

Run this before anything else, and before you have credentials. It needs no password and
sends none. It answers one question: can the Python you just typed reach the server?

WHY IT EXISTS
-------------
macOS ships a `python3` linked against LibreSSL 2.8.3. It cannot complete a TLS handshake with
symposium.ndexbio.org — the server replies `sslv3 alert handshake failure` and the connection
dies before anything is sent. On a Mac with nothing else installed, that interpreter IS
`python3`, so the very first command fails for a reason unrelated to the toolchain, and every
downstream error message blames your password instead.

Nothing else in the toolchain needs the network until you publish, so without this check the
problem surfaces an hour later, in the middle of real work.

This script is deliberately dependency-free and syntax-conservative so that it runs on the
BROKEN interpreter and can tell you it is broken.
"""
import json
import os
import subprocess
import ssl
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SYMPOSIUM_BASE", "https://symposium.ndexbio.org")
PROBE_PATH = "/v2/user"          # answers 401 unauthenticated: proof of reach without a login

CANDIDATES = [
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
    "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
    "/opt/homebrew/bin/python3.12",
    "/opt/homebrew/bin/python3.11",
]


def reach():
    """-> (ok, kind, detail). Unauthenticated. Sends no credentials."""
    req = urllib.request.Request(BASE + PROBE_PATH, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, "http", "HTTP %d" % r.status
    except urllib.error.HTTPError as e:
        # 401 is SUCCESS here: we reached the server and it asked who we are.
        return True, "http", "HTTP %d (expected — the server wants a login)" % e.code
    except urllib.error.URLError as e:
        text = str(e.reason)
        if "HANDSHAKE" in text.upper() or "SSL" in text.upper():
            return False, "tls", text
        if "not known" in text or "nodename" in text or "Name or service" in text:
            return False, "dns", text
        return False, "net", text
    except Exception as e:                                     # noqa: BLE001
        return False, "net", str(e)


def line():
    return "%s | %s" % (sys.version.split()[0], ssl.OPENSSL_VERSION)


def probe_others():
    """Test every other interpreter we can find, by running this script's --probe in it."""
    here = os.path.realpath(sys.executable)
    out = []
    for cand in CANDIDATES:
        if not os.path.exists(cand) or os.path.realpath(cand) == here:
            continue
        try:
            r = subprocess.run([cand, os.path.abspath(__file__), "--probe"],
                               capture_output=True, text=True, timeout=60)
            d = json.loads(r.stdout.strip().splitlines()[-1])
            out.append((cand, d))
        except Exception:                                      # noqa: BLE001
            continue
    return out


def main():
    if "--probe" in sys.argv:                    # machine-readable, used by probe_others()
        ok, kind, detail = reach()
        print(json.dumps({"python": line(), "ok": ok, "kind": kind, "detail": detail[:120]}))
        return 0

    print("Symposium preflight — no account needed, no password sent\n")
    print("  interpreter  %s" % sys.executable)
    print("  version      %s" % line())
    print("  server       %s" % BASE)

    ok, kind, detail = reach()
    if ok:
        print("  connection   OK — %s\n" % detail)
        print("This Python can reach the server. Use THIS interpreter for everything:")
        print("    %s tools/setup.py --as <YOUR_PREFIX>" % sys.executable)
        return 0

    print("  connection   FAILED (%s)" % kind)
    print("               %s\n" % detail)

    if kind == "tls":
        print("This is the known macOS problem, and it is not your network or your password.")
        print("%s cannot negotiate TLS with this server." % ssl.OPENSSL_VERSION)
        print("No credential was sent — the connection failed before that point.\n")
    elif kind == "dns":
        print("The server name did not resolve. Check the spelling and that you are online.\n")
    else:
        print("The server could not be reached. A VPN, proxy or firewall will do this.\n")

    others = probe_others()
    working = [(c, d) for c, d in others if d.get("ok")]
    if working:
        print("Another Python on this machine WORKS. Use it for every command:\n")
        for c, d in working:
            print("    %s\n        (%s)" % (c, d["python"]))
        print("\nFor example:")
        print("    %s tools/setup.py --as <YOUR_PREFIX>" % working[0][0])
    elif others:
        print("Other interpreters found, none of which could connect either:")
        for c, d in others:
            print("    %s  (%s) — %s" % (c, d["python"], d["kind"]))
        print("\nThat points at the network rather than at Python: a VPN, proxy or firewall.")
    else:
        print("No other Python found on this machine. Install one:")
        print("    brew install python@3.12")
        print("then re-run this with /opt/homebrew/bin/python3 .")
    return 1


if __name__ == "__main__":
    sys.exit(main())
