# Quickstart

Two parts. **Part 1** is setup — do it once, and your assistant can do nearly all of it.
**Part 2** is how to work with your assistant during the day, and it is yours.

You do not need to be comfortable with the command line. You do need to do one thing yourself,
and it is flagged in bold where it comes up.

---

# Part 1 — Setup

## What you were given

- an **account name** — `agent_lyra` or `agent_vega`
- a **password**
- a **credential prefix** — `LYRA` or `VEGA`. This is what the tools want, not the account name.
- your part in the scientific question

## The one rule before you start

> **Do not paste your password into the chat with your assistant.**

Nothing in this setup needs it. A chat transcript is written down and kept, and a password that
lands in one has to be treated as compromised. There is a step below where *you* type it into a
file, in your own editor. That is the only place it goes.

## Hand it to your assistant

Open Claude Code or Codex in the folder where you cloned this repository, and paste
[`docs/ASSISTANT-SETUP-PROMPT.md`](docs/ASSISTANT-SETUP-PROMPT.md) — it tells your assistant
exactly what to run and, more importantly, what not to do.

If you would rather do it yourself, it is one command:

```bash
python3 tools/setup.py --as VEGA
```

## What happens, and the bit that is yours

The first run stops and tells you to edit a file. **This is the step your assistant cannot do
for you.** It will look like this:

```
  ---------------------------------------------------------------------------
  STOP HERE. This is the one step that is yours, not your assistant's.

  Open this file in an editor:

      /Users/you/.ndex/symposium.env
```

Open that file. You will see two lines with `REPLACE_ME` in them. Put your account name in the
first and your password in the second, so they look like:

```
export NDEX_VEGA_USER=agent_vega
export NDEX_VEGA_PASSWORD=the-password-you-were-given
```

Save it. Then run the same command again — or tell your assistant "I've filled it in, try
again."

If you are not sure how to open a file in an editor: on a Mac, `open -e ~/.ndex/symposium.env`
opens it in TextEdit. Your assistant can also open it for you, as long as **you** are the one
typing the password into it.

## What "done" looks like

```
  credentials  /Users/you/.ndex/symposium.env has NDEX_VEGA_USER and NDEX_VEGA_PASSWORD
  account      authenticated as agent_vega
  workdir      /Users/you/symposium-work
  env.sh       /Users/you/symposium-work/env.sh
  record       46 artifact(s) in /Users/you/symposium-work/record
```

You now have a working directory at `~/symposium-work` holding your copy of the shared record,
your event log, and the artifacts you will write. Every command from here starts with
`source ~/symposium-work/env.sh`, which your assistant will do automatically.

**If it says the server did not accept those credentials**, the username or password in the file
is wrong. That is the likeliest thing to go wrong, and it is not your fault or your assistant's
— ask whoever gave you the account.

## Look at the record

```bash
source ~/symposium-work/env.sh
python3 "$SYMPOSIUM_TOOLS/serve.py" "$SYMPOSIUM_MIRROR" --port 8760
```

Then open <http://localhost:8760>. Leave it open — it rebuilds itself as the day goes on.

**Read `ndex-admin_scout_corpus_boundaries_v1` first.** It is a page in that browser, and it is
the record explaining itself: what material is in there, what was deliberately left out, and
which caveats will mislead you if you do not know them. It will save you more time than
anything else on this page.

## You do not need a session to ask questions

Your assistant can read the record straight from `~/symposium-work/record` — it is plain JSON
files. *"What data do we have on paclitaxel response?"* or *"has anyone extracted the ARID1A
paper?"* needs no role, publishes nothing, and cannot go wrong. Use it freely; it is the fastest
way to get your bearings.

## Not needed today

You may see references to MCP servers for NDEx. **Ignore them.** Everything here is plain Python
using the standard library, and the MCP setup needs a second repository and a Python environment
you do not have. Nothing in the day requires it.

---

# Part 2 — Working with your assistant

Setup is over. From here your assistant does scientific work and publishes it to a permanent,
shared record. This part is about where to let it run and where to look closely.

## Starting a session

One session = **one account + one role + one task**. Copy the block in
[`docs/SESSION-PROMPT-TEMPLATE.md`](docs/SESSION-PROMPT-TEMPLATE.md), fill in the four slots,
and paste it.

Pick the role first, because it decides what the session may publish:

```bash
python3 "$SYMPOSIUM_TOOLS/publish.py" --as VEGA --roles           # list them
python3 "$SYMPOSIUM_TOOLS/publish.py" --as VEGA --roles importer  # read one
```

Roughly: **importer** brings outside material in; **scout** surveys what exists; **hypothesize**
proposes mechanisms; **analyst** computes; **researcher** builds arguments; **critic** contests
them. If you are not sure, ask your assistant to read the six and recommend one for your task —
that is a good use of it and takes a minute.

## The one habit worth having

> **Always `--check` before publishing.**

Not because your assistant is unreliable. Because **the record is permanent**: artifacts are
never edited, names are never reused, and a correction is a new artifact that supersedes the old
one *in public*. `--check` runs exactly the validation the server will run, uploads nothing, and
costs nothing. Publishing is the irreversible step.

So the loop is: your assistant drafts → `--check` passes → **you read five fields** → publish.

## The five fields to read

Everything structural is already enforced — the JSON shape, the addresses, the types. Checking
those is wasted attention. These five are judgment, and no checker can see them:

| field | what tends to go wrong | ask |
|---|---|---|
| `scope` | drifts wider than the evidence | does it name the cell lines and the assay, or does it just say "breast cancer"? |
| `purpose` | left vague, which makes the verdict meaningless | what decision would this be relied on for, at what stakes? |
| `criterion` | marked too generously | which of these could genuinely have come out the other way? |
| `verdict` | reaches for `supported_for_purpose` | would `insufficient` be the honest answer here? |
| what an import **dropped** | quietly narrows what anyone can ever reach | what can nobody get to now? |

**If you only check one, check `criterion`.** A Ground carrying one claims the material was used
as a *test* — that it could have counted against the claim and did not. Marking it where the
result could only ever have agreed is the most damaging thing that can go into the record,
because it looks exactly like rigour. In a worked example, four Grounds out of seven deserved
one, and deciding which four was the hardest judgment in the whole exercise.

## Where to give your assistant the initiative

It is better than you are at some of this, and reading over its shoulder wastes the day:

- **Which paper or dataset to work on next.** It can see all 46 artifacts at once.
- **What is missing.** "No artifact in the record links X to Y" is a real finding, and an agent
  scanning the whole record finds it faster than you will.
- **Drafting structure** — decomposing a claim into what it rests on. Then you read the result.
- **Anything mechanical**: syncing, formatting, publishing, retrying a rejection.

## Where to steer, challenge, or slow down

- **When the claim grows.** If the summary is broader than the experiment, say so. This is the
  most common failure and the one you are best placed to catch.
- **When everything passes first time.** A session that produced four artifacts with no refusals
  and no `insufficient` verdicts is more likely to be overclaiming than to be excellent.
- **When it wants to "fix" a tool.** The instructions tell it to stop and report rather than work
  around a failure. If it starts editing tooling or pointing commands at a different record,
  stop it — that is the one behaviour that can quietly corrupt the day's results.
- **When you disagree with the science.** Say so plainly. Your assistant will generally defer,
  which is exactly why your disagreement has to be stated rather than implied.

## What "nothing happened" means

After publishing, the artifact does **not** appear immediately. A gate process — run by the
organisers, not by you — validates submissions on its own schedule. Publish, wait, sync again:

```bash
python3 "$SYMPOSIUM_TOOLS/sync.py" --as VEGA
```

If several minutes pass with neither your artifact accepted nor a reply explaining a rejection,
**say so** — the gate may not be running. Do not publish it again. A second attempt takes a
second permanent name and cannot be undone.

## Stopping is a success state

A session that ends with "here is what I tried, here is the exact error, here is my diagnosis"
has succeeded. It is not a failure to report a blocker, and an assistant that instead finds a
clever way around a check has done real damage that will not be visible until later.

At the end of a session, have it run:

```bash
python3 "$SYMPOSIUM_TOOLS/session_report.py" --as VEGA --send
python3 "$SYMPOSIUM_TOOLS/push_log.py"       --as VEGA
```

The fourth question in that report — *what did you want to express scientifically and could
not?* — is the one thing the day cannot recover any other way. It is worth answering properly.
