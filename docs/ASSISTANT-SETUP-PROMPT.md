---
schema_version: 1
title: "Setup prompt — asking your assistant to install the Symposium toolchain"
area: build
created: "2026-08-06"
---

# Ask your assistant to set you up

Copy everything in the block below and paste it as your first message to Claude Code or Codex,
in the folder where you cloned this repository.

This is **not** the same as starting a working session — see
[`SESSION-PROMPT-TEMPLATE.md`](SESSION-PROMPT-TEMPLATE.md) for that. Setup comes first, and your
assistant is not a Member of the community while it does it.

---

## The block

```
Please set up the Symposium participant toolchain in this repository for me.

YOU ARE NOT A MEMBER YET
You are helping me install and verify a tool. You are not acting as a Symposium Member,
you have no role, and you must not publish anything to the record. If you find yourself
reading tools/MEMBER-AGENT-INSTRUCTIONS.md and following it, stop — that document is for
later, when I start an actual working session.

WHAT TO RUN
    python3 tools/setup.py --as «VEGA»

Replace «VEGA» with my credential prefix. It is safe to run repeatedly.

THE CREDENTIAL STEP IS MINE, NOT YOURS
The script will stop and ask for a file to be edited with a username and password.
- Do NOT ask me for my password.
- Do NOT offer to type it, echo it, or read it back to me.
- Do NOT write it into any file, command, or note.
If I paste my password into this chat anyway, tell me immediately that it is now in the
transcript and should be changed, and do not use it.

What you SHOULD do: tell me the exact path of the file, tell me which two lines to edit,
and offer to open it in an editor for me — I will type the password in myself. Then run
the setup command again.

WHEN IT WORKS
Tell me: which account it authenticated as, where my working directory is, and how many
artifacts are in my copy of the record. Then start the record browser:

    source «workdir»/env.sh
    python3 "$SYMPOSIUM_TOOLS/serve.py" "$SYMPOSIUM_MIRROR" --port 8760

and tell me to open http://localhost:8760 .

IF SOMETHING FAILS
Report the exact error and stop. Do not edit any file in tools/, do not work around a
failing check, and do not install any Python PACKAGES — this toolchain needs only the
standard library, so a missing module means something else is wrong. A clear report of a
blocker is a complete and successful outcome.

ONE EXCEPTION, AND IT IS COMMON ON A MAC
If setup.py says the interpreter is linked against LibreSSL, that is real and it will not
work: macOS's built-in python3 cannot complete the TLS handshake with this server, and it
fails BEFORE any credential is sent, so it looks like a rejected password and is not one.
setup.py names the working interpreters it can find. Re-run it with one of those full
paths, and use that same path for every command afterwards.

WHILE I GET ORIENTED
Once the record is synced you can answer questions about it directly from the JSON files
in «workdir»/record — that needs no role and publishes nothing. Start by reading
ndex-admin_scout_corpus_boundaries_v1, which describes what is in the corpus, what was
deliberately left out, and which caveats will mislead a reader.
```

---

## Why the prompt says what it says

**"You are not a Member yet"** — the repository contains a long, forceful set of instructions for
an agent acting as a Member. An assistant that opens them while trying to install something will
adopt the role and start behaving as though it were publishing. Setup and membership are
different jobs; this sentence is what keeps them apart.

**The credential paragraph** — the natural, helpful thing for an assistant to do is offer to take
the password and set it up for you. That would put the credential into the chat transcript,
which is stored. The prompt forecloses it, and tells the assistant what to do if it happens
anyway, because saying "don't" is not the same as knowing how to recover.

**"Do not install any Python packages"** — the toolchain is standard library only. If an
assistant thinks it needs to `pip install` something, its diagnosis is wrong, and installing will
bury the real error under a new one. The interpreter itself is the exception: a Mac with only the
built-in `python3` genuinely needs a different one, because LibreSSL cannot reach the server.
