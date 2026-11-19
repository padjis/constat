# Discovery guide — CON-26

Version 1 · 2026-11-19 · for the 5–10 conversations `PRODUCT_SPEC.md` § 10 puts in weeks 1–2

This is the script and the record-keeping for CON-26. It exists because seventeen tickets closed
between 2026-11-17 and 2026-11-19, every one of them a judgement about what a business reader
needs, and **none of those judgements has met a business reader.**

The purpose of these conversations is **not** to find out whether people like Constat. It is to find
out whether the problem it solves is one that costs somebody something today.

---

## 1. The one rule

**Do not describe Constat until the conversation is over.**

The moment you explain the idea, the other person starts being polite, and polite data is worse
than no data — it feels like validation and cannot be acted on. Everything below asks about *their
last three months*, not about a tool.

If they ask what you are building, say: *"I'll tell you at the end — I don't want to lead you."*
Nobody has ever minded.

Three things that are not evidence, however good they feel:

| Not evidence | Why |
| --- | --- |
| "That sounds useful." | A compliment. Costs them nothing and predicts nothing. |
| "We'd definitely use that." | A hypothetical about a future self. |
| "Could it also do X?" | A feature request before the problem is confirmed. Write it down, do not act on it. |

What *is* evidence: a specific past incident, with a date, a cost, and what they did instead.

## 2. Who to talk to

**Five to ten people who work across more than one repository.** The spec names the roles:
architects, engineering managers, platform leads, product owners, business analysts.

Aim for a **mix of two audiences**, because product rule 8 claims Constat serves both and that claim
is untested:

- **Technical** (4–6): architect, tech lead, platform engineer, staff engineer.
- **Business-facing** (3–4): product owner, business analyst, engineering manager who reports
  upward, anyone who signs off a release.

Where they are, in rough order of how fast they answer: people you have worked with; their
colleagues, by introduction; one or two strangers from a community where this work is discussed.
Introductions outperform cold outreach by enough that it is worth spending two conversations asking
for them.

**Twenty minutes is enough.** Ask for twenty, use twenty-five if offered. An hour-long ask gets
refused and a twenty-minute ask gets accepted.

### Outreach message

> I'm looking into how teams keep track of what their software actually *does* when the behaviour
> is spread across several repositories — not docs as such, more what happens when nobody is sure
> any more.
>
> Could I ask you about the last time that bit you? Twenty minutes, no demo, nothing to prepare.
> I'm not selling anything — I'm trying to work out whether the problem I think exists is real.

No NDA, no slides, no recording unless they offer.

## 3. The script

Four areas, taken verbatim from `PRODUCT_SPEC.md` § 10. Ask them in order; follow interesting
answers wherever they go and come back.

### Opening (2 minutes)

> Tell me what you work on, and roughly how many repositories it takes to ship one user-visible
> change.

You are listening for whether "across several repositories" is even true for them. If one
repository holds everything, say so in the notes — that is a finding about Constat's first
differentiator, not a failed interview.

### A. The last cross-repository change (6 minutes)

> Think of the last time a feature changed across more than one service. Walk me through it — what
> changed, and how did you work out what it meant?

Then, only as follow-ups:

- Who needed to understand it besides you?
- How long did working it out take? What did you read?
- What would have gone wrong if you had got it subtly wrong?
- Has that happened?

**Listen for:** who assembles the picture, from what, and how long it takes. **Write down the
tools they name** — a wiki, a spreadsheet, a release-notes doc, a person.

### B. Keeping behavioural documentation accurate (5 minutes)

> Where does the written description of how your product behaves live, and who keeps it true?

- When did you last find it wrong? What happened next?
- Who is allowed to change it? Does anybody approve that?
- If you deleted it tomorrow, who would complain, and when?

**This is the question that matters most.** If the honest answer is "nowhere, and nobody would
complain", Constat has no customer in that organisation — and that is the single most useful thing
one of these conversations can tell you.

### C. When documentation and implementation disagree (4 minutes)

> The last time the documentation said one thing and the code did another — how did you find out?

- Who decided which one was right?
- What did fixing it cost?
- Does anything check? What would have caught it?

**Listen for:** whether anybody notices, and whether noticing is somebody's job. An organisation
where drift goes unnoticed for months has the problem and does not feel it, which is a harder sale
than one that has been burnt.

### D. Trusting a generated explanation (4 minutes)

> Suppose something produced a plain-language description of what a change did to your product's
> behaviour. What would you need to see before you would put your name to it?

- Would you want to approve it yourself, or would you expect somebody else to?
- What would make you distrust it immediately?
- Who in your organisation would have to sign it off before it counted?

**Listen for:** the words they use for evidence, and whether approval is one person's job or a
committee's. Constat currently assumes **one named person accepts one rule at a time** — if nobody
describes anything like that, say so.

### Closing (2 minutes)

> Last thing — who else should I be asking about this?

Then, and only then, if they ask: describe Constat in two sentences, and watch what they do with
it. Interest *after* the problem conversation is worth more than enthusiasm before it.

## 4. The assumptions you are actually testing

These are the judgements the last three days were built on. **Do not ask about them directly** —
they are here so you can recognise an answer that bears on one. Mark each in the notes as
*supported*, *contradicted*, or *not touched*.

| # | Assumption | Where it came from | What would contradict it |
| --- | --- | --- | --- |
| 1 | A business reader will read rules about behaviour at all | product rule 8 | Nobody outside engineering reads anything like this, ever |
| 2 | Examples are what make a rule checkable | D-077 | Reviewers skim examples; prose is what they argue with |
| 3 | The exact text a user sees is the most verifiable thing | D-082, D-083 | Nobody can quote their own product's messages, or care |
| 4 | Coverage should be counted in business areas, not files | D-079 | They think in services or components, not areas |
| 5 | One named person accepts one rule at a time | D-048, D-061 | Sign-off is a committee, a ticket state, or nobody |
| 6 | Approval belongs at a command line, not where business works | D-055 | Every business reader they describe lives in a wiki or a tracker |
| 7 | Trunk-based development is an acceptable constraint | D-076 | They run Git Flow or long-lived release lines, and would not change |
| 8 | Documenting an existing area from scratch is wanted | D-080 | They would never start; only new changes matter |
| 9 | Cross-repository is the valuable axis | differentiator 1 | Their pain is within one repository, or across teams rather than repos |
| 10 | A stored agreed state is worth comparing against | D-085 | Nobody has ever wanted to know what changed since a previous agreement |

**Assumption 6 is the one to watch.** It is the most load-bearing and the least tested: Constat
deliberately keeps acceptance at the CLI, and CON-58 is open precisely because that may be wrong.

## 5. Recording a conversation

One file per person, in `discovery/` (git-ignored — see below), from this template:

```markdown
# P3 — 2026-11-26

**Role:** platform lead, ~40 engineers, 12 repositories
**Found via:** introduction from P1
**Length:** 25 minutes

## The last cross-repository change
<their words, in their words — quote rather than paraphrase where you can>

## Where behaviour is written down, and who keeps it true

## When documentation and implementation disagreed

## What they would need before trusting a generated explanation

## Assumptions touched
- 1 supported — "the PO reads our release notes line by line"
- 5 contradicted — "nobody signs anything off; it's in the ticket or it isn't"
- 6 not touched

## Quotes worth keeping
> "…"

## What they do today instead
<the workaround — this is the competitor>

## Would they give us a repository? Would they pay?
<only if it came up naturally>
```

**No names, employers or personal details in this repository.** `CLAUDE.md` forbids personal data in
project files, and that applies to interview notes as much as to evidence. Use `P1`…`P10`, keep the
mapping somewhere private, and add `discovery/` to `.gitignore`. What belongs in the repository is
the *synthesis*, not the transcripts.

## 6. What to do with ten conversations

After each one, write the notes **the same day** — a day later you will have smoothed them into what
you expected to hear.

After all of them, write one page in `PROJECT_STATUS.md` answering three questions:

1. **Does the problem exist?** How many of the ten described a specific, dated, costly incident of
   not knowing what their software does? Name the number.
2. **Who owns it?** Which role described it as *their* problem rather than somebody else's? If no
   role owns it, there is no buyer.
3. **Which assumptions moved?** The table above, filled in across all ten.

### What would mean stopping

Written down now, while it is cheap to be honest:

- **Nobody describes a specific incident.** The problem is theoretical, and the product is a
  solution to a feeling.
- **Everybody owns it and nobody owns it.** Interesting to all, budgeted by none.
- **The workaround is good enough.** A spreadsheet somebody maintains in an hour a month is not a
  problem worth a tool.
- **Approval is nobody's job.** Constat's entire governance half — the half that makes it more than
  a summariser — has no purchaser.

Any of those is a reason to change the product or stop, and finding it out after ten conversations
is a cheap outcome. Finding it out after a hosted platform is not.

## 7. Status

| | |
| --- | --- |
| Conversations held | **0** |
| Target | 5–10 |
| Guide written | 2026-11-19 |
| First two | `PROJECT_STATUS.md` has put these on "Day 7" since 2026-11-08 |

The code is not the constraint. This is.
