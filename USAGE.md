# Using Constat

How to run it. For *why* it works this way see [DECISIONS.md](DECISIONS.md); for the shape of the
code see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Install

Python 3.11 or newer.

```bash
git clone https://github.com/padjis/constat && cd constat
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,mcp]"
```

Two optional extras, neither needed for the evidence pipeline:

| Extra | For | Install |
| --- | --- | --- |
| `mcp` | `constat mcp`, the agent surface | `pip install -e ".[mcp]"` |
| `ai` | Constat calling a model itself | `pip install -e ".[ai]"` |

`dev` deliberately omits `ai`, so the test suite cannot reach a real API.

**Put it on your PATH.** The commands below write `constat`; the venv must be activated
(`source .venv/bin/activate`) or you must spell out `.venv/bin/constat`. For an MCP config, always
use the absolute path — your client has neither your PATH nor an activated venv.

The same applies to `pip`. On a system with no global pip — NixOS, for instance — `pip install …`
fails with `command not found` until you activate, which is the better failure: it cannot quietly
install into the wrong environment. Use `.venv/bin/pip` or activate first.

---

## 2. Decide who reads the evidence

Constat gathers evidence deterministically and never guesses what it means. Something has to
*read* that evidence to propose business rules, and there are three choices. Pick one before you
start, because a rule-generating command refuses if the answer is "nothing" (D-059).

| | Who calls the model | Cost | Model id recorded as |
| --- | --- | --- | --- |
| **MCP** — `constat mcp` driven by an agent | your client's host | none beyond your existing plan | self-reported |
| **Provider** — `CONSTAT_AI_PROVIDER=anthropic` | Constat | billed to your API account | attested |
| **By hand** — export, read, submit | you | whatever you use | self-reported |

**Tell the workspace once**, and no command asks again (D-060):

```bash
constat init --reader mcp          # at creation
constat config reader mcp          # or afterwards
constat config reader              # show it
```

`provider` is the default, and on it a rule-generating command refuses when
`CONSTAT_AI_PROVIDER` is unset — that refusal is the point (D-059). On `mcp` there is nothing to
configure, because your agent does the reading.

> **Claude Pro does not include API credits.** They are separate products. If you have a Pro
> subscription and no credits, use the MCP path — that is what it exists for.

---

## 3. A workspace, and the repositories to read

```bash
constat init
constat repo add ~/git/billing --name billing
constat repo add ~/git/web     --name web
constat repo list
```

`init` creates one SQLite file: `--workspace PATH`, else `$CONSTAT_HOME`, else `~/.constat`. It
always prints which it used, and refuses to overwrite an existing one — the thing it would destroy
is the record of your decisions.

`repo add` resolves the default branch from `origin/HEAD` and **refuses if it cannot**, because
that branch becomes the reference point for every later comparison. Pass `--default-branch main`
if your clone has no `origin/HEAD`. Repository identity is the root commit, so the same repository
cloned twice is recognised as one.

---

## 4. The loop

[LOOP.md](LOOP.md) draws this whole section as one diagram — every command, who runs it, the rework
loop after a rejection, and what is designed but not built. Read it first if you want the shape
before the detail.

### With MCP (recommended on a Pro subscription)

The server does not replace the CLI — it does the **middle third**. You set up, the agent reads,
you decide.

| Phase | Where | Commands |
| --- | --- | --- |
| Set up | your terminal | `init`, `repo add`, `config reader mcp` |
| Read | your agent | `gather_evidence`, `get_payload`, `submit_rules` |
| Decide | your terminal | `rule proposals`, `rule accept --by <who>` |

```bash
claude mcp add constat -- /absolute/path/to/.venv/bin/constat --workspace ~/.constat mcp
```

**The `--workspace` here must be the workspace you set up in.** If `constat init` used the default,
that is `~/.constat` and both must agree. Point them at different places and the agent reports
`no ticket '622'` for a ticket you can see perfectly well.

**Say so once**, and then nothing asks for a provider again:

```bash
constat config reader mcp
```

**You no longer open the ticket first.** `gather_evidence` opens one when the reference is new, so
the loop starts from the agent (D-063). A reference that matches no commits in any registered
repository is refused instead — a typo does not become a ticket, and the agent is told which
repositories were searched:

```
reference '6222' matched no commits: searched 3 repository(ies). No ticket was
opened: a reference that matches nothing is more often a typo than a ticket…
```

`constat ticket add 622` still works and is still the way to open a ticket deliberately — but it
now searches first (D-108). A reference no registered repository recognises is refused and no
ticket is opened, because at a terminal a mistyped reference should be a question rather than a new
ticket, and an empty ticket cannot be opened again. For work the repositories genuinely do not
mention yet — not started, or tracked where Constat cannot see — say so:

```bash
constat ticket add 622 --even-if-absent
```

The CLI's own `constat document <REF>` keeps refusing an unknown ticket, for the same reason.

`--no-provider` still exists, but you no longer need it here. It is a per-run override for the
genuine one-off — gathering evidence on a `provider` workspace without spending anything — and it
does not change the setting.

Then ask in plain language:

> Use constat to gather evidence for ticket 622 and propose the business rules it changed.

Four tools — `gather_evidence`, `get_payload`, `submit_rules`, `list_rule_proposals`.
**There is no accept tool and there will not be one** (D-055). The agent reads; you decide.

### With a provider

```bash
export CONSTAT_AI_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...      # read from the environment, never stored
constat ticket add 622                   # gathers, reads, fills the queue
```

`CONSTAT_AI_MODEL` overrides the default of `claude-opus-5`. What gets recorded is the model id the
API *returned*, not the alias you asked for, so a proposal still names the model that read it in a
year.

### By hand

```bash
constat ticket add 622 --no-provider          # evidence only
constat document 622 --payload > payload.json # redacted, credential-gated
#  …any model, anywhere, reads it…
constat rule submit 622 --from reply.json --provider claude --model opus-5
```

The reply is JSON:

```json
{"rules": [{
  "name": "daily-transfer-limit",
  "statement": "A transfer above the daily limit is refused.",
  "behaviours": ["Refuse the transfer and explain the limit"],
  "anchors": [{"path_glob": "rules.py", "repository_alias": "billing"}],
  "revises": 3
}]}
```

`revises` is optional — the payload includes your catalogue, so a reading can revise a rule it was
shown instead of duplicating it. Every anchor is checked against re-gathered evidence; anything
anchored to a path that is not there is discarded **with a reason**, never silently.

---

## 5. Review and decide

```bash
constat rule proposals 622          # the queue: undecided only
constat rule proposals 622 --all    # including decided ones
constat rule accept 1 --by emmanuel --rationale "matches the diff"
constat rule reject 2 --by emmanuel
constat rule history R-1            # every version, back to the reading and its evidence
constat rule list                   # the catalogue
constat document 622 --show         # the document
```

Three things that are not accidents:

- **A decision always names someone.** `--by` is optional: omitted, the name comes from your git
  identity and is recorded as *inferred* rather than *stated*. Neither is verified — nothing proves
  who ran the command — so this is not a trust level, only the difference between a name a person
  asserted and one a machine supplied. With no git identity at all, Constat refuses rather than
  recording an account name.
- **`rejected` means inconclusive, not wrong** (D-036). A later reading of better evidence is
  expected, not precluded.
- **Accepting creates the rule.** Nothing else does — not gathering, not submitting, no MCP tool.
  It also freezes a version; rules are superseded, never deleted.

The queue tells you *which* kind of empty it is:

```
No undecided rule proposals for 622.

That is not a statement that this ticket has no rules —
nothing has read its evidence yet.
```

---

## 6. Publish it

```bash
constat review 622                       # the ticket page, and the catalogue refreshed
constat review 622 --target <git-url>    # target named explicitly
constat publish                          # the catalogue alone, as `state` renders it
```

Two kinds of page, for the two audiences product rule 8 asks for (D-110):

| Page | Holds | Decisions |
| --- | --- | --- |
| `<REF>.md` | one ticket's evidence and its review queue — the technical view | this is where a verdict is written. Written by `constat review <REF>` |
| `the-product-as-it-stands.md` | every accepted rule, by area — the business explanation | none: nothing on it can be decided. Written by `constat publish` |

**Two commands, because they are two moments** (D-111). Before anyone has decided, a ticket page is
something you *circulate*: `constat review 622` writes it, and the output says how many proposals
await a decision. Afterwards the same command writes the same page as a record, and says so.
`constat publish` writes the catalogue — the record of what was agreed.

`review` refreshes the catalogue page too, and so does `--record-decisions`, so the record never
lags behind the decisions. `publish` alone is how a rule accepted from a baseline, with no ticket
that changed it, reaches a page.

The catalogue page is rewritten in full each time, so nothing written into it survives. The
decision flags live on `review` and nowhere else: a verdict is written against a rule proposal, and
the catalogue page carries none. `the-product-as-it-stands` is a **reserved**
reference — a ticket cannot be published over it.

By default the target is the wiki of the current repository's remote. An unrecognised host
**refuses** rather than guessing: a push to a guessed URL is not undone by noticing afterwards.

`review` and `publish` are the only commands that write outside the workspace, and both go through the same scanner. Gathering never publishes, accepting
never publishes, and publishing approves nothing.

> On GitHub and GitLab a wiki does not exist until you open it once in the browser. An existing but
> empty repository is fine — Constat makes the first commit.

### Deciding on the page instead of at the command line

Publishing also seeds `decisions/622.md` beside the page, once, and never writes it again — the page
is regenerated on every run, so a decision written *there* would be destroyed. A reviewer who never
opens a terminal edits that file instead, one line per rule proposal, using the `#N` shown beside
each rule on the page:

```
1: approved
2: rejected — the limit is per account, not per customer
```

They commit and push it, in the browser or otherwise. Then:

```bash
constat review 622 --read-decisions      # report what is there; records nothing
constat review 622 --record-decisions    # record it against the catalogue
```

**Do not write your name in the file.** Who decided is taken from the commit, which the repository
attests and a typed name does not — so there is no `--by` on this path. A signed commit is recorded
as `signed_commit` where git could check it and `signed_unverified` where it could not, because the
allowed-signers file lives with the signer and never on the machine reading the decisions back.

Reading the same commit twice records nothing the second time. A verdict rewritten in a *new* commit
is **reported, not applied**: a recorded decision is append-only, and `constat rule retire` is how a
rule stops describing the product. Anything Constat cannot record — a rule citation like `R-7`
instead of a proposal id, an unknown id, another ticket's proposal, two verdicts for one proposal —
is reported line by line and exits **8**, because a decision somebody made and Constat does not hold
must not look like success.

Works on any git repository: no forge API, no token, no per-platform backend. That is also what
keeps product rule 7's "no stored credentials" true — Constat is never the thing holding one.

---

## 7. Recomputing

`ticket add` refuses a second time; the ticket already exists. To re-read the same ticket:

```bash
constat document 622
```

It re-resolves the commits, re-reads the diffs, and proposes again. **Readings accumulate** — they
are append-only, so re-running three times leaves three entries in the queue, and accepting one
does not retire the others. Decide the queue before recomputing, or reject the stale duplicates.

To re-derive a rule you have already accepted, let the reading claim `revises: <rule id>`. That
appends version N+1 rather than duplicating the rule. You cannot erase version 1, by design.

---

## 7a. Landing the branch on acceptance

Off by default. Turned on, accepting a rule proposal also merges the ticket's branch into the
default branch of every registered repository that has one, and pushes it (D-062):

```bash
constat config merge-on-accept          # show it
constat config merge-on-accept on       # turn it on
```

What it does, precisely:

- The branch is the one whose **name encodes the ticket** — `feat/615-no-ads` for `615` — the same
  attribution that decides which commits belong to the ticket. You do not name it here.
- The merge is made in a **temporary clone of the remote** and lands by pushing. The repository you
  registered is never written to; it may hold work in progress.
- It **refuses rather than resolves**: a conflict, two branches naming the ticket, a branch that is
  not on the remote, no remote, or no git identity. Each refusal says which, exits 7, and pushes
  nothing.
- A refused merge **does not unwind the acceptance**. The decision is recorded and the rule version
  baselined; only the merge is missing, and merging by hand afterwards is fine.

---

## 7b. The product as it stands

The catalogue **is** the product's business documentation (D-070). This reads it against the current
mainline of every registered repository:

```bash
constat state                  # the whole product
constat state --repo 237feed   # one repository
constat state --json           # for a script
```

What it reports, in order:

- **what it read from** — each repository's mainline ref and revision, how many files it holds, and
  how many of them a rule claims. Pinned, because a picture of "now" that cannot name the commit it
  described is not checkable.
- **the business rules**, grouped by area, with the paths in mainline each one still matches.
  `(unplaced)` comes last: a rule with no area is a gap, not a section.
- **rules whose anchors are gone** — retirement candidates, never retirements. A rule leaves the
  picture only by a human decision, and an unreadable repository produces the same symptom, which
  the report says out loud.
- **what it does not describe** — the files no rule claims. On a young catalogue this is almost
  everything, and that is the honest headline rather than a footnote.

Nothing is stored. The view is computed each time, so it is always of the revisions it names — and
there is deliberately nothing here to drift from. A frozen baseline to compare against is a separate
thing and does not exist yet.

**Mainline is also what a rule can be anchored to** (D-072). An anchor must name a path the ticket
changed *or* a path that exists in mainline, so a rule can be filed where it actually lives even
when this ticket did not touch it — and a ticket that has already shipped can still be documented.
The review queue says which ground supports each anchor, because "the evidence shows this changed"
and "this file exists" are different claims.

---

## 8. Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 2 | Usage — bad arguments or malformed input |
| 3 | Repository — bad path, unresolvable revision, unknown default branch |
| 4 | Workspace — not initialised, unknown ticket, workspace already exists |
| 5 | Provider — misconfigured, unreachable, unparseable reply, or a credential in the evidence |
| 6 | Publish — target unknown, unreachable, or a credential in the document |
| 7 | Merge — the acceptance is recorded; landing the ticket's branch did not happen (D-062) |
| 8 | Decisions — the target was read; at least one decision could not be recorded (D-106) |

---

## 9. When it refuses

Constat refuses rather than guessing, so most of what you will see is deliberate. The message is
the documentation; this table is the short version.

| Message | What it means | What to do |
| --- | --- | --- |
| `CONSTAT_AI_PROVIDER is not set, so nothing would read this ticket's evidence` | A rule-generating command on a `provider` workspace with nothing configured (D-059) | Using MCP? `constat config reader mcp`, once. Otherwise configure a provider, or `--no-provider` for evidence only |
| `names a provider this version of Constat does not implement` | A typo, or a provider that is not built yet | `anthropic` is the only one today; Gemini is CON-62, ChatGPT CON-63 |
| `needs ANTHROPIC_API_KEY in the environment` | Provider named, credential absent | Export the key. It is never written to a file |
| `the 'anthropic' package is not installed` | The `ai` extra is missing | `pip install -e ".[ai]"` |
| `Your credit balance is too low` | The key works; the API account has no credit | Buy credits, **or use the MCP path** — Pro does not include API usage |
| `refusing to send evidence… possible credential(s) found` | A credential-shaped string in the evidence | Remove it from the code and **rotate it**. `--accept-scan-findings` overrides, on the record |
| `refusing to publish this document` | Same, on the page about to be published | A page cannot be recalled. Fix the evidence and re-gather |
| `no anchor grounded in the evidence supplied` | A reading anchored to a path nobody sent | Correct the anchor. Constat will not store an invented one |
| `could not determine the default branch` | `origin/HEAD` is not set | `git remote set-head origin -a`, or pass `--default-branch` |
| `whose documentation convention Constat does not know` | Publishing to an unrecognised host | Pass `--target` with the documentation repository URL |
| `a workspace already exists` | `init` on an existing workspace | Nothing was touched. Remove the file deliberately if you mean to start over |
| `no ticket '622'. Open one with \`ticket add\`` | At the CLI, or from `get_payload` before anything gathered | `constat ticket add 622`, or call `gather_evidence` first — it opens one |
| `matched no commits: searched N repository(ies)` | The reference appears in no commit message or branch name anywhere. Refused on both `ticket add` and `gather_evidence` (D-108) | Check the reference for a typo. If the work is real but unmentioned, `constat ticket add <REF> --even-if-absent` |
| `no repositories are registered` | `ticket add` or `gather_evidence` on a workspace with an empty registry — nothing was searched, so the reference was not missed | `constat repo add <path>` first, or `--even-if-absent` if the ticket should exist regardless |
| `… of which 1 could not be read` | A registered repository has moved or been deleted, so absence could not be established | Fix the path with `repo add`, or accept that the answer is unknown rather than "no" |

Two that are *not* refusals, and matter:

- **`not_found` for a repository** is an answer, not a failure. Every registered repository is
  reported, including those that contributed nothing — silence about a repository is not the same
  as no changes in it.
- **"no rules were identified"** is a statement about configuration, never about your code.

---

## 10. What Constat will not do

> The full account is in **[LIMITS.md](LIMITS.md)**: what it does not do, what it cannot check, what
> is declared and unused, and what has not been verified. This section is the short version.


Not limitations to work around — they are the product.

- **Accept anything by itself.** No command, flag, tool or provider can mark a rule proposal
  approved. Only `rule accept --by <who>`.
- **Send author or committer identity to a model.** The payload type has no field for it.
- **Write to a repository it reads** — unless you turn `merge_on_accept` on, which is off by
  default and is the one exception (D-062). Gathering never writes, whatever the setting says.
- **Report a failure as a finding.** A timeout, an unparseable reply or a missing provider is an
  error, never "no rules were identified".
- **Delete a rule, a decision, or an approved version.** Enforced by database trigger, not by
  convention.
