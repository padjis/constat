# Backlog

Ticket register. The single source of truth for *what work exists*; the single source of truth for
*what was decided* is [DECISIONS.md](DECISIONS.md), and for *where things stand* it is
[PROJECT_STATUS.md](PROJECT_STATUS.md).

## Conventions

- **ID format:** `CON-NN`. Stable and never reused, including for abandoned tickets.
- **`CON-01` … `CON-20` are the twenty roadmap sessions**, in order. Session *N* is always
  `CON-NN`, so no mapping table is needed.
- **`CON-21` onwards** is everything that is not a session: commercial, legal and validation work.
- **Commit messages** reference the ticket in the subject and close it in a trailer:

  ```
  Session 04: read a local Git repository (CON-04)

  ...body...

  Closes: CON-04
  Signed-off-by: ...
  ```

  Use `Refs: CON-04` for partial work and `Closes:` only when the done-when criterion is actually
  met.
- **Tickets are not decisions.** A ticket is work that gets closed; a `D-NNN` entry is an immutable
  record of why. A ticket may produce a decision, and the commit should mention both — but closing
  a ticket never deletes or supersedes anything.

**Status:** ✅ done · 🟡 in progress · ⬜ not started · 🔴 blocked

---

## Phase 1 — Foundation

| ID | Title | Done when | Status |
| --- | --- | --- | --- |
| CON-01 | Create the repository and working agreement | A documented empty project with clear scope and rules. | ✅ `b092b62` |
| CON-02 | Create the Python project skeleton | The CLI installs and runs locally; tests execute. | ✅ `68d2ffb` |
| CON-03 | Add configuration and input validation | Helpful errors; no silent defaults for important inputs. | ✅ `7458423` |
| CON-04 | Read a local Git repository | Tests cover valid, invalid and missing repositories/revisions. | ✅ `184fa0b` |

## Phase 2 — Evidence engine

| ID | Title | Done when | Status |
| --- | --- | --- | --- |
| CON-05 | Compare two revisions | A deterministic change summary for two revisions. | ✅ `6e3b07d` |
| CON-06 | Collect inspectable evidence | Evidence records can be traced back to Git. | ✅ `eb957b6` |
| CON-07 | Define the change data model | Stable, tested structured output. | ✅ `24d3746` — top-level object revised by D-029 |

## Phase 3 — Meaning and reporting

| ID | Title | Done when | Status |
| --- | --- | --- | --- |
| CON-08 | ~~Classify changes conservatively~~ | — | 🔁 **superseded by CON-40..43.** Classification by code signal was dissolved: D-034 removed flags, D-038 removed migrations, D-035 established that rules are business statements no signal can produce. |
| CON-09 | Generate the first report | A developer can understand the report without reading raw command output. | ✅ D-056 — business and evidence halves, rendered from stored state; usable as PR markdown |
| CON-10 | Separate facts from interpretation | Every claim has a provenance type; unsupported claims are visibly uncertain. | ⬜ |
| CON-11 | Strengthen quality with tests | The report remains safe and useful across realistic Git cases. | ⬜ |

## Phase 4 — Human governance and history

| ID | Title | Done when | Status |
| --- | --- | --- | --- |
| CON-12 | Implement review decisions | No proposal becomes official without an explicit human decision. | ✅ CON-44/D-053 — `--by` is required with no default, decisions are append-only in their own table, and D-055 keeps acceptance out of every MCP tool |
| CON-13 | Persist proposals and decisions | A restart does not lose review history. | 🔁 **superseded by CON-31** — persistence is now a prerequisite, not Phase 4 |
| CON-14 | Create immutable approved baselines | A later approval creates a new version; previous content remains recoverable. | ✅ CON-43/D-053 — versions are frozen rows with `UPDATE`/`DELETE` aborted by trigger. **Partial on recoverability:** see CON-61 |
| CON-15 | Compare against the last approved baseline | A reviewer can see what is new since the last approved state. | ✅ D-085 — schema 20; a *checkpoint*, taken explicitly and compared by version number, with four outcomes per rule. The word "baseline" was already taken twice over, so this object has its own noun |

## Phase 5 — GitHub and realistic demonstration

| ID | Title | Done when | Status |
| --- | --- | --- | --- |
| CON-16 | Read GitHub repository metadata | Constat can identify the GitHub repository and map it to its local clone. | ⬜ |
| CON-17 | Link pull requests to change proposals | A proposal can be traced to its originating PR. | ⬜ |
| CON-18 | Add traceability references | A reviewer can navigate from a proposal to its supporting artefacts. | ⬜ |
| CON-19 | Run a realistic multi-change scenario | A repeatable demo shows the product-level value, not just a Git diff. | ⬜ no longer the *first* cross-repo work — CON-32 makes the set primary |
| CON-20 | Package the MVP and document limits | A new person can run the demo and understand what Constat does and does not do. | ⬜ |

---

## Non-session work

Not optional, and not code. These are the items most likely to be skipped because no session
forces them.

| ID | Title | Done when | Status |
| --- | --- | --- | --- |
| CON-21 | The site has a home | The project site resolves somewhere its author controls. | ✅ D-075 — `constat.padjinou.com`, a subdomain of an owned domain. No domain bought: `tryconstat.com` stays the choice from D-014 for when there is something to put on it, and stays registerable by anyone until then |
| CON-22 | ~~Trademark knockout search on "Constat"~~ | — | ❌ **withdrawn 2026-11-19 (D-086).** Attempted 2026-11-16 and not possible from this environment (`BRAND_NAME_REVIEW.md` § 10). The name is used as-is and unverified; the risk is accepted rather than cleared |
| CON-23 | ~~Trademark attorney review~~ | — | ❌ **withdrawn 2026-11-19 (D-086).** The FR/EU descriptiveness question — is `CONSTAT` registrable for software that produces findings — is left unanswered. Reopen as a new ticket if the name is ever to be defended |
| CON-24 | Ratify the proposal unit (Q1) | A `D-NNN` entry fixes the unit of a proposal. | ✅ D-025 |
| CON-25 | Decide the copyright holder | `LICENSE` and `NOTICE` name the intended holder. | ✅ D-074 — held personally; `LICENSE` and `NOTICE` were already correct, so this closes as recorded rather than implemented. A CLA is needed only if relicensing is intended |
| CON-26 | Hold 5–10 discovery conversations | Notes from 5–10 people who work across multiple repositories. | 🔴 **0 held** — the roadmap puts the first two on Day 7. The script, the outreach message, the record template and the ten assumptions being tested are written: [DISCOVERY.md](DISCOVERY.md). Only the conversations are missing |
| CON-27 | Secure one design partner | A safe, non-sensitive sample repository from someone other than us. | ⬜ weeks 3–5 |
| CON-28 | Obtain two pilot commitments | Two time-boxed pilots with named users and agreed success criteria. | ⬜ weeks 6–8 |

## New scope

| ID | Title | Done when | Status |
| --- | --- | --- | --- |
| CON-56 | Render from stored state | The document shows the catalogue and the review queue, not just the current run. | ✅ D-056 |
| CON-60 | The first real provider | `CONSTAT_AI_PROVIDER=anthropic` makes `ticket add` fill the review queue with no `rule submit` step, and the recorded model id is the one the API returned. | ✅ D-057 — also closes CON-42 |
| CON-57 | A publishing port, and the default target | A document is published to the repository's page tool, through the credential gate. | ✅ D-058 |
| CON-58 | Read decisions back, with provenance | A decision records its channel and how identity was established, including a decision taken on the published surface rather than at the CLI. | ⬜ **next** — the port's `read_decisions` raises `DecisionsNotReadable` until this lands. **Widened 2026-11-18** from prior experience of this problem: a business audience that approves on the published surface, per rule, and never sees the repository is the only arrangement in which product rule 8's audience can actually decide. That makes `channel` the load-bearing field rather than a label: an approval recorded on the page is *more* verified than a CLI `--by` string, which nothing checks (D-061). **Needs a decision before implementation** — D-048 and D-055 put acceptance at the CLI only, and reading an off-CLI approval back as a decision either amends that or must stay a report that a human still has to act on |
| CON-97 | Registration states which branch Constat treats as the product's released state | `repo add` names the mainline it resolved, and warns when the repository looks like Git Flow — a default branch called `develop`, or a `master`/`main`/`production` branch ahead of the default. | ⬜ D-076 — a warning, never a refusal: the signal is a naming convention, and refusing on one would reject a legitimate repository that happens to use the word |
| CON-59 | Confluence, GitBook, GitLab docs backends | Each behind the same port, as optional extras. | ⬜ — the port exists; each backend is a `Target` implementation |
| CON-65 | Who reads the evidence is a workspace setting | `ticket add` needs no flag on an MCP workspace; `init --reader` and `config reader` set it. | ✅ D-060 |
| CON-66 | MCP prompts, so the loop is one command | `/mcp__constat__document <REF>` runs the whole loop; the rule-writing guidance is shared with the provider path. | ✅ |
| CON-68 | Infer the decider from git config | `rule accept` needs no `--by`; the record says whether the name was stated or inferred. | ✅ D-061 |
| CON-69 | Accepting a rule proposal can land the ticket's branch | With `merge_on_accept` on, `rule accept` merges the branch naming the ticket into each registered repository's default branch and pushes it; off by default, and every ambiguity refuses without unwinding the acceptance. | ✅ D-062 |
| CON-70 | A re-run must not duplicate a pending rule proposal | Submitting a reading that matches one already awaiting a decision is reported as a possible duplicate, and `get_payload` shows the pending queue alongside the catalogue. | ✅ D-064 — reported, never refused |
| CON-71 | A rule can be attested by evidence it is not anchored to | A reading can propose a rule the evidence states but whose home was not changed, without either inventing an anchor or being discarded. | ✅ D-072 — two grounds, and which one supports an anchor is recorded; also unblocks reading a ticket after it lands |
| CON-72 | The guidance says whether a rule may be conditional on a transient state | A reader is told whether "while the site is not approved" is a rule or a situation, so the question is answered once rather than per reading. | ✅ D-071 — yes, and the condition goes in the statement |
| CON-74 | A rule statement is purely business | A statement or behaviour that leaks code is refused with the offending token named, and the guidance states the business-only test as one question. | ✅ D-066 — leakage is mechanical; business-ness is the guidance's job and the reviewer's |
| CON-73 | A reading can say that evidence repairs a rule | A pure bug fix proposes the rule it repairs, marked as repaired rather than established, including a rule nobody had written down. | ✅ D-065, D-067 — schema 10; a repair states its rule rather than naming an id |
| CON-75 | Constat's own merge commit is not evidence | A commit Constat made when landing a ticket is excluded from that ticket's evidence, identified by a `Constat-Landed:` trailer it writes rather than by its subject, and the document states that it was excluded. | ✅ D-069 — not retroactive: merges made before the trailer stay in their ticket's evidence |
| CON-76 | A landed ticket does not keep reading as pending | Mainline is the remote-tracking ref, Constat refreshes that ref in the registered repository after its own push, and the document states how old each repository's picture of the remote is. | ✅ D-068 — drift counted both ways; CON-38 still owns staleness no write can fix |
| CON-77 | A rule carries a business area | A reading proposes the area a rule belongs to, the area is refused if it names code, and acceptance carries it onto the rule and its frozen version. | ✅ D-070 — schema 11; areas are nullable and nothing is back-filled |
| CON-78 | The current picture of the product | `constat state` renders the accepted rules by area, across every registered repository pinned at its own mainline revision, flagging rules whose anchors no longer exist and paths no rule claims. | ✅ D-070 — computed, never stored; a stored baseline is still CON-15 |
| CON-79 | A rule records the evidence it was accepted on | An accepted rule version names the commits whose evidence produced it, and the pointer survives the ticket landing, the document being regenerated and the repository being re-cloned. | ✅ D-073 — a pointer, not a copy; nothing back-filled because the earlier evidence is gone |
| CON-67 | A rule has a title and details, and details are tracked across versions | `rule history` shows which details were added, removed, edited or unchanged between versions. | ✅ D-078 — schema 15; identity is the detail's text, numbered at acceptance, never reused, and compared by number rather than by position |
| CON-64 | An agent can open a ticket | The MCP workflow starts from the agent: `gather_evidence` on an unknown reference opens the ticket rather than failing. | ✅ D-063 — opens when the repositories recognise the reference; a reference matching nothing is still refused |
| CON-62 | Gemini as a provider | `CONSTAT_AI_PROVIDER=gemini` proposes rules through the same `parse` and the same gates, as an optional extra. | ⬜ — CON-60 built the seam; this is a second `Provider` implementation |
| CON-63 | ChatGPT as a provider | `CONSTAT_AI_PROVIDER=openai` likewise. The error D-041 raises for an unimplemented name currently names this one as the example. | ⬜ |
| CON-61 | Read a frozen version's behaviours and anchors back | `rule history` can show what a version's behaviours and anchors were at the time it was accepted, not only its name and statement. | ✅ — read path only, no schema; completes CON-14's recoverability criterion and unblocks CON-67 |
| CON-80 | A rule carries worked examples, each an input and its outcome | A rule proposal may carry examples as (situation, outcome) pairs; they survive acceptance onto the frozen version, render as a table in the document and in `constat state`, and an example that restates the statement rather than instantiating it is refused. | ✅ D-077 — schema 14; shape is checked, truth never is, and a revision now sees the examples it would otherwise delete |
| CON-81 | A rule has a permanent, citable identifier | Every rule gets an identifier stable across versions, printable, quotable in a review conversation, and never reused after retirement. | ✅ D-081 — schema 17; flat (`R-14`), stored rather than derived, back-filled, and resolvable as a lookup argument |
| CON-82 | A user-facing message is a catalogue entry a rule refers to | A message a user can see is stored once with its own permanent identifier and its exact text, rules refer to it rather than quoting it, and the document renders the message catalogue beside the rules. | ✅ D-082 — schema 18; verbatim and exempt from D-066's leakage gate, stored once on exact text, cited `M-7`, minted at acceptance |
| CON-83 | A rule can be retired, and its identifier is never reused | A rule can be retired with a reason and a decider, stops appearing in `constat state`, stays readable in history, and its identifier is refused for any later rule. | ✅ D-084 — schema 19; a human decision, final, deletes nothing, and the place a lapsed condition (D-071) is expressed |
| CON-84 | The catalogue carries the business terms its rules use | A term can be defined once and rendered as a glossary alongside the rules. | ⬜ — smallest of the §1 cluster; do it last or drop it if the rules read clearly without one |
| CON-85 | A release is declared, and a rule version is agreed for one | A release is declared in the workspace spanning the registered set, several may be open at once, and accepting a rule proposal records which release its version is agreed for. | ⬜ **D-076 names the model this sits on.** Decided 2026-11-18: declared rather than derived from tags; the release is optional and nullable, so a workspace that declares none behaves as today; the release name is a free string stored verbatim (D-032's reasoning) |
| CON-86 | Closing a release puts its rule versions into effect | A human records that a release shipped, and every rule version agreed for it becomes the product's current behaviour from that point. | ⬜ — the ship is asserted, not verified: Constat cannot detect a partial ship across a plural registered set, so the record must say the release name is asserted (a stated weakening of product rule 2 for that one field) |
| CON-96 | A rule version agreed for an unshipped release is not rendered as current behaviour | `constat state` shows only versions in effect; agreed-but-unshipped versions render in their own view, never mixed into the current picture. | ⬜ — fixes the defect found on 2026-11-18: today an accepted rule from unmerged work renders as the product's current behaviour, which breaches product rule 1 in the one command whose purpose is to state the present. Absorbs the earlier framing of this as a refusal at submit time |
| CON-87 | The catalogue can be read as it stood at a past release | The rules in effect at a named past release can be rendered from stored versions, without a snapshot having been taken at the time. | ⬜ — needs CON-85/86 first; CON-61 already made a version's substance readable, which is the data this reads |
| CON-88 | A business area is declared before a rule can claim it | Areas are declared in the workspace, a reading proposing an undeclared area is reported rather than silently coining it, and the declared set is what coverage is measured against. | ✅ D-079 — schema 16; the register is *derived* from accepted rules, with a table only for areas named ahead of their first rule. Amends D-070 |
| CON-89 | An area can be documented from its current behaviour, with no ticket | An area's rules can be proposed from the state of mainline rather than from a ticket's delta, recorded as documenting existing behaviour rather than as a change. | ✅ D-080 — `constat baseline <AREA>`, no schema change: Constat supplies no evidence (the reader has the repository), the reading is recorded under a reference, and scope is the command's argument. Not available on the provider path, which is stated |
| CON-90 | Coverage is measured in declared areas, not in files | The coverage statement names documented and undocumented areas; the file count stays available as a technical figure, not as the headline. | ✅ D-079 — landed with CON-88, because the denominator is the reason CON-88 exists. The view also states what it cannot measure: parts nobody has declared |
| CON-91 | A quoted message in a statement is verified against the code | Text a rule quotes as user-visible is checked against the evidence or mainline, and a quotation found nowhere is reported. | ✅ D-083 — no schema change; searched by its longest literal fragment (placeholders and newlines cut it), absence reported never refused, and a third state for text too short to be evidence |
| CON-95 | Publication refuses a document disclosing a weakness, infrastructure or commercial data | `guard_publication` refuses on security-weakness wording, internal hostnames and addresses, and commercial figures, with the same recorded-override posture as the credential gate. | ⬜ — credentials (D-044) and identity (D-040) are covered; these three are not, and a published page reaches everyone with access to the target |
| CON-98 | The review queue can be read across the whole workspace, by state | Every rule proposal in the workspace can be listed grouped by state and ticket, filtered by state, without naming a ticket reference. | ⬜ — read path only, no schema: the states are already stored and `rule proposals` renders them per ticket. Today "what is waiting?" cannot be asked without already knowing which tickets to name |
| CON-29 | Ticket-scoped documentation (`constat document <ref>`) | A proposal can be initialised from a reference found in commit messages, across one or more repositories. | 🔁 **promoted** — now the primary workflow, delivered by CON-33/34 |
| CON-39 | Regeneration must not destroy human input | Re-running an operation preserves every comment and decision, each still attached to what it was about. | ⬜ **blocks CON-47/48** — reframed by D-043: human *edits* no longer exist, so this is now about durable comment anchors. Decisions are already safe: CON-12 closed, and a decision is attached to a rule proposal rather than to document prose |
| CON-40 | Rule catalogue storage | Rules, behaviours and anchors persist and report coverage. | ✅ |
| CON-41 | AI provider interface | A provider can be configured; absent one, Constat reports evidence and states that no rules were identified. | ✅ D-040, D-041 |
| CON-42 | Rule generation | An AI pass proposes rules, behaviours and anchors from a ticket's evidence, all as `ai_interpretation`. | ✅ — the trust boundary at D-046, storage at CON-51, the submit path at CON-52, the MCP host at CON-50, and the provider itself at CON-60/D-057 |
| CON-49 | Export the payload through the same gate | The payload can be handed out, and only through the credential gate. | ✅ D-047 — `document --payload` |
| CON-54 | Run identity | One run per invocation, with its operations attached to it. | ✅ D-049 — schema 4; prerequisite for CON-51 |
| CON-51 | Rule proposal storage | A rule proposal survives the run that produced it and the regeneration of the body. | ✅ D-051 — schema 5; the versioned catalogue lands with CON-44 |
| CON-53 | Withdraw the manual rule commands | `rule add` / `behaviour` / `anchor` / `remove` are gone, and a trigger aborts `DELETE ON rule`. | ✅ D-048 — landed with CON-51 |
| CON-52 | Submit a reply from outside | A reply produced anywhere becomes grounded, stored rule proposals via the CLI. | ✅ D-052 — `rule submit`, `rule proposals` |
| CON-55 | Propose a revision, not just a new rule | A reading can claim to revise a rule it was shown; overlap warns without deciding. | ✅ D-054 |
| CON-50 | MCP server | An MCP client can gather evidence, read the payload and submit rule proposals; acceptance is never exposed as a tool. | ✅ D-055 — `constat mcp`, stdio, optional extra |
| CON-45 | Secret scanning before the payload leaves | A payload containing a credential is refused rather than sent. | ✅ D-044 |
| CON-47 | Document comments | A comment is stored, attributed and anchored to a durable identity; the body stays machine-written. A comment collected from the published surface is stored the same way. | ⬜ D-043 — needs CON-39's anchor model. **Widened 2026-11-18** from prior experience of this problem: a comment is the *normal* way a business reader says "this is wrong", and rejection is reserved for "not wanted at all". Constat offers accept or reject and nothing between, so a reviewer who disagrees with one sentence has to reject the whole reading — which D-036 then records as inconclusive, losing what they actually said. The anchor model CON-39 owes this is therefore on the critical path for the review loop, not only for regeneration |
| CON-48 | Comments reach the interpretation pass | Commenting changes the next draft. | ⬜ D-043 — without it, commenting is a suggestion box |
| CON-46 | A built wheel actually contains the package | Installing the wheel and importing the CLI works, asserted by a test. | ✅ D-042 — discovery replaces the explicit list; `tests/test_packaging.py` builds a wheel and imports from it |
| CON-43 | Rule maintenance | Evidence contradicting a baselined rule proposes an update to it rather than a duplicate. | ✅ D-053 — a revision baselines version N+1 of the same rule. The *finding* of candidates by anchor overlap is in place (`candidates_for`); having the interpretation pass populate `revises_rule_id` is CON-55 |
| CON-44 | Per-rule review decisions | A reviewer accepts rule changes individually or rejects the implementation as inconclusive, with comments. | ✅ D-053 — `rule accept` / `reject` / `history` |
| CON-30 | ~~Surface near-duplicate proposals~~ | — | ❌ **withdrawn.** The problem was an artefact of proposal-per-run; D-029's one-document-per-ticket model does not have it. |



### CON-78 — the current picture, and the grounding it unlocks

Found while testing CON-77 on a copy of the live workspace: a rule submitted for ticket 628 was
discarded as *ungrounded*, because 628 has landed and a landed ticket contributes no evidence
(D-031). Its paths are not in the window, so nothing can be anchored to them.

So once a ticket lands, no rule can be proposed for it at all. That is the same root cause as
CON-71 — **evidence is only ever a ticket delta** — and it is sharper than the 615 case that raised
it: there, one rule out of several went unproposed; here every rule for the ticket is refused.

Grounding against the state of mainline fixes both, which is why CON-78 should land before CON-71 is
answered. CON-71 may have no answer left to give.

### CON-75 — Constat's own merge commit is not evidence

Found by re-reading 628 after `merge_on_accept` landed its branch. The payload came back with two
commits — the real fix and `9eda7b44 Merge feat/628-first-launch-device-race for 628`, which
Constat wrote — so 14 changed files were reported for 7 real ones, and a commit Constat authored was
presented as the team's implementation evidence (product rule 3).

**Identify it by a trailer, not by its message.** The only signal today is `MERGE_SUBJECT`, and
matching on that is a heuristic over text anyone could write: a human merge worded the same way
would be silently dropped, and under-reporting evidence is worse than over-reporting it. Constat
authors the commit, so it can mark it exactly — `Constat-Landed: <reference>` — and match on the
trailer line.

**State the exclusion.** Removing a commit silently breaks the pattern the rest of the product
holds to: every repository is reported even when it contributed nothing, and a truncated diff says
what it omitted. One line is enough — "1 commit excluded: made by Constat when landing this
ticket."

**Left as a note rather than a ticket:** whether a merge commit should contribute evidence *at
all*. A human merging the same branch through a GitLab MR double-counts identically and carries no
trailer to filter on. Worth answering before the narrow fix is generalised; 628 is the test case.

### CON-76 — A landed ticket does not keep reading as pending

The other half of CON-69. The merge is made in a throwaway clone and pushed, so the registered
repository never learns of it: `237feed`'s local `main` sat 2 commits behind `origin/main`
immediately after landing 628.

This is **cumulative and self-inflicted**. One merge commit per landed ticket, and nothing in
Constat ever fetches, so the gap only grows. Before CON-69 Constat could not cause drift at all,
because it only ever read.

**It is not cosmetic.** D-031's statuses carry the meaning: `pending` is "merged, not landed",
`landed` is "already shipped". With mainline behind, a ticket that has shipped keeps reading
`pending` and its evidence keeps being gathered as unlanded work — which is what 628 does now. The
status misreports the one thing it exists to say.

**Three parts, and no `git pull` in any of them.** Pulling writes to a working tree that may hold
uncommitted work, sit on another branch, or be mid-rebase — the reason the merge happens in a clone
to begin with.

1. **Mainline is the remote-tracking ref.** `origin/<default-branch>` is what everyone else pulls;
   local `main` is one checkout's opinion. D-028 already resolves the default branch from
   `refs/remotes/origin/HEAD`.
2. **Refresh that ref after Constat's own push.** Constat knows it just pushed, so
   `git fetch origin <default-branch>` closes the gap it caused. Touches `.git` refs, never the
   working tree, and only in the repository it pushed for.
3. **Disclose the rest.** A repository someone else pushed to is stale and no write fixes that —
   only saying how old the picture is. CON-38 is the same disclosure for remote caches and should
   cover a local clone that has not fetched.

## Workspace model (D-027, D-028, D-029)

Added 2026-11-09 after a direction change. These replace the single-repository, one-shot shape the
first seven sessions assumed. The Git and evidence layers are unaffected.

| ID | Title | Done when | Status |
| --- | --- | --- | --- |
| CON-31 | Workspace storage | A SQLite workspace persists across runs; schema versioned. | ✅ |
| CON-32 | Repository registry | Repositories can be added, listed and removed; local paths and remote URLs both work. | ✅ local paths; remote URLs are CON-35 |
| CON-33 | Tickets and documents | A ticket can be opened and owns exactly one living document. | ✅ |
| CON-34 | Operations against the set | An operation gathers evidence for a ticket across every registered repository, measured against mainline, and expands the document. | ✅ |
| CON-35 | Remote clone-and-cache | A remote URL is cloned into a local cache and read like any local repository; fetch time is recorded. | ⬜ **next** |
| CON-36 | Default-branch resolution | Each repository's default branch is resolved and stored, never assumed to be `main`. | ✅ delivered with CON-32 |
| CON-37 | Merged-ticket semantics | A ticket whose work is already merged still produces a document rather than an empty one. | ✅ resolved by D-030; implementation lands with CON-34 |
| CON-38 | Cache staleness disclosure | Every document states when each repository's cache was last fetched. | ⬜ |

---

## Notes on specific tickets

### CON-41 — the interface was the easy part

Done. The `Protocol` and the null provider took an afternoon's worth of thought; the two
prohibitions around them are the ticket's actual content.

**Identity does not cross the boundary (D-040).** D-023 had deferred this and required it settled
before a provider existed. Settled the stronger way: the payload type has no field for an author,
so the guarantee is structural rather than a stripping step someone can forget. The non-obvious
half is free text — commit trailers are entirely a person, and a changed `AUTHORS` file puts
addresses in the diff itself. Messages lose the trailer line; diffs keep every line and mask the
address, because dropping a diff line would misstate the change.

**A misconfiguration is refused, never nulled (D-041).** Graceful degradation here means emitting
"no rules were identified" to someone who configured a provider. Exit code 5.

**Two honest limits.**

- On 8 real commits from Subject B, no masking was needed at all: identity was absent
  structurally, and the trailer and diff-masking paths were exercised only by fixtures. They rest
  on anticipating the case, not on having observed it.
- **Secret scanning is not solved.** Commit messages and diffs do leave the machine — that is the
  product — but a payload containing a leaked credential would be sent as readily as anything
  else. Raised as CON-45 rather than left implicit.

**The cost is now measurable, not estimated.** 8 commits in one repository produced a 186,636-char
payload — roughly 47,000 tokens, for one ticket in one repository. D-039 called the cost real; this
is the number. CON-42 should treat payload size as a design constraint rather than discover it on a
bill.

### CON-50 — four tools, and the fifth one must never exist

Done. `constat mcp` serves `gather_evidence`, `get_payload`, `submit_rules` and
`list_rule_proposals` on stdio (D-055). The `mcp` SDK is an optional extra, so a CLI user carries
no protocol library they never run and D-003's promise holds.

**The important test asserts an absence.** There is no `accept` tool, because a model that could
call one would make "no proposal becomes official without an explicit human decision"
unenforceable. The tool list is checked against the *live* server rather than the source, so a tool
added by a decorator anywhere shows up. Mutation-checked: adding an `accept_rule_proposal` tool
fails 3 tests.

**No tool reimplements an operation**, so the gates hold by construction — `get_payload` *is*
`export_payload`, which is why a credential refuses through MCP as readily as through the CLI.
Verified through a real client over stdio, not just in process.

**A wrapper that lost the reason.** Letting a `ConstatError` escape gets it wrapped as an
unexpected crash, and the client sees "Error executing tool get_payload" with the refusal gone.
`ToolError` — the SDK's "a failure you anticipated" — keeps the message, which for this product is
the part worth sending: "remove the credential and rotate it". Mutation-checked: letting it escape
fails 4 tests.

Two small things the SDK taught me rather than my memory: `mcp` 2.x renamed `FastMCP` to
`MCPServer`, and a client-side `CallToolResult` field is `is_error`, not `isError`. Both found by
running it, which is the argument for the end-to-end test existing at all.

### CON-55 — the missing input was the catalogue

Done. The payload now carries each rule's id, name, statement and anchors, so a reply can name
`revises: <rule_id>` — and that claim is checked exactly like an anchor: the rule must have been in
the payload (D-054). An invented claim is rejected for the same reason an invented anchor is.

**Overlap warns and never decides.** A reading claiming to be new is stored as new, with the
reviewer told what it overlaps. Accepting a second rule on the same file is often correct — one
file routinely implements several rules — so the warning informs the choice rather than preventing
it.

**An honest limit, asserted rather than left to be discovered.** Overlap is *identical glob
string*, not glob intersection: a rule anchored to `rules.py` and a reading anchored to `**/*.py`
overlap in reality and are not flagged. Widening it means comparing globs for intersection, which
has no exact answer in general.

**A test of mine had an `or` escape hatch** that could not fail, and replacing it is what surfaced
that limitation. Worth remembering: an assertion with an alternative branch is usually a sign the
expected behaviour was not actually understood.

**Mutation-checked:** ignoring the `revises` claim fails 8 tests; the payload dropping the
catalogue fails 4; auto-picking the overlapping candidate fails 3.

### CON-44 — the loop closes

Done, and most of CON-43 with it. `rule accept` baselines a frozen version that points back at the
reading accepted; `rule reject` records inconclusive and leaves the catalogue alone; `rule history`
shows the chain (D-053).

**A revision adds a version rather than duplicating the rule** — CON-43's done-when. It works
because `revises_rule_id` is a claim and accepting the reading accepts the claim (D-050), so
acceptance is the only place the claim takes effect. What is left of CON-43 is having the
interpretation pass *fill* that claim from anchor-overlap candidates: `candidates_for` exists, but
nothing calls it yet. That is CON-55.

**`--by` has no default**, which is the no-automatic-approvals prohibition expressed in the
argument parser rather than in a comment.

**Mutation-checked:** ignoring the revision claim fails 6 tests; rejecting that baselines a version
fails 2; removing `rule_version`'s append-only triggers fails 2.

**A guard the database made unreachable.** A claim to revise a nonexistent rule cannot even be
recorded — the foreign key refuses it. The acceptance-time guard stays anyway, and the test says
why: if the key were ever relaxed, the alternative is silently creating a new rule when the
reviewer accepted a revision.

**Verified on the real workspace:** migrated v5 → v6 with its 8 operations intact, then the stored
reading from Subject B was accepted into rule 1 version 1.

### CON-52 — the inbound half, and a false rejection caught by a test

Done. `rule submit` parses a reply, grounds every anchor against **re-gathered** evidence, stores
what survives and reports what it discarded; `rule proposals` shows the queue (D-052).

Re-gathering is the load-bearing part. If the payload came from the caller, a reply could ship a
payload that makes any anchor look grounded — the check would be verifying the reply against
itself.

**A false rejection, found by a test rather than in use.** `**/rules.py` is the most natural way to
write "this file anywhere", and plain `fnmatch` never matches it against a root-level file, so a
correct anchor was being discarded as ungrounded. Grounding and catalogue matching now share
`constat/globs.py` — two matchers that disagreed would accept a rule proposal at submit time and
then never match it to a change.

**Mutation-checked:** trusting a caller-supplied payload fails 13 tests; auto-accepting into the
catalogue fails 2; letting the two matchers diverge again fails 4.

**Verified end to end on Subject B:** a 195 KB payload exported, a reply submitted, the grounded
reading stored and the invented anchor discarded, with the catalogue still empty.

### CON-51 — the reading now outlives the prose that showed it

Done. A rule proposal is stored append-only with its run, its self-reported reader and its claim
about which rule it revises; a human's answer appends to a separate table so deciding never mutates
the reading (D-051). CON-53 landed with it: the authoring commands are gone and a trigger aborts
`DELETE ON rule`.

**The riskiest migration so far.** Dropping `rule.name`'s UNIQUE needs a table rebuild, and `rule`
is the parent of `behaviour` and `anchor` with `ON DELETE CASCADE` — so dropping the parent alone
would have silently emptied the catalogue. All three are rebuilt, children dropped first. Verified
on a real v4 workspace: migrated to 5 with its 8 operations and 1 run intact.

**Mutation-checked:** removing the append-only triggers fails 5 tests; `gather` not persisting what
the provider returned fails 3; a migration that forgets to copy `behaviour` rows fails 1.

**Half a change, stated as such.** `Catalogue` is still name-keyed — `add_rule` keeps its own
duplicate guard and `find` looks up by name — so two rules cannot yet share a name through the API
even though the schema now allows it. The guard is a leftover of the pre-D-050 model and goes when
the catalogue becomes id-keyed and versioned (CON-43). The test asserts the schema, not the API,
and says why.

### CON-54 — one run per invocation, not one per repository

Done. A gather writes one `operation` row per repository, so no operation row could answer "which
run produced this" — and a rule proposal is a reading of the evidence one run gathered (D-046), so
it needed something to point at. Schema 4 adds `run` and `operation.run_id` (D-049).

**Pre-migration rows keep `run_id` NULL.** Back-filling would fabricate provenance. Verified on a
real workspace built by the previous commit: it migrated to v4, kept its 7 pre-run operation rows
NULL, and a fresh gather opened run 1 with its operation attached.

**Mutation-checked:** opening a run per repository instead of per invocation fails 5 tests; a
migration that creates the table but forgets the column fails 4.

**A fixture of mine tripped a real guard.** Registering three repositories failed as a duplicate,
because `make_subject` seeds byte-identical history and identical content commits in the same
second produce the same root commit — so D-025's identity check refused the second. The test
helper now varies each root. The guard was right; the fixture was lazy.

### CON-49 — a gate with one door was decoration

Done. D-045 created a second front door and that door bypassed both D-040 and D-044, because the
credential gate was keyed on a provider being configured. `guard_release` is now the single
chokepoint, and `document --payload` is its first caller besides `gather` (D-047).

**The asymmetry is the decision.** `gather` with no provider scans, reports and continues; an
export refuses unconditionally. A local run that transmits nothing can tolerate a false positive;
an export cannot, because by the time it has printed it has left.

**The real-data check is the one that matters.** Subject A has credentials in the documented
window, and `document --payload` refuses with **zero bytes on stdout**. Before this, the export
would have handed them to a third-party model. Subject B exports cleanly: 8 commits, 33 files,
~195 KB, and no identity field on the commit type at all.

**Mutation-checked:** reverting the export to the provider-only gate fails 3 tests, including the
one asserting stdout stayed empty.

**CON-49 was going to be the submit path too.** It split, because submitting needs somewhere to
put a proposal and there is nowhere — see CON-51.

### CON-67 — title, details, and what "edited" means

Stated as an expectation: a rule has a **title** summarising what it is about, and **details** that
characterise it. Across iterations a detail may be added, removed, edited or left unchanged.

Most of this exists under different names. `Rule.statement` is the title — "one sentence a business
reader would recognise" — and `behaviours` are the details. `name` is a kebab-case identifier and
not a title; D-050 already settled that identity is the surrogate id, so `name` is a label. The
vocabulary should move to `title` and `details`, because the current words invite the wrong
reading: a *behaviour* sounds like something the system does, which is what made D-035 necessary.

The tracking half does not exist, but the data does. `rule_version_behaviour` freezes every
version's details already — nothing reads it, which is CON-61. CON-61 plus a diff gives added,
removed and unchanged for free.

**"Edited" is the part that needs a decision.** A detail is a string today, so if version 1 says
"Refuse above the limit" and version 2 says "Refuse above the daily limit", nothing can tell an
edit from a removal plus an addition. Reporting it as an edit would be a guess, and this project
does not guess (product rule 1). Two honest options:

- **Give a detail a surrogate id that survives across versions**, as D-050 did one level up for
  rules. A reading then says which detail it is revising, and the answer is recorded rather than
  inferred. Costs: the reply contract grows, and a model has to be shown the current details with
  their ids.
- **Report only added, removed and unchanged.** Truthful, cheaper, and an edit shows up as one of
  each — which a reader can see for themselves, side by side.

The second is the smaller honest answer and the first is the better one. Worth deciding
deliberately rather than by whichever is easier to implement.

### CON-64 — the MCP workflow cannot start from the agent — **closed, D-063**

Found by trying to use it: `gather_evidence` raises `no ticket '622'` unless someone has already
run `constat ticket add 622` at the command line. There is no tool that opens a ticket, so an
agent asked to "work out what ticket 622 changed" fails at the first step on a clean workspace.

The question to settle is whether opening a ticket is a governance act. It is not obviously one —
a ticket is a container for a document, it carries no authority, and `ticket add` already gathers
immediately, so letting `gather_evidence` open one adds no capability beyond what it already has.
Against: D-055's list is deliberately short, and every addition to it has to be argued rather than
assumed.

If it lands, the refusal it replaces must not simply vanish. A reference that matches nothing in
any repository should still be reported as `not_found` rather than silently creating an empty
ticket, or the agent will cheerfully open tickets for typos.

**Settled** (2026-11-14). Not a governance act, and the argument that carried it was narrower than
"a ticket carries no authority": **the tool list does not grow.** `EXPOSED_TOOLS` is the same four,
so this removes a precondition rather than adding a capability D-055 withheld.

The refusal survived as `ReferenceMatchedNothing`. One thing the ticket did not anticipate: a
repository that cannot be read reports `NOT_FOUND` *with an error set*, so "matched nothing
anywhere" and "nobody could look" are indistinguishable by status. Those are refused too, with the
unreadable repositories named and the message saying it is not a claim of absence.

Left undone deliberately: nothing records whether a person or an agent opened a ticket. That needs
a column on `ticket` and schema 10, and a ticket's origin is not a governance fact by the same
argument that closed this one.

### CON-62 / CON-63 — a second and third provider are small, and that is the test of the seam

CON-60 built one provider against the `Provider` protocol and D-003's registry. Each further one
should be a single module in `constat/ai/providers/`, an entry in `PROVIDERS` and `CREDENTIAL_ENV`,
an optional extra in `pyproject.toml`, and nothing else. If either of these needs a change outside
that list, the seam is wrong and the change belongs in the seam rather than in the provider.

Specifically, neither may touch: `parse` (the reply contract and anchor grounding), `redact` (what
crosses), `guard_release` (the credential gate), or `rule_proposal` storage. All four are shared,
and a provider that needed its own version of one would be routing around a governance property.

Two things to settle when the first of them lands:

- **Whether the reply contract survives contact with a second model.** `SYSTEM` asks for JSON and
  `parse` refuses anything else (D-046). A model that reliably wraps JSON in prose would make that
  a provider-specific problem, which is the argument for structured outputs noted in D-057.
- **What `model_attested` means for each** (D-057). It is true only where the response carries a
  resolved model id. A provider whose API does not return one must record `None` and stay
  unattested rather than echoing the requested name back as though it were established.

### CON-42 — the trust boundary first, the provider later

In progress. What landed is the half that needs no provider and is required either way: a parser
that turns a reply into proposals, refuses what it cannot use, and **checks every anchor against
the paths actually supplied** (D-046).

Anchor grounding is the part worth keeping. A model will propose a rule anchored to a
plausible-sounding path whether or not that path was in the payload, and storing it would mean the
tool invented its own evidence — the inverse of product rule 2. It costs nothing to check, so it
is checked. Verified on both real subjects (30 and 72 grounding paths): grounded replies kept,
invented anchors rejected, prose replies refused.

**Mutation-checked**, since everything passed first try: swallowing a bad reply as "no rules"
fails 14 tests, removing the grounding check fails 3, and never rendering rejections fails 2.

**What is left, and why it split.** D-045 changed the shape of the remainder: the agent surface is
an MCP server, not a provider Constat calls, so the next step is a **submit path** (CON-49) rather
than an HTTP client. The parser is provider-agnostic by construction — it takes `(text, payload)`
and does not care where the text came from — which is what makes that pivot cheap.

**Prerequisite that must not be forgotten:** redaction and credential refusal gate on
`provider.name != NULL_PROVIDER_NAME`. A submit or export command is a new front door, and the
same gate has to apply to it, or D-040 and D-044 become decorative.

### CON-45 — real evidence changed the implementation twice

Done. Known formats only, refusal at the point of transmission, overridable once and on the record
(D-044).

The design decision that paid off was **separating the scan from the refusal**. Scanning every run
means a false positive cannot block a local run that sends nothing, and the scanner is not dead
code until CON-42 — the mistake D-040 avoided by running redaction on the default path.

**Two rounds against real commits, each of which changed the code.**

1. A first pass flagged a `token`-named variable assigned an expression — ordinary source, not a
   credential. That produced the code-expression rule. One refusal of that kind is enough to teach
   someone to pass `--accept-scan-findings` without reading it, which would make the whole control
   decorative.
2. A wider pass over a different stack produced **true positives**. That is the feature justifying
   itself before it had a provider to protect.

A "bare identifier" rejection rule was tried in between and removed: a real credential and a
variable name are the same shape. Character-class variety does that work, with a stricter
threshold for unquoted values — quoting being the only signal that a value is a literal, and one
that cannot be required because a `.env` file has none.

**Per the repository owner's instruction, nothing identifying what was found is recorded here.**
Findings belong in a workspace document, not in a public backlog. The test fixtures use synthetic
lines and published documentation examples for the same reason.

**The miss list is the honest part.** A passphrase of one character class, a base64 credential
beginning with `+`, and anything without a recognisable shape all go undetected. `scan` returning
nothing is not a statement that the payload is clean, and the rendered section says so.

### CON-46 — found while checking a claim, not while looking for it

CON-41 claimed "no new dependency" and the check was to build a wheel and look inside it. The wheel
contains nine modules and **no subpackages at all** — `constat/git`, `constat/store`,
`constat/evidence` and `constat/ai` are all missing, because `pyproject.toml` says
`packages = ["constat"]` and setuptools takes that literally.

Nothing has noticed because the development install is editable and imports from the working tree.
A built wheel would fail on `import constat.cli`, at the first `from .store import …`.

Pre-existing since CON-04 added the first subpackage.

**Fixed (D-042).** The list became a `find` directive, so a subpackage added in a later ticket is
shipped without anyone remembering to extend a list.

**The test was harder than the fix, and twice gave a false pass.** Both failures are worth
remembering, because both made a broken wheel look fine:

1. **Stale `build/lib`.** setuptools stages into `build/` and never cleans it, so a module that
   landed there during an earlier build is included in every later wheel regardless of
   configuration. With the defect deliberately restored, an in-tree build still produced a
   *complete* wheel. The test now builds from a staged copy of the source.
2. **The editable install backfills missing modules.** It registers a meta path finder via a
   `.pth` file which claims `constat.*` from the working tree, ahead of `sys.path`. The import
   probe loaded `cli` from the wheel and `store` from the repository and passed against a wheel
   with no `store` in it at all. The probe now runs with `-S`, so `.pth` files are skipped and the
   unpacked wheel is the only `constat` available.

Mutation-checked: with the explicit list restored, five of the six tests fail.

### CON-37 — resolved by measurement, not by argument (D-030)

An integration-branch workflow was proposed as the answer. Checked against the real subjects it
did not hold: **every branch is zero commits ahead of mainline.** Subject A's `develop` is 0 ahead
and 1119 behind; its `feat/622-…` ticket branch is 0 ahead and 10 behind; Subject B has no
integration branch at all. Ticket 622's work is already in mainline, and the diff between
`merge-base(main, feat/622)` and the branch tip is **0 files**.

So branch divergence alone would have produced an empty document for a ticket whose work sits
plainly in history — and Constat would have been unable to document its own primary test data.

Resolved as D-030: mainline stays the reference point, but the target is a **commit set**
attributable to the ticket, resolved from a branch name encoding it, commit-message references, or
an explicit list. The branch-name signal (`feat/622-…`) is the better one where it exists:
unambiguous, and independent of commit-message discipline, which only ~5% of Subject A's commits
exercise.

### CON-34 — per-commit evidence, and the hazard it leaves

A ticket's commits need not be contiguous, so there is no single revision range meaning "this
ticket's effect". Diffing the first commit's parent against the last would attribute whatever else
landed between them to the ticket. Evidence is therefore collected **per commit** (D-033), at the
cost of duplicating a file touched more than once. A test builds the trap deliberately — ticket
work, an unrelated commit, more ticket work — and asserts the unrelated file never appears.

`ticket add` now fills the document itself. The earlier shape ran the same search, printed it and
threw it away, leaving `operation` empty and the document blank: two implementations of one idea,
one of which persisted nothing.

**The hazard this leaves is CON-39.** The body is regenerated on every run, which is safe only
while it is entirely machine-derived. The moment a reviewer can edit (CON-12), regeneration
destroys their work. That must be solved before review ships, not after.

> **Reframed by D-043.** The body is now machine-written *only* — a human comments, validates a
> rule or rejects an implementation, and never edits. So regeneration destroys no prose. What
> survives of this hazard is narrower and still real: a comment is anchored to something the next
> run rewrites. Anchors must be durable identities rather than positions in text. CON-39 keeps the
> number and gains that as its content.

### CON-33 — no ticket title, and the first migration

The title was dropped (D-032): unverified free text has no category in the provenance taxonomy,
and the nearest one — `human_decision` — means an approval, not a note. Anything descriptive must
come from evidence, and can be derived at display time rather than stored.

The useful side effect is the **first schema migration**. Version 2 drops the column and preserves
the rows, establishing that a version bump carries a migration rather than a refusal. A governance
tool that lost stored decisions whenever its schema changed would contradict product rule 5 on the
surface where it matters most.

Note for future migrations: `executescript()` implicitly commits, so it cannot be used inside a
transaction. Statements are listed individually. A test caught this with "cannot commit - no
transaction is active".

### CON-33 — the expected window, and the three answers

D-031 narrowed the search: a ticket's work is expected to be **merged onto an integration or
release branch but not yet in mainline**. That makes the search space `--all --not <mainline>` —
bounded, and exactly the set a reviewer cares about — without needing an integration branch to be
configured. Neither subject could have shared one name anyway: Subject A has `develop` plus seven
release branches, Subject B has release branches and no `develop`.

Three outcomes, deliberately not collapsed into "found / not found":

| Status | Meaning |
| --- | --- |
| `pending` | Commits ahead of mainline. The expected case. |
| `landed` | Already in mainline. Not nothing — a different answer. |
| `not_found` | The reference matched no commits. Also not "changed nothing". |

**The real subjects cannot exercise `pending`** — every branch in both is zero ahead of mainline —
so the fixture builds that shape deliberately. Running `ticket add 622` against Subject A
correctly reports `landed`, which is honest rather than convenient.

Branch-name attribution proved its worth: ticket 700's commit in the fixture never mentions 700,
only the branch does. And token-boundary matching found a genuine body reference on real data —
`(#622)` inside a commit whose subject says nothing about the ticket — while refusing `6220` and
`1622`.

### CON-32 — two refusals worth keeping

**The default branch is resolved from `refs/remotes/origin/HEAD` or not at all.** It never falls
back to HEAD's symref, because HEAD is whichever branch is checked out *right now*: registering
while on a feature branch would make that branch the permanent reference point for every
comparison (D-028), wrong in a way nobody would notice. A repository created with `git init` has
no `origin/HEAD` — this one does not — so `--default-branch` must be stated. Verified: both
subjects resolve to `main` automatically; this repository is refused.

**Duplicates are detected by identity, not path.** The same project cloned to two directories is
one repository (D-025), and path comparison would miss it. The error names the existing alias and
the shared root commit.

### CON-31 — immutability is enforced by the database

Append-only history is a database trigger, not an application convention. `document_version`
rejects `UPDATE` and `DELETE` outright, so a future bug cannot quietly rewrite an approval by
forgetting to call the right helper. Tests assert the triggers actually fire — a trigger that does
not is worse than none, because it looks like protection.

Also enforced in schema rather than code: one document per ticket (`UNIQUE` on `ticket_id`), only
`approved`/`rejected` as decisions, and foreign keys on — SQLite leaves those off by default, so
referential integrity has to be requested on every connection.

### CON-31 — why persistence moved

It was CON-13, in Phase 4. A registry (CON-32) and an accumulating document (CON-33) both need
storage to exist at all, so it became a prerequisite. The integrity rules in ARCHITECTURE.md
section 5 apply from here on rather than later.

### CON-04 — done, and the tag problem turned out not to be due here

**Corrected during implementation.** This ticket was expected to force the build-tag-versus-release-
tag problem from D-009. It did not, and the reason matters: **nothing in Constat selects a revision
for the user.** Every option is required with no default (D-016), so there is no code path that
could pick a build tag. The problem arrives only when something auto-selects — "latest tag",
"default branch", "since last release".

So the obligation at this stage was *negative*: do not add that convenience. The adapter module
says so explicitly, and Subject A's 777 build tags and Subject B's 11 semver tags both resolve
correctly because the caller names them.

The tag classification question moves to whichever ticket first wants to auto-select. It is not
abandoned, just not yet real.

**What was actually hard here:**

- **Annotated tags** (D-019). Resolution must go through `^{commit}`, and neither subject repository
  can catch a resolver that forgets to, because both use lightweight tags where the two SHAs
  coincide. The fixture adds an annotated tag specifically to cover this.
- **Ambiguous refs** (D-020). `--quiet` hides the only warning Git gives, so it must not be passed.
- **Subdirectory widening.** `--repo some/subdir` resolves to the enclosing repository. Accepted for
  convenience, but both paths are kept and the CLI states which repository was actually read —
  otherwise scope widens silently, which is how a confidently wrong report happens.
- `branch` is read from HEAD's symref and never inferred. A bare mirror has one too (verified), and
  `main` is never assumed to be the default branch (product rule 6).

### CON-06 — done; the budget had an ordering bug worth remembering

Bounding evidence turned out to be the easy half. The hard half was *who gets the budget*: spending
it first-come let a generated lockfile take 400 of 4000 lines and starve every file later in the
alphabet. Evidence selection depending on filename ordering is not a performance detail, it is a
correctness problem for a governance tool (D-024).

Also surfaced here and deferred deliberately:

- **Privacy.** Evidence carries author and committer email addresses. Harmless locally; a disclosure
  the moment an AI provider is wired up (D-003). Must be settled before, not after — see D-023.
- **Copy detection stays off.** `-M` rename detection only; `-C` is more expensive and more
  ambiguous. Stated rather than defaulted into.
- **One `git diff` per file** rather than splitting a combined diff on `diff --git` boundaries.
  Slower, but a filename containing that string cannot corrupt the split.

### CON-07 — done; identity was the real question

The models were straightforward. The decision that mattered was **generated versus derived
identity** (D-025), and it is not obvious until you ask what happens on a re-run: a derived
identity would make a fresh re-analysis collide with an approved baseline for the same range.
Append-only history (product rule 5) requires a new identity per run, and a separate
`selection_key` recovers the idempotent lookup that derivation was wanted for.

Repository identity is the **root commit**, not the path or the remote. This project changed both
its name and its forge within two days of starting, which is as good an argument as any.

**New ticket arising:** re-running `analyse` ten times produces ten proposals. Correct, but the
store will fill with near-duplicates — needs surfacing once CON-13 lands. See CON-30.

### CON-09 — must not collapse state and change

A snapshot asserts "this is how it behaves"; an analysis asserts "this is what moved" (D-016).
Sharing the evidence collector is fine; sharing the renderer would blur provenance.

**Corrected at CON-05.** This note used to say a snapshot is "a diff against the empty tree". It is
not, and that framing was the problem: the empty-tree diff labels every file `ADDED`, which is
change vocabulary answering a state question. State is now read with `ls-tree` and returns plain
paths with no `ChangeType` at all (D-022).

### CON-19 — the differentiator, demonstrated late

Cross-repository value is the actual product thesis but is only shown here, at ticket 19 of 20
(D-001). Treat it as a milestone rather than a trailing task. Uses Subjects A and B, whose
incompatible version schemes force product rule 6 to be honoured properly.

### CON-29 — a third selector shape, and the cross-repo mechanism

Initialise a proposal from a reference appearing in commit messages, rather than from a revision
range. This is a genuinely different shape from the other two selectors:

| Selector | Question | Unit |
| --- | --- | --- |
| `analyse --base --target` | What changed between two revisions? | closed range |
| `snapshot --rev` | What does this revision do now? | state |
| `document <ref>` | What changed for this piece of work? | **commit set** — possibly non-contiguous, possibly spanning repositories |

**Why this matters more than it appears.** An explicit reference in a commit message is
*human-authored evidence of grouping*. That answers the risk recorded in PRODUCT_SPEC.md section 9
— "multi-repo linking is ambiguous → require explicit links or evidence" — with actual evidence
rather than inference from timestamps or filenames. It is the mechanism CON-19 was otherwise
missing.

It also probably settles Q1 / CON-24: the proposal unit is `(repository, selection)` where a
selection is a range, a state, or a commit set.

**The command is `document`, not `review`** (D-018). `review` is reserved for the human approval
step (CON-12); two meanings of *review* in one CLI is precisely the conflation this product cannot
afford.

**Measured on Subject A, 2026-11-08, across all 1130 commits:**

| Pattern | Count |
| --- | --- |
| `ADR-NNNN` | 21 |
| `plans/NNNN` | 13 |
| bare `#N` | 12 |
| JIRA-style `ABC-1` | 8 |
| `repo#issue` (cross-repo) | 3 |

Roughly **5% of commits carry any reference**, in four coexisting schemes. Two hard consequences:

1. **The pattern must be configurable.** Hardcoding `CON-NN` would make the feature work only on
   repositories that adopted our own convention, and fail on the primary test subject.
2. **It cannot be the primary entry point.** For comparison, 94 commits touch tracked migrations —
   the business-rule spine from D-010 (two signals since D-034). Reference density is far below
   evidence density, so this is
   a precision tool for well-tracked work, not a replacement for range selection. A report built
   from it must say what fraction of the range it accounts for, or it will quietly under-report.

The three `repo#issue` references are real cross-repository links already present in history,
which gives CON-19 genuine evidence to work from rather than a simulated link.

### CON-26 — the one most likely to slip

The roadmap is explicit: *"Do not wait until the software is finished to discover whether anyone
needs it."* Every other ticket here is more comfortable to work on than this one. That is the
reason it has a ticket.
