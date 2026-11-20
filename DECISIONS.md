# Decision log

Append-only. Newest first. Never rewrite a decision — supersede it with a new entry that references
the old one.

Format: `## D-NNN · YYYY-MM-DD · Title` → **Decision**, **Context**, **Consequences**, and
**Status** (`accepted` / `superseded by D-NNN`).

---

## D-098 · 2026-11-20 · An area can be documented over MCP, and the prompt names the areas that exist

**Closes CON-101.** The tool D-080 left unbuilt, plus a gap that only became visible once it
existed.

**Decision.** `baseline_area_tool(area, reply, reference=None)` is the fifth MCP tool, and the
`baseline` prompt is the third prompt.

**The tool is a wrapper and nothing more.** The scope refusal, the mainline grounding, the revision
pointers and the append-only storage are all `operations.baseline_area`, unchanged — which is what
ARCHITECTURE § 2 requires of every tool here. The only thing added is a door.

D-080 chose the agent-driven shape for a baseline *because* an agent already has the repository and
can read it directly, and then left the only door at the command line. The reasoning and the surface
disagreed; this is the surface catching up, not a new capability.

`reference` defaults to `baseline-<area>`, so documenting an area in a fresh workspace needs nothing
from a person first, and the result reports `opened_reference` — because an invented reference turns
up in `ticket list`, and a reference appearing there unannounced reads as work somebody forgot
about.

**The prompt names the areas that already exist, and that is the part worth recording.**
`baseline_area` builds a payload carrying the whole catalogue, but uses it only to ground anchors and
spot duplicates — it never returns it. So an agent documenting an area could not see which areas
existed, and D-079's defence against "ads" arriving beside "advertising" depends on exactly that
sight. The ticket path gets it from `get_payload`; this path had nothing. The question that found it
was asked out loud: *will this baseline be incremental and depend on the areas in context?* Yes to
the first, no to the second, which is why the second is now fixed.

**Pending areas are named alongside declared ones**, because an area is declared by acceptance
(D-079). Listing only declared areas would tell two baselines run back to back that there are none,
and the second would coin the synonym the first had already avoided.

**What the tool does not do.** It does not declare the area. A proposal that coins one reports it in
`new_areas` and the catalogue still has no such area until somebody accepts a rule in it — otherwise
an agent could populate the structure coverage is measured against with no decision behind it. A
test asserts the catalogue is still empty after a baseline is stored.

**Consequences.** `EXPOSED_TOOLS` is five and `EXPOSED_PROMPTS` is three; both are asserted against
the live server, and `FORBIDDEN_TOOLS` is still absent from both. The count is not the policy — the
absence is. Each prompt takes exactly one argument, and `baseline` takes an *area* rather than a
reference, because a baseline has no ticket; the test that asserted "every prompt takes a reference"
was narrowed to "exactly one argument, and it is the one thing the user already knows".

Five mutations were run and each was killed by one intended test: dropping the declared-area
sentence, folding out-of-area readings into `discarded`, hard-coding `opened_reference` to true,
dropping pending areas, and failing to exclude a declared area from the pending list.

**Status.** accepted

---

## D-097 · 2026-11-20 · The demo is a script, the limits are a document, and the demo found two defects

**Closes CON-20**, the roadmap's last ticket: "a new person can run the demo and understand what
Constat does and does not do." Two halves, and D-088 raised both to near the point of the project —
a demonstration of practice that nobody else can run is a claim about rigour rather than a
demonstration of it.

**Decision.** `demo.sh` at the repository root, and `LIMITS.md` beside the README.

**The demo needs no API key and no network.** It builds a throwaway repository in a temporary
directory, points `CONSTAT_HOME` at it so a reader's own workspace is untouched, and runs the whole
loop: gather, export the payload, submit a reading by hand, decide, verify the message, show the
product before and after the work lands, take a checkpoint, revise, diff the versions, and then
**fail twice on purpose** — an ungrounded anchor and a statement that leaks code, each refused with
its reason named. A demo that needed a key would be a demo of somebody's billing relationship, and
the evidence pipeline runs with no provider by design (D-003).

**Verified from a built wheel into a clean virtual environment**, not from the development install.
CON-46 already asserts a wheel imports; this is the first time the whole loop has run from one.

**The demo found two defects in its first two runs**, which is the argument for it:

1. **Coverage conflated two situations.** An area whose only rules were agreed-but-unshipped read as
   *"Declared and undocumented: payments. An area with no rule is an intention, not
   documentation"* — said about an area that had a rule. Fixed: a third sentence names "declared,
   with every rule agreed and not yet shipped", because the work existing and not having landed is
   neither documented nor undocumented.
2. A smaller wording slip in the same section, found reading the output end to end.

Neither was reachable from a unit test, because neither is wrong in isolation — they are wrong in
sequence, which only a document read from top to bottom shows. That is now the third time in four
days that running the product found what the suite did not (D-091, D-096).

**`LIMITS.md` assembles what fourteen decision entries each say once.** Nine sections: it will not
decide, it will not write to your code, it assumes trunk-based development, what it cannot check,
what is declared and unused, what a business reader cannot do, what is deferred, **what has not been
verified**, and what the project is. Every row cites the decision that made it, so a reader who
disagrees has something to argue with rather than a tone to object to.

The section that matters most is § 8. It states in one place that the name is legally unverified
(D-086), that **zero discovery conversations have been held** while every judgement about what a
business reader needs was made without one (D-088), that the provider transport has never been
billed (D-057), and that an authenticated push has never been tried (D-062).

**Consequences.**

- **`README.md` indexes both** and offers `./demo.sh` beside the tests, describing the refusals as
  the product working rather than failing.
- **`USAGE.md` § 10 points at `LIMITS.md`** rather than duplicating it, so the short version and the
  full account cannot drift.
- **The MVP's definition of done is now met in full.** All seven acceptance criteria in
  `PRODUCT_SPEC` § 6.3 are satisfied, the last of them — provenance — at D-094 this morning.

**Status.** accepted

---

## D-096 · 2026-11-20 · The review queue is readable across the workspace, and found a forgotten decision

**Closes CON-98.** Every other query in `RuleProposals` was scoped to a ticket, so *"what is
waiting?"* required already knowing which tickets to name — which is how a review queue stops being
a queue.

**Decision.** `constat rule proposals` with no reference lists every reading in the workspace,
grouped by state and then by ticket, one line each. With a reference it keeps the detailed per-ticket
view unchanged. `--state` narrows to one of `awaiting`, `accepted`, `rejected`.

**No schema change.** The states have been stored since CON-51 and rendered per ticket since CON-52.
The data was there; the question could not be asked. Worth recording because the gap was not a
missing feature so much as a missing *read* — and three sessions of building sat on top of it.

**It found a forgotten decision on the first run.** Against the live workspace:

```
awaiting (5):
  628
    [6] a-first-launch-works — (unplaced)
  baseline-app-install
    [9] … [10] … [11] … [12] …
```

Proposal **6 has been awaiting a decision since 2026-11-15** and had been lost track of entirely —
`PROJECT_STATUS` last mentioned it on the day it was made. Nothing in the product could have
surfaced it, because asking required naming ticket 628, and nothing pointed at 628 any more. That is
the ticket earning itself in one command.

**Compact on purpose.** One line per reading, with the area and whether it came from a baseline
(CON-89) — enough to choose what to look at, and no more. The per-ticket view answers *what does
this say* with statements, examples and messages; this one answers *what is waiting*, and a page of
detail per proposal would bury the only number a reader came for.

**Awaiting is listed first and named as the only actionable state**, with `rule accept` and
`rule reject` as the only door to either (D-048). A queue that presented all three states as
equivalent would invite a reader to think a rejection needed action.

**A mistyped filter shows nothing, not everything.** Mutation-checked: falling back to the full set
when a state matches nothing fails the test written for it. Silently widening reads as an answer,
which is the failure product rule 1 exists to prevent at every scale.

**Consequences.**

- **`StoredRuleProposal.reference` is populated by every query**, not just the new one, so a caller
  never has to know which query filled it in. Three queries gained a ticket join.
- **The per-ticket view is untouched**, and a test asserts the detailed output still appears for a
  reference. The two views answer different questions and neither replaces the other.
- **Five proposals in the live workspace are awaiting a decision**, four of them from the 2026-11-19
  baseline and one from 2026-11-15.

**Status.** accepted

---

## D-095 · 2026-11-20 · Publication refuses disclosure, on that door only, and not commercial data

**Closes CON-95**, the last hole in egress. D-044 and D-047 gate credentials on every path out and
D-040 keeps identity from crossing at all — but a published page could still carry an internal
hostname, a connection string, or a sentence describing how to defeat a check.

**Decision.** `guard_publication` now refuses four classes beyond a credential: an **internal
hostname**, an **IP address**, a **connection string**, and **wording that describes a weakness**.
Same posture as the credential gate — refuse by default, override recorded as an operation, nothing
published on a refusal.

**On publication only, and this asymmetry is the decision.** The credential gate fires on every
egress because a credential is a credential wherever it goes. These are not: a provider payload is
**evidence read from the code**, and code legitimately contains hostnames, connection strings and
the word "bypass". Refusing to export a diff because the code mentions a hostname would make the
product unusable. A page is the one egress that cannot be recalled (D-058) and the one a whole
organisation reads. Mutation-checked: applying the gate to export fails two tests written for
exactly that.

**Commercial data is not covered, and that is a decision rather than an oversight.** CON-95 asked
for it. There is no generic detector, and the proof is cheap: a plausible currency-figure pattern was
written as a mutation and immediately refused

> "A transfer above 500 euros is refused."

— this project's own canonical example of a business rule, from `ai/statements.py`. A commercial
detector would refuse the sentences the catalogue exists to hold. Named customers are equally
undetectable without a customer list Constat does not have. So the gate does not cover it, and
**says so in its own output on both paths**: in the refusal message, and in the clean-pass line
after a successful publish. A silent pass would be read as proof, which is the posture D-044 set for
the credential scan's own blind spots.

**`1.2.3.4` is reported and the ambiguity is honest.** It is a valid address and a plausible version,
and nothing in the text decides which. This gate reports rather than decides, and the override
exists for exactly this case. `1.2.3` and `1.2.3.4.5` are not addresses and do not fire.

**A false negative found by a test on first writing.** The guard against version numbers was
`(?![\d.])`, which rejected `10.0.0.14.` — an address at the end of a sentence, the most likely form
in prose. It is now "not followed by another number", which keeps `1.2.3.4.5` out and lets the full
stop through.

**Consequences.**

- **`DISCLOSURE` is separate from `DETECTORS`**, because the two have different reaches and keeping
  them in one list would make the publication-only scope a comment rather than a structure.
- **`DocumentFinding` is shared** with the credential scan: the reader's question is the same —
  which line, what kind of thing — and two shapes for one answer is how two reports come to
  disagree.
- **The clean pass now says what was scanned and what was not.** Previously it said nothing at all,
  which is worse than a stated limit.
- **Product rule 7 is unchanged.** This adds a refusal; it opens nothing.

**Status.** accepted

---

## D-094 · 2026-11-20 · Provenance is labelled per part, and the three types nothing writes are named

**Closes CON-10**, the last MVP acceptance criterion with a real gap (§ 6.3 #3), and the useful half
of it turned out to be the opposite of what the ticket implied.

**Decision.** Three things:

1. **Every document carries a provenance legend**, generated from the taxonomy so it cannot drift
   from it, and placed last because it is reference rather than content.
2. **A rule's parts are labelled separately.** The statement, behaviours and examples are a reading;
   the anchors are `observed_fact` — paths somebody can look at; a message is a **quotation whose
   truth is checkable and has not been checked here** (CON-91 does that, on demand).
3. **`unknown` gets its first producer.** An unreadable repository is tagged, because "could not be
   read" and "contributed nothing" are different claims and only the second is a finding.

**Three of the seven types have no producer, and saying so is the ticket's real content.**
`ProvenanceType`'s docstring promised the opposite — "the rest exist so CON-10 extends the taxonomy
rather than inventing it" — which read as a commitment to populate all seven. It should not be kept:

| Type | Why nothing writes it |
| --- | --- |
| `test_evidence` | Nothing runs tests and no test result is read. No ticket owns this. |
| `requirement_ref` | Nothing is ingested; supplied traceability is CON-18. |
| `assumption` | Every inference is either a reading or an admission. Nothing between them has needed a third word. |

`assumption` is the interesting one. "Stated inference not backed by evidence" sounds like a real
category until you look for an instance: a rule proposal is `ai_interpretation`, an anchor resting
on mainline is still observed, a decider's name taken from git config is recorded as `inferred`
within its own field (D-061), and everything Constat cannot determine is `unknown`. The gap is not
an oversight to fill but a distinction the design does not make.

**They are kept rather than removed.** The taxonomy is the product's stated vocabulary, and a reader
should find the gap rather than a tidied enum that hides it. `PRODUCT_SPEC` § 7.1 gains a *Produced?*
column saying the same thing, and the document's legend lists all seven with the reason for each
absence — so the absence cannot be mistaken for having been checked.

**Consequences.**

- **The legend is generated, and a test asserts it covers every member** of `ProvenanceType`. A type
  added with no entry in either dictionary fails that test, which is the only thing keeping the
  legend true. Mutation-checked by deleting an entry: three tests fail.
- **The legend is unconditional**, including on an evidence-only document — the one most likely to
  be read as plain fact, and therefore the one that needs it most.
- **A message is never presented as verified by a document.** Its provenance line says what would
  check it. That is the difference between a quotation and a verified quotation, and conflating them
  would be the failure D-082 took care to avoid.
- **Acceptance criterion 3 is marked met** in `PRODUCT_SPEC` § 6.3, with what met it.
- **No schema change.** Provenance on stored records is unchanged; what changed is what the document
  says about which kind of claim each line is.

**Status.** accepted

---

## D-093 · 2026-11-20 · Cache age is stated everywhere and judged nowhere

**Closes CON-38.** D-027 put this beside bounded excerpts deliberately: **unstated staleness is the
same class of failure as unstated truncation.** It was impossible until CON-35, because there was no
cache to be stale.

**Decision.** Every repository in a document, and in `constat state`, says how current Constat's
copy of it is. A cached remote names the fetch time and its age in words; a local path says it is
read in place. **No threshold is applied and no verdict is given.**

**Why no threshold.** "Older than a week is stale" is a judgement about somebody's release cadence,
not a fact about their repository. CON-76 set the posture for mainline drift — report the count,
leave the conclusion to a person — and this is the same question one layer out. A test asserts that
a cache fetched **400 days ago** is reported as "400 days ago" and that the words *stale*, *out of
date*, *too old* and *warning* appear nowhere in the sentence. Mutation-checked by adding a verdict.

**Coarse on purpose.** "3 days ago", not a duration to the second. The reader's question is whether
it is old enough to matter, and false precision invites a confidence the number does not carry. A
future timestamp — two machines with skewed clocks — reads as "just now" rather than as a negative
age.

**Three states, not two.** Fetched at a known time; read in place with no cache; and **fetched at a
time nobody recorded**, which is reported as "how old this is cannot be said" rather than defaulting
to current. An unknown age is not a recent one, which is D-031's posture for exactly this ambiguity.
That third case cannot arise today — no path writes a cache without a fetch time — and is handled
because the column is nullable and a future path might.

**A local path says so too**, which costs one clause and stops the absence of a fetch time reading
as a missing field. In `constat state` the opposite choice was made: a local repository gets no line
at all there, because a per-repository list of "nothing to disclose" is noise rather than honesty.

**Consequences.**

- **The sentence sits beside "Measured against …"**, because both answer the same question — how far
  to trust this — one by naming the ref and the other by saying how old the copy of it is.
- **`RepositoryState.fetched_at`** carries it into the product state, which needs it most: that
  view's entire claim is to be of the revisions it names, and a picture assembled from a week-old
  cache is a picture of last week.
- **Nothing is auto-refreshed**, and the sentence says so with the command that would. Fetching on
  render would make a read command write, and make two runs of the same command describe two
  different products.
- **The payload is unchanged.** Cache age is context for a human deciding how much to trust a
  document, not for a model reading evidence.

**Status.** accepted

---

## D-092 · 2026-11-20 · A remote is cloned into the workspace, with no checkout and no credentials

**Closes CON-35**, which `PRODUCT_SPEC` § 6 has promised since 2026-11-08: "a remote is registered
by URL and cloned into a local cache; everything is then read with the same read-only Git layer."
The schema has carried `source_kind`, `cache_path` and `last_fetched_at` since CON-32 and never
populated one of them.

**Decision.** `repo add` accepts a remote URL and clones it into
`<workspace>/cache/<alias>`. `source` stays the URL — the record of where the repository came
from — and `cache_path` is where it lives. Everything downstream opens
`RegisteredRepository.local_path`, never `source`. `repo fetch` refreshes a cache and records when;
`repo remove` deletes it.

**Inside the workspace, not beside it.** One `rm -r ~/.constat` then removes everything Constat owns
and nothing it does not. A cache in a separate location would outlive the workspace that knows about
it, leaving clones nobody can account for.

**`--no-checkout`, and not `--mirror`, which was the first attempt and broke fourteen tests.** A
mirror looks obviously right: every ref, no working tree, smallest cache. But a mirror puts the
remote's branches straight into `refs/heads/*` and has **no remote-tracking namespace at all**, so
`refs/remotes/origin/HEAD` does not exist — and D-028 resolves the default branch from exactly that
ref, while D-068 resolves mainline from `origin/<branch>`. Constat's entire read-only layer is built
on that namespace. `--no-checkout` keeps it and still materialises no files, so the cache behaves
*exactly* like a local clone, which is what § 6 promised.

**This does not widen the subject-repository guarantee.** ARCHITECTURE § 6 says Constat is read-only
against every repository it reads, with one opt-in exception for publishing (D-058) and one for
`merge_on_accept` (D-062). A cache clone writes **nothing to the remote**: it is a read whose result
was kept. `constat/git/cache.py` is a third writer in `git/` and its reach is Constat's own
directory — three writers, three reaches, one file each, so the reach is legible from the layout.

**A remote is recognised by form, never by elimination.** `https://`, `git://`, `ssh://`, `file://`
and the scp-like `git@host:path`. Anything else is treated as a path, so **a mistyped path fails as
a missing path** rather than being cloned from. Mutation-checked: "anything that is not a directory
is a remote" fails three tests.

**Identity is only knowable after the clone**, because it is the root commit (D-025) — two different
URLs can be one repository, and the same URL can be typed two ways. So a duplicate is detected late
and **the clone is then discarded**. A refusal that left a directory behind would make the next
attempt fail on `clone`'s own exists-check for a reason the user never caused. Also
mutation-checked.

**No credentials, ever.** The clone uses git's own helpers, as `merge.py` does for its push. A URL
needing authentication Constat cannot supply fails as a clone failure with git's own message, and
nothing is remembered.

**Consequences.**

- **`RegisteredRepository.local_path` exists and must be used.** Six call sites in `operations.py`
  read `source` directly before this; one property is why that cannot drift back.
- **CON-38 is unblocked** — "every document states when each repository's cache was last fetched"
  was impossible with no cache. `last_fetched_at` is now populated and rendered by `repo list`,
  though not yet in the document.
- **A fetch moves the remote-tracking refs and not the cache's local branches**, which is correct:
  mainline is `origin/<branch>` (D-068), so the local branch is not the picture. The first test
  asserted the wrong ref and was corrected.
- **No automatic refresh.** Nothing fetches on its own, so a cache is as old as its last `repo
  fetch` — stated in the command's own output and the reason CON-38 matters.

**Status.** accepted

---

## D-091 · 2026-11-19 · A semicolon is punctuation; the leakage gate had come to refuse a live rule

**Narrows D-066**, found on the **first real use** of the baseline path against a real repository.

**Decision.** The semicolon is removed from `code_leakage`'s inline-code character class. Everything
else in that class — a backtick, a brace, an angle bracket, `::` — stays.

**How it was found, and why the evidence is decisive.** Documenting the install and landing pages of
a real product, a rule was discarded because one example read *"They are not there; the note under
the download buttons says they are in the app"*. The gate called a semicolon inline code. Checking
the live catalogue then produced the finding that settles it: **the accepted rule R-2 contains a
semicolon** —

> Losing an analytics beacon is acceptable; failing a request a user is waiting on is not.

— so the gate had come to refuse a rule a human had already agreed to. A gate that would reject what
the catalogue already holds is not protecting the catalogue.

**This is the failure the module's own docstring warned about.** `ai/statements.py` says it is
"deliberately forgiving in one direction... a false refusal is worse than a miss: it discards a
reading a person might have accepted, and the reader is given no way to argue". The semicolon was
the counter-example to its own stated posture, and it survived CON-74's twenty-nine tests because
every one of them was written by the same person who wrote the pattern.

**What this says about the method, which matters more than the fix.** Twenty-nine tests, a mutation
check, and a docstring stating the exact risk did not catch it; **one use against a real repository
did, in under a minute.** That is the argument for D-088's mitigation in its strongest form: a
demonstration of practice is kept honest by running on something real, not by more tests of the same
shape.

**Consequences.**

- **Raised and closed as CON-100**, with the rule it discarded re-submitted successfully afterwards.
- **Tests added both ways**: three real sentences with semicolons pass, and four other inline-code
  signals still fire — removing one character from a class must not empty it.
- **D-066 is not superseded.** Its decision — that leakage is refused mechanically and business-ness
  is the guidance's job — stands exactly as written. One pattern was wrong.
- **The other characters are left alone deliberately.** A brace or an angle bracket in business prose
  is rare, and messages are already exempt from the gate entirely (D-082), which is where
  placeholders legitimately live.

**Status.** accepted

---

## D-090 · 2026-11-19 · Parallel release lines are intended, so product rule 6 is staged not abandoned

**Amends D-076's framing, not its content.** D-076 named trunk-based development as the assumption
and recorded product rule 6 — "release streams are distinct" — as an invariant the product intends
and the code does not hold, adding that parallel production lines "wait for a pilot that asks for
it". Asked directly on 2026-11-19, the author's answer is that an environment with long-lived
release lines **is** one Constat must eventually serve.

**Decision.** Supporting parallel release lines is **intended work**, not a deferred maybe. D-076's
limit stands as today's truth and is still what `README.md` states; what changes is that it is
staged rather than permanent, and the shape of the store must stop being built further in the
direction that forecloses it.

**What it costs, named now so it is not discovered later.** A rule version would have to be in
effect on one line and not another, which the single `rule` / `rule_version` shape cannot express —
`rule` holds one current state per rule, and every renderer assumes it. Three things already lean on
one trunk per repository:

- **D-028 / D-068** — mainline is *the* default branch's remote-tracking ref, singular.
- **D-087** — shipping is verified by asking whether a commit is an ancestor of *that* ref. On two
  supported lines the honest answer becomes "in effect on 1.x, not on 2.x", which the current
  three-way answer cannot carry.
- **D-085** — a checkpoint records one version per rule, so "the agreed state" is implicitly the
  agreed state of one line.

**Consequences.** Raised as **CON-99** rather than started: it is a schema and rendering change
across the governance store, and it should follow the real use D-088 makes the next step, not
precede it. Product rule 6's note in `PRODUCT_SPEC.md` is corrected from "waits for a pilot that
asks for it" to intended. D-076 is **not** superseded — its description of what the code does today
remains accurate, and the README's stated limit stays until CON-99 lands.

**Status.** accepted

---

## D-089 · 2026-11-19 · Approval outside the command line is intended; D-055 will be amended by CON-58

**Records an intent that reverses a standing invariant**, so that CON-58 is designed for it rather
than around it.

**Decision.** An approval taken **outside the CLI** — on a published page, in a tracker — is
intended to count as a human decision. Asked directly on 2026-11-19, the author's answer is that
off-CLI approval should be possible.

**What this does and does not change now.** It changes nothing in the code today: D-048 and D-055
stand, there is still no `accept` tool on any MCP surface, and a test still asserts the live tool
list. What it changes is CON-58's design target. The amendment to D-055 **lands with the
implementation**, not here — writing an invariant out of force before the mechanism exists would
leave a window in which the record permits something nothing enforces.

**The distinction D-055 was protecting, which survives.** The objection was never the *channel*; it
was that **a model must not be able to accept**. An approval ticked by a person on a page is a human
decision that happened somewhere else; a tool call by an agent is not, whatever it is named. CON-58's
`channel` and `verification` exist to keep those apart — and a page approval is arguably *more*
verified than a CLI `--by` string, which nothing checks (D-061).

**Consequences.** CON-58 stays open and widened, now with a stated target rather than an open
question. `DISCOVERY.md` § 4 assumption 6 is answered by intent rather than by evidence, and is
worth asking about anyway: knowing where approval *should* live does not tell us where the people
who would do it actually work.

**Status.** accepted

---

## D-088 · 2026-11-19 · Constat is a demonstration of practice; the validation track is not the plan

**The most consequential decision in the log, and it reframes a week of work.** Asked directly on
2026-11-19 what Constat is for, the answer is **a demonstration of how its author works**: the
decision log, the test discipline, the mutation checks and the written reasoning are the artefact,
and the software is the medium.

**Decision.** Constat is built as a demonstration of practice, not as a product being taken to
market. `PRODUCT_SPEC.md` § 10's validation track — discovery conversations, a design partner, two
pilot commitments — is **no longer the governing plan**, and § 8's success signals (willingness to
pay, cross-repo value proven with a real feature) are not the measure.

**What I got wrong all week, stated plainly.** Every status report since 2026-11-17 ended by naming
CON-26 as the critical path and the only thing that mattered. That was the spec's framing applied
without checking whether it was still the author's, and the evidence was visible the whole time:
eighteen tickets closed and zero conversations held is not a team failing to validate, it is a
project whose purpose was something else. The right move was to ask on day one. `DISCOVERY.md`
(2026-11-19) was written in the same mistaken frame — it stands as a usable artefact and is no
longer an overdue task.

**What the measure becomes.** Whether a reader of this repository can follow *why* each thing is the
way it is, and whether what is claimed is true. That makes several things first-class that were
treated as overhead: the decision log's completeness, a refusal that explains itself, a test that
pins a property rather than asserting the code, and the honesty of what is recorded as unverified
(D-076's unmet invariant, D-086's unverified name, D-087's uncheckable rules).

**The failure mode this creates, and the mitigation.** A demonstration can drift into unfalsifiable
self-regard — prose about rigour, with nothing checking the rigour. The mitigation is the second
answer given on the same day: **Constat must actually run on a real repository.** A worked area of
a real product, documented with the machinery as it stands, is what keeps the demonstration
honest, and it is the next step rather than another feature.

**Consequences.**

- **CON-26, CON-27 and CON-28 are deferred, not withdrawn.** They are the validation track of a
  product being sold. They stay in the register, reframed, because the purpose could change again
  and because `DISCOVERY.md` is already written.
- **CON-20 rises.** "A new person can run the demo and understand what Constat does and does not do"
  is now close to the point of the whole thing, rather than a packaging chore.
- **Features are worth less than they were; legibility is worth more.** A ticket that adds a
  capability nobody will exercise is weaker than one that makes an existing claim checkable.
- **D-086 reads better in hindsight.** Dropping the trademark work was already right; under a
  demonstration it is not even a risk being accepted so much as a cost that was never owed.
- **This does not relax any product rule.** A demonstration of practice that quietly lowered its own
  standards would demonstrate the opposite of what is intended.

**Status.** accepted

---

## D-087 · 2026-11-19 · Unshipped work is a state in the view, verified against mainline

**Closes CON-96**, and closes it **without the release concept CON-85 and CON-86 were to supply.**

**Decision.** `constat state` renders a rule as current behaviour only when the commits it was
accepted on are **ancestors of the repository's mainline**. A rule whose evidence is present and not
an ancestor renders in its own section, *Agreed, not yet shipped*. A rule whose shipping cannot be
checked stays in the picture and is flagged.

**The fix is a state in the view, not a gate on the decision.** `rule accept` still has no
pending/landed guard and deliberately gets none: refusing the acceptance would stop a reviewer
deciding about work they can see, which is the normal case and the one the product is for. What was
wrong was *presenting* the result as shipped.

**Verified, not asserted — which is why this did not need releases.** CON-96 was written as
depending on CON-85/86's two-state model, where closing a declared release would put versions into
effect. D-085 already recorded the weakness of that: the ship is **asserted** by a human and
Constat cannot detect a partial ship across a plural registered set. Checking whether the evidence
commits are ancestors of mainline is a *stronger* claim, needs no schema, and needs no human to
remember to close anything. The release concept remains worth having for naming and grouping; it is
no longer what makes the current picture honest.

**Three answers, not two.** `contains_commit` returns `yes`, `no`, or `unknown`, and the third is
load-bearing: a squash-merge or force-push destroys the commit a rule points at — D-073 keeps the
subject beside the SHA for exactly this reason — and a missing object must not be read as "not
shipped". The rule may well have shipped; what is lost is the ability to check. Only exit codes 0
and 1 from `merge-base --is-ancestor` are answers, and the 128 band maps to `unknown`.

**Uncheckable rules stay in the picture and are flagged**, never moved out of it. Moving them would
assert they are *not* current behaviour, which is exactly as unsupported as the claim being fixed.
There are three causes and none of them is "not shipped": no evidence pointer at all, a pointer to a
vanished commit, or no readable repository for the alias.

**A limit this exposed, and it follows from D-031.** A rule accepted **after** its ticket landed can
never be verified: a landed ticket contributes no evidence, so no pointer is recorded and there is
nothing to check. Such a rule is reported as *shipping not checked* rather than silently trusted,
and a test asserts it. The lifecycle that verifies cleanly is the real one — accept while the work
is pending, let it land.

**Consequences.**

- **No schema change.** `git/adapter.py` gains `contains_commit`, read-only like everything else
  there; `operations.py` gains `_partition_by_shipping` and two fields on `ProductState`.
- **An all-unshipped catalogue is not an empty one**, and the view distinguishes them — the third
  such distinction after D-084's all-retired case. The sentence now counts retired and agreed
  together and says it is not an empty catalogue.
- **A dead safeguard was removed.** An explicit `cat-file -e` existence check stood in
  `contains_commit` and failed no mutation, because 128 already fell into the `unknown` band. It
  read as a safeguard and did nothing, so it went — the same treatment `area_is_declared` got under
  D-079.
- **CON-85, CON-86 and CON-87 stay open and are no longer urgent.** What they add is a *name* for a
  release and the ability to read the catalogue as it stood at one, not the correctness of the
  present picture.

**Status.** accepted

---

## D-086 · 2026-11-19 · The trademark work is dropped, and the name risk is accepted unverified

**Withdraws CON-22 and CON-23.** Both are struck from the register rather than deleted: an ID is
never reused here, including for an abandoned ticket, so a reader five months from now finds the
decision instead of a gap.

**Decision.** No trademark clearance is sought. **Constat** is used as the name with no register
search and no attorney opinion, and the risk that follows is accepted rather than mitigated.

**What is being accepted, stated plainly** so that nobody later reads this as "cleared":

- **The name may be unregistrable.** The open question was whether `CONSTAT` is *descriptive* in
  FR/EU for classes 9 and 42 — software that produces findings — and a descriptive mark cannot be
  registered. That question is now unanswered rather than answered favourably.
- **The word is already in commercial software use in French.** `e-constat auto` is the French
  insurance industry's official application (`BRAND_NAME_REVIEW.md` § 10). That was the strongest
  negative signal found, and nothing has been done about it.
- **The repository has been public throughout**, so first use is visible and dated. That cuts both
  ways and is not a defence.
- **A rename later costs more than a rename now**, and more again after a pilot: the name is in the
  package, the CLI, the schema's own prose, the published pages and the domain plan (D-075).

**Why accept it anyway.** `PRODUCT_SPEC.md` § 10 puts the attorney review before the first pilot
conversation, and the first pilot conversation is itself behind CON-26, which stands at **zero
conversations**. Paying for an opinion on a name for a product nobody outside this repository has
confirmed they want is spending in the wrong order. If discovery kills the premise, the trademark
question never needed answering; if discovery validates it, the question returns with a reason to
pay for the answer.

**Consequences.**

- **D-013 is unchanged** — the name is still Constat — and `BRAND_NAME_REVIEW.md` stays as the
  record of what was checked and what was not. It is a review, not a clearance, and now says so by
  the absence of a follow-up ticket.
- **The register keeps both IDs struck through**, with this entry named, so the withdrawal is
  traceable rather than silent.
- **Reopening is a new ticket**, not a reinstatement of these two — the same posture D-084 takes for
  a retired rule. If the name is ever to be defended, the descriptiveness question is the one to ask
  first and the cheapest to ask.
- **The validation tickets are untouched.** CON-26, CON-27 and CON-28 are commercial, not legal, and
  remain the critical path.

**Status.** accepted

---

## D-085 · 2026-11-19 · The agreed state is a checkpoint, taken explicitly and compared by version

**Closes CON-15**, the oldest open ticket in the register. It was waiting on something `constat
state` deliberately is not.

**Decision.** A **checkpoint** is a frozen record of which rules stood, at which versions, when a
person took it. `constat checkpoint take --label …` freezes it; `constat checkpoint changes` reports
what the catalogue has done since, as one of four outcomes per rule: **added**, **retired**,
**revised**, **unchanged**.

**Why a new object rather than reusing `constat state`.** D-070 made that view computed and stored
nowhere, which is exactly what keeps it always true of the revisions it names — and also what left
nothing to compare against. The two are complementary: `state` says what the product does now, a
checkpoint says what it did when a person last looked, and the difference is what a reviewer wants.

**Taken explicitly, not derived.** "The last approved state" needs a point somebody chose. Derived
from the newest acceptance it would move every time a rule was accepted, so "what is new since"
would quietly come to mean "since the previous rule" — a moving reference point, which is no
reference point at all.

**Compared by rule id and version number, never by statement text.** A rule a later version
rephrased has changed; one nobody touched has not; and only the stored version numbers tell those
apart. That is why a checkpoint records the *version* rather than the rule. Mutation-checked.

**The word.** `PRODUCT_SPEC` § 6 calls this a *baseline*, CON-14 did too, the CLI says "version 1
baselined" when freezing a rule version, and CON-89 took `constat baseline <AREA>` for documenting
an area — three senses of one word, the third of which I introduced on 2026-11-18. This object is
therefore a **checkpoint**, and "baseline" keeps its other two uses. Recorded rather than left for
somebody to trip over; renaming CON-89's command stays available if the overload proves worse than
the new noun.

**Four outcomes, kept apart**, because a reviewer's next move differs for each — and one subtlety:
a rule **added and retired since** the checkpoint is reported as *nothing*. It was never in the
state being compared against, so calling it retired would describe the product losing something it
never had in that state.

**Consequences.**

- **Schema 20:** `checkpoint` and `checkpoint_rule`, both append-only by trigger. A checkpoint that
  could be edited would make "what changed since" unanswerable, which is the whole reason to have
  one. Nothing is checkpointed by the migration: a checkpoint records that a person looked and
  agreed, and inventing one would put a decision in the record nobody made.
- **Retired rules are excluded when taking one.** A checkpoint records the product as it stood, and
  a rule a person had taken out of the picture was not part of it (D-084). A rule retired *after* a
  checkpoint is therefore a reported change, which is the behaviour wanted.
- **An empty catalogue can be checkpointed.** "We agreed it was empty" is a real starting point, and
  refusing it would make the first comparison impossible.
- **A missing checkpoint refuses rather than answering.** "Nothing has changed since a checkpoint
  that does not exist" is the confidently-wrong answer this product exists to avoid.
- **A revision reports *that* the rule changed, not *what* changed in it.** The per-detail diff is
  CON-67's, reached through `rule history`, and the output says so rather than implying it covers
  both.
- **CON-14 is now fully met.** Its criterion — "a later approval creates a new version; previous
  content remains recoverable" — held for versions since D-053; what was missing was a stored state
  to compare against, which this supplies.

**Status.** accepted

---

## D-084 · 2026-11-18 · Retirement is a human decision, final, and deletes nothing

**Closes CON-83, and answers the question D-071 left open.**

**Decision.** A rule can be **retired**: a person records that it no longer describes the product,
with a mandatory reason. The rule leaves `constat state`'s current picture and stays in the record —
its versions, citation and evidence all readable. Retirement is append-only and **final**: there is
no reinstatement, and a retired rule cannot be revised.

**A human decision, in the same sense acceptance is.** D-070 already said a rule whose anchors have
vanished is a *retirement candidate, never a retirement*; this is the other half of that sentence.
Nothing automatic retires anything — not vanished anchors, not an unreadable repository, not a
migration. A test asserts that deleting a registered repository retires nothing.

**A decision, not a deletion.** `rule` cannot be deleted at all — the trigger aborts it (D-048) —
so retirement is a state recorded *about* a rule, in its own append-only table, the shape
`rule_proposal_decision` uses for acceptance. Product rule 5 requires this: a catalogue that forgets
what it used to claim cannot be audited.

**Final, and that is a choice.** No reinstatement row exists by design. Bringing behaviour back
means accepting a new reading as a **new rule with its own citation**, which is a decision somebody
makes rather than a flag somebody clears — and it leaves both the retirement and the return in the
record. A reading that claims to revise a retired rule is therefore refused at acceptance, with the
route back named in the message.

**This is where a lapsed condition goes.** D-071 allowed a rule conditional on a business state —
"while the site is not approved by the ad network" — and left open what happens when that state
changes. The rule becomes false, nothing in the statement can say so, and editing the statement
would rewrite what a person accepted. **Retiring it with that reason is the answer**, and it is why
a reason is required rather than optional: the reason is the only record of why the product stopped
behaving this way.

**Consequences.**

- **Schema 19:** `rule_retirement`, with both append-only triggers. Nothing is retired by the
  migration — inventing a human decision is precisely what D-048 prevents.
- **`rules_matching` excludes retired rules.** A retired rule is not current behaviour, so reporting
  a change as touching it would send a reviewer back to something they had taken out of the picture.
  A path claimed only by a retired rule is therefore claimed by nothing, which `unmatched_paths`
  correctly says.
- **An all-retired catalogue is not an empty one**, and the state view distinguishes them. The first
  implementation printed "the catalogue holds no rules" after every rule had been retired, which is
  a different claim about the product and a false one.
- **The reason is rendered.** The picture says how many rules left and why, because "the product
  used to do this and deliberately stopped" is a fact a reader of business documentation needs, and
  silence would read as the rule never having existed.

**Status.** accepted

---

## D-083 · 2026-11-18 · A message is verified by its longest literal fragment, and absence is reported

**Closes CON-91.** A stored message was a *claim*: Constat held `Failed to start upload` because a
reading said so, and nothing checked it. This is the strongest verification available without
running anything — the wording is either in the code or it is not.

**Decision.** `constat message verify` searches every registered repository at its mainline for each
stored message, literally. A message found nowhere is **reported, never refused**, and a message
with no searchable text is reported as *not checkable* rather than as absent.

**Searched by its longest literal fragment, because the whole text is normally unsearchable.** Two
reasons, both ordinary rather than exceptional:

- **Placeholders.** `The following files have already been uploaded: <file names>` exists in the
  code as a format string, so the full text appears nowhere. Verified on a real repository where the
  catalogue says `<file names>` and the code says `{names}` — the fragment matched anyway, which is
  the point of cutting at the placeholder rather than demanding the whole string.
- **Line breaks.** `git grep` is line-oriented, so a needle spanning a newline matches nothing.

So the message is cut at both, and the longest remaining run is the needle. **The fragment is
reported with the result**, because a reader has to know what was checked: a match on a fragment is
evidence the wording exists, not proof the whole string does.

**A floor of twelve characters, below which nothing is checked.** `Refused` appears in every
codebase; finding it proves nothing, and reporting that as a verified message would be exactly the
confident-wrong answer this product exists to avoid. A message that is almost all placeholder is
therefore *not checkable*, and says so — a third state, kept apart from found and not-found because
collapsing it into either would assert something untrue.

**The search is `--fixed-strings`.** User-facing text is full of regular-expression syntax; a message
containing `(` must not become a search for a group, and one containing `.` must not match any
character. Mutation-checked.

**Absence is reported rather than refused** (D-064's posture). A message can be assembled from
fragments, translated, held in a resource file, or built by a formatter this cannot see. Refusing a
true message because the search was naive is the worse error, and the output says so in as many
words rather than leaving a bare NOT FOUND to read as a verdict.

**Consequences.**

- **No schema change.** `git/adapter.py` gains `search_text` — read-only, as everything else there
  is — and `operations.py` gains `literal_fragment` and `verify_messages`.
- **An unreadable repository is named in the result.** Silence about it would make a message living
  there read as absent from the product (D-070's posture).
- **`constat message list` arrives with it.** D-082 added messages and no way to see them, which
  made the catalogue's most checkable content invisible.
- **Verification is on demand, not at submission.** A message is not in the catalogue until a rule
  carrying it is accepted, so there is nothing to verify at submit time; and a check that ran on
  every submission would make the gate's cost proportional to how often a reading is re-run.
- **This does not verify statements, examples or behaviours.** Only the field whose entire value is
  being verbatim. Everything else remains a reading a human has to judge, which is the division of
  labour D-066 set.

**Status.** accepted

---

## D-082 · 2026-11-18 · A message is a verbatim quotation, stored once, exempt from the leakage gate

**Closes CON-82.** A rule could describe what the product does and never show what the product
*says*. The text a user reads was either absent or paraphrased inside a statement.

**Decision.** A message a user can see is a catalogue entry of its own: stored once, keyed on its
exact text, cited as `M-7` in D-081's scheme, and referred to by every rule that shows it. A reading
proposes the text; the entry is minted at acceptance.

**Verbatim, and therefore exempt from D-066.** This is the load-bearing decision. The code-leakage
gate refuses an identifier, a file path, an HTTP verb or a snake_case name — and real user-facing
text contains all four:

> `No ExcelMappingType was found in the workbook`
> `Could not read render.ts`
> `HTTP 503: the service is unavailable`

Applying the gate here would refuse the true text and leave a reviewer with a tidied approximation,
**which is worse than nothing because it still looks like evidence**. D-066 protects sentences
Constat writes *about* the product; a message is a sentence the product writes itself. The gate still
applies to the statement, the behaviours, the examples and the area — a test asserts a statement
naming a file is refused while a message naming one is kept, so the exemption cannot be read as the
gate weakening.

**Stored once, matched on exact text.** One message routinely belongs to several rules — the same
refusal covers a size limit and a duplicate name — and a second copy is how two wordings come to
disagree. Correcting a message therefore corrects it everywhere, which is the point and the one
piece of a version's substance that is *not* frozen against later change: `rule_version_message`
links to the entry rather than copying the text. Stated because it differs from behaviours and
examples, which are frozen per version.

A **near-match is a different message.** Treating one as the same is a judgement no gate here is
entitled to make, and it would silently rewrite what a user sees.

**Minted at acceptance, never at submission.** A reading carries text and no citation, like an
example carrying no number (D-078): minting an entry for an unaccepted reading would put something
in the catalogue no human had agreed to (D-048).

**Consequences.**

- **Schema 18:** `message`, `rule_message`, `rule_proposal_message`, `rule_version_message`. No
  back-fill, and nothing to back-fill from — mining quoted strings out of existing statements would
  be Constat inventing the evidence a reviewer is meant to check.
- **The guidance block is shared by all three reading paths** — provider, MCP and baseline — and a
  test asserts the same object reaches each. It asks for the text copied from the code, and says an
  approximation is worse than nothing.
- **CON-91 gets simpler.** "A quoted message is verified against the code" now has an obvious
  implementation: check `message.text`, rather than scraping quotations out of statements.
- **A mutation survived first, again.** Applying `code_leakage` to messages failed only one of four
  parametrised cases, because three of my example texts did not actually trip the gate. The test now
  asserts `code_leakage(text) is not None` before asserting the exemption, so a text that stops
  tripping the gate fails loudly rather than quietly weakening what it was written to pin. Two
  tickets in a row where the first mutation attempt was uninformative; the lesson is that a mutation
  which survives tells you about the test, not about the code.

**Status.** accepted

---

## D-081 · 2026-11-18 · A rule's citable identifier is flat, stored, and never reused

**Closes CON-81.** A rule could be identified two ways and neither was citable: the row id is an
implementation detail that means nothing to a business reader, and `name` is a label that may change
between versions (D-050). There was nothing to write in a comment, an email or a pull request.

**Decision.** Every rule carries `ref` — `R-14` — assigned at acceptance, stored, unique, and never
reused. It is shown wherever a rule is rendered and resolves as a lookup argument
(`constat rule show R-1`).

**Flat rather than area-prefixed.** `BR-PAY-001` reads better and encodes the area, which is
*mutable by design*: D-079 deliberately left an area as free text, and a rule may be re-grouped. An
identifier encoding a mutable fact becomes a false claim the moment that fact changes — what D-078
established about positions, applied to areas. A flat citation cannot go wrong, and the area is one
field away in every rendering.

**Stored rather than derived from the row id.** `R-{id}` would be free and is a trap: a public
citation would then depend on rowids surviving every future table rebuild, and `rule` has already
been rebuilt once (migration 4 → 5). A citation that can shift is not a citation.

**Back-filled, unlike every migration before it, and the difference is the point.** D-070, D-072,
D-077 and D-078 all refused to back-fill because they would have been inventing a claim nobody
made — an area, a ground, an example, a number standing for an identity. A citation invents nothing:
the rules exist, and naming them asserts nothing about them. Refusing here would leave a catalogue
whose rules nobody can cite, which is the defect this closes.

**Never reused holds without qualification here**, unlike D-078's details: a rule can never be
deleted (the trigger aborts it), so `rule` *is* the whole history and the greatest citation in it is
the high-water mark.

**Two mutations survived before the property was pinned.** Replacing the high-water mark with a
count of rules passed every test, including a first attempt at catching it that inserted an
*uncited* rule — which does not distinguish the two, since a NULL ref is counted by neither. The
case that does distinguish them is a **gap** in the citations, which the back-fill can produce
because it derives from row ids and row ids can have gaps. Recorded because the first two attempts
being wrong is the useful part: a mutation that survives means the test did not pin the property,
not that the property holds.

**Consequences.**

- **Schema 17**, with uniqueness as an explicit index rather than an inline constraint, so a freshly
  created workspace is structurally identical to a migrated one — `ALTER TABLE` cannot add an inline
  `UNIQUE`, and two shapes of one table is a difference waiting to surprise somebody.
- **No column on `rule_version`.** A citation names the rule, not a version of it, and never
  changes; storing it per version would duplicate an immutable fact.
- **The payload is unchanged.** `revises` still names the integer id, which is checked against the
  ids a reading was shown (D-050). The citation is a human-facing name, and a reading has no use for
  one — a statement must not contain identifiers at all (D-066).
- **`Catalogue.find` resolves a name or a citation**, name first. A citation nobody can look up is
  decoration.
- **CON-82 is unblocked:** messages as catalogue entries need the same scheme, and now have one.

**Status.** accepted

---

## D-080 · 2026-11-18 · A baseline documents an area with no evidence from Constat, under a reference

**Closes CON-89.** A new workspace had an empty catalogue and no route into it but one ticket at a
time. This is the way in.

**Decision.** `constat baseline <AREA>` stores a reading that describes an area **as it already
behaves**. Three parts:

1. **Constat supplies no evidence.** There is no delta to read, so there is no payload worth
   building — the reader has the repository and reads it directly. What Constat does is what only it
   can: ground every anchor, record which revision was described, and store the result as proposals
   nobody has accepted.
2. **It is recorded under a reference** — the ticket that occasioned it, or one supplied and opened
   for a cold start.
3. **Scope is the argument.** A reading naming another area is refused rather than re-filed.

**The agent-driven shape was chosen over three alternatives**, and the decisive trade is stated
plainly: it means a **baseline cannot be produced on the provider path**, because a provider has no
repository access. The rejected options were a human-supplied path glob (bounded and symmetric, but
requires knowing the layout and a wrong glob documents the wrong part of the product), a fifth MCP
tool serving excerpts on demand (probably the right long-run answer, and the most work), and
inferring an area's home from directory names (refused outright: that is organising by where the
code lives, the axis D-070 rejects, and a wrong guess produces a confidently wrong baseline).

**A correction to how this was first argued.** The asymmetry was initially described as violating
D-045. It does not. D-045's invariant is that a rule proposed over MCP and the same rule proposed by
a provider must **mean** the same thing, which the shared guidance enforces — `for_baseline` reuses
`WHAT_A_RULE_IS`, `EXAMPLES` and `ANCHORS` unchanged. A command being unavailable on one path is a
**capability** asymmetry, not a meaning one. The provider path refuses clearly rather than producing
nothing, which is D-059's posture.

**Why it hangs off a reference rather than an area.** The chain
`ticket -> document -> run -> rule_proposal` is `NOT NULL` at every link, and a proposal must point
at a run. Letting a run belong to an area instead would mean rebuilding nine tables — SQLite cannot
drop `NOT NULL` without a table rebuild, `run`'s children cascade on delete, and
`PRAGMA foreign_keys=OFF` is a no-op inside the transaction migrations run in. That is the riskiest
migration in the project for one nullable column. **So there is no schema change here at all.** The
cost is stated rather than hidden: a cold-start reference appears in `ticket list` without being a
unit of work, and the command says so when it opens one.

**Grounding needed nothing new** — D-072 already allows an anchor to rest on mainline — with one
exception found by a test: a baseline's payload carries no repositories, so a repository-scoped
anchor was refused as naming an alias nobody had shown the reader. The mainline map's keys *are* the
registered aliases, so that is now the second source for the alias check. It loosens only toward
repositories Constat actually has.

**Consequences.**

- **The revision is recorded as the run's evidence pointer** (D-073), in the same `run_commit` table
  a ticket's commits go in. A claim about the present that cannot name the revision it described is
  not inspectable (product rule 2), and a baseline has no commit set to point at.
- **A baseline's anchors are the weaker ground by construction**, and correctly so: nothing here is
  evidence that anything changed. The queue says *"anchored in mainline"* without the clause about a
  ticket's changes, which on a baseline would imply a deficiency.
- **The queue says a reading came from a baseline.** A reviewer's question differs — "this change
  established a rule" versus "this is how it already behaves" — even though accepting them has the
  same effect.
- **An out-of-scope reading is reported as out of scope**, never as ungrounded or malformed. The
  first implementation folded the two together and reported it twice, the second time under a label
  that was false.
- **Nothing is accepted.** A baseline documents existing behaviour, which makes it tempting to treat
  as uncontroversial; a rule still enters the catalogue only by a human decision (D-048), and a test
  holds that.
- **The MCP tool is not built.** `constat baseline` is the CLI path; an MCP tool would be a thin
  wrapper over the same operation, which ARCHITECTURE § 2 requires.

**Status.** accepted

---

## D-079 · 2026-11-18 · An area is declared by accepting a rule, and coverage is counted in areas

**Closes CON-88 and CON-90. Amends D-070**, which made an area free text with no vocabulary and
recorded the drift into "advertising / ads / monetisation" as *expected and unsolved*. This is what
solves it, and the solution is deliberately not a vocabulary.

**Decision.** The declared set of business areas is **the areas on accepted rules**, because
acceptance freezes the area onto the version (D-070) — the catalogue already is the register. A
separate `area` table holds only areas named **ahead of their first rule**, which is what
documenting a new area needs (CON-89). `Catalogue.areas` unions the two and is the single answer to
"which areas exist".

A reading proposing an area the catalogue does not have is **reported, never refused** (D-064's
posture). Coverage in `constat state` is counted in **areas**; the file count stays as a stated
technical figure rather than the headline.

**Why the register is derived.** The alternative — a table a human fills before any rule can be
filed — forces a refusal path, and a refusal at acceptance would block a person mid-decision over a
heading. Worse, it creates two sources of truth for one fact: a rule carrying an area the register
has never heard of is a contradiction the store would have to adjudicate. Deriving the set means
there is nothing to reconcile. Mutation-checked: reading only the table fails eight tests.

**Why a coined area is reported rather than refused.** A new area is often correct — products grow —
and refusing one would make Constat the authority on how somebody's business is organised, which
nothing here is entitled to be. What it must not do is let "ads" in beside "advertising" unremarked:
nothing afterwards can tell a synonym from a distinction, and merging two areas is a rename across
frozen versions. So the report names the coined area *and the areas already declared*, and the
decision stays the reviewer's — accepting the rule declares the area with it.

**Why coverage moves to areas.** Files are the wrong denominator for business documentation. A
product can be wholly described by thirty rules over a thousand files, and "970 files are claimed by
no rule" reports that as a permanent failure — a number that cannot be improved by doing the work
well. Areas are the denominator a reader has an opinion about. **The honest caveat is printed with
it:** counting declared areas flatters a catalogue that has declared two of twenty, so the view says
that parts nobody has declared are not counted at all, and that this is the larger gap.

**Consequences.**

- **Schema 16:** one `area` table, nothing migrated into it. Every area already in use is on an
  accepted rule, and copying them in would create the second source of truth this avoids.
- **`constat area list` distinguishes documented from declared** — "payouts — declared, no rules
  yet". An area with no rule is an intention, and rendering it like a documented one would overstate
  the catalogue.
- **Declaring is a write, so it is not on `Catalogue`.** That class stays read-only (D-048) with a
  test asserting its exact surface; `store/areas.py` owns the write, as `acceptance.py` owns its own.
- **No vocabulary, no CHECK, no refusal of a name** beyond the 60-character bound the parse already
  applies. A test declares an area in French to hold that open.
- **Merging two areas is deliberately not built.** It is a rename across frozen versions, which is a
  different ticket and a harder one.
- **CON-89 is unblocked**, and this was its prerequisite: an area can now be opened before it has
  rules.

**Status.** accepted

---

## D-078 · 2026-11-18 · A detail's identity is its text, recorded as a number at acceptance

**Closes CON-67**, whose open question was what identifies a detail across versions.

**Decision.** Each of a rule's details — a behaviour, an example — carries a **number** that is
durable within its rule. The number is assigned **at acceptance** by matching the detail's text: a
behaviour's `description`, an example's `situation`. A detail whose text the rule has carried before
keeps its number; a new one takes the next number the rule has **never** used. Two versions are
compared by number, never by position.

**Position cannot be identity**, which is the whole reason this ticket existed. "The second example
changed" means something different the moment an earlier one is removed: under a positional
comparison, dropping example 1 makes example 2 slide up and read as changed — a wrong claim about a
case nobody touched. D-043 already required durable identities rather than positions in text for
comment anchors; this is the same requirement arriving for details, and CON-47 will use it.

**An example's outcome is compared but is not part of its identity.** That asymmetry is the
feature: a changed outcome under an unchanged situation is the case a reviewer most needs to see, and
it is visible only because identity excludes it. Mutation-checked — folding the outcome into the key
makes a changed outcome read as one example removed and another added, and four tests fail.

**The cost, stated and printed.** A *reworded* situation is a different example: one removed, one
added, not an edit. The alternative was to let a reading name the id it is amending, which would
have made identity a model claim — unverified, like `revises`, and attachable to anything. Text
identity is checkable by reading the two versions. So the limit is accepted, and `rule history`
**prints it** whenever a diff contains both a removal and an addition, rather than leaving it in a
decision entry nobody reads at the terminal.

**The high-water mark comes from the version tables, not the live ones.** `example` and `behaviour`
are deleted and rewritten on every acceptance, so their maximum forgets every detail a rule ever
dropped — and the next acceptance would hand a retired number to something unrelated, making the
diff claim a case had been *edited* when it had been replaced. The version tables are append-only,
so their maximum is the rule's whole history. Mutation-checked: reading the live table fails exactly
the test written for it.

**Consequences.**

- **Schema 15:** `behaviour_no`, `example_no`, on both the live and the frozen detail tables.
  Nullable, **nothing back-filled** — a detail accepted earlier was never numbered, and matching it
  today would let `rule history` present this code's guess as what a reviewer saw. Such details are
  reported as `unnumbered` and are **not compared**.
- **A number is spent at acceptance, never at submission.** A reading carries no numbers: numbering
  a proposal would commit an identity to something that may be rejected.
- **Behaviours and examples number independently.** Sharing a counter would make a behaviour's
  number depend on how many examples happened to be accepted first.
- **A restored situation gets its old number back**, which is not a contradiction of "never reused":
  identity is the text, so the same situation returning *is* the same example, and giving it a fresh
  number would claim a replacement where there was a reinstatement.
- **The first version prints no diff.** It has nothing to differ from, and "4 added" there would
  read as a change when it is the rule arriving.
- **CON-81 is still blocked and still separate.** This numbers details *within* a rule; a citable
  identifier for the rule itself needs the decision on form.

**Status.** accepted

---

## D-077 · 2026-11-18 · A rule carries worked examples, and nothing checks whether they are right

**Closes CON-80.** The catalogue held statements and nothing a reader could disagree with.

**Decision.** A rule and a rule proposal both carry **examples**: ordered pairs of a `situation` and
an `outcome`, stored on the reading, frozen on the accepted version, and rendered wherever a rule is
shown. Two columns, not a per-rule table of input columns. Examples are **optional**, and what is
checked at parse time is their *shape*, never their truth.

**Why two columns.** The richer form — each rule defining its own input columns — reads better when
a person writes it once. A reading gets re-run, twice on ticket 615 already, and a per-rule column
schema comes back different each time: one rule accumulates three shapes of table, and nothing can
diff them. Two columns compose, render in every surface, and survive re-reading.

**What is checked, and what is deliberately not.**

| Checked at parse time | Not checked, ever |
| --- | --- |
| Both halves present | Whether the outcome is what the code does |
| Each half within 200 characters | Whether the cases are the *interesting* ones |
| Neither half leaks code (D-066) | Whether the examples are complete |
| The example is not the statement restated | |
| No repeated situation in one reading | |

The second column is the point. Deciding whether "a transfer of 600 against a 500 limit is refused"
is *true* is the reviewer's entire job, and a gate that guessed at it would manufacture the
certainty product rule 1 forbids. A test asserts that a plausible-but-wrong example is stored, with
a docstring saying why, so the test file cannot later be mistaken for a correctness guarantee — the
posture CON-74 set for `code_leakage`.

**A bad example rejects the whole reading.** Not itself. Dropping one example from three would store
a reading that says something the reader did not, which is the failure `parsing.py` exists to
prevent, one level down. `_examples` therefore returns a reason rather than a filtered tuple.

**The restatement check errs toward allowing.** A real example shares most of the statement's
vocabulary by construction — it is a case *of* it — so the threshold is high (85% of non-filler
words) and a near-restatement with one added clause passes. A false refusal discards a case a person
might have wanted and the reader cannot argue back. Half the new tests assert that direction.

**A revision replaces a rule's examples, and the payload now shows them.** Acceptance rewrites the
live table from the reading, so a revision that omits examples *deletes* cases a human accepted.
`KnownRule` therefore carries the accepted examples, and `REVISION` in the guidance says so. This
hazard already existed for behaviours; examples make it expensive, because they are the part a
person actually checked.

**Consequences.**

- **Schema 14:** `rule_proposal_example`, `rule_version_example`, `example`. Nothing is back-filled,
  and here that is not even a choice of principle: no reading before this could propose an example,
  and deriving one from a stored statement would be Constat inventing the evidence a reviewer is
  meant to check.
- **Absence has two meanings and the renderers claim neither** — a rule accepted before schema 14,
  and a reading that proposed none. Neither is "this rule has no cases".
- **`constat state` says when a rule has no examples**, rather than printing nothing. A rule nobody
  can check is a gap in the documentation, and the view that exists to state coverage should state
  this too.
- **One renderer**, `operations.example_table`, used by the ticket document and the product state, so
  a reviewer comparing them never reads two formats. Pipes are escaped; an unescaped one would move
  half a sentence into a column that does not exist.
- **CON-67 is next and is now worth more**: tracking which *details* changed between versions has a
  shape worth tracking, and examples are where a diff between two versions will be read.
- **CON-81 is unaffected and still blocked.** An example is addressed by position within its rule;
  giving examples their own citable identifiers waits for the rule identifier decision.

**Status.** accepted

---

## D-076 · 2026-11-18 · Constat assumes trunk-based development, and says so

**Names an assumption that was already in the code.** D-028 made mainline the reference point,
D-068 made it the remote-tracking ref, and D-031 bounded the search to what is ahead of it. None of
the three said which *branching model* those choices commit to. This one does, so that a team can
tell before adopting Constat rather than after reading a wrong answer.

**Decision.** Constat supports **trunk-based development**: exactly one mainline per repository,
and that mainline is the product as shipped. Mainline is the default branch's remote-tracking ref
(D-028, D-068). Work ahead of mainline may sit anywhere — `develop`, `release/*`, an open ticket
branch — because D-031's window is `git log --all --not <mainline>` and names no integration
branch. Git Flow, long-lived parallel release lines, environment branches and fork-based workflows
are **not supported**, and the limit is documented in `README.md` rather than detected.

**Context.** The assumption is one line of configuration away from producing a confident wrong
answer. Under Git Flow, if `refs/remotes/origin/HEAD` points at `develop`, "already landed" means
*merged to develop* and `constat state` renders unreleased behaviour as the product's current
behaviour — a direct breach of product rule 1 in a command whose entire purpose is to state the
present. If it points at `master` instead, the whole `develop` tree reads as never landed. **The
same project yields either answer depending on a repository setting**, which is why this cannot be
left implicit.

What is *not* assumed is worth recording, because it was designed for deliberately: D-031 refused
to configure an integration branch, so the staging topology above mainline is free-form; and D-030
established that rebase- and squash-heavy histories are supported, having found 3 merge commits in
Subject A's last 200 and none in Subject B's.

**Product rule 6 is aspiration, not code.** "Release streams are distinct — do not assume every
branch or release follows one linear timeline" is a stated invariant, and the implementation
assumes exactly one linear timeline per repository. That contradiction is recorded here rather
than resolved. In particular, **the release concept decided alongside this does not discharge
rule 6**: declared releases spanning the registered set, several open at once, are several staging
sets ahead of one trunk. Coherent trunk-based development, and still not parallel production
lines. Anyone reading the release work as satisfying rule 6 would be wrong.

**Consequences.**

- **`README.md` states the limit** before the getting-started section, with the four models that
  break and how each breaks. `PRODUCT_SPEC.md` § 6 carries one line of it, since it bounds the MVP.
- **Partly detectable, so partly detected — later.** CON-97 names the resolved mainline back at
  `repo add` and warns on a Git Flow shape (a default branch called `develop`; a
  `master`/`main`/`production` branch ahead of the default). A warning, never a refusal: the signal
  is a naming convention, and refusing on a convention would reject a legitimate repository that
  happens to use the word.
- **Supporting parallel production lines is a schema question, not a flag.** A rule version would
  need to be in effect on one line and not another, which the single `rule`/`rule_version` shape
  cannot express. It is therefore out of scope until a pilot asks for it, and rule 6 stays unmet
  until then.
- **Nothing in the code changes.** This records what is already true; the only edits are
  documentation and CON-97's row.

**Status.** accepted

---

## D-075 · 2026-11-15 · The site starts at `constat.padjinou.com`, and no domain is bought yet

**Amends D-014**, which chose `tryconstat.com` and treated registering it as securing the name. That
choice is not withdrawn — it remains the domain to buy when there is something to put on it — but
the *timing* changes: nothing is registered now, and the web presence starts on a subdomain of a
domain already owned.

**Decision.** The project site is hosted at **`constat.padjinou.com`**. No new domain is purchased.

**Context.** D-014 reasoned that registering was "about securing the name, not launching", and
CON-21 has been marked 🔴 *not done* since, on the grounds that the name is public while the domain
is free. A subdomain of an owned domain answers the hosting need at zero cost and immediately, and
there is nothing to deploy yet: validation is at **zero discovery conversations** (CON-26), so a
landing page has no audience to fail in front of.

**What this accepts, rather than solves.**

- **The name is not protected by this.** `tryconstat.com` stays registerable by anyone, and
  `constat.ai` is still on an aftermarket listing that can be bought or withdrawn. D-014's note that
  a listed domain can disappear applies unchanged. The bet is that the risk of losing a `try…`
  prefix is small enough to carry — and it is a bet, not a mitigation.
- **A personal subdomain reads as a personal project.** That is accurate today and becomes a
  liability at precisely the moment it stops being: a pilot conversation with a business audience
  (roadmap weeks 3–8). D-014 already observed that `try<name>.com` "reads as a product landing
  page"; `constat.padjinou.com` does not.

**Consequences.**

- **CON-21 is deferred, not closed.** Reworded from "register `tryconstat.com`" to "the site has a
  home", which this satisfies. Buying a domain returns as its own item when it has a reason.
- **The trigger to revisit is the first pilot conversation**, not a date. Before showing the product
  to someone outside, the question is whether a subdomain is the address to show them.
- **Nothing in the product depends on either name.** Publishing targets are per-repository (D-058)
  and the catalogue has no notion of a website.

**Status.** accepted.

---

## D-074 · 2026-11-15 · The copyright holder is Emmanuel Padjinou personally

**Decision.** Copyright in Constat is held by **Emmanuel Padjinou** as a natural person, as `LICENSE`
and `NOTICE` already state. It is not assigned to a company, and no contributor licence agreement is
required beyond Apache-2.0's own § 5.

**Context.** CON-25 had stood open as "decide the copyright holder" while `LICENSE:189` and
`NOTICE:2` already named him — so the ticket's own done-when was satisfied and the question it
pointed at was a different one: person or entity. Left unrecorded, that gets rediscovered every time
someone reads the backlog.

**Why personal.** There is one contributor. Apache-2.0 means any future contributor licenses their
contribution *to the holder* under § 5, so nothing is lost by the holder being a person. And a
company to assign to does not exist: choosing an entity now would mean blocking the licence on
incorporation, which is a real cost for no present benefit.

**What would change it**, stated so the question is reopened deliberately rather than by accident:

- **Incorporation.** If a company is formed to commercialise Constat, the copyright should be
  assigned to it, and that assignment is a document, not an edit to `NOTICE`.
- **An outside contributor.** Apache-2.0 § 5 covers the inbound licence, but a project taking
  substantial outside contributions and intending to relicense later needs a CLA. Relicensing is
  the trigger, not contribution itself.
- **A pilot that demands it.** An enterprise pilot may ask who owns the software. A person is a
  complete answer; it is simply a different one from a company.

**Consequences.**

- **`LICENSE` and `NOTICE` are already correct** and need no change. CON-25 closes as recorded
  rather than as implemented.
- **Nothing here clears the *name*.** Copyright and trademark are separate: `BRAND_NAME_REVIEW.md`
  § 9 tasks 1–3 (USPTO/EUIPO knockout search, attorney review, INPI/RCS check) remain outstanding
  and are CON-22 and CON-23. Deciding the copyright holder does not touch them.

**Status.** accepted.

---

## D-073 · 2026-11-15 · A rule records the evidence it was accepted on, as a pointer

**Decision.** A run writes down the commits whose evidence it read: SHA, identity-scrubbed subject,
the repository's alias, and the repository's **identity** (its root commit, D-025). An accepted rule
version resolves to them through the reading it was baselined from. The evidence itself is **not**
copied into the workspace.

**Context.** CON-79, found by re-reading 615 after it landed. The chain
`rule_version -> rule_proposal -> run -> operation` ended at a summary line reading
`pending: 1 commit(s)`. No table in the workspace held a commit SHA — not the proposal, not the
version, not the operation — and once a ticket lands it contributes no evidence (D-031), so the
document regenerates with no diffs. Both rules in the live catalogue had been accepted on evidence
the workspace could no longer produce. Product rule 2 requires an important claim to point at a
source commit; it was failing for every rule as soon as its ticket shipped.

**A pointer rather than a copy.** Storing the redacted payload was the alternative and was rejected:
a copy in the governance store becomes a second source of truth that can disagree with git — the
failure D-002 avoids by shelling out to git rather than reimplementing it — and it grows without
bound, every gather on every ticket with diff excerpts, forever.

**The cost of that choice is a dangling SHA**, and it is accepted with its mitigation. A squash-merge
or a force-push destroys the commit a rule points at. The subject is therefore stored beside the
SHA, so a broken pointer still says *what* it pointed at and the gap is visible rather than blank.

**Consequences.**

- **Stored against the run, not copied onto each reading.** Every reading of one run read the same
  evidence, and `run_commit` is itself append-only history: a reference to an immutable row is as
  durable as a duplicate of it and does not create two places for one fact.
- **The subject is scrubbed even though it never leaves the machine.** Identity in a store is a
  disclosure waiting to happen (`ai/redaction.py`), a subject can carry an address, and over-masking
  a pointer costs nothing because the SHA is what resolves it.
- **Nothing is back-filled, and here that is not only principle.** The evidence those earlier runs
  read is *gone*. There is nothing to recover, and inventing a SHA would be the worst possible lie
  to tell in a governance record. Rules accepted before schema 13 report "evidence: not recorded".
- **A run that read nothing records nothing, and says so.** The review queue prints "read from no
  commits — this run gathered none", which is exactly the state D-072 made possible: a rule can now
  be proposed for a landed ticket, and a reviewer must be able to see that its run had no evidence
  behind it.
- **`operation.payload` is untouched.** It looked like dead weight and is not: the scan-override
  path writes it to keep a credential-scan override auditable. Dropping it was proposed and
  withdrawn after reading the code.

**Status.** accepted.

---

## D-072 · 2026-11-15 · An anchor may be grounded in mainline, and which ground is recorded

**Decision.** An anchor is grounded if it names a path in the ticket's evidence **or** a path that
exists in the product's mainline. Which of the two supports it is recorded on the anchor, on the
rule and on the frozen version (`grounded_in`: `evidence` | `mainline`). The evidence is tried
first, because it is the stronger claim. An anchor matching neither is still refused. Mainline's
file list is **not** part of the payload: it is grounding data for the parse, not context for the
model.

**Context.** CON-71, reopened by CON-78 rather than answered by it. Grounding looked only at a
ticket's delta, and that produced two failures, both found by running the loop:

- On 615 a real rule went unproposed. The evidence *described* it — the install pages deliberately
  carry no advertising — but their home, `src/pages/`, was not in that commit's diff, so the only
  groundable anchor would have been a false claim about where the rule lives.
- On 628, after the ticket landed, **no** rule could be proposed at all. A landed ticket contributes
  no evidence (D-031), so there were no paths to anchor to. The product could document a ticket only
  in the window between merge and release.

**D-049 is not relaxed.** The reason anchors are checked at all is that a model will otherwise
invent a path, and an invented path is invented against either ground. What widens is the set of
*verifiable* paths, not the willingness to accept an unverifiable one.

**Why the two grounds stay apart.** "The evidence shows this changed" and "this file exists in the
product" are different claims, and product rule 3 requires the provenance types to stay
distinguishable. An anchor grounded only in mainline means **this ticket is not the evidence that
the rule's home changed** — true and weaker, and a reviewer deciding has to see it. The review queue
says so in as many words.

**Consequences.**

- **Nothing extra is sent to a provider.** The live workspace holds 922 files across three
  repositories; shipping that on every gather would cost real money to say what one sentence of
  guidance says. The reader is told the rule and names such a path only when the evidence tells it
  the path exists.
- **`parse` defaults to the old behaviour.** With no mainline supplied it grounds exactly as before,
  so a caller that cannot supply it is not silently weakened.
- **The provider protocol gained an optional argument.** `interpret(payload, mainline=None)` —
  defaulted, so an implementation that does not parse anchors is unaffected.
- **Nullable, no back-fill.** An anchor recorded before this was grounded in the evidence by
  construction, that being the only ground, but writing `evidence` into it now would assert
  something nobody recorded. NULL reads as "not recorded".
- **A mainline-grounded anchor can go stale in a new way.** It names a file the ticket never touched,
  so nothing in that ticket's evidence will ever confirm it again. CON-78's retirement flagging is
  what catches it later.

**Status.** accepted.

---

## D-071 · 2026-11-15 · A rule may be conditional, and the condition is in the statement

**Decision.** A rule may be conditional on a business state that will change. The condition belongs
**in the statement**, where a business reader meets it, not in a field beside it. A rule may not be
conditional on a technical state: "while the site is not approved by the ad network" is a business
condition; "while the cache is cold" is not.

**Context.** CON-72, raised by the first real reading. Rule 1 in the catalogue reads "…while the
site is not approved by the ad network", and nothing told the reader whether that was allowed. It
was written in because the evidence supported it, and a reviewer then had to decide both the rule
and whether the rule was the right *shape* — a question that belongs in the guidance, answered once,
rather than in every reading.

**Why in the statement.** A contingent rule read as unconditional is a false statement about the
product. Holding the condition in a separate field means a business reader can be shown the rule
without the thing that limits it, which is the kind of confident under-report product rule 1 exists
to prevent. One sentence, complete on its own.

**Consequences.**

- **Rule 1 stands as accepted.** No superseding version is needed, and the catalogue is unchanged
  by this decision.
- **It constrains what a *statement* may contain, not what a rule may be.** D-066 still refuses a
  statement that leaks code, and a technical condition is refused for the same reason — it is not
  something a business reader can evaluate.
- **A lapsed condition is not yet expressible.** When the site *is* approved, rule 1 becomes false
  and the only mechanism is a superseding version, which says "the rule changed" rather than "the
  condition lapsed". Left open deliberately: the right answer probably lives with retirement
  (D-070's flagging), and inventing a second mechanism before that is understood would be guessing.

**Status.** accepted.

---

## D-070 · 2026-11-15 · The catalogue is the business documentation, read as a current picture

**Decision.** Four answers, taken together because they describe one thing.

1. **The accepted rules *are* the business documentation.** Constat renders them; there is no second
   editable artifact and nothing to approve twice. Approving a rule is approving the documentation.
2. **The picture is product-level.** One view across every registered repository, each pinned at its
   own mainline revision, with a per-repository filter rather than a per-repository primary form.
3. **A rule never leaves the picture automatically.** When its anchored paths no longer exist in
   mainline it is *flagged* as a retirement candidate. A person decides, as with everything else
   that changes the catalogue (D-048).
4. **A reading proposes the business area a rule belongs to.** The catalogue has structure rather
   than being a flat list, and the area is a claim a human accepts with the rule.

**Context.** Accepting a ticket's rules should expand the scope of the product's documentation, not
just record that one ticket. Nothing in the product did that. Three things were called "baseline"
and none was the state of the product: `rule accept` baselines a *rule version*, which has no
repository and no revision column; `document_version` is per ticket; and `constat snapshot` prints
a description of a revision and stores nothing — its own help says it is what a baseline is "made
from". So `rule list` returned every rule ever accepted with nothing tying it to `main`, and "what
applies now" was unanswerable. PRODUCT_SPEC § 6 has promised this since the first version.

**It also reframes CON-71.** That ticket asked what grounding means when a rule is attested by
evidence it is not anchored to — a real rule went unproposed on 615 because its home, `src/pages/`,
was not in the commit's diff. The cause is that evidence is only ever a *ticket delta*. Against the
state of mainline the rule is groundable, so the question may dissolve rather than need an answer.

**Consequences.**

- **Computed, not stored.** The picture is derived on demand, so nothing is frozen and nothing can
  drift from it. **CON-15** — compare against the last approved baseline — therefore stays open and
  still needs a stored baseline; drift cannot be measured against a view that is recomputed. Reading
  the rendered picture first is the cheaper way to learn what is worth freezing.
- **An area is a business statement.** D-066 applies to it unchanged: "advertising" is an area,
  `DeviceProvisioningService` is a package. Same gate, no new machinery.
- **The area is separately rejectable.** A sound rule in the wrong area must be answerable without
  rejecting the rule, because it is a distinct claim.
- **Taxonomy drift is expected and unsolved.** Successive readings will offer "advertising", then
  "ads", then "monetisation". The payload already shows the catalogue, so the guidance requires
  reusing an existing area where one fits, but nothing enforces it and a human will have to correct
  it for a while. Stated now rather than discovered later.
- **No retire decision yet.** Flagging only. If the flag proves to be ignored noise, that is the
  evidence for adding one — not an assumption to build on first.

**Status.** accepted.

---

## D-069 · 2026-11-15 · Constat's own commits are not evidence, and the exclusion is stated

**Decision.** A commit Constat made is left out of a ticket's evidence. It is identified by a
`Constat-Landed: <reference>` trailer Constat writes and git parses — never by its subject. The
excluded SHAs are kept and the document names them. A reference known *only* to a commit Constat
wrote does not make a ticket `pending`: the tool is not its own witness.

**Context.** Re-reading 628 after `merge_on_accept` landed its branch returned two commits — the
team's fix and Constat's merge — so 14 changed files were reported for 7 real ones, and a commit
Constat authored was presented as implementation evidence. Product rule 3 requires the provenance
types to stay distinguishable, and "a commit Constat wrote" is not the team's work by any reading.

**Why a trailer rather than the subject.** `MERGE_SUBJECT` is text anyone could write, so matching
it would silently drop a human merge worded the same way. Under-reporting evidence is the worse
failure of the two — an over-reported commit is visible and arguable, a dropped one is not — and a
trailer is a token Constat controls, with a defined syntax that git parses through
`%(trailers:key=…)`. A commit that merely mentions the word in prose is not marked by it, which a
grep could not promise.

**Why the exclusion is stated.** Every other omission in this product says so: a truncated diff
names what it dropped, a repository that contributed nothing is still listed, a reference matching
nothing is distinguished from a ticket with no rules. Evidence that quietly disagrees with
`git log` would be the one place Constat asked to be trusted rather than checked.

**Consequences.**

- **Not retroactive, and that is the cost of refusing the heuristic.** Merges Constat made before
  this landed carry no trailer and stay in their ticket's evidence — `9eda7b44` in `237feed` is one,
  and ticket 628 will over-count it permanently. Excluding it would mean matching its subject, which
  is the thing this decision rejects. One historical commit in one ticket is the price.
- **The same filter applies to the landed lookup**, not only the pending one. 628's over-count was
  in the landed path, which is where a merge naturally sits.
- **Left open:** whether a merge commit should contribute evidence *at all*. A human merging the
  same branch through a forge double-counts identically and carries no trailer to filter on. The
  narrow fix is deliberate; the general question needs evidence from a real human merge before it is
  answered.

**Status.** accepted.

---

## D-068 · 2026-11-15 · Mainline is the shared ref, and drift from it is disclosed

**Decision.** A ticket's work is measured against `<remote>/<default-branch>` — the ref everyone
pulls — not against the local branch of whichever clone is registered. Where no remote-tracking ref
exists the local branch is used and the document says the picture is only as current as that clone.
Drift is counted in both directions and disclosed: commits the shared ref has that the clone lacks,
and commits the clone has that were never pushed. After Constat's own push it refreshes that one
remote-tracking ref in the registered repository. It never runs `git pull` anywhere.

**Context.** CON-69 let `rule accept` land a ticket's branch, and CON-76 is the half that was
missing. The merge is made in a throwaway clone and pushed, so the repository someone actually works
in never learns of it: `237feed`'s local `main` sat two commits behind `origin/main` immediately
after landing 628. Measured against the local branch, a ticket that had shipped kept reading
`pending` — D-031's status misreporting the one thing it exists to say. The drift is cumulative and
self-inflicted: one merge per landed ticket, and nothing in Constat fetched.

**Why not a pull.** Pulling writes to a working tree that may hold uncommitted work, sit on another
branch, or be mid-rebase. That is the reason CON-69 merges in a clone, and it does not stop being
the reason here. The refresh updates one ref under `.git` and touches nothing else.

**What this changes in meaning.** "Landed" now means *in the mainline the team shares*, not *in this
clone's branch*. Work committed to a local `main` and never pushed therefore reads as not yet
landed, which is true and surprising — two existing tests asserted the old reading and were
corrected. The surprise is answered by disclosure rather than by softening the rule: the document
states how many local commits are not on the shared ref and that work in them reads as unlanded.

**Consequences.**

- **`resolve_mainline` resolves, never assumes.** It verifies the remote-tracking ref exists and
  falls back explicitly, in the posture `resolve_default_branch` set for D-028. A local-only
  repository is valid and is reported as such, not presented as mainline.
- **The ref is carried on the finding, not re-derived at render time.** A document must report the
  ref the comparison actually used, including the status line: "already in `origin/main`" rather
  than "already in `main`", so a reader checking the claim looks at the right ref.
- **Disclosure is a signal, not boilerplate.** A clone in step with its remote says nothing beyond
  naming the ref. Only real drift prints.
- **A failed refresh is not a failed landing.** The merge is on the remote either way;
  `MergeResult.refreshed` is False and the detail says the ticket will read as unlanded here until
  something fetches. `None` means nothing landed, so there was nothing to catch up with — "not
  applicable" and "tried and failed" are different states.
- **Staleness no write can fix stays CON-38's job.** A repository someone else pushed to is stale
  the moment they push, and only saying how old the picture is addresses that.

**Status.** accepted.

---

## D-067 · 2026-11-14 · A repair states its rule rather than naming one

**Decision.** A reading whose `relation` is `repairs` must not carry `revises`. It states the rule
it repairs, in full, and is refused if it names a catalogue id instead. `revises` keeps its one
meaning: the rule's statement is changing.

**Context.** CON-73 implemented D-065 and ran into a question D-065 did not settle. A repair of a
rule *already in the catalogue* has nowhere sensible to land: accepting it would baseline a second
version with an identical statement, which makes `rule history` a log of conformance events wearing
the shape of rule versions. Those are different things, and D-029's split exists so that a version
means "the rule said this".

**Why narrow rather than solve.** The valuable case D-065 names is the rule nobody wrote down —
"your catalogue is missing this, and production was breaking it" — and that case needs no id,
because there is nothing to point at. Supporting the other case properly means a conformance record
of its own, against the rule, which is a bigger design than this ticket. Refusing it keeps the
mechanism honest and the question open, rather than answering it by accident with a duplicate
version.

**Consequences.**

- **A repair of a known rule is still reportable, through the existing path.** The reading states
  the rule; CON-70's anchor overlap then warns that it matches rule N, and the reviewer collapses
  the two. Less direct than an id, and it loses nothing a person cannot see.
- **The refusal is explicit, not a silent drop.** A reading that sends both halves is told which to
  remove. Discarding one half would store a claim the reader did not make.
- **What is deferred is named.** A conformance record against an accepted rule — "the code was
  found violating this on date D, and repaired" — is the thing to build if the narrow form proves
  too narrow.

**Status.** accepted.

---

## D-066 · 2026-11-14 · A rule statement is purely business, always

**Decision.** A rule's statement and its behaviours contain nothing technical: no class, method or
field name, no file, no endpoint or status code, no table, index or column, no framework, database
or library, and no condition only a developer could evaluate. The test is one question — *would
someone in the business have an opinion on this sentence, read aloud?* — and it is stated that way
in `WHAT_A_RULE_IS` rather than as a list of prohibitions.

**Context.** Ticket 628 was read through the MCP loop and produced three proposals. Two should not
have existed: one was an allocation-set leak described as a rule, and one carried the cause of a
concurrency bug inside its sentence. The catalogue is meant to be readable by the business audience
product rule 8 names, and a catalogue of repaired mechanisms is not that.

**What is enforced, and what is not.** Leakage is refused **mechanically** — `constat/ai/statements.py`
matches an identifier, a qualified name, a path, a snake_case token, an annotation, a call, an HTTP
verb, inline code — and the refusal names the offending token so the reading knows what to remove.
Whether a sentence is *business-oriented* is a judgement, and guessing at judgements is what this
product refuses to do everywhere else. The sentence that caused this decision contains no code
token and passes every check; the guidance and the reviewer are what stop it. That division is
stated out loud, in the module and in its tests, so nobody later mistakes the check for a quality
guarantee.

**Consequences.**

- **The detector errs toward allowing.** A false refusal discards a reading a person might have
  accepted, and the reader cannot argue. So every pattern needs two signals or an unambiguous one:
  `AdSense`, `GitHub` and `iPhone` carry one internal capital and pass; `findOrCreateDevice` and
  `PostgreSQL` carry two and do not. A status code is matched only through the word HTTP, because a
  bare three-digit number is money far more often — "a transfer above 500 euros is refused" is the
  canonical business rule, not a leak.
- **Behaviours are tested too.** A clean statement with behaviours naming classes is still a
  technical record of a rule.
- **A bug fix usually establishes no rule.** The guidance now says so: a fix restores conformance
  to a rule that was already true, and often never written down. Until D-065 is built, the correct
  output for a pure repair is no rules at all.
- **An existing rule is unaffected.** The catalogue is append-only (D-048) and this gate runs at
  parse time, so nothing already accepted is re-judged. Rule 1 passes the check anyway.

**Status.** accepted.

---

## D-065 · 2026-11-14 · Evidence can repair a rule, and the repair reaches the review queue

**Decision.** A reading may report that evidence **repairs a violation** of a rule that was already
true, rather than establishing a new one. It reaches the review queue as the rule it repairs —
including a rule nobody had written down — marked as repaired. Acceptance stays the only way a rule
enters the catalogue (D-048). The repair claim is provenance *about the code* and is carried
alongside the rule, never inside its statement, because product rule 3 requires implementation
evidence to stay distinguishable from the rule it supports.

**Context.** A proposal could stand in only two relations to the catalogue: it establishes a rule,
or it revises one. A bug fix is neither. Ticket 628 fixed a first-launch failure affecting ~3% of
new installs; the product always intended a first launch to work, so there was no new business
knowledge in the commit — only new knowledge about whether the code honoured knowledge already
held. With no way to say that, the reading invented rules out of the repair.

**Why the queue rather than a document note.** A repair that proposed nothing would be an assertion
Constat made with no human decision behind it, which is what D-048 exists to prevent. Routing it
through the queue keeps one mechanism and one door. The cost is that a rule version carries a claim
about code fidelity, which is why the claim sits beside the statement rather than in it.

**Consequences.**

- **The valuable case is the unwritten rule.** "Your catalogue is missing a rule, and production was
  breaking it" is a stronger claim than any new-rule proposal, and today the violation half is
  discarded.
- **Not yet built.** CON-73 carries it: a relation on the proposal, a schema 10 migration, guidance
  naming the three relations, and a document rendering that distinguishes a repair from a new rule.
- **Until then, a repair returns no rules.** D-066's guidance says so explicitly, and that interim
  answer is correct rather than a stopgap: no rules is better than a manufactured one.

**Status.** accepted.

---

## D-064 · 2026-11-14 · A duplicate rule proposal is reported, never refused

**Decision.** When a submitted reading overlaps a rule proposal nobody has decided yet, both are
stored and the overlap is **reported** — to the reviewer as a warning, and to the next reader as the
ticket's queue inside the payload. Nothing is discarded, merged or deduplicated. `revises` stays
what it was: a claim about a *catalogue rule*, never about a pending proposal, because a proposal is
not yet a rule and has no version to append to.

**Context.** CON-70, found by running ticket 615 through the MCP loop on 2026-11-14. Two
independent readings of one commit produced near-identical proposals and `submit_rules` reported
`possible_duplicates: {}`, because `candidates_for` queries the `anchor` table — accepted rules
only — and the payload showed `catalogue` but never the queue. Every re-run of a ticket cost the
reviewer another decision for a rule they had already read.

**Why reporting rather than refusing.** Convergence is evidence. Those two proposals agreeing is
what validated `guidance.py` in the first place: two readings reaching the same business sentence
from the same commit is the strongest signal available that the guidance constrains the output
rather than the model's instincts carrying it. A product that discarded the second would have
destroyed its own validation. Deduplication is also a judgement about meaning — the thing this
product never makes on a person's behalf (D-050 for anchors, product rule 4 for acceptance).

**Consequences.**

- **Two separate reports, never merged.** `candidates` holds catalogue rule ids, `pending_candidates`
  holds rule proposal ids, and both are plain integers. A reviewer told "overlaps 1" cannot act
  without knowing which table indexes it: one invites a revision, the other asks for two proposals
  to be collapsed. The MCP tool keeps them as `possible_duplicates` and
  `possible_duplicate_proposals` for the same reason.
- **The queue reaches the reader as `pending`, beside `catalogue`.** Scoped to the ticket: a
  duplicate only matters against the evidence being read now, and the whole workspace's queue would
  bury the one entry that matters. `PendingProposal.proposal_id` is deliberately not named
  `rule_id`, so a reading cannot mistake it for something to put in `revises`.
- **Decided proposals are not reported.** An accepted one became a rule and `candidates_for` finds
  it there; a rejected one was found inconclusive, and another reading of the same evidence is
  exactly what D-036 expects to follow.
- **Collapsing a duplicate is `rule reject`.** Which is correct under D-036 rather than a
  workaround: a duplicate reading is inconclusive, not wrong.

**Status.** accepted.

---

## D-063 · 2026-11-14 · Opening a ticket is not a governance act, and `gather_evidence` may do it

**Decision.** `gather_evidence` opens a ticket for a reference the workspace does not know, **when
the registered repositories recognise that reference**. A reference matching no commits anywhere is
refused with `ReferenceMatchedNothing` and no ticket is created. The MCP tool passes
`open_if_absent=True`; the library default is `False`, so the CLI keeps its refusal.

**Context.** The agent's own workflow failed at its first step. `gather_evidence` raised
`no ticket '622'` unless a person had already run `constat ticket add 622` at the command line — a
prerequisite nothing in the MCP interface mentioned, on the path the product recommends (D-045,
D-060). CON-64 was found by trying to use it, not by reading the code.

**Why this is compatible with D-055.** The load-bearing argument is not that a ticket carries no
authority, though it does not: it is that **the tool list does not grow**. `EXPOSED_TOOLS` is the
same four it was, acceptance is as absent as ever, and what changed is that an existing tool no
longer has an unstated precondition. D-055's list is deliberately short and every addition to it
has to be argued; this is not an addition. `ticket add` already gathered immediately, so no
capability exists here that the agent did not already have one command later.

**Consequences.**

- **The search has to run before the ticket is opened**, which is why the guard moved out of
  `collect` behind `require_ticket`. The search was always read-only; the guard was about who may
  act on the result, not about safety.
- **`LANDED` counts as recognition.** It contributes no evidence and is still a match (D-031) —
  work found in mainline is work, and a ticket for it is about something real.
- **A repository that could not be read is not evidence of absence.** It reports `NOT_FOUND` with an
  `error` set, indistinguishable by status from a genuine miss. A reference seen by nothing and
  unreadable somewhere is therefore refused with the unreadable repositories *named*, and the
  message says explicitly that this is not a claim the reference is absent from them. Product rule 1
  applied to a refusal rather than to a report.
- **The refusal it replaces had to survive, in a narrower form.** Opening a ticket for a typo would
  be worse than failing: `ticket add` refuses a duplicate, so the empty ticket could never be
  opened again. `ReferenceMatchedNothing` subclasses `NotRegistered` so the exit code and every
  existing handler are unchanged.
- **Only the gathering step may do this.** `get_payload` and `list_rule_proposals` still refuse an
  unknown ticket, and `constat document <REF>` still refuses at the CLI. A person who mistypes a
  reference should be told, not handed a new ticket.
- **Who opened a ticket is deliberately not recorded.** That would need a column on `ticket` and a
  schema 10 migration, and by the argument above a ticket's origin is not a governance fact. If a
  later ticket wants it, it is a migration and not a redesign.

**Status.** accepted

---

## D-062 · 2026-11-14 · Accepting a rule proposal may land the ticket's branch

**Decision.** A workspace setting, `merge_on_accept`, decides whether `rule accept` also merges the
ticket's branch into each registered repository's default branch and pushes it. Default `off`. When
on, the merge is made in a **temporary clone of the remote** and lands by pushing; the registered
repository is never written to. Every ambiguity refuses: a conflict, two branches naming the
ticket, a branch absent from the remote, no remote, no git identity. A refused merge exits 7 and
**never unwinds the acceptance**.

**Context.** Until now acceptance wrote to the workspace and nothing else, and `publish` was the
only command that wrote outside it (D-058). This is the second such command and the more
consequential one: a push to mainline is seen immediately by everyone who pulls, and no later
Constat command can take it back. It was asked for directly, after the alternatives — accept then
publish, or opening a merge request instead — were put and declined.

**On the number.** This entry takes `D-062`, which CON-64 reserved when it renumbered itself to
`D-063` rather than claim a number another session was already citing. The log is now contiguous
again.

**What this amends.** Product rule 7 (security by design: read-only, least privilege) held for
every path into a subject repository. It no longer holds for this one, and the amendment is stated
here rather than left for a reader to infer from the code. Rules 1–6 and 8 are untouched, and
product rule 4 is the reason the setting exists at all: generated content is a proposal, so the act
that promotes it must be one a person chose, including its side effects.

**Consequences.**

- **Off by default, and an existing workspace is inert.** Silence is not consent to a push. A
  workspace that never answered the question behaves exactly as it did before.
- **The branch is evidence, not an argument.** It comes from `branches_naming` — the same
  branch-name attribution D-030 uses to decide which commits belong to a ticket — so nothing is
  merged on the strength of a name typed into this command. Two candidate branches refuse rather
  than one being chosen.
- **The write lives in one module.** `constat/git/merge.py` is the only writer in `constat/git/`;
  `adapter.py` keeps its read-only guarantee intact, which is what makes the boundary auditable.
- **A failed merge leaves a recorded acceptance and an unmerged branch.** That asymmetry is
  deliberate. The acceptance is a human decision and a git conflict is not grounds to discard it;
  the reverse — unwinding a decision because a merge failed — would let the state of a repository
  overrule a person.
- **No credentials are stored.** The push uses git's own credential helper or SSH agent, with
  `GIT_TERMINAL_PROMPT=0` so a missing credential fails rather than hanging.

**Status.** accepted.

---

## D-061 · 2026-11-13 · The decider's name may be inferred, and the record says that it was

**Decision.** `--by` is optional on `rule accept` and `rule reject`. Omitted, the decider is taken
from git's configured identity and `rule_proposal_decision.attribution` records `inferred`;
supplied, it records `stated` (schema 9). Every view that shows who decided shows which.

**Context.** `--by` was mandatory with no default, on the reasoning that a decision with no decider
is not a decision. That reasoning survives. What did not survive examination is the idea that
typing a name made it *stronger*: `--by` is a free string nobody checks, so a typed name and a name
read from git config are **equally unverified**. The mandatory flag bought friction, not
assurance.

**What this is not.** It is not a trust level, and `inferred` is not weaker than `stated`. Nothing
here proves who ran the command — an agent with shell access can run either form. The distinction
recorded is narrower and more honest: whether a person asserted this name or a machine supplied it.
A reviewer reading a decision a year later is entitled to know which, and that is product rule 3
applied to the decision itself rather than to the claim it approves.

**Consequences.**

- **git config, not `$USER` or the OS login.** Those name an *account*: `padjis` is not who decided
  anything, while `user.name` is what this person already chose to be called in a record of who did
  what. With no git identity configured, Constat **refuses** rather than falling back — "who
  accepted this rule" is the last question to answer with a guess (D-028's posture).
- **Existing decisions migrate to `stated`.** They were typed, so that is what happened.
- **This is not CON-58's `channel` and `verification`, and must not be confused with them.**
  `channel` will say *where* a decision was made — CLI, a forge approval, a page edit — and
  `verification` whether anything attested to it. A forge approval is genuinely verified; nothing
  on the CLI is. `attribution` is finer than both and sits inside the CLI channel.
- **It does not make an MCP `accept` tool any more acceptable.** The objection there was never the
  name: it is that the agent which wrote the proposal would be accepting its own proposal, and
  inference does nothing about that. D-055 stands until a verified channel exists (CON-58).
- **A naming collision was found and fixed while building this.** `StoredRuleProposal.attribution`
  already meant who *read* the evidence (D-057). The decider's is `decided_attribution`. Two
  different people and two different questions: the reader of the evidence, and the authority over
  the result.

**Status.** accepted

---

## D-060 · 2026-11-13 · Who reads the evidence is a workspace setting, not a per-command flag

**Amends D-059 one day later, after using it.** The refusal stays; the way it is answered changes.

**Decision.** `setting.reader` is `mcp` or `provider`, stored in the workspace (schema 8). With
`mcp`, no rule-generating command asks for a provider. `constat init --reader mcp` sets it at
creation and `constat config reader mcp` changes it afterwards; `--no-provider` survives as a
per-run override.

**Context.** D-059 made `ticket add` and `document` refuse when nothing could read the evidence,
and the signal for "something else will read it" was `--no-provider` on every invocation. That
punished the **recommended** workflow: on MCP the host supplies the model (D-045), so having no
provider is correct rather than a fault, and a user on that path met a refusal on every ticket.
The first version of the message did not even list MCP among the ways forward.

**The modelling error, which is the real content of this entry.** How evidence gets read is a
property of a *setup*, not of an invocation. Nobody alternates between an agent and a provider from
one ticket to the next; they choose once and keep it for months. Asking per-command for an answer
that never changes is the defect — not the refusal, which still catches the case it was built for.
A flag that is passed every single time is a configuration value wearing a flag's clothes.

**Consequences.**

- **Settings are not append-only**, unlike everything else in this store. A setting says how the
  workspace is *operated* and never what anyone *decided*, so keeping a history of changes would
  imply an authority it does not have. The one table that may be updated in place is the one
  carrying no governance meaning.
- **The default is `provider`, the strict one.** A workspace that never said how it reads keeps
  D-059's refusal, and turning it off is deliberate. Defaults should lean towards the refusal.
- **Existing workspaces migrate to `provider`.** Setting them to `mcp` would silently switch off a
  refusal someone may be relying on — a migration must not change behaviour on a guess.
- **The refusal now teaches the cure.** It names `constat config reader mcp` first, so the one time
  an MCP user meets it, they fix it permanently rather than learning a flag to repeat.
- **`--no-provider` stays**, for the genuine one-off: gathering evidence on a provider workspace
  without spending anything. It is no longer the mechanism for an entire workflow.
- **Constat still cannot infer this.** `ticket add` on a machine with no provider looks identical
  whether an agent is about to read the evidence or the key was forgotten. The setting is the
  answer because there is no way to deduce one.

**Status.** accepted

---

## D-059 · 2026-11-12 · A rule-generating command refuses when nothing can read the evidence

**Amends D-003 and D-041 at the command boundary.** Neither is superseded: both remain true of the
library, and the MCP server depends on them.

**Decision.** `constat document <REF>` and `constat ticket add <REF>` **refuse with exit 5** when
`CONSTAT_AI_PROVIDER` is unset, naming the three ways to proceed. `--no-provider` gathers the
evidence and nothing else, explicitly. `ProviderRequired` is the new error type.

**Context.** D-041 established that a *misconfigured* provider must fail loudly rather than being
downgraded to the null provider, and that has held: an unimplemented name and a missing credential
both exit 5. The case it left succeeding was *nothing configured at all*, where the document said
"no rules were identified — no AI provider is configured". Accurate, and useless to someone who ran
the command in order to get rules. The complaint that produced this was exactly that: the step that
should generate rules did not fail when it could not.

**The tension, stated rather than glossed.** `CLAUDE.md` prohibits an AI dependency in the critical
path and requires the pipeline to work with no provider configured. That requirement is kept, and
is now something the user says out loud with `--no-provider` instead of something they discover
from a line in the output. The guarantee was never that the *command* succeeds silently; it was
that the evidence path does not need a provider, and it still does not.

**Consequences.**

- **The refusal is at the command boundary, not in `gather`.** `operations.gather` still runs with
  the null provider and 77 library tests still call it that way, because they are about evidence.
  Moving the refusal into `gather` would have made the library unusable without a key and broken
  the MCP server, where having no provider is *correct*.
- **MCP is deliberately exempt.** On that path the **host** supplies the model (D-045), so Constat
  having no provider is the design rather than a misconfiguration. `gather_evidence` does not
  refuse, and a test asserts it.
- **`ticket add` checks before it creates the ticket.** A refusal that left an opened ticket with
  no evidence would be worse than no ticket, because `ticket add` then refuses to open it again.
- **The default changed, so a scripted `document` in anyone's pipeline starts failing.** Accepted
  deliberately: a script that was quietly producing documents with no rules in them was not doing
  what its author believed. The fix is one flag.
- **`--no-provider` is not `--no-ai`.** It says "do not expect rules from this run", which is also
  the honest way to run the export path: `document <REF> --no-provider --payload`.

**Status.** accepted

---

## D-058 · 2026-11-12 · A document is published through a port, and publishing is egress

**Implements CON-57.** Amends `PRODUCT_SPEC.md` § 6.2 and `ARCHITECTURE.md` § 6, both of which
asserted that Constat never writes outside its workspace.

**Decision.** `constat publish <REF>` writes the stored document to a documentation target.

1. **A `Target` port, not a GitHub client.** `publish/port.py` declares `publish(reference, body)
   -> PublishedRef` and `read_decisions(ref)`. Confluence, GitBook and GitLab docs arrive behind
   the same protocol as optional extras (CON-59). Only `publish` is implemented here;
   `read_decisions` raises `DecisionsNotReadable` until CON-58, because a port whose second half
   silently returns nothing would read as "nobody has decided".
2. **The default target is derived from the repository's remote, and never guessed.**
   `remote_url()` joins `resolve_default_branch()` as the second read-only fact taken from a remote.
   A recognised host maps to its wiki; an unrecognised one **refuses** and asks for `--target`, the
   same posture D-028 took for the default branch. A wrong guess here publishes a team's business
   rules somewhere nobody expected.
3. **Publishing goes through the credential gate.** `guard_publication` is a second entry point to
   the scanner that already guards the provider and export paths (D-047), sharing `_scan_line`
   rather than re-deriving detection. A document carries commit subjects and diff excerpts, and a
   published page is the one egress that cannot be recalled: the model path at worst sends a
   credential to a provider under contract, while this one can put it on a wiki the whole company
   reads.
4. **Each publication is a `run` and an `operation`** of kind `publish_document`, so where a
   document went is attributable (D-029, D-049) — recorded *after* the write succeeds, because an
   operation row for a publication that failed is a false record of disclosure.

**Context.** Everything until now lived in a local SQLite file, and rules were accepted in a
terminal. Product rule 8 requires serving a business audience, and that audience is not in a
terminal. The gap was found by asking where acceptance was expected to happen and discovering the
answer was nowhere.

**Consequences.**

- **Constat stores no credential for this.** Git's own authentication applies — SSH agent, or a
  credential helper the user already configured — and `run_git` inherits the environment. Nothing
  is written to a file in this repository, and no new secret-bearing config exists.
- **The subject repository is still read-only.** Publishing writes to a documentation target, never
  to the repository the evidence came from. `gather` cannot reach this code at all.
- **Publishing is explicit.** There is no `--publish` flag on `gather` and no automatic publication
  on acceptance. A document leaves the machine when someone runs one command that does nothing
  else, because "it published when I didn't expect it to" is unrecoverable.
- **A published page is a proposal, not an approval** (product rule 4). The page carries the review
  queue as an inert task list and says so, exactly as the pull-request body does (D-056). Reading
  ticks back is CON-58, and when it lands it is the *unverified* channel.
- **Overwriting a page is the normal case**, and it is the right one: a document is a living view
  of one ticket. The durable record is the workspace, where `document_version` is append-only. The
  page is a view, which is D-004 applied one layer out.
- **`run_git` now runs write commands.** It did not before. Writes are confined to a clone Constat
  made itself in a temporary directory, so a failure cannot leave a user's working tree dirty.

**Status.** accepted

---

## D-057 · 2026-11-12 · The first real provider, and a model id Constat resolved itself

**Implements CON-60.** `CONSTAT_AI_PROVIDER=anthropic` makes `constat ticket add 622` read its own
evidence and fill the review queue, with no `rule submit` step.

**Decision.** Three parts.

1. **`constat/ai/providers/anthropic.py` implements the `Provider` protocol** and is registered in
   `PROVIDERS` and `CREDENTIAL_ENV`. It is reached only through `resolve()`, so the null provider
   stays the default and the pipeline still runs end to end with nothing configured (D-003).
2. **The model is configuration, not an argument.** `CONSTAT_AI_MODEL` overrides a default of
   `claude-opus-5`. No `--model` flag is added to `gather`; a reading's model is not something the
   person running a command should be able to misstate.
3. **Schema 7 adds `rule_proposal.model_attested`.** On the provider path Constat made the call, so
   it records the model id **the API response returned** and marks it attested. On the
   `rule submit` path the value is whatever the caller claimed, and stays unattested.

**Context.** D-045 made every recorded model id self-reported, because every reading arrived from
outside: `--provider claude --model opus-5` is a string a caller types, and Constat had no way to
check it. The queue says so — `read by claude (opus-5) (self-reported)`. Once Constat issues the
request itself that caveat becomes false in one direction and still true in the other, and a single
undifferentiated label would understate the provider path and overstate the submit path at the same
time. Product rule 3 is about keeping provenance distinguishable; this is the same distinction one
level down, inside the provenance itself.

**Consequences.**

- **The requested model and the resolved model are not the same fact.** `claude-opus-5` is an
  alias; what is stored is `response.model`. A proposal recorded six months ago must still name the
  model that read the evidence, and an alias would quietly re-point (product rule 5).
- **A provider failure raises; it never returns an empty `Interpretation`.** `ProviderFailed`
  joins `MalformedResponse` under `ProviderError`. An empty result would reach the document as "no
  rules were identified" — D-041 and D-046 refused exactly this, and a network timeout is not a
  finding about the code.
- **`anthropic` is an optional extra, not a dependency.** `pip install constat` installs no HTTP
  client, and the SDK is imported inside the factory rather than at module scope, so registering
  the provider does not import it. `CLAUDE.md`'s prohibition is on an AI dependency in the critical
  path, and the critical path is the evidence path.
- **The credential is read from the environment and never written anywhere**, per `settings.py`.
  Nothing about the key reaches the workspace; the provider name and model do, because a reviewer
  needs them.
- **This costs money per ticket**, which is why it was deferred rather than missing. It is opt-in
  through an environment variable that defaults to off, so no existing workflow starts billing.
- **Pre-migration rows have `model_attested = 0`.** Not backfilled: nothing can retroactively
  establish who read evidence a year ago. Same honest gap as `operation.run_id` (D-049).
- **The reply contract is JSON, parsed by the existing `parse`.** Structured outputs would make
  `MalformedResponse` unreachable on this path, which is worth doing later; it is not done here
  because `parse` also performs the grounding check and that has to run either way.

**Status.** accepted

---

## D-056 · 2026-11-12 · The document renders from stored state, and works as a pull-request body

**Closes CON-09's core.**

**Decision.** `render()` takes a `CatalogueView` — impacted rules, unclaimed paths, the review
queue, the catalogue size — read from the workspace. The document leads with a **business** section
and puts the evidence under its own `## Evidence` heading. The current run's own result is labelled
**"This run:"**. The whole document is plain Markdown and usable as a pull-request body; the review
queue renders as a GitHub task list.

**Context.** The body rendered from the current run's `Interpretation`, so `constat document 622
--show` printed *"no rules were identified"* while the catalogue held a rule at version 3 and that
ticket had rule proposals waiting. A statement about configuration, presented as a statement about
the code — product rule 1's failure mode, in the product's own output.

**Consequences.**

- **Rendering stays a pure function of stored structure** (ARCHITECTURE.md § 2). The view is passed
  *in*; `render` takes no workspace and so cannot discover a fact the store does not hold. A test
  asserts the signature.
- **Rule proposals are now stored before the body is rendered.** They were stored after, which left
  the queue a run behind: a reader saw "1 rule proposed" and an empty queue in the same document.
- **The business half is never trimmed.** `bound_for_pr` drops the evidence section when the
  document exceeds GitHub's 65,536-character body limit and *states* the omission with the command
  that shows it in full — because GitHub truncates silently, which is the failure D-023 refuses for
  diff excerpts one level up. A real 30-commit document measures ~21 KB, so this bites only on
  large tickets.
- **Plain Markdown, no raw HTML.** No `<details>` however useful, because the same document has to
  render in Confluence and GitBook later (CON-59). Asserted in a test so it is not reintroduced.
- **A tick on the task list is inert and says so.** A checkbox that looks actionable and does
  nothing is worse than no checkbox. Reading ticks back is CON-58, and it is the *unverified*
  channel when it lands.
- **Unclaimed paths are listed one per line and never abbreviated.** A real ticket produced 29;
  "and N more" would hide the coverage gap that D-038 and D-039 require to stay prominent.
- A test that asserted the opposite was rewritten rather than deleted: it checked that a rule
  proposal *disappeared* from a regenerated body, which was the honest description of the old
  behaviour. It now asserts the stronger property — a later run with no provider still shows the
  reading, because it reads it back rather than remembering it.

**Status.** accepted

---

## D-055 · 2026-11-12 · The MCP server exposes four tools, and acceptance is not one of them

**Implements D-045.** `constat mcp` runs an MCP server on **stdio**.

**Decision.** Four tools: `gather_evidence`, `get_payload`, `submit_rules`,
`list_rule_proposals`. **There is no `accept` or `reject` tool**, and the tool list is asserted in
a test so the absence cannot be lost quietly.

The `mcp` SDK is an **optional extra** (`pip install constat[mcp]`), not a runtime dependency.

**Context.** `CLAUDE.md` prohibits marking a proposal approved without a recorded human decision,
and product rule 4 makes generated content a proposal rather than knowledge. A model that could
call `accept` would make both unenforceable — not by malice, but because the tool would be there.
Acceptance therefore stays a human act at the CLI, outside the agent's reach.

**Consequences.**

- **An absence is the easiest property to lose**, so it is tested on the *live* tool list rather
  than by reading the source. A tool added by a decorator anywhere shows up there.
- **Stdio, not HTTP.** The client spawns Constat as a subprocess and nothing listens on a port,
  which is what keeps this a local tool rather than the hosted service `PRODUCT_SPEC.md` § 6.2
  defers — and means no authentication layer, which § 6.2 also defers.
- **No tool reimplements an operation.** Every one calls the same function the CLI does, so the
  gates hold by construction: identity never crosses (D-040), the credential gate fires on
  `get_payload` because that *is* `export_payload` (D-047), and a submitted reading is grounded
  against re-gathered evidence (D-052). Tested through a real client, not only in process.
- **Constat's errors become `ToolError`, deliberately.** That is the SDK's "a failure you
  anticipated", and it keeps the message. Letting a `ConstatError` escape gets it wrapped as an
  unexpected crash and the client sees only "Error executing tool get_payload" — losing "remove
  the credential and rotate it", which is the only part worth sending.
- **The optional extra keeps the promise in D-003**: the evidence pipeline runs with nothing but
  pydantic installed, and a CLI user carries no protocol library they never run.
- **The server tells the model its output is provisional.** The instructions say nothing submitted
  is accepted and that no tool here can accept — a model that believes otherwise will present a
  reading as settled.
- The workspace is opened per call rather than held for the session: a session outlives any one
  operation, and a long-lived connection to a governance store is a lock waiting to be contended.

**Status.** accepted

---

## D-054 · 2026-11-12 · A reading may claim to revise a rule it was shown

**Closes the finding half of CON-43.**

**Decision.** The payload carries the catalogue — each rule's id, name, statement and anchors. A
reply may name `revises: <rule_id>`, and that claim is validated the way an anchor is: the rule
must have been in the payload. For readings that claim to be new, anchor overlap is computed and
**reported as a candidate**, never applied.

**Context.** A reading had never been shown what exists, so every reading claimed to be new and the
second reading of a rule created a duplicate — CON-43's failure arriving by a different route. The
missing piece was an input, not logic.

**Consequences.**

- **An invented `revises` is rejected like an invented anchor.** A reading cannot have read a rule
  it was never shown, so claiming a relationship to one is inventing it rather than observing it.
  The symmetry is deliberate: both are the model asserting something the evidence does not support.
- **A booleans check is not pedantry.** `True` is an `int` in Python and would otherwise pass as
  rule id 1.
- **Overlap warns and never decides** (D-050). A reading that claims to be new is stored as new,
  and the reviewer is told what it overlaps. Rewriting the claim would be exactly the structural
  key D-050 refused — and accepting a second rule on the same file is often correct, since one file
  routinely implements several rules.
- **A claimed revision is not flagged.** It already decided; warning about it would be noise.
- **An honest limit, asserted in a test.** Overlap is *identical glob string*, not glob
  intersection. A rule anchored to `rules.py` and a reading anchored to `**/*.py` overlap in
  reality and are not flagged. Widening it means comparing globs for intersection, which has no
  exact answer in general, and a warning that fired on every broad glob would be noise.
- The catalogue in the payload carries no identity, so D-040 is unaffected — it is the user's own
  rules, not evidence about people.

**Status.** accepted

---

## D-053 · 2026-11-11 · Accepting a rule proposal baselines a version; rejecting changes nothing

**Closes CON-44, and most of CON-43.** Schema 6.

**Decision.** `rule_version` is a frozen snapshot of a rule at the moment a human accepted a
reading of it, append-only by trigger. `rule` remains the current state — the same split
`document`/`document_version` already uses (D-029). Accepting a reading that claims to revise a
rule appends the next version; accepting one that claims to be new creates the rule at version 1.

**Rejecting changes nothing in the catalogue.** Under D-036 it means *inconclusive*, so there is
nothing to unwind, and a rejected reading can still be accepted later.

**Context.** Rule proposals could be stored but never acted on. D-037 required acceptance to be
per-rule and human; this is that act, and it is the only way a rule enters or changes (D-048).

**Consequences.**

- **Every rule version names the reading it came from** (`from_rule_proposal_id`), and that
  reading names the run whose evidence it read (D-049). A rule is therefore traceable to a diff
  without storing the diff.
- **A revision is a version, not a duplicate** — CON-43's done-when. It works because
  `revises_rule_id` is the reading's claim and a human accepting the reading accepts the claim
  (D-050). Acceptance is the only place the claim takes effect.
- **A name may change between versions** and the rule stays one rule, which is what D-050's
  surrogate identity was for.
- **`rule` is mutable and that is deliberate**, for the same reason `document.body` is: it is the
  working view, and the durable record is the frozen version beside it. Behaviours and anchors are
  replaced on acceptance; their history lives in `rule_version_behaviour` / `_anchor`.
- **Accepting twice is refused** — it would baseline a second identical version.
- **A claim to revise a rule that does not exist cannot even be recorded**: the foreign key refuses
  it. `Review._target_rule` refuses it again at acceptance, unreachable while the key holds and
  kept because the alternative — silently creating a *new* rule when the reviewer accepted a
  revision — is exactly the duplicate CON-43 exists to prevent.
- **`--by` has no default.** There is no way to accept without naming who decided, which is the
  no-automatic-approvals prohibition expressed in the argument parser.
- Rules that predate acceptance keep no version. They were never accepted, and inventing one would
  fabricate an approval.

**Status.** accepted

---

## D-052 · 2026-11-11 · A submitted reply is grounded against re-gathered evidence

**Decision.** `constat rule submit <REF>` takes a reply produced outside Constat and stores the
rule proposals that survive grounding. Three rules shape it:

1. **The evidence is re-gathered, never taken from the caller.** Grounding is checked against what
   Constat can see now.
2. **No credential gate.** The payload is rebuilt locally and never transmitted, so there is
   nothing to refuse. The gate belongs on egress (D-047).
3. **Nothing is accepted.** Submitting fills the review queue; the catalogue is untouched.

**Context.** D-045 made the host supply the model, so Constat needs an inbound path. `parse` takes
`(text, payload)` and does not care where the text came from (D-046), so everything after the reply
is the provider path's machinery unchanged.

**Consequences.**

- **A caller cannot widen its own grounding set.** If the payload came from the caller, a reply
  could ship a payload that makes any anchor look grounded — the check would verify the reply
  against itself.
- **Parsing happens before the run is opened**, so an unusable reply leaves no empty event behind.
- `provider` and `model` are self-reported and recorded as such (D-045). Nothing verifies them.
- **Discards are printed before the kept count.** A reader shown only what was stored has been told
  a shorter truth than what happened (D-046).
- **One matcher, shared.** Grounding and catalogue matching now both use `constat/globs.py`. Two
  matchers that disagreed would accept a rule proposal at submit time and then never match it to a
  change, or the reverse.
- **`**/x.py` also matches at the root.** Plain `fnmatch` requires a directory after `**/`, so a
  model writing the most natural "this file anywhere" glob would have been rejected as ungrounded.
  A false rejection here is the same failure as a false credential positive: it teaches people to
  stop reading the rejections.
- The document body still reflects the run that wrote it, so a submitted reading is stored but not
  rendered there. `rule proposals <REF>` shows the queue; rendering from stored readings belongs
  with the display work.

**Status.** accepted

---

## D-051 · 2026-11-11 · A rule proposal is stored append-only; its decision is a separate record

**Implements D-048 and D-050.** Schema 5.

**Decision.** `rule_proposal` stores each reading with its run, its self-reported reader
(`provider`, `model`) and its claim about which rule it revises. `rule_proposal_decision` stores a
human's answer separately. Both abort `UPDATE` and `DELETE` by trigger; so does `rule`.

**Context.** A rule proposal previously lived for one `gather()` call and was rendered into a
document body that the next run regenerates — so a reading could not survive long enough for
anyone to accept it. D-037 makes acceptance per-rule and human, which requires durable
pre-acceptance state.

**Consequences.**

- **A decision does not mutate the reading**, the shape `document_version` uses (CON-31).
  Accepting leaves the reading exactly as the reviewer saw it.
- **Changing one's mind appends.** Both decisions stay visible; the latest is what displays.
  History rather than a correction to be hidden (product rule 5).
- **`revises_rule_id` is nullable and is a claim, not a key** (D-050). Null means the reading
  claims to be new.
- **An anchor naming an unregistered repository keeps its glob and loses its scope.** Losing the
  reading would be worse than losing the scope.
- **`rule.name` lost `UNIQUE`,** which needed rebuilding `rule` plus its two cascading children —
  dropping the parent alone would have taken the catalogue with it. Verified: a real v4 workspace
  migrated with its rows intact.
- **One half has not moved.** `Catalogue` is still name-keyed: `add_rule` keeps an
  application-level duplicate guard and `find` looks up by name, so two rules cannot yet share a
  name through the API even though the schema allows it. That guard is a leftover of the pre-D-050
  model and goes when the catalogue becomes id-keyed and versioned (CON-43). Recorded rather than
  quietly left.
- Acceptance does not yet write into the catalogue — that needs the versioned rule table, and
  lands with the acceptance flow (CON-44).

**Status.** accepted

---

## D-050 · 2026-11-11 · Anchors match a rule; they do not identify it

**Decision.** A rule has a **stable surrogate identity** that survives renames, restatements and
anchor drift. Anchors are the **candidate matcher**: overlapping anchors mean "this rule proposal
may revise that rule". Whether it actually does is an **AI judgment carried as
`ai_interpretation`**, accepted or rejected by a human like any other interpretation — not a
database key.

`rule.name` loses its `UNIQUE` constraint. A name is a label that may change between versions, not
an identity.

**Context.** Identity had to come from somewhere, and the name is the wrong place: AI-generated
names drift between runs, so a `UNIQUE` name would fork one rule into two whenever the wording
changed. Anchors are the better signal — a rule is identified by where it lives rather than what it
is called.

But anchors cannot be the key. **One file routinely implements several business rules** — a
`limits.py` can hold both a daily transfer limit and a per-merchant cap — so an anchor-set key
would collapse distinct rules into one, failing in the opposite direction from duplicates. Path
globs are too coarse to be unique per rule, and making anchors finer (symbol or line level) would
be a change to the evidence layer for a benefit a judgment call already provides.

**Consequences.**

- **CON-43 becomes a proposal, not a lookup.** "Evidence contradicting a baselined rule proposes an
  update rather than a duplicate" is now: find candidates by anchor overlap, let the interpretation
  pass say which rule is revised, and let a human accept that. The hardest part of D-039 stays hard,
  but it stays *reviewable*, which a key would not have been.
- **A wrong match is recoverable.** It is a rejectable interpretation rather than a corrupted
  identity, so the failure mode is a bad suggestion instead of a merged pair of unrelated rules.
- **The match itself must be reported.** "This was treated as a revision of rule X" is a claim a
  reviewer has to see, for the same reason discarded rule proposals are listed (D-046). A silent
  match would hide the one judgment most likely to be wrong.
- A rule proposal records which rule it claims to revise; null means it claims to be new.
- The versioned rule table (CON-51, merged with CON-43 per D-048) hangs off the surrogate id, so
  supersession is independent of both the name and the anchor set.
- Several rules sharing an anchor is normal and expected, not a conflict to resolve.

**Status.** accepted

---

## D-049 · 2026-11-11 · A run has an identity; operations belong to one

**Decision.** Schema 4 adds a `run` table — one row per invocation that touched a document, with
its kind and start time — and `operation.run_id`. A gather opens one run regardless of how many
repositories it reads.

**Context.** A gather writes one `operation` row *per repository*, so no operation row can answer
"which run produced this". A rule proposal is a reading of the evidence one run gathered (D-046),
so it needs a single thing to reference. Nothing existed to reference.

**Consequences.**

- **Rows written before schema 4 keep `run_id` NULL.** Back-filling a run for them would
  fabricate provenance — they were written when runs did not exist, and saying so is the honest
  record. Verified on a real workspace: 7 pre-migration rows stayed NULL across the migration.
- **An export opens a run only when it accepted scan findings.** An export that found nothing made
  no decision, and recording it would put an empty event in the audit trail.
- A scan override joins the run whose evidence it let through — the override and the payload are
  one event, not two.
- `run_id` is on the result objects, so a caller does not have to re-query and guess which row is
  its own.
- This unblocks CON-51: a rule proposal can now say which run it read.

**Status.** accepted

---

## D-048 · 2026-11-11 · Rules are only AI-generated, and the catalogue is append-only

**Supersedes D-039's manual-command carve-out**, which kept `rule add` / `behaviour` / `anchor` as
a bootstrap and test path.

**Decision.** Two halves of one simplification:

1. **A rule enters the catalogue only as an accepted rule proposal.** There is no human-authored
   path. The `rule add`, `rule behaviour` and `rule anchor` commands go.
2. **A rule cannot be removed.** `rule remove` goes, `Catalogue.remove_rule` goes, and a
   `BEFORE DELETE ON rule` trigger aborts the operation — enforced by the database, not by the
   absence of a command.

`rule list` and `rule show` stay; they are read-only. `Catalogue.add_rule` and friends stay as the
*storage* API the interpretation path writes accepted rule proposals through — what is removed is
the human-facing surface, not the ability to store.

**Context.** D-039 already made AI the author and kept the manual commands only as scaffolding.
Keeping them meant two authorship paths, two provenance stories, and a question — "who wrote this
rule?" — that the taxonomy had to answer twice. Removing them deletes the question.

Removal went for a different reason. The project's own pattern is that integrity lives where it
cannot be bypassed: `document_version` aborts `UPDATE` and `DELETE` by trigger precisely so a
future bug cannot rewrite an approval by forgetting to call the right helper (CON-31). A catalogue
that can be emptied by a `DELETE` is protected by convention only.

**Consequences.**

- **Supersession replaces removal, and this is the load-bearing consequence.** CON-43 already
  requires that evidence contradicting a baselined rule *propose an update rather than a
  duplicate*. With no deletes, that update is a **new version**, not a mutation. A wrongly
  accepted rule is therefore permanent as *history* and replaceable as *current* — which is
  product rule 5 working as intended rather than a trap.
- **The rule catalogue needs the versioned shape `document_version` already has.** That makes
  CON-43 and CON-51 the same schema change: append-only versioned rules, written only by accepted
  rule proposals. Schema v4, with a migration.
- **A bootstrap gap, stated rather than discovered.** With the provider registry still empty
  (CON-41), nothing can put a rule in the catalogue, so `unmatched_paths` coverage is unreachable
  from the CLI until the interpretation path completes. Tests exercise it through the storage API
  directly. This is a real loss of a manual smoke path, accepted deliberately.
- 8 CLI tests covering the removed commands go with them; the 24 catalogue tests call the storage
  API and are unaffected.
- **"Rule proposal", never bare "proposal."** A rule proposal is a rule in a pre-acceptance state,
  not a separate kind of object — and after this decision it is the *only* way a rule comes into
  being, which makes the naming load-bearing rather than stylistic.

**Status.** accepted

---

## D-047 · 2026-11-11 · Every path where the payload leaves goes through one gate

**Decision.** `guard_release(payload, accepted=…)` is the single chokepoint for any path where the
payload leaves the process. It scans and raises `PayloadRefused` unless a human accepted the
findings for that run. `constat document <ref> --payload` is the first caller besides `gather`.

**An export refuses unconditionally**, where `gather` with no provider scans, reports and
continues. That asymmetry is the decision: a local run that transmits nothing can tolerate a false
positive, and an export cannot, because by the time it has printed it has left.

**Context.** D-044 gated the provider path, keyed on `provider.name != NULL_PROVIDER_NAME`. D-045
then created a second front door — the host supplies the model, so the payload has to be handed
out — and that door bypassed both D-040 and D-044 entirely. A gate covering one of two doors is
decoration.

**Consequences.**

- **It raises rather than returning a flag.** A caller that forgets to check a boolean still sends
  the payload; a caller that forgets to catch an exception does not.
- **Export writes nothing** except an override record. A reader that mutated the governance record
  would make the document depend on who looked at it.
- **An export override is recorded under its own kind** (`scan_override_export`), distinct from a
  send override. Two different disclosures; collapsing them loses which one a reviewer is seeing.
- **`collect()` is shared** by both paths, so a reviewer and a model cannot be looking at different
  evidence for the same ticket. A test asserts the two payloads are identical.
- **Any future egress path inherits this obligation** — a submit command that echoes the payload,
  an MCP resource, a debug dump. The gate exists so the answer is "call `guard_release`" rather
  than "remember D-040 and D-044".
- Verified on real data: Subject B exports cleanly with no identity field present; Subject A is
  **refused with zero bytes on stdout**, having real credentials in the window. Without this the
  export would have handed them to a third-party model.

**Status.** accepted

---

## D-046 · 2026-11-11 · A provider reply is parsed, grounded and refused — never silently emptied

**Decision.** `constat/ai/parsing.py` converts a provider reply into `RuleProposal`s under three
rules:

1. **A reply that cannot be parsed raises `MalformedResponse`** (exit 5), never returns zero
   proposals. Empty, prose, broken JSON, JSON with no `rules` key, and `rules` that is not a list
   are all errors.
2. **Every anchor must match a path actually present in the payload**, and any
   `repository_alias` must name a repository that was searched. An ungrounded proposal is
   rejected whole, with a reason.
3. **Rejections are reported** — in the `ParseResult`, on the `Interpretation`, in the document,
   and in the CLI summary.

**Context.** Rule 1 is D-041's principle applied one layer in: a parse failure that returns
nothing makes the document read "no rules were identified", which is a provider failure wearing
the costume of a finding.

Rule 2 is the one with teeth. A model will propose a rule anchored to a plausible-sounding path
whether or not that path was in the payload; storing it would mean the tool had **invented its own
evidence**, which is the exact inverse of product rule 2. Grounding is checkable for free, so it
is checked.

**Consequences.**

- **A rejected proposal keeps only its name and the reason.** The rest is unvalidated model
  output, and storing its text would put unattributable prose into a governance record.
- **One ungrounded anchor rejects the whole proposal**, rather than keeping the grounded half.
  Silently narrowing a rule the model meant more broadly is a different claim, not a smaller one.
- **An unanchored proposal is rejected**, because a rule with no anchors can never be matched to a
  future change (CON-40) — inert rather than merely incomplete.
- Code fences are unwrapped and bare-string anchors accepted. Pragmatism about how models
  actually reply; the content inside still has to parse and still has to ground.
- `name` and `statement` are length-bounded. An unbounded statement lets a model write a page of
  prose into a field a reviewer reads in a list.
- **This module is provider-agnostic on purpose.** It takes `(text, payload)` and does not care
  whether the text came from an HTTP response or from an agent in the same terminal — which is
  what makes D-045 cheap.
- Verified on both real subjects (30 and 72 grounding paths): a grounded reply is kept, an
  invented anchor is rejected, a prose reply is refused.

**Status.** accepted

---

## D-045 · 2026-11-11 · The agent-facing surface is an MCP server, not a skill

**Decision.** Constat's agent-facing surface will be an **MCP server**. A Claude skill is not the
target. The interpretation pass may therefore be driven by a *host-supplied* model rather than by
a provider Constat calls itself, and the `Provider` protocol (D-003, CON-41) is not the seam that
gets used in that mode.

**Context.** Two separate forces, and the second corrected an earlier recommendation of mine.

**Cost.** `CLAUDE.md` postpones the finished product's API calls until the workflow is validated,
and validation stands at zero discovery conversations (CON-26). If the host supplies the model,
the subscription is the inference and CON-42's HTTP client may never need to exist.

**Portability.** A skill is an *instruction-packaging format*, portable only to runtimes that
implement it — several surfaces, one vendor. **MCP is a protocol**, and is the mechanism that
actually crosses implementations. "Works across AI implementations" is an MCP question; a skill
was the wrong answer to it.

**Consequences.**

- **The prerequisite work is identical either way**, so the surface choice costs nothing to defer:
  a submit command that runs D-046's parser, a payload-export command, and provenance handling.
  The server is a thin shell over those.
- **A hole this opens, and a prerequisite.** Redaction (D-040) and credential refusal (D-044)
  currently gate on `provider.name != NULL_PROVIDER_NAME`. An export or submit front door would
  bypass both — the same gate must apply there, or D-040 and D-044 are decorative.
- **Provenance degrades, and must be recorded as degraded.** With a host-supplied model, the
  model's identity is *self-reported* by the client. That is nearer `assumption` than
  `observed_fact` and must never be stored as the latter.
- **Control inverts.** Constat stops orchestrating and becomes a service: it cannot guarantee an
  interpretation pass happened, only validate what it is handed. Acceptable, because it never
  trusted that output — grounding is checked (D-046) and acceptance is still human (D-036).
- **Approval is never exposed as a tool.** A model that can call `approve` would make the
  no-automatic-approvals prohibition unenforceable. Acceptance stays a human act outside the
  agent's reach.
- MCP over stdio is a local process, so this is not the hosted service `PRODUCT_SPEC.md` § 6.2
  defers — but it is new infrastructure, and the ticket needs agreeing before it is built.
- The portability *floor* remains the CLI: any agent can be told to run a command. A skill would
  only ever have been a convenience wrapper.

**Status.** accepted

---

## D-044 · 2026-11-11 · Credentials are detected by format; a refusal is overridable on the record

**Completes D-040**, which stopped identity crossing the provider boundary and stated plainly that
credentials in messages and diffs were not solved.

**Decision.** The payload is scanned for credentials before it is sent. Detection is by **known
format only** — issuer-specified prefixes and lengths, PEM headers, JWT structure, passwords in
connection strings, and credential-named assignments whose value survives a placeholder, code and
character-variety test. Entropy scoring is not used.

A payload with findings is **refused** (`PayloadRefused`, exit 5). The refusal is overridable with
`--accept-scan-findings`, which applies to one run only and is recorded in the document as a
`human_decision` and as a `scan_override` operation.

**Scanning runs on every run; refusal applies only when a provider would actually receive the
payload.** Those are deliberately separate.

**Context.** Entropy scoring catches more and is the wrong trade here. It fires on minified
JavaScript, lockfile integrity hashes and base64 assets, all abundant in the subjects. In a
governance tool a false refusal blocks real work until someone overrides it, and the second time
that happens the override stops being read. A detector that is nearly always right is worth more
than one that catches more.

**Consequences.**

- **The scanner must not become the leak.** A finding records repository, commit, path, line and
  detector — never the matched text. Anything else would copy the credential into the workspace and
  from there into every frozen version of the document, outliving the repository it came from. Four
  tests assert the secret is absent from the finding, the error message, the document body and the
  stored override record.
- **Separating scan from refusal keeps two things true.** A false positive cannot block a local run
  that sends nothing, and the scanner is not dead code until a provider exists — the mistake D-040
  avoided by running redaction on the default path.
- **An override with no record is the same as no scan**, so it is written to the document and to
  the operation log. It is per-run by construction: there is no stored state to make it sticky.
- **Refusal happens before `interpret` and before the document is written.** A partially written
  document would record evidence as if the run had succeeded.
- **Stated misses, in exchange for believable refusals.** A passphrase of one character class is
  not detected; nor is a base64 credential beginning with `+`; nor any credential with no
  recognisable shape. `scan` returning nothing is **not** a statement that the payload is clean,
  and the document says so rather than implying a clean bill of health.
- **Validated on real evidence, which changed the implementation.** A first pass over real commits
  produced a false positive — a `token`-named variable assigned an expression — and a second over a
  wider sample produced true positives. The code-expression rule exists because of the first; the
  second is why the feature exists. Per the repository owner's instruction, nothing identifying
  what was found is recorded in this repository: findings belong in a workspace, not in a public
  decision log.
- A "bare identifier" rejection rule was tried and removed: a real credential and a variable name
  are the same shape. Character-class variety does that work instead, with a stricter threshold for
  unquoted values, since quoting is the only available signal that a value is a literal — and it
  cannot be required, because a `.env` file has none.

**Status.** accepted

---

## D-043 · 2026-11-10 · The document is written only by AI; humans comment, validate or reject

**Amends D-029's authorship of the draft**, which had humans editing the document body directly.

**Decision.** The document body is machine-written, always. A human never edits it. Human input
takes exactly three forms:

| Action | Effect |
| --- | --- |
| **Comment** | Free text attached to the document or to one of its parts. Never becomes document content; it is input to the next regeneration. |
| **Validate a business rule** | Per-rule acceptance (D-037). The rule migrates into the baseline. |
| **Reject an implementation** | Inconclusive, not wrong (D-036). Another PR is expected. |

Amendments are requested by commenting, not by typing into the body. The AI rewrites; the human
directs and decides.

**Context.** Two problems dissolve at once.

The first is **CON-39**, raised as a hazard at CON-34 and recorded as blocking CON-12: the body is
regenerated on every run, which destroys anything a reviewer wrote into it. If nobody writes into
it, there is nothing to destroy. The hazard was a consequence of mixed authorship, not a flaw in
regeneration.

The second is **provenance**. A document that is part machine-derived and part hand-edited has no
way to say which sentence is which, and product rule 3 requires exactly that. Single authorship
makes every sentence in the body attributable by construction, and human intent stays in comments
and decisions where it carries its own category.

**Consequences.**

- **CON-39 is not withdrawn; it is transformed.** The residual problem is real and is the same
  class: a comment is anchored to something, and regeneration rewrites the thing it is anchored to.
  A comment attached to a rule survives if it is anchored to the rule's identity; a comment
  attached to a line of rendered prose does not survive the next run. **Comment anchors must be
  durable identities, not positions in text.** This is now CON-39's actual content, and it still
  gates CON-12 and CON-44.
- **Free text gets a home without contradicting D-032.** D-032 dropped the ticket title because
  unverified human free text had no category in the taxonomy. A comment is not a counter-example:
  it is never a claim *in* the document, so it asserts nothing. It can only influence what the AI
  writes next, and whatever the AI then writes is still `ai_interpretation` requiring acceptance.
  A comment carries no authority and makes no assertion about the product.
- **The "no automatic approvals" prohibition gets easier to hold.** The body cannot contain an
  approval, because the body is machine-written and machine output is a proposal by definition
  (product rule 4). Authority lives only in validated rules and frozen versions.
- **Rejection does not edit anything either.** It records that the implementation is inconclusive
  and expects another PR (D-036). It does not mark the write-up wrong.
- The `Document` docstring in `models.py` said "humans edit it". Corrected.
- New scope: comments must be stored, attributed and durable — **CON-47** — and must reach the
  interpretation pass so that commenting actually changes the next draft — **CON-48**. Without
  CON-48 commenting is a suggestion box.

**Status.** accepted

---

## D-042 · 2026-11-10 · Packages are discovered, never listed

**Decision.** `pyproject.toml` configures `[tool.setuptools.packages.find]` with
`include = ["constat*"]` and `namespaces = false`. An explicit `packages = [...]` list is not used.
A test asserts the configuration is a `find` directive, that every package directory on disk
matches an include pattern, and that a wheel built from a staged copy of the source contains every
module and imports on its own.

**Context.** The explicit list said `packages = ["constat"]`, which setuptools took literally: from
CON-04 onwards every subpackage — `git`, `store`, `evidence`, `ai` — was dropped from the wheel. No
test noticed for five tickets, because the development install is editable and imports from the
working tree. A built wheel would have failed at the first `from .store import …`. Found while
verifying an unrelated claim about dependencies (CON-46).

The deeper point is the failure *shape*: forgetting to extend a list produces a silently broken
artefact rather than an error. Discovery cannot forget.

**Consequences.**

- A new subpackage is shipped without anyone remembering anything.
- `namespaces = false` stays, or any directory — including `__pycache__` — becomes a package.
- **Two testing traps are recorded here because both produced a false pass**, and both would
  silently return if the test were rewritten:
  - setuptools stages into `build/` and never cleans it, so an in-tree build includes modules left
    by earlier builds. With the defect restored, building in place still produced a complete wheel.
    The test builds from a staged copy.
  - The editable install registers a meta path finder through a `.pth` file that claims `constat.*`
    from the working tree, ahead of `sys.path`. The import probe loaded `cli` from the wheel and
    `store` from the repository, passing against a wheel containing no `store`. The probe runs with
    `-S` so `.pth` files are skipped.
- CON-20 ("package the MVP") rests on this. It was not going to be discoverable at that point
  without it, since nothing before CON-20 builds an artefact.

**Status.** accepted

---

## D-041 · 2026-11-10 · A provider misconfiguration is refused, never reported as a finding

**Decision.** If `CONSTAT_AI_PROVIDER` names a provider that is not implemented, or an implemented
provider's credential is absent from the environment, Constat **fails** — exit code **5**, distinct
from 2 (input), 3 (repository) and 4 (workspace). It never falls back to the null provider.

Credentials are read from the environment only. The workspace may record *which* provider and model
produced a proposal, because a reviewer needs that provenance; it never records the key.

**Context.** The tempting behaviour is to degrade gracefully: if anything about the provider is
wrong, use the null provider, and nothing ever breaks. What that actually produces is a document
reading "no rules were identified" for a user who believed they had configured a provider — a
configuration fault wearing the costume of a finding. That is product rule 1's failure mode exactly,
and it is worse here than a crash, because the output looks like an answer.

**Consequences.**

- The provider registry ships **empty** in CON-41. No provider is implemented until CON-42, and an
  empty registry is the honest way to say so — unlike an entry that exists and fails when used. The
  error names what is available, which is currently `none`.
- A fifth exit code is a cost. It is paid because the alternative is telling a user to check their
  repository or their workspace when both are fine.
- **The provider is resolved before any repository is read.** Resolving it last would mean reading
  every repository and collecting all the evidence before refusing. A test watches the collector
  rather than the document, because the document is written at the end either way and would not
  catch the regression.
- `ticket add` gathers too, so it carries the same exit code. A provider fault there leaves the
  ticket open with an empty document, which is recoverable by re-running `constat document` once the
  environment is fixed — a living document (D-029), not a lost one.

**Status.** accepted

---

## D-040 · 2026-11-10 · Identity does not cross the provider boundary

**Settles the question deferred by D-023** and required by it to be settled *before* a provider is
wired up, not after.

**Decision.** Nothing that identifies a person is sent to an AI provider. No author name, no
committer name, no email address, no authored or committed timestamp. The payload carries the
ticket reference, repository aliases, default branches, per-repository status, commit SHAs, commit
subjects and bodies, changed paths and diff text — and has **no field** in which identity could be
placed.

Two further rules follow, because stripping declared fields is the easy half:

- **Identity trailers are removed from commit messages.** `Signed-off-by`, `Co-Authored-By`,
  `Reviewed-by` and the rest are entirely a person, so the line goes. Any remaining address-shaped
  string in the prose is masked.
- **Addresses in diff text are masked, but no diff line is ever dropped.** A changed `AUTHORS`,
  mailmap or contributor list puts addresses in the evidence itself. Masking the address is correct;
  removing the line would misstate the change, and this boundary must not trade one dishonesty for
  another.

**Context.** Product rule 7 (least privilege) decides it once the question is put properly: rule
generation needs to know *what* changed and never *who* changed it. Identity therefore has no
purpose on the far side of the boundary, and sending it would be a personal-data disclosure with
nothing bought for it. Pseudonymisation was considered and rejected as the worst of both — still
personal data in the regulatory sense, for a grouping capability nothing asks for.

**Consequences.**

- **Redaction is not a flag.** An option to disable it would be disabled in the run that matters.
  The payload types are constructible only by going through `redact`.
- **Redaction runs on the default path**, with no provider configured, so the boundary is exercised
  by the ordinary workflow rather than first tested against a live API.
- **SHAs stay.** A sha identifies a commit, not a person, and without it a proposal could not be
  checked against the evidence that produced it (product rule 2).
- The guarantee is partly structural rather than behavioural, which is the stronger form: a future
  field-copying change cannot reintroduce an author without first adding the attribute to the type.
- **An honest limit on the real-data evidence.** Verified against 8 real commits in Subject B: zero
  address-shaped strings survive into the payload. But that range needed **no masking at all** —
  identity was absent structurally, and the trailer and diff-masking paths were exercised only by
  fixtures. Those paths rest on anticipating the case, not on having observed it here.
- **Commit messages and diffs still leave the machine.** That is the product, not an oversight, and
  it is what a prospective user must be told before a provider is enabled. Secret-scanning the
  payload is *not* solved by this decision and is not claimed to be.

**Status.** accepted

---

## D-039 · 2026-11-10 · Rules are generated and maintained by AI, stored in the catalogue

**Supersedes D-038's authorship.** The catalogue stays; people do not write it.

**Decision.** Business rules, their behaviours and their anchors are **generated and maintained by
an AI interpretation pass** over collected evidence. The catalogue is where they are stored and
versioned. Humans do not author rules; they **accept or reject** them (D-036), and accepted rules
migrate into the baseline (D-037).

**Context.** D-038 chose a human-declared catalogue to avoid recurring API cost before validation.
That is reversed deliberately: a catalogue only ever contains the rules someone remembered to
declare, and the drift between a hand-maintained catalogue and the code is the disease this
product exists to treat. Having Constat suffer from it would be self-defeating.

**Consequences.**

- **Provenance is corrected.** D-038 reasoned that a human-written statement is `requirement_ref`.
  Generated rules are **`ai_interpretation`** — proposals, visibly uncertain, carrying no
  authority until accepted. The governance model already enforces this; the taxonomy entry simply
  changes.
- **AI stops being optional for the core output.** D-003 keeps the provider interface and keeps
  the *evidence* path provider-free, so Constat still runs without a key — but with no provider
  there are no rules, only evidence, and it must say so rather than imply none exist.
- **This is now the roadmap's top risk made concrete.** The plan says to postpone AI API calls
  until the workflow is validated, and validation stands at zero discovery conversations
  (CON-26). The cost is real: evidence is already 2000–4000 diff lines per range per repository.
  Proceeding is a deliberate choice, not an oversight.
- **"Maintained" means rules change as the code does.** A later ticket whose evidence contradicts
  a baselined rule must propose an update to that rule, not silently create a second one. That is
  harder than generation and is the part most likely to go wrong.
- The catalogue's coverage reporting matters more, not less. An AI pass will miss rules too, so
  changed files claimed by no rule must stay prominent.
- Manual `rule` commands are kept as a bootstrap and test path, not as the model. They are how the
  catalogue is exercised without a provider configured.

  > **Withdrawn by D-048** on 2026-11-11. There is no human-authored path into the catalogue, and
  > no removal either. Two authorship paths meant answering "who wrote this rule?" twice; the
  > bootstrap convenience was not worth it.

**Status.** accepted

---

## D-038 · 2026-11-10 · Rules come from a catalogue, not from code signals

**Supersedes the "deterministic spine" of D-010.** Feature flags went at D-034; SQL migrations go
now; nothing replaces them.

**Decision.** Business rules live in a **catalogue** held in the workspace. Each rule carries its
behaviours and a set of **anchors** — the paths in registered repositories whose code is
understood to implement it. Rules are never inferred from code *signals* such as migrations or
annotations.

> **Authorship superseded by D-039.** This entry originally had people declaring the rules. They
> are generated and maintained by AI; the catalogue structure below is unchanged.

**Context.** D-035 settled that a rule is a business statement and a behaviour is a way the
application handles a business case. Neither can be read out of a migration or an annotation, so
the spine was never going to produce rules — only evidence. Migrations are irrelevant for the same
reason flags were: a schema change is a technical artefact that may accompany a rule change, or
may not, and treating it as one would report on the machinery again.

The alternative was an AI pass, deferred here on cost grounds and **chosen the same day in
D-039**. The cost concern stands and is recorded there rather than dismissed.

**Consequences.**

- **It works in any language.** Subject B is TypeScript with no migrations and no bean validation;
  under the catalogue it is served exactly as well as Subject A, which no code-derived signal
  could have managed.
- ~~Rule statements become authoritative rather than proposed.~~ **Corrected by D-039:** generated
  rules are `ai_interpretation` — proposals carrying no authority until accepted.
- **Status is computed at the level of evidence, never meaning.** Constat can say "the code
  anchored to this behaviour changed in this ticket"; it cannot say what the behaviour now *is*.
  The reviewer supplies that. This is D-012's drift reasoning applied to rules: a signal, never a
  verdict.
- **Changes covered by no rule must be reported prominently.** This is the catalogue's failure
  mode: it only knows the rules someone declared, so a ticket touching ten files where only two
  are anchored must say so loudly. A document listing two impacted rules while silently ignoring
  eight unanchored files would be exactly the confident under-report this product exists to
  prevent.
- The catalogue drifts from the code — the disease Constat treats. This is the specific weakness
  that D-039 reverses authorship to address: a hand-maintained catalogue would have drifted by
  construction.
- `NEW` and `REMOVED` behaviours come from review, not detection: the reviewer adds a behaviour
  the implementation introduced, or marks one whose anchor has gone.

**Status.** accepted

---

## D-037 · 2026-11-10 · Accepted rules migrate into the baseline

**Decision.** When a reviewer accepts a rule change, that rule is **migrated into the main
baseline** — the approved description of how mainline behaves. A later gather compares the
ticket's rules against the baseline, not against a fresh reading of mainline.

**Context.** Answers the question CON-39 raised: what happens to accepted rules when a document is
re-gathered. Nothing is re-litigated, because an accepted rule is no longer part of the proposal —
it has become approved product knowledge.

**Consequences.**

- This unifies three things that were separate tickets. The baseline (CON-14) *is* the accepted
  rule set; comparing against the last approved baseline (CON-15) *is* how NEW / CHANGED /
  UNCHANGED / REMOVED are computed; and drift (D-012) is a baseline rule whose supporting evidence
  has since moved.
- **`NEW` and `CHANGED` are relative to the baseline, not to mainline.** A rule absent from the
  baseline is new even if it has existed in code for years but was never documented. That is the
  correct meaning for a governance record: it tracks what has been *approved*, not what exists.
- Baseline versions stay immutable and append-only (D-029, enforced by trigger). Migrating a rule
  creates a new baseline version; it never edits the previous one.
- A rule accepted on one ticket and then changed by another will show as `CHANGED` against the
  baseline, which is exactly right.

**Status.** accepted

---

## D-036 · 2026-11-10 · Rejection means inconclusive, not wrong

**Decision.** Rejecting a document marks the attempt **inconclusive**: the implementation is
missing something and another pull request is expected. It is not a statement that Constat
described the change badly, and it is not a permanent verdict on the work.

A rejection carries **commentary** explaining what is missing. Comments are first-class, not a
single free-text rationale field.

**Context.** The schema's `decision` column allows `approved` and `rejected`, but "rejected" was
ambiguous between two very different signals: *the write-up is wrong* and *the change should not
ship*. The intended meaning is neither — it is "not done yet, iterate".

**Consequences.**

- The stored decision must say which it is, or a later reader cannot tell why work stopped. The
  vocabulary needs to carry "inconclusive — another PR expected" distinctly.
- Comments need their own storage, not a single `rationale` column: there may be several, attached
  to specific rules rather than only to the document as a whole.
- **Multi-person commenting is out of MVP scope.** Reviewer identity is asserted rather than
  authenticated (D-007), so "people commented" is a claim Constat cannot verify. One reviewer's
  comments are recorded as asserted; a real multi-user flow needs identity first.
- A rejected document is not closed. The ticket stays open, the next gather picks up the follow-up
  commits, and the rejection and its comments remain in history.

**Status.** accepted

---

## D-035 · 2026-11-10 · A rule is business-oriented; a behaviour is a way the app handles it

**Decision.**

- A **rule** is purely business-oriented and determines how the application behaves. Not a
  migration, not an annotation — those are *evidence for* a rule, never the rule itself.
- A **behaviour** is any distinct way the application handles a business case under that rule.

So "a transfer over the daily limit is refused" is a behaviour of the rule "daily transfer limit".
`@Size(max=250)` is evidence that such a rule exists, but is not itself either.

**Context.** This is the definition that makes the product its stated promise rather than a diff
viewer, and it settles what D-010's spine was for: migrations and validation constraints are
**evidence**, not rules.

**Consequences — one of them forces a decision deferred since D-003.**

- **Rules cannot be derived deterministically.** No amount of reading migrations or annotations
  produces "a transfer over the daily limit is refused". That sentence requires either
  interpretation or a human. The deterministic spine supports rules; it cannot generate them.
- Behaviours are branches of business logic, which are semantic rather than syntactic. Same
  conclusion.
- Combined with the requirement that the MVP work across more than one repository — Subject B is
  TypeScript, with no migrations and no bean validation — a deterministic-only extractor is ruled
  out on both counts.
- This is the roadmap's own "interpretation layer" arriving: *AI proposes impact and plain-language
  explanations, always tied to evidence and uncertainty*. It is consistent with the plan, provided
  output stays a proposal, carries `ai_interpretation` provenance, and is human-approved — all of
  which the governance model already enforces.
- What it does change is **D-003's "optional"**. Without a provider there can be no rules, only
  evidence. The honest shape is that Constat still runs and still reports evidence, but states
  plainly that no rules were identified — rather than implying none exist.

**Status.** accepted

---

## D-034 · 2026-11-10 · Feature flags are not a business rule source

**Amends D-010**, which listed feature flags as one of three deterministic rule-bearing signals.

**Decision.** Feature flags are removed from the rule model entirely. Constat will not derive
rules, behaviours or statuses from flag declarations, defaults or descriptions.

**Context.** A flag is a *control over* behaviour, not a statement of it. "This behaviour can be
switched off" is a delivery and rollout mechanism that any change might use; it says nothing about
what the rule is. Including it would have made Constat report on the machinery of shipping rather
than on the rules themselves — a generic property of software change, which is precisely what the
product is meant to rise above.

Two further reasons, both visible in Subject A:

- Many registered flags are plainly not rules. `padjis.app.version` with default `2.3.0` is
  configuration; so is an AI prompt template. A rule extractor that emitted those as "business
  rules" would bury real findings in noise.
- **The live value is not in the repository.** Flags are seeded into Redis via `setIfAbsent` and
  edited by operators at runtime (ADR-0001), so a changed default need not change behaviour at
  all. Constat could only ever have reported "the declared default moved", and reporting that as a
  behaviour change would have been unsupported certainty on the product's most sensitive surface.

The second point alone would have forced heavy caveating; the first makes the signal low-value;
the principle makes it wrong in kind. Removing it is cheaper than qualifying it.

**Consequences.**

- **The deterministic spine narrows to two signals**: schema/data migrations, and declarative
  validation constraints. That is thinner and should be stated plainly rather than implied away.
- **Coverage in a non-Java repository is now close to zero.** Subject B is TypeScript with no
  Liquibase migrations and no bean validation, so a rule extractor built on this spine will find
  nothing there. The document must say "no rule-bearing signals found" rather than "no rules
  changed" — the two are different claims.
- Nothing is removed from the code: CON-08 had not been built, so this changes a plan rather than
  an implementation. Caught before it cost anything.

**Status.** accepted

---

## D-033 · 2026-11-10 · Evidence is collected per commit, and `ticket add` fills the document

**Decision.** Two things, both about CON-34.

**Evidence is collected per commit, not as one cumulative diff.** For each commit attributable to
a ticket, Constat diffs it against its first parent and collects bounded evidence for that commit
alone.

**`ticket add` runs the gathering operation immediately.** Opening a ticket writes its document in
the same invocation; there is no intermediate state where a ticket exists with an empty document
that says nothing.

**Context — per commit.** A ticket's commits need not be contiguous. Diffing the first commit's
parent against the last would sweep in whatever else landed between them, attributing other
people's work to the ticket. There is no single revision range that means "this ticket's effect",
so there should not be a single diff pretending to be one.

The cost is duplication: a file touched by three commits produces three excerpts. That is accepted
because each hunk stays attributable to the commit that made it, which is the point of provenance
(product rule 3). A test builds exactly the trap — ticket work, an unrelated commit, more ticket
work — and asserts the unrelated file never appears.

First parent rather than merge base, for a merge commit: that yields what the merge brought in,
which is what the merge contributed.

**Context — filling on add.** The earlier shape ran the same search at `ticket add`, printed it,
and discarded it: `operation` stayed empty and the document stayed blank. Two implementations of
one idea, one of which persisted nothing. The ephemeral version is deleted.

**Consequences.**

- `constat document <ref>` remains, for re-gathering after new commits and for `--show`. It is a
  refresh, not a required first step.
- **`ticket show` reports stored state only** and no longer re-searches. A `show` that searched
  afresh could disagree with the document it was describing.
- The document body is **regenerated** on each run rather than appended to, so re-running does not
  duplicate findings. That is safe only while the body is entirely machine-derived. Once human
  editing exists (CON-12), regeneration would destroy edits — recorded as **CON-39**, and it must
  be solved before review ships.
- Excerpt limits apply per commit, so a ticket with many commits can capture more in total than a
  single range would. Every bundle states its own completeness, so nothing is hidden, but a
  document-wide budget may be wanted later.
- A commit with no parent (a root commit) has nothing to diff against. The reason is recorded on
  the commit rather than dropping it, since dropping would under-report silently.

**Status.** accepted

---

## D-032 · 2026-11-10 · A ticket has no title

**Decision.** A ticket is a reference and a creation time. There is no title field, and no
`--title` option. Schema bumped to version 2 with a migration dropping the column.

**Context.** The title was added for readability — `ticket list` showing bare `622`, `ADR-0019`,
`plans/0015` is hard to scan. But it is **unverified free text**, and the provenance taxonomy
(PRODUCT_SPEC.md section 7.1) has no category for one. The nearest, `human_decision`, is wrong: a
decision is an approval, not a note. A title appearing in a document could be read as established
when nobody checked it against anything — in a product whose entire discipline is separating what
is supported from what is asserted.

Two alternatives were considered and rejected: marking it as an unverified label (which keeps the
hazard and adds ceremony), and deriving it from evidence such as a branch name or the first
attributed commit subject (defensible, but it adds a field nothing needs yet; a derived label can
be rendered on demand without being stored).

**Consequences.**

- `ticket list` shows bare references. If that proves unreadable in practice, the fix is to render
  a label derived from attributed evidence at display time, not to store free text.
- **The first schema migration exists because of this**, which is the useful part. A governance
  tool that discarded stored decisions whenever its schema changed would contradict product
  rule 5 on exactly the surface where it matters most. Version bumps carry migrations; only a
  version with no migration path is refused.
- `executescript()` is not used for migrations: it implicitly commits, which would silently defeat
  the surrounding transaction and could leave a workspace half-migrated. Statements are listed and
  executed individually. Found by a test that failed with "cannot commit - no transaction is
  active".
- Tests build a real version-1 workspace, migrate it, and assert the row survives while the column
  does not. Asserting the version number alone would not have shown that data was preserved.

**Status.** accepted

---

## D-031 · 2026-11-10 · A ticket is expected to be merged, but not yet into mainline

**Refines D-030.** The commit set is not searched across all of history; it is searched in the
window between mainline and everything else.

**Decision.** Constat expects a ticket's work to be **already implemented and merged** — onto an
integration or release branch — but **not yet in mainline**. The commit set for ticket `T` is
therefore:

```
commits reachable from any ref, excluding those reachable from mainline,
that are attributable to T
```

In Git terms, `git log --all --not <mainline>`, filtered by the attribution rules in D-030.

**Why this formulation rather than a configured integration branch.** Naming one integration
branch per repository would need configuration, and would be wrong the moment work sits on a
release branch instead of `develop`. "Reachable from anything, but not from mainline" describes
the same window without naming it, and covers `develop`, `release/*` and a still-open ticket
branch identically. Subject A has `develop` *and* seven release branches; Subject B has release
branches and no `develop` at all, so no single configured name would have served both.

**Consequences.**

- **The search space is bounded and small.** Not "all 1130 commits" but "whatever is staged ahead
  of mainline", which is the set a reviewer actually cares about.
- **Three outcomes, which must not be conflated.** `unknown` is an acceptable result (product
  rule 1), and so is "already landed":

  | Outcome | Meaning |
  | --- | --- |
  | Commits found outside mainline | Documentable. This is the expected case. |
  | Commits found, but only in mainline | Already landed. Not nothing — a different answer. |
  | No commits anywhere | The reference matched nothing. Not "this ticket changed nothing". |

- **`ticket add` warns rather than refuses** when the expected case does not hold. A ticket may
  legitimately be registered before its repositories are, or before the attribution pattern is
  tuned. Refusing would make a tuning problem look like a missing ticket.
- **The ref a commit was found on is evidence and must be recorded.** "Found on
  `refs/heads/develop`" and "found on an abandoned branch" are different provenance (product
  rule 3), and only the first should carry weight.
- Searching `--all` includes remote-tracking and stale refs, so an abandoned branch can
  contribute. Recording the ref is what makes that visible rather than silently misleading.
- This is the assumption that makes mainline-only (D-028) coherent: there is divergence to measure
  precisely because the work has not reached mainline yet. Documenting *after* a mainline merge
  falls back to the attribution rules alone.

**Status.** accepted

---

## D-030 · 2026-11-09 · A ticket resolves to a commit set; mainline stays the reference

**Resolves CON-37.**

**Decision.** The *reference point* is always mainline (D-028 stands). The *target* is a **commit
set** attributable to a ticket, not a branch tip. A ticket's commits are resolved from, in order:

1. **A branch whose name encodes the ticket** — `feat/622-prune-dead-fcm-tokens` names ticket 622.
   Unambiguous while the branch exists.
2. **Commit-message references** — the configurable pattern from CON-29.
3. **An explicit commit list**, supplied by a human.

The effect of that set is expressed against the mainline tree.

**Context.** An integration-branch workflow was proposed as the answer, and in principle it works:
work on `develop` diverges from mainline, so there is something to measure. Checked against the
real subjects on 2026-11-09, it does not hold:

| Branch | Ahead of mainline | Behind |
| --- | --- | --- |
| Subject A `develop` | **0** | 1119 |
| Subject A `feat/622-…` | **0** | 10 |
| Subject A `release/…` | **0** | 362 |
| Subject B `release/1.2.0` | **0** | 182 |

Every branch is zero ahead; Subject B has no integration branch at all. Ticket 622's commit is
already in mainline, `merge-base(main, feat/622) == tip of feat/622`, and the diff between them is
**0 files**. Under branch-divergence alone, documenting ticket 622 would produce an empty
document while the work sits plainly in history.

Both teams also rebase rather than merge — 3 merge commits in Subject A's last 200, zero in
Subject B's — so a ticket's commits do not survive as a distinguishable merge group.

**Consequences.**

- This is the `commit_set` selection reserved in D-025, now required rather than speculative.
- **Already-merged work becomes documentable**, which matters because all of both subjects is
  already merged. Branch divergence alone would have made Constat unable to document its own
  primary test data — a failure that would otherwise have surfaced at CON-34.
- Branch-name resolution is a genuinely better signal than commit messages where it exists:
  unambiguous, and it does not depend on commit discipline. Only ~5% of Subject A's commits carry
  any reference at all.
- Resolution order matters and must be reported. A document has to state *how* its commit set was
  determined, because "the branch said so" and "a human listed them" are different provenance
  (product rule 3).
- A commit set may be **empty**, and that is a legitimate answer meaning "no commits reference this
  ticket" — not "this ticket changed nothing". The two must not be rendered alike.
- Prospective documentation still works and is still better: a ticket documented before it merges
  has a live branch, and approval freezes the version (D-029) so it survives the merge.

**Status.** accepted

---

## D-029 · 2026-11-09 · A ticket owns one living document, frozen on approval

**Supersedes D-025's proposal-per-run model.** D-025's identity reasoning survives; its top-level
object does not.

**Decision.** A **ticket** owns exactly one **document**. Operations expand or edit that document
rather than creating new top-level records. Approval freezes an immutable, versioned snapshot;
later operations continue editing the draft, and every approved version stays recoverable.

| Artefact | Mutable? | Lifetime |
| --- | --- | --- |
| Document (draft) | yes — operations append, humans edit | one per ticket, ongoing |
| Document version | **no** — frozen at approval | one per approval, forever |

> **Authorship amended by D-043.** The draft is written by operations only. Humans comment,
> validate a rule or reject an implementation; they do not edit the body. The lifetimes above are
> unchanged.

**Context.** The user's model, and it is better than mine for a reason I had already logged
without recognising: CON-30 ("re-running `analyse` fills the store with near-duplicate proposals")
was not a storage problem, it was evidence that proposal-per-run was the wrong unit. Ten runs
against one ticket should deepen one document, not create ten.

It also promotes CON-29 from a peripheral idea to the primary workflow.

**Consequences.**

- **CON-30 is withdrawn**, not deferred. The problem does not exist in this model.
- Product rules 4 and 5 are satisfied by the split, not by the draft: the draft is working
  material and carries no authority; the frozen version is the governance record. "Edit the doc"
  and "immutable baselines" only contradict each other if there is one artefact.
- From D-025, kept: identity is generated rather than derived, and repository identity is the root
  commit. A document version gets a fresh ID per approval for exactly the reason a proposal did.
- From D-025, dropped: one top-level record per analysis run.
- Persistence moves much earlier. A registry and an accumulating document both need storage before
  any of this works, so CON-13's SQLite is now a prerequisite rather than a Phase 4 task.
- An operation needs to be a first-class, recorded thing — what ran, against which repository, when,
  and what it contributed. Otherwise a document becomes unattributable prose, which is the failure
  this product exists to prevent.

**Status.** accepted

---

## D-028 · 2026-11-09 · Mainline is the only reference point

**Supersedes the closed-range half of D-016.** `snapshot` survives; arbitrary `--base`/`--target`
does not.

**Decision.** Every comparison is against the repository's **default branch**, resolved per
repository and never assumed to be literally `main` (product rule 6, and D-009 found both subjects
use `main` only by coincidence). Explicit base/target range selection is removed.

**Context.** Chosen deliberately for a sharper model: the question Constat answers becomes "what
does this work add that mainline does not have", which is the question a ticket actually poses.
Merge-base semantics (D-021) already implement exactly this, with base = mainline.

**Consequences — including one that is a real loss.**

- **MVP acceptance criterion 2 is amended.** It read "a user can compare two commits or tags".
  Release-to-release documentation is no longer possible: a release tag is normally an *ancestor*
  of mainline, so `compare(mainline, v2.3.1)` is a backwards range and is refused by design
  (D-021). PRODUCT_SPEC.md section 6.3 is updated to say comparison is against mainline.
  Recorded rather than quietly dropped — this was flagged before the choice was made and accepted
  with the cost understood.
- The default branch must be **resolved** from each repository and stored in the registry. Hardcoding
  `main` would break product rule 6 and any repository still on `master`.
- `--base` and `--target` leave the CLI. The machinery behind them stays: `compare_revisions` is
  unchanged, it simply always receives mainline as base.
- Open and needing a decision during implementation: **what happens once a ticket's work is merged
  into mainline.** At that point there is no divergence left, and "what does this add to mainline"
  answers "nothing". The document must describe the commits' effect rather than the branch's
  divergence, or every merged ticket goes blank. This is the one unresolved piece of the model.

**Status.** accepted

---

## D-027 · 2026-11-09 · Constat holds a workspace of registered repositories

**Amends D-001**, which kept the MVP to one repository per run. Local-first is unchanged;
single-repository is not.

**Decision.** Constat maintains persistent state: a **workspace** holding registered repositories.
Repositories are added and removed at setup or at any later point. A remote is registered by URL
and **cloned into a local cache**, then read with the existing read-only Git layer.

**Context.** Operating on a set is the point of the product — "connect changes across several
repositories to one capability" is the first stated differentiator, and `--repo` once per
invocation never served it. The cross-repository demo was parked at CON-19, which made the
differentiator the last thing to be proven.

**Consequences.**

- **Everything in `constat/git/` and `constat/evidence/` keeps working unchanged.** A cached clone
  is an ordinary local repository, which is why clone-and-cache was chosen over API access: one
  code path, not two, and the security posture of D-001 is preserved.
- Fetching is a **write to the cache but never to the source**. Read-only against the user's
  repositories still holds; the cache is Constat's own.
- Credentials for private remotes are needed and must never be stored in the workspace
  (product rule 7). Defer to the system Git credential helper rather than handling tokens.
- A registered repository stores: alias, source (path or URL), cache location, root-commit identity
  (D-025), and resolved default branch (D-028).
- Staleness becomes a real concern. A cached clone is a point-in-time copy, so every document must
  record **when the cache was last fetched**, or evidence silently ages. Unstated staleness in a
  governance tool is the same class of failure as unstated truncation (D-023).

**Status.** accepted

---

## D-026 · 2026-11-09 · Pydantic bounds the published schema; internals stay dataclasses

**Decision.** Pydantic becomes the project's first runtime dependency, applied **only** to the
models that are persisted, serialised or reported — those in `constat/models.py`. The Git adapter,
diff and evidence types stay frozen dataclasses, with an explicit mapping layer between them.

**Context.** D-002 chose Pydantic; D-015 deferred it until there was something to validate. There
now is. The open question was how far it should reach, and the worst outcome would have been
ending up with two conventions by accident rather than by choice.

The boundary follows the layering in ARCHITECTURE.md section 2. The Git layer is deterministic
plumbing over `subprocess` whose "validation" is whether Git succeeded; schema enforcement there
would be ceremony. The proposal is the opposite: it is the stable contract that gets written to
SQLite (CON-13), rendered (CON-09) and frozen into baselines (CON-14), and a malformed one is a
governance failure rather than a bug.

**Consequences.**

- `pip install constat` now pulls one package. The security-review surface argument in D-015 still
  holds: one well-known dependency, and the deterministic evidence path remains free of any AI
  provider (D-003).
- A mapping layer is required, and is where the two worlds meet. It is deliberately one-directional:
  adapters build models, models never reach back into Git.
- `schema_version` lives on the proposal (D-008) and is asserted in tests, so a future format change
  cannot go unnoticed.
- Rejecting Pydantic in the Git layer means `Repository`, `Revision`, `ChangeSummary`,
  `EvidenceBundle` and friends stay dependency-free and trivially constructible in tests — which is
  why the existing 143 tests needed no changes.

**Status.** accepted

---

## D-025 · 2026-11-09 · The unit of a proposal, and how one is identified

**Decision.** Closes Q1 and CON-24, the last of the original ten open questions.

A proposal is **`(repository, selection)`**, where a selection is one of:

| Kind | Question | Status |
| --- | --- | --- |
| `change` | What changed between two revisions? | implemented (CON-05) |
| `state` | What does this revision contain now? | implemented (CON-05) |
| `commit_set` | What changed for this reference? | reserved for CON-29 |

**A proposal belongs to exactly one repository.** Cross-repository work is a *group* referencing
several proposals, never one proposal spanning repositories. Forced by D-009: the two subjects have
no shared version space, so a single range cannot be meaningful in both. This also satisfies
product rule 6 structurally rather than by convention.

**Identity is generated, not derived.** Each run produces a new proposal with a fresh UUID, and
additionally carries a deterministic `selection_key` — a hash of the repository identity, the
selection kind and the resolved SHAs.

**Context.** The tempting choice is a derived identity: hash the inputs, so re-analysing a range
yields "the same" proposal. It breaks on the governance model. An approved baseline and a later
re-analysis of the same range are *different things* — one is a human decision, the other a fresh
machine output — and giving them one identity would force the re-analysis either to collide with
the approved record or to silently overwrite it. History must be durable (product rule 5), which
means append-only, which means new identity per run.

The `selection_key` recovers what derivation was for: "show me every proposal for this range" and
"has this been documented before?" remain single lookups. Append-only history and idempotent lookup
are not actually in tension; they just need two fields rather than one.

**Repository identity is the root commit, not the path.** A filesystem path changes when a clone
moves, and a remote URL changes when a project migrates host — this project changed both its name
and its forge inside two days. The SHA of the earliest root commit does not. Where a repository has
several root commits (orphan branches), all are recorded and the lexicographically smallest is used
as the key, so the choice is deterministic.

**Consequences.**

- CON-13 gets its stable identifier, and CON-14's baselines can reference a proposal UUID that will
  never be reused.
- CON-15 compares against the last approved baseline *for the same `selection_key`*, which is what
  "since the last approved state" has to mean.
- Re-running `analyse` ten times produces ten proposals. That is correct but needs surfacing in the
  UI eventually, or the store fills with near-duplicates; worth a ticket when CON-13 lands.
- Computing repository identity costs one extra `git rev-list --max-parents=0` per run. Cheap, and
  it buys identity that survives moving, renaming and re-cloning.
- `commit_set` is reserved in the schema now so adding CON-29 later is additive rather than a
  schema break.

**Status.** accepted

---

## D-024 · 2026-11-09 · Excerpt budget is shared fairly, not spent first-come

**Decision.** The total line budget is allocated across changed files *before* any text is kept,
smallest need first: each file is offered an equal share of what remains, takes only what it needs,
and the surplus is redistributed. Files are never served in path order.

**Context.** The first implementation spent the budget as it walked the sorted change list. Run
against a Subject B release range it produced the obvious failure: a generated lockfile sorts
early, took its full 400-line allowance out of a 4000-line budget, and files later in the alphabet
received **nothing**. Which evidence a reviewer saw depended on filename ordering.

For a governance tool that is indefensible. A file named `zzz_pricing_rules.java` would be silently
excerpt-free while a generated lockfile was quoted at length — and the report would look equally
confident either way.

**Consequences.**

- Measured on the same real range after the change: **49 of 50 files captured whole**, with only
  the lockfile truncated (393 of 3835 lines). The generated file absorbs the loss instead of
  imposing it on source files.
- Allocation requires reading every diff before keeping any of it, so the whole range is held in
  memory briefly. Acceptable at this scale (7442 lines is well under a megabyte); revisit if a range
  ever approaches repository size.
- Ties break on path, so allocation is deterministic and does not depend on dictionary ordering.
- A test asserts that two equally-sized files get shares within one line of each other, and another
  asserts a small file survives alongside a 2000-line sibling. Both would fail under first-come.
- This is **not** classification. Constat is not deciding that lockfiles matter less — it has no
  opinion about any file. Fair sharing simply removes an arbitrary bias. Treating generated files
  differently on purpose would be CON-08's business, and would need evidence.

**Status.** accepted

---

## D-023 · 2026-11-09 · Evidence is bounded by measured limits, and every omission is stated

**Decision.** Diff excerpts are capped at **400 lines per file** and **4000 lines per comparison**.
Every excerpt records its true total line count, whether it was truncated, how many lines were
omitted and why. Every excerpt — including a fully omitted one — carries a source pointer and the
exact `git` command that regenerates it in full.

**Context.** D-005 required bounded evidence but named no numbers. These were measured against the
subject repositories on 2026-11-08 rather than invented:

| Range | Files | Diff lines | Largest file |
| --- | --- | --- | --- |
| Subject A, a build-tag range | 29 | 2255 | 345 |
| Subject B, a release range | 50 | 7442 | 3835 (a generated lockfile) |

A 400-line per-file cap captures essentially all genuine source changes in both ranges while
containing the generated lockfile. The per-file and total caps are separate precisely because one
pathological file should not be able to consume a whole range's budget.

**Consequences.**

- **Truncation is only safe because the original stays reachable.** The recorded command is tested
  by actually running it and confirming it returns content the excerpt does not contain. Without
  that, bounding would violate "evidence is inspectable" (product rule 2).
- **A file is never dropped from the record.** Running out of budget removes an excerpt's *text*,
  never its entry — omitting the file would under-report the change itself.
- `EvidenceBundle.is_complete` and `completeness_note()` exist so a report can never imply
  completeness it does not have. CON-09 must surface the note.
- Binary files are recorded as binary with no excerpt and a zero line count, rather than being given
  a fabricated textual diff.
- Author and committer are both captured and never collapsed: a rebase or cherry-pick rewrites the
  committer while preserving the author, so merging them would misattribute work.
- **Privacy note for later:** evidence includes author and committer email addresses. That is fine
  locally, but when the optional AI provider arrives (D-003), sending commit metadata to a third
  party means sending personal data. PRODUCT_SPEC.md rule 7 applies and the question must be
  settled before any provider is wired up, not after.

  > **Settled by D-040** on 2026-11-10, with the provider interface and before any provider exists.
  > Identity does not cross the boundary at all. This entry is unchanged; the obligation it
  > recorded is discharged.

**Status.** accepted

---

## D-022 · 2026-11-08 · State is read with `ls-tree`, not as a diff against the empty tree

**Decision.** `summarise_state` lists the files present at a revision using `ls-tree -r`, and
returns a `StateSummary` carrying plain paths. It does **not** diff against Git's empty tree, and it
shares no return type with `compare_revisions`.

**Context.** Diffing against the empty tree is the idiomatic trick for "everything at this
revision", and it was the plan recorded in CON-05's notes. It is wrong here: every file comes back
labelled `ADDED`. That is change vocabulary answering a state question, and D-016 exists precisely to
keep the two apart. A snapshot asserts "this is what is present", not "this was all just added" —
and a reviewer skimming a report full of `ADDED` would reasonably conclude the latter.

`ls-tree` also avoids needing the empty-tree hash, which differs between SHA-1 and SHA-256
repositories.

**Consequences.**

- `StateSummary` has `paths: tuple[str, ...]`, not `changes`. There is no `ChangeType` present to
  misread. A test asserts the absence of a `changes` attribute, so a future refactor cannot quietly
  merge the two shapes.
- The two renderers stay separate at CON-09, as that ticket's note already requires.
- Sharing the *evidence collector* between state and change at CON-06 is still fine; it is the
  vocabulary and the output type that must not be shared.

**Status.** accepted

---

## D-021 · 2026-11-08 · Comparison runs from the merge base, not between endpoints

**Decision.** `compare_revisions` computes `merge-base(base, target)` and diffs from there to
`target` — equivalent to `git diff base...target`. The merge base is stored on the summary and
always stated in output.

**Context.** `git diff base..target` compares two endpoints; the merge base asks what `target`
introduced since it diverged. The second is the question Constat exists to answer: a report
documenting a change should describe what the change *added*, not how two trees happen to differ.
Under endpoint comparison, work done only on `base` after the fork appears as a **deletion** in
`target` — a claim that is simply false, and one that would look exactly as confident as a true one.

**Consequences.**

- **The merge base must be reported.** The comparison does not necessarily start at `base`, and a
  reviewer cannot verify the summary without knowing where it did start. `base_is_merge_base`
  distinguishes the simple ancestor case from the diverged one, and the CLI says which applies.
- **A backwards range had to become an error** (`BackwardsRange`). If `target` is an ancestor of
  `base`, the merge base *is* `target`, so the diff is empty — "no changes" in answer to reversed
  arguments. That is the confidently-wrong-empty-report failure, so it is refused with a message
  naming the fix. This fired immediately on real data: a Subject A build-tag pair supplied in the
  wrong order was caught rather than reported as unchanged.
- `git log A..B` already has merge-base semantics for commit listing, so commit enumeration in
  CON-06 will agree with this without special handling. Note the asymmetry: `A...B` means
  merge-base-to-B for `diff` but *symmetric difference* for `log`. Use the explicit merge base
  rather than three-dot notation, so the two can never be confused.

**Evidence, stated precisely.** The semantics provably differ — a constructed test
(`test_endpoint_diff_would_have_differed`) shows the endpoint diff reporting a base-only file as a
deletion while the merge-base diff excludes it. On real data the difference has **not yet been
observed to change a report**: two adjacent Subject B release tags are on divergent lines (the
merge base is neither tag), yet both semantics yield identical results — 50 changed files with one
deletion either way. The decision rests on correctness of the question being asked, not on an
observed discrepancy in this repository.

**Status.** accepted

---

## D-020 · 2026-11-08 · An ambiguous revision is an error, not a precedence decision

**Decision.** When a revision name matches more than one ref — a branch and a tag of the same name —
Constat raises `AmbiguousRevision` rather than letting Git's precedence rules pick one. The caller
must qualify the name (`refs/heads/…`, `refs/tags/…`).

**Context.** Git resolves `collision` to the branch and prints a warning. Accepting that would mean
documenting one revision while the reviewer may have meant the other, and the report would look
exactly as confident either way. That is the failure product rule 1 exists to prevent, arriving on
the input path where it is cheapest to stop.

**Consequences.**

- `rev-parse` must **not** be passed `--quiet`: that flag suppresses the ambiguity warning, which is
  the only signal Git gives. Verified empirically — with `--quiet` the call exits 0 with empty
  stderr and the ambiguity is invisible.
- Detection depends on Git's warning text, so `LC_ALL=C` is set for every Git call to keep the
  message stable regardless of the user's locale.
- Not-found must be decided *before* ambiguity: Git's message for an unresolvable revision can also
  contain the word "ambiguous". A genuinely ambiguous name exits 0; an unknown one exits non-zero.
- A test pins this behaviour, so a future Git changing its wording fails loudly rather than silently
  disabling the check.

**Status.** accepted

---

## D-019 · 2026-11-08 · Revisions always resolve through `^{commit}`

**Decision.** Every revision is resolved with `rev-parse --verify --end-of-options <rev>^{commit}`,
and both the symbolic name and the full 40-character SHA are retained.

**Context.** An annotated tag names a *tag object*, not a commit. Resolving `v2.0.0` without
`^{commit}` yields the tag object's SHA, which would corrupt every later diff and every piece of
evidence anchored to it.

This is a bug the real subject repositories **cannot** catch: Subjects A and B both use lightweight
tags, where `rev-parse <tag>` and `rev-parse <tag>^{commit}` return the same SHA (verified
2026-11-08). The test fixture therefore creates one annotated and one lightweight tag on
purpose, and asserts the two SHAs differ before asserting which one is used.

**Consequences.**

- Keeping both forms is load-bearing, not redundant: the SHA is what evidence points at and what
  integrity depends on; the symbolic name is what a reviewer recognises. A report showing only SHAs
  would be correct and unreadable.
- `--end-of-options` (Git 2.24+) prevents a revision beginning with `-` being parsed as a flag.
- Test fixtures must not mirror only the subject repositories' conventions, or they inherit their
  blind spots.

**Status.** accepted

---

## D-018 · 2026-11-08 · `document` initialises a proposal; `review` stays the governance verb

**Decision.** The ticket-scoped command is **`constat document <ref>`**. The word **`review`** is
reserved for the human approval step (CON-12) and will not be used for anything else.

**Context.** The natural phrasing for "start documenting this ticket's changes" is *review the
ticket*, but `review` already carries a precise meaning here: a person examining a proposal and
approving, editing or rejecting it. Two meanings of *review* in one CLI is exactly the conflation
this product exists to prevent — and it would land on the governance surface, where clarity matters
most.

**Consequences.**

- `document` is the verb for initialising a proposal from a reference; `review` is the verb for
  deciding on one. A reader can tell which stage of the workflow a command belongs to from the verb
  alone.
- CON-12 keeps `review`, so no ticket needs renaming.
- The vocabulary is now a fixed, small set worth protecting: `snapshot` (state), `analyse` (change
  between revisions), `document` (change for a reference), `review` (human decision). A new command
  should reuse one of these or justify a genuinely new concept.

**Status.** accepted

---

## D-017 · 2026-11-08 · Work is tracked as `CON-NN` tickets in an in-repo backlog

**Decision.** Work is tracked in [BACKLOG.md](BACKLOG.md) as `CON-NN` tickets, versioned alongside
the code rather than in an external tracker. Sessions 01–20 are `CON-01`–`CON-20`, so session *N* is
always `CON-NN`. `CON-21` onwards is non-session work. Commits reference the ticket in the subject
and close it in a `Closes:` trailer.

**Context.** Correlating changes needed stable identifiers. GitHub Issues was the alternative and
would have given automatic cross-referencing plus a dogfooding story for CON-17/CON-18 — but an
in-repo register is versioned with the code, works offline, needs no credentials, and is readable in
a clone. For a project whose premise is durable, inspectable records, keeping the register in the
repository is the more consistent choice.

**Consequences.**

- **Tickets are not decisions.** A ticket is work that gets closed; a `D-NNN` entry is an immutable
  record of why. Closing a ticket never deletes or supersedes a decision. Both are referenced from
  the same commit when a ticket forces one.
- The register must be updated in the same commit as the work, or it drifts. Added to the
  end-of-session checklist in `CLAUDE.md`.
- No automatic cross-referencing: a reader must grep for `CON-NN` rather than following a link. An
  acceptable cost at this size; revisit if collaborators arrive.
- `CON-21`–`CON-28` capture the legal, commercial and validation work that no session forces. Two
  are already overdue — the domain is unregistered and no discovery conversations have been held.
  Making them tickets is the point: they are the items most easily avoided in favour of code.

**Status.** accepted

---

## D-016 · 2026-11-08 · Constat documents state as well as change

**Decision.** Constat produces two kinds of document, via two commands:

| Command | Question | Unit |
| --- | --- | --- |
| `analyse --repo --base --target` | What changed between two revisions? | closed range |
| `snapshot --repo --rev` | What does this revision do now? | open range |

This supersedes the implicit assumption in D-001 and PRODUCT_SPEC.md section 6 that the MVP only
ever compares two revisions.

**Context.** The specified MVP produced deltas only, which left a real hole:

- **The first baseline had nothing to diff against.** With delta-only analysis, the earliest
  approved record for a repository would describe a *change* rather than a *behaviour*, which is not
  what "approved product knowledge" should mean.
- **The product promise is present-tense** — "knowledge about how a product behaves" — and the two
  stated audiences ask what the system *does*, not only what moved last week.
- **Drift (D-012) presumes a documented present state** to measure approved claims against.

**Consequences.**

- **Q1 is generalised rather than ratified.** The unit of a change proposal is
  `(repository, revision_range)`, where a range is either *closed* (`base` → `target`) or *open* (a
  single revision). The earlier working assumption of `(repo, base_rev, target_rev)` was too narrow;
  it is good that it was never ratified. Q1 remains open pending Session 07.
- Reports must distinguish the two. A state description and a change description carry different
  claims, and conflating them would blur provenance — "this is how it behaves" is a different
  assertion from "this is what moved".
- `--rev` is required rather than defaulting to HEAD. A snapshot can become an approved baseline, so
  the revision must be stated by the reviewer, not inferred from whichever branch is checked out.
- `--rev` is not restricted to a branch name: a tag or SHA is equally valid, and not every release
  stream has a branch called `main` (product rule 6).
- Snapshot plumbing can share the evidence collector with analyse — in Git terms a snapshot is a
  diff against the empty tree — but the *reports* must stay separate documents. Sharing the renderer
  would be a false economy.
- PRODUCT_SPEC.md section 6 is updated accordingly. ARCHITECTURE.md section 4's data model needs the
  open-range case at Session 07.

**Status.** accepted

---

## D-015 · 2026-11-08 · argparse, and zero runtime dependencies for now

**Decision.** The CLI uses stdlib `argparse` rather than `click`. The package declares **no runtime
dependencies**; `pytest` is the only dev dependency. Build backend is setuptools, version derived
from `constat.__version__` so metadata cannot drift.

**Context.** ARCHITECTURE.md section 1 left the choice open ("click/argparse"). The roadmap says to
keep the first version deliberately boring, and CLAUDE.md forbids a new runtime dependency without
a stated reason. For `--version` and `--help`, argparse is entirely adequate, and argparse handles
subcommands fine when Session 03 needs them.

Pydantic is still the intended choice for data validation (D-002) and will be added in Session 07
when there are models to validate — not before.

**Consequences.**

- `pip install constat` pulls nothing else, which keeps the security-review surface minimal for an
  enterprise pilot. That matters more for this product than CLI ergonomics do.
- The deterministic evidence path demonstrably cannot depend on an AI provider (D-003), because
  there is nothing in `dependencies` at all.
- Revisit if Session 03's revision/option handling becomes unwieldy. Switching to click later is a
  contained change, because `cli.py` is thin by design and `build_parser()` is isolated from
  `main()`.
- Development on NixOS has no system pip; a venv with `ensurepip` supplies one. Recorded in the
  README so a new contributor is not stuck.

**Status.** accepted

---

## D-014 · 2026-11-08 · The project website is tryconstat.com

**Decision.** The web presence is **`tryconstat.com`**. Confirmed unregistered on 2026-11-08
(NXDOMAIN on both NS and SOA lookups).

**Context.** Closes the domain open item from D-013. Every primary TLD for the bare name was gone:
`constat.com` sits with a legacy Network Solutions owner, `constat.dev` and `constat.fr` are live,
and `constat.ai` and `constat.io` are held on aftermarket nameservers — `constat.ai` redirects to a
GoDaddy for-sale page, so it is purchasable at an unknown price. Paying aftermarket rates before any
user validation would contradict the roadmap's own guiding principle.

**Consequences.**

- **`constat.ai` remains the upgrade path.** It is listed for sale rather than in use. If validation
  succeeds and a brand budget exists, it is the domain to buy. Worth re-checking periodically; a
  listed domain can be withdrawn or bought by someone else.
- A `try<name>.com` form reads as a product landing page, which suits the pilot-recruitment phase
  the roadmap schedules for weeks 3–8. It reads less well as a long-term corporate identity.
- `getconstat.com` and `constathq.com` are already taken, so the two next-most-obvious prefix
  patterns are unavailable. If `tryconstat.com` is ever abandoned, the fallback is a different TLD,
  not a different prefix.
- Nothing is deployed to it yet, and nothing should be: there is no product to show. Registering it
  now is about securing the name, not launching.

**Status.** accepted

---

## D-013 · 2026-11-08 · The product is named Constat

**Decision.** The working name "Claudine" was rejected and the product is renamed **Constat**. The
GitHub repository is `padjis/constat`. Done before the initial commit, so no public history or
external reference needed rewriting.

**Context.** Resolves the escalated name blocker. Preliminary research found that "Claudine"
conflicted with Anthropic's registered CLAUDE mark (US #7645254) in the same class of goods and
services, with an enforcement precedent from 2026-01-27 against *Clawdbot* — a weaker, merely
phonetic resemblance. "Claudine" contains the literal string `Claud` and parses as *Claude* plus the
French diminutive `-ine`, which is a textbook formative mark. Full analysis in
[BRAND_NAME_REVIEW.md](BRAND_NAME_REVIEW.md).

Under D-011 the trademark is the primary defensible asset, because Apache-2.0 makes the code
forkable. Building that asset on a name that might have to be surrendered inverted the whole
strategy.

**Why Constat specifically.** In French law a *constat* is a formal written statement of observed
fact; a `constat d'huissier` is admissible evidence. That is precisely what this product emits —
observed facts, formally recorded, attested by a named person, distinguishable from inference. The
name states the product thesis rather than gesturing at it, and it is institutional rather than
persona-flavoured, which suits a governance and audit buyer.

**Consequences.**

- **The name is not cleared.** No USPTO, EUIPO or INPI search has been run. See
  BRAND_NAME_REVIEW.md § 9 for the outstanding list. Do not print it on anything expensive yet.
- **No primary domain is available.** `constat.com`, `.ai`, `.dev` and `.io` were all registered as
  of 2026-11-08. A domain must be acquired before outbound discovery work. This is the one naming
  criterion the choice knowingly fails, traded against the strength of the semantic fit.
- **Jurisdictional asymmetry.** In France and before the EUIPO, `constat` applied to evidence
  software is suggestive of the goods and therefore a weaker mark; in the US and UK it is arbitrary
  and stronger. If the first customers are French or EU, this may argue for a distinctive composite
  rather than the bare noun. A question for counsel, not a reason to revisit now.
- The Python package is `constat/`; the CLI command name is settled at Session 02.

**Status.** accepted

---

## D-012 · 2026-11-08 · Drift is per-claim evidence staleness, not a correctness verdict

**Decision.** Resolves open question Q4. Documentation drift is defined as **"the evidence
supporting this claim has moved"**, evaluated per claim rather than per document, using the
evidence source pointers established in D-005. Three states:

| State | Meaning | How it is determined |
| --- | --- | --- |
| `current` | No commit since the baseline's target revision touched the cited evidence. | Deterministic |
| `unverified` | The cited evidence changed. The claim **may or may not** still hold. | Deterministic |
| `orphaned` | The cited path no longer exists. | Deterministic |

**Context.** The tempting definition — "the documentation is now wrong" — is one Constat cannot
support. Detecting that an approved description no longer matches current behaviour requires
semantic understanding, i.e. AI inference, which would make the headline governance feature the
least trustworthy thing in the product and break product rule 1 on exactly the surface where trust
matters most.

**Consequences.**

- **Drift is a signal, never a verdict.** Reports say "this claim's evidence has changed;
  re-verify", never "this claim is false". Non-negotiable; it is the difference between a reviewer
  trusting the tool and dismissing it.
- Fully deterministic, so it works with no AI provider configured and `unverified` counts are
  directly testable.
- It aggregates into a sentence a reviewer can act on: *"7 of 23 approved claims are unverified
  since baseline v4."*
- **Noise suppression is required, not optional.** Rename-following (`--follow`) and
  whitespace-insensitive comparison (`-w`) must be in from the start. Against a repository with
  Subject A's commit volume, drift without these flags fires on everything and the feature becomes
  noise.
- **Known weakness, must be documented at Session 20:** a business rule changed in a file the
  baseline never cited produces *no* drift signal. Constat under-reports rather than over-reports.
  That is the correct direction to fail, but a pilot will find it and it must be disclosed rather
  than discovered.

**Status.** accepted

---

## D-011 · 2026-11-08 · Apache-2.0, with a DCO on all contributions

**Decision.** Resolves open question Q10. Constat is licensed under Apache License 2.0
(`LICENSE`, `NOTICE`). All contributions require a Developer Certificate of Origin sign-off
(`git commit -s`), documented in `CONTRIBUTING.md` with the DCO 1.1 text in `DCO`.

**Context.** Three factors decided it:

1. *Procurement survivability.* The roadmap has us asking pilot customers in weeks 6–8 what
   procurement and security checks apply. Apache-2.0 is on effectively every enterprise allowlist;
   AGPL is on many deny lists, and for a tool pointed at a customer's private source code an AGPL
   licence invites a legal discussion unrelated to the product.
2. *The patent grant.* MIT offers none. Apache-2.0's explicit grant is what an enterprise reviewer
   looks for and costs nothing to give.
3. *BUSL is premature.* Source-available non-compete licensing is the right tool when there is
   revenue to protect. At zero users it signals paranoia and still fails some allowlists. The real
   risk is obscurity, not cloning.

**Consequences.**

- **Relicensing freedom depends on the copyright position staying clear.** A future commercially
  licensed edition is only possible while contributions are traceable. Accepting a single outside
  pull request without a sign-off would permanently foreclose that option — hence the DCO is in
  place *before* the repository attracts contributors, not after.
- The DCO was chosen over a CLA deliberately: it preserves the same optionality with no paperwork
  and no signing ceremony, which is appropriate for a project with one contributor.
- The copyright holder is recorded as "Emmanuel Padjinou" in `LICENSE` and `NOTICE`. If the work
  should be held by a company rather than an individual, both files need updating before any
  outside contribution is accepted.

**Status.** accepted

---

## D-010 · 2026-11-08 · "Behaviour change" means business rule change

**Decision.** Constat's subject is **business rule change** — not any code change, and not all
externally observable behaviour. Refactors, dependency bumps, build changes, formatting and
infrastructure edits are reported as context but are not the thing Constat claims to explain.

**Context.** Resolves open question Q2. "Any code change" makes Constat a diff viewer; "externally
observable behaviour" still includes performance, UX and operational change that Constat has no
evidence for. Business rules are what product owners, business analysts and engineering leaders
actually argue about, which matches the stated audiences.

**Consequences — the hard part.** Business rules are *not* reliably detectable from a diff. A rule
living in a service-layer `if` statement is invisible to deterministic analysis. Inferring it would
violate product rule 1 (no unsupported certainty). So the MVP needs a deterministic spine of
rule-bearing evidence and must return `unknown` elsewhere.

In the chosen sample repository (D-009) that spine exists and is strong:

> **This table is withdrawn.** It listed three code signals — feature flags, SQL migrations and
> bean validation — as deterministic sources of business rules. Flags were removed by D-034,
> migrations and the remainder by **D-038**. None of them are rules: under D-035 a rule is a
> business statement, and a migration or an annotation is at most *evidence* that one exists.
> Rules now come from a human-declared catalogue.

Classification (Session 08) targets these three first. Everything else is `unknown` until a human
says otherwise. This is a narrower and more defensible MVP than "explain the diff".

**Status.** accepted; the rule-source table withdrawn by D-038

---

## D-009 · 2026-11-08 · Sample subjects are two private repositories, aliased A and B

**Decision.** The primary test subjects are two private repositories belonging to the author,
referred to throughout as:

| Alias | What it is | Scale | Tagging |
| --- | --- | --- | --- |
| **Subject A** | Java/Gradle backend, four modules | 1130 commits, 777 tags | machine-generated build tags, one per build |
| **Subject B** | Mobile application | 444 commits, 11 tags | semver release tags |

The Session 19 cross-repo scenario uses this pair. They are **private**, so they are named only in
a gitignored `SUBJECTS.local.md`; this public repository carries the measurements and properties
the decisions rest on, but not the identities.

**Context.** Resolves open question Q8. The roadmap asks for a small project we own and can safely
analyse. These are owned, local, actively developed, and — critically — the owner knows them well
enough to judge whether Constat's output is *accurate*, which is what prototype validation
requires.

**Consequences.**

- **The two repos version incompatibly.** Subject A uses machine-generated build tags (date plus
  hash, one per build); Subject B uses semver release tags.
  There is no shared version space. This is a gift rather than a problem: it forces product rule 6
  ("release streams are distinct") to be honoured from the start instead of being discovered late.
- **Constat must distinguish release tags from build tags** or drown in 777 of them. Tag selection
  needs to be a deliberate feature, not an afterthought — revisit at Session 04 (revision
  resolution).
- Subject A carries an in-repo architecture decision log. That is a real source for the
  `requirement_ref` provenance type, which anchors Session 18 traceability in something that already
  exists rather than something hypothetical.
- Analysis must respect `.gitignore`: Subject A's build-output directories contain generated
  artefacts and are correctly untracked. Evidence collection reads tracked files only.

**Status.** accepted

---

## D-008 · 2026-11-08 · Report and proposal schemas are versioned from day one

**Decision.** Every stored proposal and rendered report carries a `schema_version`. No backward
compatibility is promised before the MVP ships.

**Context.** Governance data is meant to survive; a stored baseline is useless if we cannot tell
which schema produced it. Versioning is cheap now and expensive to retrofit.

**Consequences.** One extra field everywhere. Migration logic is deferred until a real schema break
occurs.

**Status.** accepted

---

## D-007 · 2026-11-08 · Reviewer identity is asserted, not authenticated

**Decision.** The reviewer recorded on a decision comes from explicit CLI input or configuration, and
is stored as an *asserted* identity. No authentication in the MVP.

**Context.** Authentication is explicitly deferred. A solo-founder prototype has no identity
provider, but "approval is explicit" still requires knowing *who* approved.

**Consequences.** The audit trail is honest about its own weakness: it records a claim of identity,
not proof. This must be stated in the README limitations section (Session 20), because an enterprise
pilot will ask.

**Status.** accepted

---

## D-006 · 2026-11-08 · Baselines are append-only rows with a content hash, not a signed chain

**Decision.** Immutability is implemented as append-only versioned rows plus a content hash per
baseline version, linked to the previous version. No cryptographic signing.

**Context.** Resolves open question Q3. The product rule is "history is durable and traceable", not
"history is tamper-proof against a hostile local user". Signing solves a threat the MVP does not
have.

**Consequences.** A user with direct SQLite access could still edit history. Acceptable locally;
revisit if a pilot raises an audit requirement.

**Status.** accepted

---

## D-005 · 2026-11-08 · Evidence is bounded, but always re-derivable from Git

**Decision.** Diff excerpts are capped per file and per proposal. Every excerpt stores a source
pointer (`rev:path:line-range`) so the complete original can be re-read from Git on demand.

**Context.** Resolves open question Q7. "Diffs become too large or noisy" is a named risk, but
truncating evidence would violate "evidence is inspectable".

**Consequences.** Constat never becomes the sole copy of the evidence. Requires the repository to
remain available at review time — an accepted local-first constraint.

**Status.** accepted

---

## D-004 · 2026-11-08 · The structured proposal is the system of record; Markdown is a view

**Decision.** Reviewer edits apply to the structured proposal. The Markdown report is a rendered
projection and is never parsed back into the model.

**Context.** Resolves open question Q5. Round-tripping Markdown into structured data would lose
provenance, which is the one thing Constat cannot afford to lose.

**Consequences.** The review experience must be good enough to edit structure directly. Rendering is
a pure function and therefore easy to test.

**Status.** accepted

---

## D-003 · 2026-11-08 · AI is optional and isolated behind a provider interface

**Decision.** The deterministic evidence pipeline has no dependency on any AI provider. A null
provider is the default. All AI output is labelled `ai_interpretation`.

**Context.** Avoids recurring API costs before the workflow is validated, keeps the "no unsupported
certainty" rule structurally enforceable, and means the prototype works offline.

**Consequences.** A test asserts the full pipeline produces a valid report with zero
`ai_interpretation` claims when no provider is configured.

**Status.** accepted

---

## D-002 · 2026-11-08 · Python CLI, Git subprocess, Pydantic, SQLite, Markdown, pytest

**Decision.** Adopt the roadmap's technology table unchanged for the first version.

**Context.** The goal is to validate the product workflow, not the infrastructure. These choices are
fast to build, easy to test and need no running services.

**Consequences.** Shelling out to `git` means depending on a `git` binary and parsing its output —
accepted, because reimplementing Git internals is strictly worse. No web UI, so the first users must
be comfortable with a terminal.

**Status.** accepted

---

## D-001 · 2026-11-08 · Local-first, single-repository MVP; defer the platform

**Decision.** The first release proves one complete workflow end to end — select, analyse, propose,
review, baseline, compare — locally, against one Git repository. Dashboard, SaaS, auth, billing,
Kubernetes, Kafka, graph database, multi-agent orchestration and automatic approval are all
deferred.

**Context.** The roadmap's guiding principle: build a small, trustworthy change-governance workflow
first and prove teams value it before investing in a platform. "Overbuilding before validation" is a
named top risk.

**Consequences.** Cross-repository value — the actual differentiator — is only demonstrated at
Session 19, via a scenario spanning two repositories or simulated linked PRs. That demo is therefore
a milestone, not an afterthought.

**Status.** accepted

---

## Open items (not yet decided)

- **Trademark clearance for "Constat"** — the name is chosen (D-013) but **not cleared**. No USPTO,
  EUIPO or INPI search has been run. Needed before the first pilot conversation. See
  [BRAND_NAME_REVIEW.md](BRAND_NAME_REVIEW.md) § 9.
- **Register `tryconstat.com`** — chosen in D-014 and confirmed unregistered on 2026-11-08, but
  **not yet actually registered**. Do this before it is discussed publicly.
- **Unit of a change proposal** (spec Q1) — has a working assumption (one proposal per
  `(repository, base_rev, target_rev)`) but no ratifying decision. Needed by Session 07.
- **Release tag vs build tag discrimination** — surfaced by D-009: Subject A carries 777
  machine-generated build tags. Revision resolution must not treat them as release points. Needed
  by Session 04.
- **Copyright holder: individual or company** — see D-011 consequences.
