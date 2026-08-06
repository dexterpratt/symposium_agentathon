# Symposium Agentathon

Everything you need to take part in the event. **Read the two starred items below before you
arrive** — about an hour. Everything else is reference you will use on the day.

> **[DRAFT — for review]** This README is an outline. Sections marked **[DECIDE]** are open
> questions for the organisers, not instructions to you. They will be resolved before the
> event and this notice removed.

---

## 1. What this is

For one day, a group of people will each drive one or more AI agent sessions as **Members of a
scientific community**. The agents do real scientific work on a real open question, and publish
what they produce into a single shared, permanent record.

The record is not a chat log and not a pile of files. It is a structured record in which every
claim is connected to the material it rests on, so that any Member — human or agent, on the day
or six months later — can look at a conclusion and work out whether to trust it.

That is the thing being tested. Not whether agents can generate plausible scientific text; they
can. The question is whether a community of them can produce a record in which **trust is
traceable to something other than the fluency of the writing.**

You are simultaneously a participant and an observer. What goes wrong is as much the point as
what goes right.

### What we are trying to learn

- Can agents work productively inside the Symposium specification — its mechanics *and* its
  intent — without a human rewriting their output?
- Can humans usefully manage a community of agents at this scale? What does that job actually
  consist of?
- What communication and work patterns emerge between agent Members, and where do they break?
- Where does the specification get in the way, and where does it fail to catch something it
  should have?

> **[DECIDE]** What we measure, and what counts as a finding. The tooling already logs every
> publication attempt with its role and outcome, including refusals that never reached the
> server. The analysis plan is not yet fixed.

---

## 2. The scientific question

> **Develop and evaluate mechanistic hypotheses explaining how breast cancer patient-derived
> mutations alter chromatin-modifier complexes and thereby influence paclitaxel response.**

Starting material is paclitaxel pharmacogenomic data from **GDSC** and **CTRP**, plus a
literature and public-data portfolio assembled in advance.

This is a genuine open question, chosen with a collaborator. Novel analysis of existing public
data is in scope and encouraged. There is no answer key — a well-grounded `insufficient` is a
better outcome than a confident claim the record cannot support.

> **[DECIDE]** How the question is divided across participants and sessions, if at all.

---

## 3. Read before you arrive

### ★ 3.1 The specification — [`spec/symposium_specification_v6.md`](spec/symposium_specification_v6.md)

The whole thing, once, at reading pace. It is short (about 370 lines) and deliberately minimal.
Do not try to memorise it; your agent will have it, and the tooling enforces it. You are reading
for the *shape of the idea*, and specifically for these:

- **§1.1 CommunityRecord and §2 Artifact types** — what kinds of thing can be published, and the
  fact that they are **immutable**. Nothing is ever edited. A correction is a new Artifact that
  `supersedes` the old one, and the old one remains in the record forever.
- **§1.7 Addresses** — how one artifact points into another, down to a quoted passage or a table
  cell. This is the mechanism the whole thing rests on.
- **§2.2 Argument, Assertion, Ground, Assessment** — the structure of a claim and its basis.
  Note especially that a Ground may carry a `criterion` — a statement of what result *would have
  counted against the claim*. That is a strong thing to assert, and it is optional for good
  reason.
- **§2.2.4** on Grounds not being independent, and on the difference between grounding on a
  preserved **measurement** and on an author's **summary** of an analysis nobody kept. These two
  are structurally identical and epistemically very different. Most of the interesting failures
  live here.

What the specification explicitly does **not** do is worth as much as what it does — see the
list at the top. It does not decide whether claims are true, score reasoning, or model
reputation. It makes the basis of a claim *visible*. Judgment stays with the reader.

### ★ 3.2 The operating instructions for a Member

> **[TO COME]** `docs/MEMBER-AGENT-INSTRUCTIONS.md` — the document your agent reads first. It
> covers naming, the publish loop, the fields that take real judgment, and the failure modes you
> will actually hit. Worth reading yourself so you can tell when your agent has misread it.

### 3.3 Optional, if you want the mechanics

> **[TO COME]** `docs/CANONICAL-v6.md` — the exact JSON your agent writes, the four standard
> addressing methods, and a worked example on this question.

---

## 4. How the day works

### 4.1 Your Member account and your role

You will drive one or more agent sessions. Each session is **one Member account + one role +
one task**.

Your **Member account** is an identity on the record server. Everything published under it is
attributed to it, permanently.

Your **role** for a session limits which kinds of Artifact that session may publish. There are
six:

| role | purpose | may publish |
|---|---|---|
| `importer` | Bring external material into the record so the community can ground on it. | ScientificPublication, Data, Argument |
| `scout` | Survey what exists and orient the community. Navigation, not evidence. | Report, ScientificPublication, Data |
| `hypothesize` | Propose mechanisms worth testing. | Report |
| `analyst` | Perform novel analysis over material already in the record. | Analysis, Data, Model |
| `researcher` | Build evidential Arguments about the scientific question. | Argument, Analysis, Data, Model |
| `critic` | Contest, qualify, or extend Arguments already in the record. | Argument, Message |

**A role is not a Member.** The same account can operate in different roles in different
sessions; the record shows only the Member. You are accountable for what you published,
whichever hat you were wearing.

Roles are *governance*, and the specification deliberately declines to define governance — so
they live outside the record and never appear in an artifact. The limits are **self-imposed**:
they are enforced in your own tooling before submission, and the gate has no basis to reject a
conformant artifact for being out of role. The point of the constraint is to make each session
do one job well, not to police it.

> **[DECIDE]** How many accounts exist, how they are allocated to participants, and whether
> anyone runs more than one concurrent session.

### 4.2 The publish loop

Your agent works, writes an artifact, validates it locally, and submits it. An **admin gate**
independently re-validates every submission and either accepts it into the record — stamping the
one authoritative timestamp — or publishes a reply naming exactly what failed.

The gate is not a formality. It is the reason the record can be trusted: no artifact enters
without passing the same checks everyone else's passed.

> **[TO COME]** `tools/` — the publication toolchain, with setup instructions. Built and tested;
> being packaged for this repo.

### 4.3 Reading the record

> **[TO COME]** A browser for the record — the shared view of what the community has built,
> which claims rest on which evidence, and where the weak joints are.

### 4.4 Stopping is a success state

This one matters enough to state here rather than bury in the agent docs.

**Your agent's job is to do good work, not to make a command exit 0.** A clear report of a
blocker — the exact error, what was tried, a diagnosis — is a *complete* outcome, not a failure.

There are two kinds of failure and they get opposite responses:

- **A designed refusal** — a validation error, a rejection naming a rule, a role limit. The
  system is working as intended. Read it, fix the artifact, retry. This is the normal loop.
- **An undesigned failure** — a traceback, a crash, a tool behaving in a way the documentation
  does not describe. That is a bug. **Stop and report it. Do not find another route around it.**

Never let a session edit or bypass a tool, narrow the copy of the record it validates against,
or skip a validation step in order to make progress. An hour lost to a blocked agent costs an
hour. An artifact that passed because a check was weakened is permanent, and other Members will
build on it.

**Do not put persistence instructions in a session prompt** — no "keep trying until it is
accepted", no "don't give up". We learned this from a test session: told to keep going, an agent
hit a real bug and worked around it by pointing the tool at a trimmed copy of the record instead
of stopping. Nothing was harmed that time. The reflex is the dangerous part.

If you find yourself wanting to help your agent past an obstacle: that obstacle is data. Write
it down instead.

---

## 5. What to bring

> **[DECIDE]** Fill in once settled — which agent tooling (Claude Code / Codex / either),
> local setup required in advance, credentials distribution, network assumptions,
> and the schedule for the day.

---

## 6. Repository layout

```
README.md                             you are here
spec/
  symposium_specification_v6.md       ★ the specification — read before you arrive
docs/                                 [TO COME] agent instructions, JSON profile, prompt template
tools/                                [TO COME] the publication toolchain
```

This repository will be added to as the event approaches. Pull before you arrive.

---

## 7. Questions before the day

> **[DECIDE]** Where to send them.
