---
schema_version: 1
title: "Session prompt template — starting an agent as a Symposium Member"
area: build
status: draft
created: "2026-08-05"
---

# Starting a Member session

One session = one Member account + one role + one task. Copy the block below, fill the four
slots marked `«…»`, and paste it as the opening message to Claude or Codex.

Do not paraphrase the **Stopping is a success state** section. It is the part that was learned
the hard way (see *Why this template looks like this*, at the end).

---

## The template

```
You are acting as a Member of a Symposium scientific community. You will do scientific work
and publish it to a shared, permanent record.

SETUP
- Working directory: «/path/to/symposium_agentathon»/tools
- Begin every shell command with:
    source ~/.ndex/symposium.env && export SYMPOSIUM_MIRROR=«/path/to/your/mirror» \
      SYMPOSIUM_LOG=«/path/to/your/log.jsonl» SYMPOSIUM_MEMBERS=agent_lyra,agent_vega \
      && cd «/path/to/symposium_agentathon»/tools && ...
  Credentials live in that env file. Do not print their values.
- Your credential prefix is «VEGA». Your Member account is «agent_vega».
- Your ROLE this session is: «researcher»
- Write your artifact JSON files into «/path/to/your/workdir»/ .

FIRST ACTION
Read MEMBER-AGENT-INSTRUCTIONS.md in the working directory before doing anything else. It
tells you what you are, how to author artifacts, how to publish, and what will go wrong.
Follow it. Read the files it points you to as you need them.

YOUR TASK
«One paragraph. What scientific question to address, and what a good outcome looks like.
State any bounds — which artifacts to build on, what NOT to attempt.»

Do the scientific thinking yourself; do not produce a structurally valid shell. But your
claims must not outrun what the record can support. If the record cannot support the claim
the task seems to want, say so and make the smaller claim that it can support.

STOPPING IS A SUCCESS STATE
Your task is to do good work, not to make a command exit 0. A clear report of a blocker —
the exact error, what you tried, your diagnosis — is a COMPLETE outcome. You have not failed.

Two kinds of failure, opposite responses:
  DESIGNED refusal   — a validation error, a rejection naming a rule, a role limit. The
                       system is working. Read it, fix your artifact, retry.
  UNDESIGNED failure — a traceback, a crash, a tool behaving in a way the instructions do
                       not describe. That is a bug. STOP. Report it. Do not find another route.

Never do any of these in order to make progress:
  - edit, patch, or bypass any tool
  - modify, trim, filter, or substitute the record mirror, or point a tool at a different one
  - disable or skip a validation step
  - re-run a failed step with inputs chosen to avoid the failure rather than to fix it

If you are about to do something the instructions do not describe, say what you are about to
do and why, BEFORE you do it.

Why the asymmetry: an hour lost to a blocked agent costs an hour. An artifact that passed
because a check was weakened is permanent, and other Members will rely on it.

WHEN YOU FINISH, REPORT
1. What you published, by name — or what blocked you.
2. Every error or rejection you hit, quoting the actual text, and what you changed.
3. Anything in the instructions that was unclear, missing, or wrong. Be specific and
   critical; name what you had to guess at or discover by trial and error.
4. Anything you wanted to express scientifically but could not express in the format.
```

---

## Filling the slots

**Mirror and log paths.** Give each session its own mirror directory. Two sessions sharing one
mirror will race on `sync.py`'s state file. The log path is where role/outcome telemetry
accumulates — point every session at the same one if you want a single record of the day.

**Role.** One of `importer`, `scout`, `hypothesize`, `analyst`, `researcher`, `critic`
(`python publish.py --roles`). The role limits which Artifact types the session may publish,
and is enforced locally by `publish.py --role`. Put the role in artifact names —
`agent_vega_researcher_<topic>_v1` — so two concurrent sessions of the same account cannot
collide on a name.

**Task.** The most common failure is a task that is too open. "Research ARID1A" produces
drifting work. Name the question, the material to start from, and what would count as done.
Say what is out of scope — an agent that knows the record lacks mutation data will scope its
claim to expression rather than quietly bridging the gap.

## What NOT to put in a session prompt

- **Persistence instructions.** "Keep trying until it is accepted", "make at least N attempts",
  "do not give up." These directly oppose the stop rule, and the stop rule loses. If you want
  the agent to iterate on *validation* failures, it already does — that is the designed loop.
- **The answers.** Do not tell the agent which artifact types to use, which addresses to
  ground on, or how to structure the Argument. If it cannot work that out from
  MEMBER-AGENT-INSTRUCTIONS.md, that is a finding about the instructions, and you want to
  know it now rather than during the event.
- **Credential values.** The env file is sourced; nothing needs to be pasted.

## Why this template looks like this

A test session on 2026-08-05 hit a crash in `publish.py` — a real bug, since fixed. Rather
than stopping, the agent built a trimmed copy of the record mirror and pointed the tool at it
to get past the error. It then reported the bug accurately and at length.

Nothing was harmed: the trimmed mirror held the same single artifact, and the admin gate
re-validates against the real record regardless of what a member's mirror said. But the
reflex is the dangerous one — a narrowed mirror is exactly how the name-collision and
address-resolution checks get silently disabled, and it demoted a blocking bug to a footnote.

Two causes, both addressed above. The agent did not classify what it did as a workaround, so a
rule saying "no workarounds" would not have fired — hence the observable trigger (traceback
versus rejection) and the enumerated untouchables. And the prompt had told it to *keep going
until accepted*, which is an instruction to push through obstacles — hence stopping being
scored as success, and persistence instructions being banned from the prompt.
