# Project status

**Last updated:** 2026-11-18
**Current phase:** Phase 3 — Meaning and reporting (reshaped by D-035 … D-039)
**Current session (2026-11-18):** **CON-81 closed (D-081)** — a rule's citation is flat (`R-14`),
stored and never reused, schema 17. Before it, **CON-89 (D-080)** — a baseline documents an area with no
evidence from Constat, under a reference, and with no schema change. Before it, **CON-88 and CON-90
(D-079)** — an area is declared by accepting a rule, and coverage is counted in areas, schema 16. Before them, **CON-67 (D-078)** — a
detail's identity is its text, numbered at acceptance, schema 15 — and **CON-80 (D-077)** — a rule
carries worked examples, schema 14. Earlier the same day, with no code: the catalogue was reviewed against a worked
implementation of the same idea, producing **D-076** (Constat assumes trunk-based development, and
product rule 6 is unmet), a decision to acquire a **release concept**, and **16 tickets**
(CON-80…CON-98).

**2026-11-16:** CON-22 attempted and recorded as not possible from here
(`BRAND_NAME_REVIEW.md` § 10); the brief for CON-23 is written and its first question is whether the
name is registrable at all.

**2026-11-15:** CON-21 closed (D-075) — the site starts at
`constat.padjinou.com` and no domain is bought, amending D-014's timing. CON-25 closed before it
(D-074) — copyright held personally, with the triggers that would reopen it named. CON-61 closed before it — a frozen version's behaviours and
anchors are readable, completing CON-14's recoverability criterion and unblocking CON-67. Rule 3
(`install-pages-carry-no-advertising`) was accepted, the catalogue's first rule derived from the
product's intent rather than from a diff. CON-79 closed before it (D-073) — a rule records the
evidence it was accepted on, as a pointer rather than a copy. Raised and closed in the same session: the defect was
already true of both rules in the catalogue. CON-71 closed before it (D-072) — an anchor may be
grounded in mainline, and which ground supports it is recorded. CON-78 and CON-72 closed before it (D-070, D-071) — the
product's current state can be read, grouped by business area, and a rule may be conditional with
the condition in its statement. CON-77 (D-070), CON-75 (D-069) and CON-76 (D-068) closed before them today;
CON-73 (D-065, D-067), CON-74 (D-066), CON-70 (D-064), CON-69 (D-062) and CON-64 (D-063) on
2026-11-14. Every one came out of reading tickets 615 and 628 through the MCP loop rather than out
of reading the code — the clearest argument available for running the product before extending it.

---

## Where things stand

The repository is public at `https://github.com/padjis/constat`. Session 01 was committed and
pushed as `b092b62`.

A workspace now persists repositories, tickets, living documents and a rule catalogue. A ticket
reference gathers evidence across every registered repository (CON-34) and the catalogue reports
which changed paths no rule claims (CON-40).

**Rules are produced, and nothing deterministic produces them** — D-035 settled that a rule is a
business statement no code signal yields, and D-039 made generation an AI pass. There are now
three ways a reading reaches the workspace, and all three land in the same append-only review
queue with the same grounding check behind them:

| Path | Who calls the model | Model id |
| --- | --- | --- |
| `CONSTAT_AI_PROVIDER=anthropic` + `ticket add` | Constat | attested |
| `constat mcp`, driven by an agent | the host | self-reported |
| `rule submit --from reply.json` | you, by hand | self-reported |

**Two backlog statuses were stale and are corrected** (2026-11-12): CON-12 ("no proposal becomes
official without an explicit human decision") closed at CON-44, and CON-14 (immutable baselines)
at CON-43. Auditing CON-14 found a real gap rather than only a stale label: `rule_version_behaviour`
and `rule_version_anchor` are written and frozen by trigger, but **no code path reads them**, so a
version's behaviours and anchors as they stood at acceptance are in the database and unreachable.
Raised as **CON-61**.

**A document can now leave the machine.** `constat publish <REF>` writes the stored document to a
documentation target — by default the wiki of the current repository's remote, derived and never
guessed. It is the only command that writes outside the workspace; `gather` cannot publish and
accepting does not. Three egress points now exist (`document --payload`, MCP `get_payload`,
`publish`) and all three go through the same credential detectors.

**A rule-generating command refuses when nothing can read the evidence** (D-059), and **who reads
is a workspace setting** rather than a per-command flag (D-060):

```bash
constat init --reader mcp     # or: constat config reader mcp
constat ticket add 615        # no flag needed, ever
```

`provider` is the default and keeps D-059's refusal; `mcp` turns it off because on that path
having no provider is correct (D-045). `--no-provider` survives as a per-run override. The
evidence path still needs no key.

**The MCP loop is one command, and both paths now define a rule the same way** (CON-66). An MCP
server cannot initiate anything, so the user starts the loop — and clients surface a prompt as a
slash command:

```
/mcp__constat__document 615    gather, read, submit
/mcp__constat__review 615      summarise what is waiting
```

**And that command now works on a clean workspace** (CON-64, D-063). `gather_evidence` opens a
ticket it does not find, so nothing at the command line precedes the agent's first call. A
reference matching no commits anywhere is still refused, with the repositories searched named.

The more important half is `constat/ai/guidance.py`: the guidance on what a business rule *is* now
lives once and is imported by both the Anthropic provider's `SYSTEM` and the `document` prompt. A
rule proposed over MCP and the same rule proposed by a provider have to mean the same thing, or the
catalogue becomes a record of which path happened to be configured. Neither prompt may instruct
acceptance, and a test asserts it.

**`--by` is optional, and the record says whether the name was stated or inferred** (D-061):

```
constat rule accept 1
  accepted: rule 1 created, version 1 baselined
  recorded as: Emmanuel Padjinou <e@…> (inferred from git config)
```

Not a trust level. `--by` is a free string nobody checks, so a typed name and a name from git config
are equally unverified; what is recorded is the narrower, honest distinction — whether a person
asserted this name or a machine supplied it. With no git identity at all it refuses rather than
guessing. This does **not** soften D-055: an MCP `accept` tool is still unacceptable, because the
objection there was never the name.

CON-42 is closed by CON-60. The pieces arrived separately — the trust boundary at D-046, storage at
CON-51, the submit path at CON-52, the MCP host at CON-50, and finally a provider that issues the
request itself at D-057. CON-09 is closed by CON-56: the document renders from stored state and
works as a pull-request body.

**Q1 is closed.** All ten original open questions from Session 01 are now resolved.

### Session 07 — done when: *stable, tested structured output* ✅

| Item | Status |
| --- | --- |
| `constat/models.py` — Pydantic schema, frozen, `extra="forbid"` | ✅ |
| `constat/mapping.py` — one-directional adapter→model layer (D-026) | ✅ |
| `schema_version` on every proposal (D-008) | ✅ asserted in tests |
| Generated `proposal_id`, deterministic `selection_key` (D-025) | ✅ |
| Repository identity from the root commit, not the path | ✅ survives move and re-clone |
| Discriminated `change` / `state` selections; `commit_set` reserved | ✅ |
| Full provenance taxonomy declared; evidence defaults to `observed_fact` | ✅ |
| JSON round-trip, including the selection discriminator | ✅ |
| `--json` on both commands | ✅ |
| Pydantic added as the first runtime dependency, with a stated reason | ✅ D-026 |

### Tests run

```
.venv/bin/python -m pytest  →  179 passed
```

36 new tests. The existing 143 needed **no changes**, which is the point of the D-026 boundary:
the Git layer stayed dependency-free dataclasses.

### Verified against a real repository

Subject A, a build-tag range, via `--json`: schema_version 1, 7 commits, 29 changes, 29 evidence
records all `observed_fact`, completeness 2223 captured / 32 omitted, and a repository identity
derived from the root commit rather than the path.

### The decision that actually mattered

Not the models — **identity**. A derived proposal ID (hash the inputs) is the tempting choice and
breaks the governance model: a fresh re-analysis would collide with an approved baseline for the
same range. History must be append-only (product rule 5), so identity is generated per run, and a
separate `selection_key` recovers the idempotent lookup derivation was wanted for. The two are not
in tension; they just need two fields.

### Session 06 — done when: *evidence records can be traced back to Git* ✅

| Item | Status |
| --- | --- |
| `constat/evidence/collector.py` — commits, excerpts, source pointers | ✅ |
| Commit metadata: sha, author, committer, both dates, subject, body, parents | ✅ |
| Author and committer never collapsed (a rebase rewrites one, not the other) | ✅ |
| Merge commits included and flagged, not filtered out | ✅ |
| Bounded excerpts, 400 lines/file and 4000/comparison (D-023) | ✅ measured, not invented |
| Fair-share allocation rather than first-come (D-024) | ✅ |
| Every excerpt records a reproduce command — **tested by running it** | ✅ |
| Truncation always stated: total lines, omitted count, reason | ✅ |
| Binary files recorded as binary, never given a fabricated diff | ✅ |
| A file is never dropped from the record, only its text | ✅ |

### Tests run

```
.venv/bin/python -m pytest  →  143 passed
```

29 new tests. The central one actually executes the recorded `git` command and asserts it returns
content the truncated excerpt does not contain — traceability proven rather than asserted.

### Verified against real repositories

- Subject A, a build-tag range: 7 commits, 29 files, 2223 lines captured, 1 file truncated.
- Subject B, a release range: 18 commits, 50 files, **49 captured whole**; only a generated
  lockfile truncated, at 393 of 3835 lines.

### A bug caught before shipping

The first implementation spent the excerpt budget first-come down the sorted file list. On the real
Subject B range that meant a generated lockfile took 400 of 4000 lines and files later in the
alphabet got **nothing** — evidence selection determined by filename ordering. Fixed by allocating
fairly before keeping any text (D-024); the real range went from starving later files to capturing
49 of 50 whole.

### Session 05 — done when: *a deterministic change summary for two revisions* ✅

| Item | Status |
| --- | --- |
| `constat/git/diff.py` — `compare_revisions`, `summarise_state` | ✅ |
| Merge-base comparison, merge base recorded and always stated (D-021) | ✅ |
| Renames keep both paths and the similarity score | ✅ |
| Deletions reported explicitly | ✅ |
| `ChangeType.UNKNOWN` for unrecognised status letters, never a guess | ✅ |
| `-z` parsing — paths with spaces, unicode and newlines survive | ✅ |
| Backwards range refused rather than reported as empty (`BackwardsRange`) | ✅ |
| Unrelated histories refused (`NoCommonAncestor`) | ✅ |
| Deterministic: explicit sort, identical output across runs | ✅ |
| State read with `ls-tree`, no change vocabulary (D-022) | ✅ |

### Tests run

```
.venv/bin/python -m pytest  →  114 passed
```

28 new tests. Merges, renames-with-edits, orphan branches, empty commits, awkward filenames and
read-only guarantees are all covered.

### Verified against real repositories

- Subject A, a build-tag range: 29 changed files, base is an ancestor of target.
- Subject B, a release range: 50 changed files, and the two tags have **diverged** — the merge
  base is neither tag.
- Subject A, `snapshot --rev main`: 628 files present.
- **The `BackwardsRange` guard fired on real data.** A Subject A build-tag pair supplied in the
  wrong order was refused. Without it the output would have read "No file changes in this range",
  which is the confidently-wrong-empty-report failure this product exists to avoid.

### An honest limit on the D-021 evidence

The two diff semantics provably differ — a constructed test shows the endpoint diff reporting a
base-only file as a deletion. But on real data the difference has **not** yet been observed to
change a report: for a Subject B release range, despite genuine divergence, both semantics
give identical results (50 files, 1 deletion). D-021 rests on asking the right question, not on an
observed discrepancy here.

### Session 04 — done when: *tests cover valid, invalid and missing repositories/revisions* ✅

| Item | Status |
| --- | --- |
| `constat/git/adapter.py` — read-only, shells out to `git` (D-002) | ✅ |
| `discover_repository()` — path, repository and branch | ✅ |
| `resolve_revision()` — symbolic name + full SHA retained (D-019) | ✅ |
| Distinct error types, separate from `InvalidInput` | ✅ `RepositoryError` and five subtypes |
| Repository failures exit **3**, malformed input still exits 2 | ✅ |
| Throwaway-repository fixtures; no dependency on the real subjects | ✅ `tests/conftest.py`, `tests/helpers.py` |
| Annotated tags resolve to the commit, not the tag object (D-019) | ✅ |
| Ambiguous revisions refused rather than guessed (D-020) | ✅ |
| Bare repositories, detached HEAD, unborn HEAD, subdirectories | ✅ |
| Read-only proven, not asserted | ✅ tests compare `status`/`HEAD`/`show-ref` before and after |

### Tests run

```
.venv/bin/python -m pytest  →  86 passed in 2.36s
```

38 new tests. Verified against both real repositories, including their incompatible tag schemes:
Subject A's build tags and Subject B's semver tags both resolve.

### Correction to an earlier claim

I had said the 777-build-tag problem would come due at Session 04. It did not. Nothing in Constat
selects a revision for the user — every option is required with no default — so no code path can
pick a build tag. The obligation here was *negative*: do not add "latest tag" convenience. Tag
classification moves to whichever ticket first wants to auto-select. See `BACKLOG.md`, CON-04.

### Session 03 — done when: *helpful errors; no silent defaults for important inputs* ✅

| Item | Status |
| --- | --- |
| `analyse --repo --base --target`, all required | ✅ |
| `snapshot --repo --rev`, all required (D-016) | ✅ |
| `constat/config.py` — `AnalysisRequest`, `SnapshotRequest`, frozen dataclasses | ✅ |
| `constat/errors.py` — `ConstatError`, `InvalidInput` | ✅ |
| No default for `--repo` — never analyses the current directory implicitly | ✅ |
| No default for `--rev` — a baseline's revision must be stated, not inferred | ✅ |
| Whitespace reported rather than silently stripped | ✅ |
| Self-comparison (`--base` == `--target`) rejected with the value named | ✅ |
| Invalid input exits 2 with a message on stderr and nothing on stdout | ✅ |

**Scope boundary held:** Session 03 validates the *shape* of input only. Whether the path exists, is
a Git repository, or the revisions resolve, is Session 04. A test asserts a nonexistent path is
*not* rejected here, so "you typed it wrong" and "your repository is broken" stay distinguishable.

### Tests run

```
.venv/bin/python -m pytest  →  48 passed in 0.30s
```

26 new tests across `tests/test_config.py` and `tests/test_cli.py`. Every rejection path asserts on
the **message**, not just the exit code — "fail clearly" is the acceptance criterion, so a correct
code with an unhelpful message would be a failure.

### Verified by hand

```
$ constat snapshot --repo <subject-a> --rev main   → input accepted, nothing read
$ constat analyse --repo <subject-a> \
    --base <tag-1> --target <tag-2>                → input accepted, nothing read
$ constat analyse --base a --target b              → error: --repo required  (exit 2)
$ constat analyse --repo <subject-a> \
    --base main --target main                      → error: nothing to compare (exit 2)
```

---

### Session 02 — done when: *the CLI installs and runs locally; tests execute* ✅

| Item | Status |
| --- | --- |
| `pyproject.toml` — setuptools, Python ≥ 3.11, Apache-2.0 metadata | ✅ |
| `constat/` package with `__version__` as single source of truth | ✅ |
| `constat/cli.py` — argparse, `--version` / `--help` (D-015) | ✅ |
| `constat/__main__.py` — `python -m constat` works pre-install | ✅ |
| `constat` console script entry point | ✅ verified running from the venv |
| Virtual environment + dependency management | ✅ `.venv`, editable install with `[dev]` extra |
| pytest configured and running | ✅ 8 tests, all passing |
| Zero runtime dependencies | ✅ `dependencies = []` |

### Tests run

```
.venv/bin/python -m pytest  →  8 passed in 0.21s
```

Covered: `--version` exit code and output; `--help`; bare invocation printing help rather than
failing silently; unknown flag exiting 2 with a usage error; parser constructible in isolation;
`python -m constat`; and the installed console script actually executing.

The version-drift test was **mutation-checked** — setting `__version__` to a wrong value was
confirmed to fail it, so it is not passing trivially.

### Verified by hand

```
$ constat --version        → constat 0.0.1
$ constat                  → usage + description + "no analysis commands exist yet"
$ python -m constat --version → constat 0.0.1
$ constat --nope           → error: unrecognized arguments: --nope   (exit 2)
```

---

### Session 01 — done when: *a documented empty project with clear scope and rules* ✅

| Item | Status |
| --- | --- |
| Git repository | ✅ initialised locally on `main`, `origin` configured |
| `README.md` | ✅ written |
| `CLAUDE.md` | ✅ written |
| `PRODUCT_SPEC.md` | ✅ written, including 10 open questions |
| `ARCHITECTURE.md` | ✅ written — proposal, nothing implemented |
| `DECISIONS.md` | ✅ written — D-001 … D-008 |
| `PROJECT_STATUS.md` | ✅ this file |
| `.gitignore` | ✅ written |
| `LICENSE` / `NOTICE` | ✅ Apache-2.0 — D-011 |
| `CONTRIBUTING.md` / `DCO` | ✅ DCO sign-off required — D-011 |
| Initial commit pushed | ✅ `b092b62`, signed off, pushed to `origin/main` |

---

### Known issues / open items

- **Personal data in evidence: settled (D-040).** Identity does not cross the provider boundary at
  all — no names, no addresses, no timestamps, and the payload type has no field for them. The
  obligation D-023 recorded is discharged, before any provider exists.
- **A built wheel was broken, and is fixed (CON-46, D-042).** `packages = ["constat"]` dropped every
  subpackage from the wheel from CON-04 onwards, unnoticed because the development install is
  editable. Now discovered rather than listed, with `tests/test_packaging.py` building a wheel and
  importing from it.
- **Secret scanning is in place (CON-45, D-044), with stated misses.** Known formats only, so a
  passphrase of one character class or any credential with no recognisable shape is not detected.
  An empty scan is not a clean bill of health, and the document says so rather than implying one.
- **The AI cost is now a measured number, not an estimate.** 8 commits in one repository produce a
  ~47,000-token payload. The registered set is plural by construction, so this scales the wrong
  way, and CON-42 must treat payload size as a design constraint.
- **CON-39 blocks review, now in a narrower form (D-043).** The document body is machine-written
  only — a human comments, validates a rule or rejects an implementation, and never edits — so
  regeneration destroys no prose. What remains is that a comment is anchored to something the next
  run rewrites: **anchors must be durable identities, not positions in text.** Still gates CON-12
  and CON-44, and now also CON-47.
- **`.venv/` is gitignored and must be recreated per clone** — see the README. On NixOS there is no
  system pip; `python3 -m venv` supplies one via `ensurepip`.
- **SSH to GitHub does not work from this machine.** The key at `~/.ssh/id_rsa` is 2048-bit RSA,
  which GitHub now rejects as too short. Pushing uses HTTPS with a stored credential instead. If SSH
  is ever wanted, generate an ed25519 key.
- **Name chosen but not cleared.** Renamed from "Claudine" to **Constat** on 2026-11-08 (D-013),
  before any commit was published. No USPTO/EUIPO/INPI search has been run. See
  `BRAND_NAME_REVIEW.md` § 9.
- **Website is `tryconstat.com`** (D-014) — chosen and confirmed unregistered, but **not yet
  registered**. `constat.ai` is listed for sale and is the upgrade path post-validation.
- **Q1 (unit of a proposal) was widened by D-016 and remains open.** The unit is
  `(repository, revision_range)` where a range is closed (`base`→`target`) or open (single
  revision). The earlier `(repo, base_rev, target_rev)` assumption was too narrow. Needed by
  Session 07.
- **Reports must keep state and change distinct** (D-016). A snapshot asserts "this is how it
  behaves"; an analysis asserts "this is what moved". Session 09 must not collapse them into one
  renderer.
- **Tag selection is deferred, not solved.** Subject A has 777 build tags against Subject B's 11
  semver tags. This only matters once something *auto-selects* a revision; today
  nothing does, because every option is required. Due at whichever ticket first adds "latest tag",
  "default branch" or "since last release".
- **Copyright holder** recorded as an individual in `LICENSE`/`NOTICE`; change before accepting any
  outside contribution if it should be a company.
- Q2, Q4, Q8 and Q10 are now resolved (D-010, D-012, D-009, D-011); the product name is resolved
  by D-013.

---

## Next single task

**CON-23 — the trademark attorney review, asked in the right order.** CON-22 was attempted on
2026-11-16 and **cannot be done from this environment**: every register is either blocked or a
JavaScript application with nothing server-rendered to read (`BRAND_NAME_REVIEW.md` § 10). It needs
a person with register access — or folding into CON-23, which is the recommendation.

§ 10 writes the brief, and its first question is the one that matters: **is `CONSTAT` registrable at
all in FR/EU for classes 9 and 42, or is it descriptive** for software that produces findings? That
is a go/no-go on the name, and it should be asked before paying for a clearance search on a name
that may be unregistrable. The two things § 10 did establish: `e-constat auto` is the French
insurance industry's official app, so the word is already in use as a software product name in
French; and no software company called Constat surfaced, which is weak evidence of availability and
nothing more.

CON-26 is still at zero discovery conversations, and the repository has been public throughout.

CON-25 is now closed (D-074): the copyright is held personally, which `LICENSE` and `NOTICE`
already said — the ticket needed a recorded decision, not an edit. CON-21 is closed too (D-075):
the site starts at `constat.padjinou.com` and no domain is bought, which accepts rather than solves
the risk that `tryconstat.com` stays registerable by anyone.

The next code task is **CON-82 — a user-facing message is a catalogue entry a rule refers to**,
which D-081 just unblocked: a message takes the same flat form (`M-7`). It is the last of the §1
cluster, and the one that most changes what a business reader can check, since a quoted message is
the most verifiable thing a rule can carry.

Two smaller things are now reachable and unblocked: **an MCP tool for `baseline`**, which would be a
thin wrapper over `baseline_area` (D-080 left it unbuilt deliberately), and **CON-15**, comparing
against the last approved baseline, which CON-67's per-detail diff supplies most of.

Still at zero: **CON-26**, discovery conversations. Nine tickets have closed in two days and the
validation track has not moved.

The cluster CON-80 and CON-67 belong to has one piece left — **CON-81, a citable rule identifier**,
and with it **CON-82, messages as catalogue entries**. CON-81 needs a decision from you on the
*form* (area-prefixed like `BR-UPL-006`, or flat), and CON-82 cannot start until it lands.

**CON-15** (compare against the last approved baseline) is now reachable for the first time: CON-67
supplies a per-detail diff between two versions, which is most of what comparing against a baseline
needs.

Then **CON-58 — read decisions back, with their channel and verification**, the half of acceptance
that is still CLI-only.

Still unanswered rather than unbuilt: whether a merge commit should contribute evidence **at all**
(noted on CON-75); and how a *lapsed* condition is expressed now that D-071 allows conditional rules
— when the site is approved, rule 1 becomes false and only a superseding version can say so, which
says "the rule changed" rather than "the condition lapsed". That probably belongs with retirement.

~~Re-read ticket 628, now that a repair is sayable~~ **done 2026-11-14.** It worked: three
proposals became one, relation `repairs`, and the concurrency clause is gone from the statement.
Rule proposal 6 is in the queue, undecided. It also produced CON-75 and CON-76 — the third time in
two days that running the loop found more than reading the code did.

Then **CON-58 — read decisions back, with their channel and verification.** CON-70 and CON-74 are
closed; CON-71 (what grounding means when a rule is attested by evidence it is not anchored to) and
CON-72 (whether a rule may be conditional on a transient business state) still need a decision from
you before any code.

An alternative worth weighing ahead of CON-58: **breadth**. The guidance was validated on one
commit touching one file. A 30-commit ticket across the three registered repositories is the case
that would actually strain a reading, and nothing yet says it holds there.

~~Run one real ticket through the MCP loop on the live workspace~~ **done 2026-11-14**, written up
below. The decision not to bill API usage stands: the MCP path validated the guidance at no API
cost and leaves the provider's transport untested.

What CON-58 involves: the publishing port's `read_decisions` raises `DecisionsNotReadable` on
every target, so acceptance is still CLI-only — half of what the original question asked for.

D-061 is the thing to keep straight while building it: `attribution` (`stated` / `inferred`) sits
*inside* the CLI channel and is not `channel` or `verification`. `channel` says where a decision was
made; `verification` whether anything attested to it. A forge approval is genuinely verified;
nothing on the CLI is. Do not collapse the three.

Then **CON-61** → **CON-67** (a version's details are stored and unreachable; tracking them across
versions needs that read first).

Still standing: validation is at **zero discovery conversations** (CON-26). The site's home is
settled — `constat.padjinou.com` (D-075) — and no domain is owned, deliberately.

---

## CON-81 — done when: *a rule has a permanent, citable identifier* ✅

`D-081` records the decision you made: **flat**, `R-14`, not area-prefixed.

**Why flat was right, in one line:** an area is mutable by design (D-079 left it free text), and an
identifier encoding a mutable fact becomes a false claim the moment that fact changes — which is
exactly what D-078 established about positions, two tickets ago.

**Live:**

```
accepted: R-1 created, version 1 baselined

1 rule(s):
  advertising:
    R-1 install-pages-carry-no-advertising: The install pages carry no third-party advertising.

$ constat rule show R-1
R-1  install-pages-carry-no-advertising
```

The citation resolves as a lookup argument, because one nobody can look up is decoration.

**Back-filled — the first migration here that does.** D-070, D-072, D-077 and D-078 all refused,
because each would have invented a claim nobody made. A citation invents nothing: the rules exist,
and naming them asserts nothing about them. Refusing would leave a catalogue whose rules nobody can
cite, which is the defect being closed.

### Two mutations survived before the property was pinned

Worth writing down, because the first two attempts being wrong is the useful part.

Replacing the high-water mark (`MAX` of the citations) with a **count of rules** passed every test
in the new file. The first test written to catch it inserted an *uncited* rule — and that does not
distinguish the two, since a NULL ref is counted by neither. What distinguishes them is a **gap** in
the citations, which the back-fill can produce because it derives from row ids and row ids can have
gaps. With a gap, counting returns a number already in use, the unique index refuses the insert, and
an acceptance is lost to a numbering bug.

**A mutation that survives means the test did not pin the property — not that the property holds.**
The third attempt fails the mutation, as it should have the first time.

### Tests run

`.venv/bin/python -m pytest tests/test_rule_citation.py` → **16 passed** (new file). **Whole
suite**, because the schema changed: **1148 passed in 234s**, exit 0.

### Two things the tests forced

- **`rewind_workspace` now drops indexes** before dropping a column, discovered rather than listed —
  a map of index names would be one more thing to remember at the next migration, which is what that
  helper exists to stop.
- **Uniqueness is an explicit index, not an inline constraint.** `ALTER TABLE` cannot add an inline
  `UNIQUE`, so a migrated workspace would have had a different shape from a fresh one. Now both run
  the same `CREATE UNIQUE INDEX`.

`test_the_storage_api_has_no_writes_at_all` caught `by_id` as well, for the second time in two
sessions. It is doing its job: both additions were reads, added to the allowlist by name.

### Deliberately not done

- **The payload is unchanged.** `revises` still names the integer id, checked against the ids a
  reading was shown (D-050). A reading has no use for a citation — a statement must not contain
  identifiers at all (D-066).
- **No column on `rule_version`.** A citation names the rule, not a version, and never changes.

---

## CON-89 — done when: *an area can be documented from its current behaviour, with no ticket* ✅

`D-080` records the decision, including the one you chose against my recommendation and the
correction that followed.

**What it does.** `constat baseline <AREA>` stores a reading describing an area as it already
behaves. Constat supplies **no evidence**: there is no delta, so the reader works from the
repository directly, and what Constat does is ground every anchor, record which revision was
described, and store proposals nobody has accepted.

**Live, on a throwaway product:**

```
baseline of 'advertising', recorded under 'baseline-advertising'
  opened 'baseline-advertising' as a reference — it is not a unit of work, and will appear in `ticket list`

Described the product at:
  ui at f1206bc00f86

1 reading(s) were out of scope:
    `payout-threshold` — names area 'payouts', but this is a baseline of 'advertising'.
```

**No schema change, and that was the finding.** The chain `ticket → document → run → rule_proposal`
is `NOT NULL` at every link. Letting a run belong to an area would mean rebuilding **nine** tables —
SQLite cannot drop `NOT NULL` without a rebuild, `run`'s children cascade on delete, and
`PRAGMA foreign_keys=OFF` is a no-op inside the transaction migrations run in. So a baseline is
recorded under a reference instead, and the cost is announced rather than buried: a cold-start
reference appears in `ticket list` without being a unit of work.

### A correction I made to my own argument

I first told you the agent-driven shape violated **D-045**. It does not. D-045's invariant is that a
rule proposed over MCP and the same rule proposed by a provider must *mean* the same thing, which
the shared guidance enforces — `for_baseline` reuses `WHAT_A_RULE_IS`, `EXAMPLES` and `ANCHORS`
unchanged. A command being unavailable on one path is a **capability** asymmetry, not a meaning one.
Your choice was better founded than my framing of it, and D-080 records the real trade: a baseline
cannot be produced on the provider path.

### Two defects the by-hand run caught, after the tests passed

1. **An out-of-scope reading was reported twice**, the second time as "ungrounded or malformed" —
   a false label. It travels on its own field now, and a test asserts the parse's rejections stay
   empty.
2. **"anchored in mainline, not in this ticket's changes"** implied a deficiency on a baseline,
   where mainline is the only ground there can be. The ground stays visible; the clause goes.

Neither was visible from the test suite. Both came from reading real output.

### A fixture that was wrong, and the code was right

The first fixture committed a file and never pushed, so every grounding test failed — because
mainline is the remote-tracking ref (CON-76) and an unpushed commit is not shipped. The fixture was
fixed to push, which is the same correction CON-76's own write-up describes making to two tests.
It then hit `DefaultBranchUnknown`, because cloning an empty bare repository leaves `origin/HEAD`
unset — D-028 refusing to guess. Both were the code being right.

**One real gap the tests found:** a baseline's payload carries no repositories, so a
repository-scoped anchor was refused as naming an unknown alias. The mainline map's keys *are* the
registered aliases, so that is now the second source for the alias check — loosening only toward
repositories Constat actually has.

### Tests run

`.venv/bin/python -m pytest tests/test_baseline.py` → **21 passed** (new file). **Whole suite**,
because the parse change touches every grounding path: **1131 passed in 230s**, exit 0.

### Deliberately not done

- **No MCP tool.** It would be a thin wrapper over `baseline_area`, which ARCHITECTURE § 2 requires
  of every tool; worth adding, not needed to close this.
- **No provider-path baseline.** Stated, not worked around.
- **Nothing is accepted.** A baseline documents existing behaviour, which makes it tempting to treat
  as uncontroversial; a test asserts the catalogue stays empty until a human decides.

---

## CON-88 — done when: *an area is declared before a rule can claim it* ✅ · CON-90 ✅

`D-079` records both, and **amends D-070**, which made an area free text and called the drift into
"advertising / ads / monetisation" expected and unsolved.

**The ticket asked for less than it looked like.** Reading the code first: an area is *already*
declared by a human accepting a rule that carries it, because acceptance freezes the area onto the
version. So the register is **derived**, and the new table holds only areas named ahead of their
first rule — which is exactly what CON-89 needs. A table a human had to fill first would have forced
a refusal at acceptance, blocking a person mid-decision over a heading, and created two sources of
truth for one fact.

**What changed.** Schema **16** (one `area` table), `Catalogue.areas` unioning both sources,
`store/areas.py` for the write, `constat area list|add`, `SubmitResult.new_areas`, and the coverage
section of `render_state`.

**Live output.** A coined synonym, reported and still stored:

```
1 rule proposal(s) name a business area the catalogue does not have:
    [2] new area: 'ads'
        the catalogue has 'advertising', 'payouts'
  A new area is often right — the product grows. What it must not
  be is a synonym: nothing afterwards can tell 'ads' from
  'advertising', and merging two areas means renaming across
  frozen versions. Accepting the rule declares the area with it.
```

And coverage, now in areas:

```
**1 of 2 declared business area(s) hold a rule.**

Declared and undocumented: *payouts*. An area with no rule is an intention, not documentation.

This counts only areas somebody has named. Parts of the product nobody has declared are not
counted here at all, and that is the larger gap: the catalogue cannot measure what it has never
been told about.

As a technical figure, 0 of 1 file(s) ... A low share is expected and is not itself a gap ...
```

That third paragraph is the part that matters. Counting declared areas flatters a catalogue that has
declared two of twenty, so the view states what it cannot measure rather than letting the number
imply completeness (D-038's posture).

### Tests run

`.venv/bin/python -m pytest tests/test_areas.py` → **22 passed** (new file). **Whole suite**, because
the schema changed: **1 failed, 1110 passed**, then **1111 passed in 220s**, exit 0.

**Mutation-checked.** Making `areas()` read only the declared table fails **eight** tests across all
three concerns — the derived register, the coined-area report, and coverage.

### The failure was worth having

`test_the_storage_api_has_no_writes_at_all` asserts `Catalogue`'s **exact** public surface, and
adding `areas` broke it. That is the test working: it exists so `add_rule` cannot come back as a
convenience. Two things followed rather than a quick edit to the list:

- **`area_is_declared` was dead code** — written, exported, called by nothing — and was deleted
  instead of being added to the allowlist.
- **The allowlist stayed exact.** Loosening it to a pattern (`not name.startswith("add_")`) would
  have been weakening an integrity test to land a change, which `CLAUDE.md` forbids. `areas` was
  added by name, and the docstring now says a read may be added and a writer may not.

### Deliberately not done

- **No vocabulary and no refusal of a name**, beyond the 60-character bound the parse already
  applies. A test declares an area in French to hold that open.
- **No merging of two areas.** That is a rename across frozen versions — a harder ticket, and the
  reason the coined-area report exists at all.
- **Declaring an area does not document it.** `area add` says so in its own output.

---

## CON-67 — done when: *`rule history` shows which details changed between versions* ✅

`D-078` records the decision, and the question it answered was yours: **position is not an
identity.** "The second example changed" means something different the moment an earlier one is
removed, so a positional comparison would claim a case was edited when it had merely moved up.

**What changed.** A `number` on `Behaviour` and `Example`, schema **15** (`behaviour_no`,
`example_no` on both the live and the frozen tables), assignment in `Review._baseline`, a
`Review.diffs` comparison, and `_print_diff` in the CLI. Identity is the detail's **text** — a
behaviour's description, an example's situation — matched at acceptance.

**Live output, after accepting two versions on a throwaway workspace:**

```
      examples (3):
        - [1] A transfer of 240 euros  →  Accepted
        - [2] A transfer of 600 euros  →  Refused, and the daily limit is shown
        - [4] Two transfers of 300 euros on one day  →  The second is refused
      ...
      changes to examples since the previous version:
        [2] changed: A transfer of 600 euros → Refused
                 now: A transfer of 600 euros → Refused, and the daily limit is shown
        [3] removed: A refund of 400 euros → Accepted, refunds are not limited
        [4] added: Two transfers of 300 euros on one day → The second is refused
      note: a detail's identity is its text, so a reworded one reads here as
      one removed and one added rather than as an edit (D-078).
```

The new case took **4**, not the retired **3**. That is the property the design rests on.

**Three things worth keeping straight.**

1. **An example's outcome is compared but is not part of its identity.** The asymmetry is the
   feature: a changed outcome under an unchanged situation is the case a reviewer most needs to see,
   and it is visible only because identity excludes it.
2. **The high-water mark comes from the version tables.** The live tables are deleted and rewritten
   on every acceptance, so their maximum forgets every detail a rule ever dropped — and the next
   acceptance would hand a retired number to something unrelated, making the diff claim an edit
   where there was a replacement.
3. **The limit is printed, not filed.** A reworded situation reads as one removed and one added, and
   `rule history` says so whenever a diff contains both. The alternative — letting a reading name
   the id it is amending — would have made identity an unverified model claim.

### Tests run

`.venv/bin/python -m pytest tests/test_detail_tracking.py` → **19 passed** (new file). The affected
files — detail tracking, rule examples, version substance, acceptance, catalogue, cli, models, rule
areas, rule relations, merge on accept, product state, evidence pointers — → **300 passed**. **Whole
suite**, because the schema changed: **1089 passed in 214s**, exit 0, with no migration fixture
broken (schema 15's columns were registered in `helpers.INTRODUCED_AT` first).

**Mutation-checked twice**, which is what the two load-bearing properties deserved:

| Mutation | Result |
| --- | --- |
| High-water mark read from the live `example` table | Fails exactly `test_a_removed_number_does_not_come_back` |
| An example's identity includes its outcome | Fails 4 tests, including `test_a_changed_outcome_reads_as_changed` |

The first attempt at the second mutation was **invalid** — it referenced `d.outcome` on the
behaviour table, so it errored instead of changing the semantics, and the failures it produced were
meaningless. Redone properly before being believed.

### Deliberately not done

- **No numbers on a reading.** A number is spent at acceptance: numbering a proposal would commit an
  identity to something that may be rejected.
- **Nothing back-filled.** A detail accepted before schema 15 was never numbered, reads as
  `unnumbered`, and is **not compared** — matching it today would present this code's guess as what
  a reviewer saw.
- **No citable rule identifier.** This numbers details *within* a rule; CON-81 is separate and still
  needs a decision on form.

---

## CON-80 — done when: *a rule carries worked examples* ✅

`D-077` records the decision. The catalogue held statements and nothing a reader could disagree
with: a business reader could read a rule and agree without learning anything.

**What changed.** An `Example(situation, outcome)` on `Rule` and `RuleProposal`, and schema **14** —
`rule_proposal_example`, `rule_version_example`, `example`. It is a fourth instance of a pattern the
store already had three of, which is why it was one session: behaviours and anchors each exist as
the same triple, so storage, freezing and the live rewrite were all shaped before this started.

**Live output, on a throwaway workspace:**

```
  [1] daily-transfer-limit — awaiting a decision
      A transfer above the daily limit is refused and the limit is shown.
      area: payments — read by external, self-reported, run 2
      examples (3):
        - A transfer of 240 euros against a 500 limit  →  Accepted
        - A transfer of 600 euros against a 500 limit  →  Refused, and the limit is shown
        - Two transfers of 300 euros on one day  →  The second is refused
```

The examples are in the **review queue**, not only in `rule show`. A queue that asked for a decision
while withholding the cases the decision is about would be asking for agreement rather than review.

**Three things worth keeping straight.**

1. **Shape is checked; truth never is.** Both halves required, 200 characters each, no code leakage
   (D-066), not a restatement of the statement, no repeated situation. Whether the outcome is what
   the code does is the reviewer's whole job, and a test stores a plausible-but-wrong example on
   purpose, with a docstring saying why.
2. **A bad example rejects the whole reading**, never itself. Two good examples and one broken one
   store nothing — dropping the third would leave a reading claiming something the reader did not
   say, which is what `parsing.py` exists to prevent.
3. **A revision would have deleted examples silently.** Acceptance rewrites the live table from the
   reading, so a `revises` reading that omitted examples erased cases a human had accepted.
   `KnownRule` now carries them and the guidance says a revision replaces them. The same hazard was
   already true of behaviours; examples made it expensive.

### Tests run

`.venv/bin/python -m pytest tests/test_rule_examples.py` → **33 passed** (new file). The affected
files — parsing, submit, ai, mcp, provider_anthropic, operations, cli, models, business statements,
product state, evidence pointers, pending duplicates, rule relations, rule areas, proposal storage,
acceptance, catalogue, version substance — → **386 passed**. **Whole suite**, because the schema
changed: **1070 passed in 216s**, exit 0, with no migration fixture broken — schema 14's tables were
registered in `helpers.TABLES_INTRODUCED_AT` before the migration tests ran, the third time that map
has paid for itself.

**Mutation-checked.** Pointing `version_examples` at the live `example` table fails exactly one
test, `test_an_earlier_version_keeps_its_own_examples`, and nothing else — CON-61's property, which
matters more for examples than for behaviours: showing version 1 the examples of version 3
misattributes the very thing a reviewer agreed to.

**Verified by hand** end to end on a throwaway subject: submit → queue → accept → `rule show` →
`rule history` → `constat state` → `document --payload`. The payload's `catalogue` entry carries the
accepted examples, which is what makes the revision path safe.

### Deliberately not done

- **No identifiers for examples.** An example is addressed by position within its rule. Citable
  identifiers wait for CON-81's decision on the rule identifier form.
- **No diffing of examples across versions** — that is CON-67, which this makes worth more: there is
  now a shape worth tracking.
- **No completeness claim.** Nothing says a rule's examples cover its cases, and nothing should
  without a way to know.

---

## 2026-11-18 — a divergence review, D-076, and sixteen tickets

Not a ticket. Constat was compared against a worked implementation of the same idea — business
documentation generated from merged code, reviewed and approved by a business audience, in daily use
on a real product. The comparison was the source of the whole session; **no code changed**.

**The headline finding.** That implementation documents *a product* — a living tree of rules by area
plus what each release changes — while Constat documents *tickets*, one document per ticket,
published a page at a time. Most of the sixteen tickets follow from that one difference.

**What changed in the repository.**

| File | Change |
| --- | --- |
| `DECISIONS.md` | **D-076** — Constat assumes trunk-based development, and says so |
| `README.md` | "What Constat assumes about your branching model", with the four models that break |
| `PRODUCT_SPEC.md` | § 6 scope line; a status note under product rule 6 |
| `BACKLOG.md` | CON-80…CON-98 added; CON-47 and CON-58 **amended** rather than duplicated |

**Three decisions came out of it.**

1. **D-076 — the branching model is named.** One mainline per repository, and mainline means
   shipped. The sharp part is that under Git Flow the answer depends on where
   `refs/remotes/origin/HEAD` points: at `develop`, "already landed" means merged to `develop` and
   `constat state` presents unreleased behaviour as current — product rule 1 breached in the one
   command whose purpose is to state the present. The same project yields either answer from a
   repository setting, which is why it could not stay implicit.
2. **Product rule 6 is unmet, and recorded as unmet.** "Release streams are distinct" is an
   invariant the product intends and the code does not hold. **The release concept does not
   discharge it** — several open releases ahead of one trunk are several staging sets, not parallel
   production lines. Noted in D-076 and beside the rule itself, so the release work cannot later be
   read as having satisfied it.
3. **Constat acquires a release concept**, decided in four parts: declared in the workspace spanning
   the registered set, rather than derived from tags; several may be open at once; accepting agrees
   a version *for* a release and closing the release puts it into effect; the ship is recorded by a
   human. Optional and nullable throughout — a workspace declaring no release behaves exactly as
   today, and the three accepted rules keep none. Carried on CON-85/86/96/87; **no `D-NNN` yet**, by
   choice: it is written up when CON-85 starts, so the entry can record what the schema really did.

**A defect found, not yet fixed.** `rule accept` has no pending/landed guard, so a rule accepted
from unmerged work renders in `constat state` as the product's current behaviour. Raised as
**CON-96**, and it is the reason the two-state model is worth the cost: the fix is a state, not a
refusal.

**Tests run: none, and that is the honest report.** Nothing executable changed, so there was nothing
to run. No claim in this entry is backed by a test; the branching claims were read off
`constat/git/adapter.py` (`resolve_mainline`, `resolve_default_branch`), D-028/D-030/D-031, and the
`rule proposals` renderer in `constat/cli.py`.

**Deliberately left undone.**

- **CON-81's identifier form is undecided** — area-prefixed (`BR-UPL-006`) or flat — and CON-82
  depends on it. Neither can start until that is settled.
- **CON-58's blocker stands.** Whether an approval taken on the published surface may count as a
  decision at all is a change to D-048/D-055 and needs its own decision. The ticket was widened to
  state the question, not to answer it.
- **No `D-NNN` for the release concept yet**, as above.
- **Nothing committed.** The four changed files are uncommitted, per the working agreement.

---

## CON-61 — done when: *a frozen version's behaviours and anchors can be read back* ✅

No decision, no schema, no new data: `rule_version_behaviour` and `rule_version_anchor` have been
written on every acceptance since CON-44, and nothing ever read them. CON-14's criterion —
"previous content remains recoverable" — held for a version's name and statement and not for its
substance. The data was on disk and unreachable.

**What changed.** `Review.versions` now carries `behaviours` and `anchors` per version, through two
new readers (`version_behaviours`, `version_anchors`); `rule history` prints them, with each
anchor's scope and its `grounded_in` mark. Around 60 lines.

**The property that matters is where the substance comes from.** `rule` holds the current state and
is rewritten by each acceptance; the version tables are what a human agreed to at the time. Reading
the live tables would give every historical version the newest one's behaviours — and it would look
entirely right. **Mutation-checked:** pointing `version_behaviours` at the live `behaviour` table
fails exactly one test, `test_an_earlier_version_keeps_its_own_substance`, which is the test written
for it.

### A false claim it exposed in CON-79's output

`rule history` printed "evidence: not recorded — accepted before Constat kept evidence pointers" for
rule 3, which was accepted minutes earlier. Two states are indistinguishable from an empty pointer
set: a version from before schema 13, and one whose run genuinely read nothing because the ticket
had landed (D-031, D-072). The message asserted the first. It now states both possibilities, which
is the posture D-031 set for exactly this kind of ambiguity, and a test holds it there.

### Tests run

`.venv/bin/python -m pytest tests/test_version_substance.py` → **7 passed** (new file). The files
this reaches — acceptance, cli, evidence pointers, rule areas, rule relations, catalogue, mainline
grounding and the new one — → **197 passed in 38s**. No schema change, so the whole suite was not
re-run.

---

## CON-79 — done when: *a rule records the evidence it was accepted on* ✅

`D-073` records the decision. Raised and closed in the same session, because the defect was already
true of both rules in the live catalogue rather than being a future risk.

**What was wrong.** Re-reading 615 after it landed, the chain
`rule_version -> rule_proposal -> run -> operation` ended at a summary line reading
`pending: 1 commit(s)`. No table held a SHA — not the proposal, not the version, not the operation —
and a landed ticket contributes no evidence (D-031), so the document regenerates with no diffs.
Product rule 2 was failing for every accepted rule the moment its ticket shipped.

**What changed.**

- `constat/store/schema.py` — schema **13**, `run_commit`: SHA, scrubbed subject, repository alias
  and repository **identity** (root commit, D-025, so the pointer survives a move or re-clone).
- `constat/operations.py` — `record_run_evidence` at both run sites, written *before* the readings
  so a proposal never exists with its pointer missing; `evidence_for_run`, `evidence_for_proposal`
  and `evidence_for_version` to read it back.
- `constat/cli.py` — `rule history` names the commits per version, and the review queue says when a
  run gathered none.

**A pointer, not a copy.** Storing the redacted payload was the alternative and was rejected: it
becomes a second source of truth that can disagree with git, and grows without bound. The cost is
that a SHA can dangle, which is why the subject sits beside it — a squash-merge leaves a visible gap
rather than a blank one, and there is a test for exactly that.

**Two corrections I made to my own proposal while building it.**

1. I had proposed dropping `operation.payload` as dead weight. It is not: the scan-override path
   writes it to keep a credential-scan override auditable. Withdrawn after reading the code.
2. The subject is **scrubbed** before storage, which I had not planned. It never leaves the machine,
   but identity in a store is a disclosure waiting to happen and a subject can carry an address.

### The live workspace now says this, honestly

```
  [7] install-pages-carry-no-advertising — awaiting a decision
      area: advertising — read by mcp (claude-opus-5), run 29
      read from no commits — this run gathered none
      anchored in mainline, not in this ticket's changes: src/pages/*
```

That proposal is the 615 rule D-072 made possible, and it rests on a commit comment read earlier in
the session which the workspace cannot produce. Before CON-79 that was invisible. It is now the
second line of the entry.

### Tests run

`.venv/bin/python -m pytest tests/test_evidence_pointers.py` → **12 passed** (new file). Whole suite
→ **1030 passed in 207s**, exit 0, with **no migration fixtures broken** — schema 13's table was
registered in `helpers.TABLES_INTRODUCED_AT` before running it, which is the second time that map
has paid for itself.

The headline test is `test_the_pointer_survives_the_ticket_landing`: accept while pending, land the
work, assert the ticket now contributes no evidence *and* the version still names its commit.

---

## CON-71 — done when: *a rule can be anchored where it lives* ✅

`D-072` records the decision. Reopened by CON-78 rather than answered by it: CON-78 supplied the
missing data, and this is the grounding change that uses it.

**Two failures it fixes**, both found by running the loop rather than reading the code:

- **615** — a real rule went unproposed. The evidence *described* it (the install pages deliberately
  carry no advertising) but their home, `src/pages/`, was not in that commit's diff, so the only
  groundable anchor would have been a false claim about where the rule lives.
- **628** — after the ticket landed, *no* rule could be proposed at all. A landed ticket contributes
  no evidence (D-031), so the product could document a ticket only in the window between merge and
  release.

**What changed.**

- `constat/ai/parsing.py` — `_anchors` takes an optional mainline map and tries the evidence first,
  because that is the stronger claim. `_in_mainline` checks a scoped anchor against its repository
  and an unscoped one against all, matching how an unscoped anchor already matches everywhere.
- `constat/models.py` — `Anchor.grounded_in`, three-valued: `evidence`, `mainline`, or None for
  "not recorded".
- `constat/store/schema.py` — schema **12**, `grounded_in` on all three anchor tables. Nullable,
  no back-fill: an anchor recorded before this *was* grounded in the evidence by construction, but
  writing that in now would assert something nobody recorded.
- `constat/operations.py` — `mainline_files`, and both submit paths supply it.
- `constat/ai/provider.py`, `providers/anthropic.py` — `interpret(payload, mainline=None)`,
  defaulted so an implementation that does not parse anchors is unaffected.
- `constat/ai/guidance.py` — the `ANCHORS` block names both grounds, says the evidence is stronger,
  and warns that **the file list is not supplied** — a reader that thinks it has mainline will guess
  paths.
- `constat/cli.py` — the review queue says when an anchor rests on mainline alone, and `rule show`
  names the ground.

**Mainline is not in the payload.** It is grounding data for the parse, not context for the model.
The live workspace holds 922 files across three repositories; sending that on every gather would
cost real money to say what one sentence of guidance says.

### Verified on the live workspace's 628, which could not be read at all an hour earlier

```
  [7] a-first-launch-works — awaiting a decision
      A new user reaches the app on their first launch rather than an error.
      area: device provisioning — read by mcp (claude-opus-5), run 29
      anchored in mainline, not in this ticket's changes:
        commons/src/main/java/padjis/feed/service/DeviceProvisioningService.java
      claims to REPAIR a rule the code was violating
```

One proposal, four of today's tickets visible in it: CON-71's mainline ground, CON-77's area,
CON-73's `repairs` relation, and CON-70's duplicate warning against the pending proposal 6.

### Tests run

`.venv/bin/python -m pytest tests/test_mainline_grounding.py` → **16 passed** (new file). Whole
suite, twice: **9 failed, 1009 passed**, then **1018 passed in 203s**, exit 0.

**Eight of those nine failures were one line.** The migration fixtures needed schema 12's columns
registered in `helpers.INTRODUCED_AT` — the map CON-77 introduced after the same problem broke three
files by hand. One entry fixed all eight, which is what it was for.

---

## CON-78 — done when: *the product's current state can be read* ✅ · CON-72 ✅

`D-070` set the shape; `D-071` closes CON-72 alongside it. `constat state` renders every accepted
rule against the current mainline of every registered repository, grouped by business area.

**On the live workspace it reads:**

```
# The product as it stands

## Read from
- **237feed** at `origin/main` `9eda7b440984` — 630 file(s), 1 claimed by a rule (0.2%)
  - this clone is 2 commit(s) behind `origin/main`, so the picture may be out of date
- **237feed-app** at `origin/main` `c9fb4b3414ff` — 143 file(s), 0 claimed by a rule (0.0%)
- **237feed-ui** at `origin/main` `7014a1c24965` — 149 file(s), 1 claimed by a rule (0.7%)
...
## What this does not describe
920 of 922 file(s) across the registered repositories are claimed by no rule.
```

That last line is the point of the view as much as the rules are. A catalogue of two rules describes
0.2% of the product, and a report that hid the denominator would flatter itself (D-038).

**What changed.**

- `constat/operations.py` — `product_state` and `render_state`, plus `ProductState`,
  `RepositoryState` and `RuleState`. Mostly composition: `resolve_mainline` (D-068) picks the ref,
  `summarise_state` lists the files at it, and `Catalogue.rules_matching` already matched anchors
  against paths. The new part is doing it against mainline rather than against a ticket's diff.
- `constat/cli.py` — `constat state [--repo ALIAS] [--json]`. An unknown alias is **refused**, not
  rendered as an empty picture: a mistyped alias would otherwise read as a claim about the product.
- `constat/ai/guidance.py` — D-071's sentence: a rule may be conditional on a business state, the
  condition goes in the statement, and a technical condition is not allowed.

**Four properties it holds to.** It is *pinned* — every repository names its ref and revision,
because a picture of "now" that cannot say which commit it described is not inspectable. Coverage is
*stated*. A rule whose anchors are gone is *flagged, never removed*, and the wording says a human
decides. An unreadable repository is *reported*, with the warning that it produces the same symptom
as a retirement candidate — the one reading it must not be allowed to produce silently.

### Tests run

`.venv/bin/python -m pytest tests/test_product_state.py` → **16 passed** (new file). Whole suite →
**1002 passed in 186s**, exit 0.

### What it does not do

Nothing is stored. The picture is computed, so it is always of the revisions it names and there is
nothing to drift from — which means **CON-15** (compare against the last approved baseline) still
needs a stored baseline and is untouched by this.

It also does not yet let a rule be *grounded* against mainline, which was the finding that made this
next: a rule submitted for landed ticket 628 is still refused as ungrounded, because grounding reads
the ticket's evidence and a landed ticket has none. The data to fix it now exists in one place.
**CON-71 is the ticket to reopen with it.**

---

## CON-77 — done when: *a rule carries a business area* ✅

`D-070` records the decision and the three answers that came with it. The catalogue is the product's
business documentation, and documentation with no organisation is a list nobody reads.

**What changed.**

- `constat/store/schema.py` — schema **11**. `area` on `rule_proposal`, `rule` and `rule_version`.
  Nullable everywhere and **no back-fill**: a rule accepted before areas existed was accepted
  without one, and inventing an area for a frozen version would put a claim nobody made into a
  governance record.
- `constat/ai/parsing.py` — the area goes through **D-066's leakage gate unchanged**. "Advertising"
  is an area; `DeviceProvisioningService`, `commons/src/main/java` and `device_provisioning` are
  not. Plus a 60-character limit, because an area is a heading and a long one is a statement that
  wandered into the wrong field.
- `constat/ai/guidance.py`, `constat/mcp.py` — an `AREAS` block on both prompt paths, requiring
  reuse of an existing area and permitting omission where the evidence does not show one.
- `constat/ai/redaction.py`, `constat/operations.py` — `KnownRule.area`, so a reading can see the
  areas already in use. Without it every reading coins a synonym.
- `constat/store/acceptance.py` — the area reaches the rule *and* is frozen on the version, so a
  later re-grouping cannot rewrite what an earlier reviewer accepted.
- `constat/cli.py` — `rule list` groups by area with `(unplaced)` last, because unplaced is a gap
  rather than a section; `rule show` and the review queue both name it.

**Test infrastructure, fixed once.** This was the **third** migration in a row to break the same
three fixtures: each winds a workspace back by version number and had to drop every later schema's
columns by hand. `helpers.rewind_workspace` now owns that, with an `INTRODUCED_AT` map to extend
when a migration lands. Three call sites, one place to maintain.

### Tests run

`.venv/bin/python -m pytest tests/test_rule_areas.py` → **22 passed** (new file). **Whole suite**,
twice, because the schema changed: first run **5 failed, 981 passed** (all five the fixture problem
above), then **986 passed in 177s**, exit 0.

### A finding that makes CON-78 next

Testing this against a copy of the live workspace, a rule submitted for 628 was discarded as
**ungrounded** — 628 has landed, and a landed ticket contributes no evidence (D-031), so none of its
paths are in the window to anchor against.

**Once a ticket lands, no rule can be proposed for it at all.** That is the same root cause as
CON-71 — evidence is only ever a ticket delta — and sharper than the 615 case that raised it: there
one rule went unproposed, here every rule for the ticket is refused. Grounding against the state of
mainline fixes both, so CON-78 should land before CON-71 is answered. CON-71 may have no answer left
to give.

---

## CON-75 — done when: *Constat's own merge commit is not evidence* ✅

`D-069` records the decision. The last loose end from landing 628: the payload carried Constat's own
merge beside the team's fix, so 14 changed files were reported for 7 real ones.

**What changed.**

- `constat/git/adapter.py` — `LANDED_TRAILER = "Constat-Landed"`. It lives in the read-only module
  because *reading* a trailer is read-only; `merge.py` imports it to write one. The reverse — the
  attribution path importing the only writer — would have pointed the dependency the wrong way.
- `constat/git/merge.py` — the merge commit carries `Constat-Landed: <reference>`.
- `constat/tickets.py` — `_log` reads the trailer through `%(trailers:key=…)`, `_partition_own`
  splits the team's commits from Constat's, and `TicketMatch.excluded_own_commits` keeps the SHAs so
  the claim can be checked. Applied to the **landed** lookup as well as the pending one, which is
  where 628's over-count actually was.
- `constat/operations.py` — the document names what was excluded and why.

**A latent bug fell out of it.** The landed path built `found_on` as
`refs/heads/{mainline}`, which CON-76 had quietly turned into `refs/heads/origin/main` — a ref that
does not exist. Now the resolved ref is used directly.

**Known limit, and it is the price of refusing the heuristic.** Merges Constat made before this
landed carry no trailer, so they stay in their ticket's evidence: `9eda7b44` in `237feed` means 628
will over-count permanently. Catching it would mean matching its subject, which is exactly what
D-069 rejects — a human merge worded the same way would then be dropped silently.

### Tests run

`.venv/bin/python -m pytest tests/test_own_commits.py` → **10 passed** (new file). **Whole suite**:
`964 passed in 176s`, exit 0 — `_log` is on every attribution path, so a subset would not have been
honest.

The test that carries this one is not the exclusion but its opposite: a human commit whose subject
is **byte-identical** to what Constat writes is kept, as is a commit that mentions
`Constat-Landed:` in prose. If those two ever fail, the identification has become a guess about
someone else's writing.

---

## CON-76 — done when: *a landed ticket does not keep reading as pending* ✅

`D-068` records the decision. The other half of CON-69: landing a ticket left the registered
repository behind its own remote, and a shipped ticket kept reading `pending`.

**What changed.**

- `constat/git/adapter.py` — `resolve_mainline` and `MainlineRef`. Prefers
  `<remote>/<default-branch>`, verifies it exists, falls back to the local branch explicitly and
  says so. Counts drift **both ways** in one `rev-list --left-right --count`.
- `constat/operations.py` — gathering measures against the resolved ref, carries it on
  `RepositoryFindings`, and the document names it in both the "measured against" line and the
  status line.
- `constat/git/merge.py` — `refresh_remote_ref` updates that one ref in the registered repository
  after Constat's own push. `.git` refs only; never the working tree, never a local branch, and
  emphatically not `git pull`. `MergeResult.refreshed` is True, False, or None for "nothing landed".

**The `ahead` count exists because two tests failed.** Both committed "already shipped" work to a
local `main` and never pushed it, so under the new rule it read as not yet landed — correct about
the shared mainline, and surprising to whoever committed it. The answer was disclosure, not
softening the rule: the document now says how many local commits are not on the shared ref and that
work in them reads as unlanded. Those two tests were corrected to push their "shipped" work, which
is what shipped means.

**Verified on the live workspace.** 628 had shipped and read `pending`; it now reads:

```
Measured against `origin/main` (the local `main` is 2 behind).
This clone has not caught up with `origin/main`. Work already merged there can
still appear below as not yet landed.
Already in `origin/main` (2 commit(s)).
```

### Tests run

`.venv/bin/python -m pytest tests/test_mainline_staleness.py` → **17 passed** (new file). **Whole
suite run, twice** — this changes the comparison ref for every gather, so a subset would not have
been honest. First run: **3 failed, 948 passed**; after the fixes above: **954 passed in 129s**,
exit 0.

The three failures were worth having. Two were the semantic shift described above; the third was a
migration test that rewinds a workspace by version number and had to drop schema 10's column as
well — it now asserts `SCHEMA_VERSION` rather than a literal, so the next migration will not have
to edit it.

---

## CON-73 — done when: *a reading can say that evidence repairs a rule* ✅

`D-065` settled the design before this started; `D-067` records the one question it left open and
how this narrows it. A reading now stands in one of three relations to the catalogue:
`establishes`, `revises`, `repairs`.

**Why it exists.** Ticket 628 was a bug fix. The product always intended a first launch to work, the
code failed to honour it for ~3% of new installs, and the commit made it conform. There was no new
business knowledge in it — and no way to say that, so the reading manufactured three rules out of a
repair. A repair is now sayable.

**What changed.**

- `constat/store/schema.py` — schema **10**. `rule_proposal.relation`, with a CHECK for workspaces
  created at 10. The migration is one ALTER and **no back-fill**: `rule_proposal` is append-only by
  trigger, and dropping that trigger to write a column into historical readings would be editing
  what a reviewer was shown, performed by the code that forbids it.
- `constat/store/proposals.py` — `_relation_of` derives the relation for pre-10 rows. Sound rather
  than a guess: before the column existed the only two relations *were* establishes and revises,
  and `revises_rule_id` already says which. A migrated reading can therefore never read as a
  repair, which is correct — nothing could claim one before there was a way to.
- `constat/models.py` — `RuleProposal.relation`, defaulting to `establishes`, so silence is the
  weaker claim.
- `constat/ai/parsing.py` — the relation and the id must agree. `revises` with no id names nothing;
  `repairs` with an id claims something D-067 refuses. Both are refused with a reason rather than
  half-dropped.
- `constat/ai/guidance.py`, `constat/mcp.py` — a `RELATIONS` block on both prompt paths, saying a
  bug fix is almost always a repair, and that the repair belongs in `relation` and never in the
  statement (product rule 3).
- `constat/cli.py`, `constat/operations.py` — the queue and the document each render a repair
  distinctly. A business reader has to be able to tell "we now do this" from "we always said we did
  this, and had stopped".

**No column on `rule_version`.** A version already points at the reading it was baselined from, and
the relation is reachable through it. Adding one would duplicate provenance that is already stored.

**Verified on a copy of the live workspace.** Opened at schema 9, migrated to 10 on open; the five
stored readings keep `relation` NULL in the table and read back as `establishes`. The live
workspace is untouched and will migrate on its next command.

### Tests run

`.venv/bin/python -m pytest tests/test_rule_relations.py` → **22 passed** (new file). The files
this change reaches — parsing, workspace, proposal storage, acceptance, submit, runs, document
rendering, mcp, cli, models, and the two new files from CON-70 and CON-74 — → **446 passed in 63s**.
Whole suite not re-run.

The migration is tested as carefully as the feature: the workspace is built forwards and wound back
to 9 by dropping the column, rather than hand-writing schema 9 DDL, which would test the
transcription instead of the migration. Four assertions carry it — the version advances, the old
row's column is NULL *and* reads as `establishes`, an old revision derives as `revises`, and a
migrated reading can never read as a repair.

---

## CON-74 — done when: *a rule statement is purely business* ✅

`D-066` records the decision, and `D-065` the one behind CON-73 that came with it. Raised by
reviewing the three proposals ticket 628 produced: two of them were not business rules, which is a
failure of the catalogue's purpose (product rule 8) rather than a wording preference.

**What changed.**

- `constat/ai/statements.py` (new) — `code_leakage(text)` returns *what kind* of code a sentence
  leaks, or None. A description rather than a bool, so the refusal can name the token to remove.
- `constat/ai/parsing.py` — two new gates, on the statement and on the behaviours, between the
  length check and the anchor check. A clean statement with behaviours naming classes is still a
  technical record of a rule.
- `constat/ai/guidance.py` — `WHAT_A_RULE_IS` rewritten around one question: *would someone in the
  business have an opinion on this sentence, read aloud?* It also now says a bug fix usually
  establishes no rule, which is the interim half of D-065.

**The limit is stated, not hidden.** No check can decide whether a sentence is business-*oriented*.
The statement that caused D-066 — "a first launch succeeds even when several requests arrive at
once" — contains no code token and passes. A test asserts that it passes, with a docstring saying
why, so these tests cannot later be read as a quality guarantee they are not.

**The detector errs toward allowing**, because a false refusal discards a reading a person might
have accepted and the reader cannot argue back. Patterns need two signals or an unambiguous one:
`AdSense` and `iPhone` pass, `findOrCreateDevice` and `PostgreSQL` do not. Status codes match only
through the word HTTP — a bare three-digit number is money far more often, and "a transfer above
500 euros is refused" is the canonical business rule in this project's own documentation.

### Tests run

`.venv/bin/python -m pytest tests/test_business_statements.py` → **29 passed** (new file). The
files this change reaches — `test_parsing.py`, `test_submit.py`, `test_ai.py`, `test_mcp.py`,
`test_provider_anthropic.py`, `test_operations.py`, `test_pending_duplicates.py` and the new file —
→ **260 passed in 42s**. Whole suite not re-run.

Half the new tests assert the *opposite* direction: nine business sentences that each trip a pattern
a careless detector would have refused — VAT, SMS, KYC, PDF, a brand with one internal capital, a
three-digit amount, and the project's own accepted rule 1. That half matters more than the
refusals: a check that rejects a real business rule has broken the product in order to protect it.

### Still in the queue, undecided

Ticket 628's three proposals (3, 4, 5) predate this and were **not** re-judged — the gate runs at
parse time and nothing stored is re-examined. Under the new guidance the honest reading of 628 is
*no rules*, or at most the beacon trade-off (#5). #4 is not a business rule and #3 carries the
cause of the bug in its sentence; both are `rule reject` candidates, which D-036 reads as
inconclusive rather than wrong. That decision is the human's and was left open.

---

## CON-70 — done when: *a re-run does not duplicate a pending rule proposal* ✅

`D-064` records the decision: a duplicate is **reported, never refused**. Convergence is evidence —
proposals 1 and 2 on ticket 615 agreeing is what validated `guidance.py` the day before — so
discarding the second would destroy the product's own validation.

**What changed.**

- `constat/ai/redaction.py` — a `PendingProposal` type and `ProviderPayload.pending`. Separate from
  `KnownRule` because the two call for different things: a catalogue rule can be revised, a pending
  one can only be left alone. The field is `proposal_id`, not `rule_id`, so a reading cannot mistake
  it for something to put in `revises`.
- `constat/store/proposals.py` — `pending_candidates_for(anchors, exclude=…)`, the queue-side twin
  of `candidates_for`. `exclude` drops the proposal being examined: a reading is recorded before its
  candidates are looked up, so without it every submission reports itself.
- `constat/operations.py` — `pending_readings(workspace, reference)` fills the payload at all three
  build sites, and `SubmitResult.pending_candidates` carries the overlap separately from
  `candidates`.
- `constat/cli.py`, `constat/mcp.py` — two distinct reports. Both hold plain integers, and a
  reviewer told "overlaps 1" cannot act without knowing which table indexes it.
- `constat/ai/guidance.py` — a `PENDING` block, imported by both the provider system prompt and the
  MCP `document` prompt, telling a reader what the queue is for and why `revises` is not the answer.

**Verified on the case that found it.** A copy of the live workspace (never the live one), a third
reading of 615 submitted:

```
1 overlap a rule proposal nobody has decided yet:
    [3] anchors overlap rule proposal(s) 1, 2
```

The payload for 615 now carries all three pending proposals with `catalogue: []`. That warning is
exactly what was missing on 2026-11-14.

**Deliberately not done.** No deduplication, no merge, no similarity scoring. Overlap is by anchor
path, which is the same signal D-050 already uses and the same caveat applies: one file routinely
implements several rules, so overlap is a candidate and not a verdict.

### Tests run

`.venv/bin/python -m pytest tests/test_pending_duplicates.py` → **13 passed** (new file). The files
this change reaches — `test_submit.py`, `test_export.py`, `test_mcp.py`, `test_ai.py`,
`test_operations.py`, `test_proposal_storage.py`, `test_cli.py`, `test_scanning.py` and the new
file — → **344 passed in 47s**. Whole suite not re-run.

Four assertions carry it: the duplicate is reported, the duplicate is still *stored*, a proposal
does not overlap itself, and catalogue overlap and queue overlap stay in separate fields. A fifth
asserts both prompt paths carry the same `PENDING` text, because a rule proposed over MCP and the
same rule proposed by a provider must mean the same thing.

---

## The first real reading through the MCP loop — 2026-11-14

Not a ticket: the task `PROJECT_STATUS.md` had carried as "next" since CON-66. Ticket **615** was
run end to end against the **live workspace** (`~/.constat`, 3 repositories, 5 tickets) by an agent
driving `constat mcp` over stdio — `gather_evidence` → `get_payload` → read → `submit_rules` →
`list_rule_proposals`. Runs 17, 18 and 19 are that work.

**The guidance holds.** What came back is a business sentence rather than a restated diff:

> 237feed's news and feed content pages carry no third-party advertising while the site is not
> approved by the advertising network.

Stored as rule proposal **2**, anchored to `functions/_lib/render.ts` in `237feed-ui`, grounded and
undecided. The evidence was one commit removing the AdSense loader from NEWS and FEED pages after
the site was rejected for "low value content" — 252 KiB and ~112ms of main-thread time for zero
ads.

**The validation is accidental and is the strongest available.** Rule proposal **1**, from run 16
and a different reader, had already produced nearly the same sentence with the same anchor. Two
independent readings of one commit converged on one business rule, which is evidence that
`constat/ai/guidance.py` constrains the output rather than the model's instincts doing the work
unaided.

**`WHAT_A_RULE_IS` also suppressed what it was written to suppress.** Two candidates were dropped
as rationale rather than rules: a Core Web Vitals performance budget, and an inference about AdMob
inventory drawn from `public/ads.txt` being deliberately left alone. Both were in the commit body;
neither is a rule the evidence supports.

### Three findings, now CON-70, CON-71 and CON-72

1. **A re-run silently duplicates a pending rule proposal (CON-70).** `submit_rules` reported
   `possible_duplicates: {}` while rule proposal 1 sat in the queue saying the same thing.
   `RuleProposals.candidates_for` queries the `anchor` table — accepted rules only — and
   `get_payload` returns `catalogue` but never the pending queue. So each re-run of a ticket costs
   the reviewer another decision for one rule, which is how a review queue stops being readable.
2. **Anchor grounding cannot say "attested here, lives elsewhere" (CON-71).** The evidence states a
   second genuine rule — the landing and install-funnel pages are deliberately ad-free because they
   market the app as paywall-free — whose home is `src/pages/`, a path this commit never touched.
   The only groundable anchor would be `render.ts`, a false claim about where the rule lives, so a
   real rule went unproposed. Structural, not a model failure: D-049's check has one notion of
   grounding where two are needed.
3. **The guidance is silent on transient rules (CON-72).** "While the site is not approved" encodes
   a temporary business state in a catalogue meant for durable rules. Nothing said whether that is
   allowed, so it was written in, and a reviewer now has to decide both the rule and whether the
   rule is the right shape. That answer belongs in the guidance, once, not in every reading.

### What this says about the roadmap

The question this task existed to answer — *does the guidance produce business statements or
restated diffs* — is answered: business statements, on one ticket, on real evidence, twice. What it
did not test is breadth. One commit touching one file is the easy case; a 30-commit ticket spanning
three repositories is where a reading either holds together or becomes a list.

**Nothing was accepted and nothing merged.** Rule proposal 2 is a duplicate of 1 by content and can
be rejected as inconclusive (`constat rule reject 2`), which D-036 reads as "another reading is
expected", not as "wrong".

---

## CON-69 — done when: *accepting a rule proposal lands the ticket's branch* ✅

`D-062` records the decision, and amends product rule 7: one path now writes to a subject
repository. It is off by default.

**What changed.**

- `constat/store/settings.py` — a second setting, `merge_on_accept`, defaulting to `off`. No
  migration: the `setting` table has existed since schema 9, so this is a key, not a schema change.
- `constat/git/merge.py` (new) — the only writer in `constat/git/`. Clones the remote into a
  temporary directory, merges `origin/<branch>` into the default branch with `--no-ff`, pushes, and
  deletes the clone. `adapter.py` keeps its read-only guarantee untouched.
- `constat/operations.py` — `land_ticket` walks the registered repositories and returns a
  `Landing` with one `MergeResult` each. The branch comes from `branches_naming` (D-030), not from
  an argument.
- `constat/store/proposals.py` — `reference_of`, because a decision is taken by proposal id while
  landing is addressed by ticket reference.
- `constat/cli.py` — `config merge-on-accept`, exit code 7, and the call after the acceptance is
  already committed.

**The ordering is the design.** The acceptance is written first, so a failed merge reports a
missing merge rather than putting the decision in doubt. A conflict must not discard a human
decision.

**Deliberately not done.** No merge request flow, no per-repository override, and no retry
command — a refused merge is finished by hand in the repository. `land_ticket` is reachable only
from `rule accept`; nothing in the MCP surface can call it, which is unchanged from D-048.

**Numbering.** This entry takes `D-062`, the number CON-64 reserved when it renumbered itself to
`D-063`. Its note that the log jumps D-061 → D-063 described the state before this landed; the log
is contiguous again.

**Known gap.** Every test uses a bare repository on disk as the remote. The push path has never
run against an authenticated remote, so credential-helper behaviour and a protected-branch refusal
are both untested — the first real one to try is the `237feed` GitLab remote.

### Tests run

`.venv/bin/python -m pytest tests/test_merge_on_accept.py` → **19 passed**. The files this change
reaches — `test_cli.py`, `test_acceptance.py`, `test_config.py`, `test_reader_setting.py`,
`test_proposal_storage.py`, `test_operations.py` and the new file — → **217 passed in 28s**. The
whole suite ran once while CON-64 was still uncommitted in this tree: **873 passed in 171s**,
exit 0, which is CON-64's 854 plus these 19.

Each refusal asserts that mainline on the remote is byte-identical afterwards, not merely that a
non-zero code came back: conflict, local-only branch, no remote, no git identity, two branches
naming one ticket, an unreadable repository. One test asserts the registered clone's working tree
and HEAD are untouched. One asserts an acceptance survives a conflicted merge with the rule still
in the catalogue and exit 7.

---

## CON-64 — done when: *the MCP workflow starts from the agent* ✅

`D-063` records the decision. `gather_evidence` opens a ticket it does not find, so
`/mcp__constat__document 615` works on a clean workspace. The prerequisite it removes was
`constat ticket add 615` at the command line — a step nothing in the MCP interface mentioned, on
the path the product recommends.

### What changed

| File | Change |
| --- | --- |
| `constat/errors.py` | `ReferenceMatchedNothing`, subclassing `NotRegistered` so the exit code and every existing handler are unchanged. |
| `constat/operations.py` | `collect(..., require_ticket=True)`; `gather(..., open_if_absent=False)`; `_open_for_reference`; `OperationResult.ticket_opened`. |
| `constat/mcp.py` | `gather_evidence` passes `open_if_absent=True` and reports `ticket_opened`. The instructions and the tool description say so. |
| `ARCHITECTURE.md`, `USAGE.md` | the refusals table, and the MCP setup no longer opening a ticket first. |

**No schema change.** The first ticket in a while without one.

### The argument that carried it

Not "a ticket carries no authority", though it does not. **`EXPOSED_TOOLS` does not grow** — it is
the same four, and acceptance is as absent as ever. This removes a precondition from a tool that
already gathered rather than adding a capability D-055 withheld, and `ticket add` already gathered
immediately, so the agent gained nothing it did not have one command later. A test asserts the list
is still four, in the file about this change, because that is the property the change rests on.

### The order had to invert

`collect` called `TicketStore.document(reference)` as its first line, so the refusal happened before
any repository was read. Both halves of the ticket — open on a real reference, refuse a typo —
require the search to run *first*. The guard moved out behind `require_ticket`; the search was
always read-only, so the guard was about who may act on the result, not about safety.

### A case the ticket did not anticipate

**A repository that cannot be read reports `NOT_FOUND` with an `error` set**, which is
indistinguishable by status from a genuine miss. Had that gone unnoticed, a reference would have
been declared absent from a repository nobody could look in — and a ticket opened, or not, on that
assumption. Those references are refused too, with the unreadable repositories *named* and the
message saying explicitly that this is not a claim of absence. Product rule 1 applied to a refusal
rather than to a report.

`LANDED` does count as recognition. It contributes no evidence and is still a match (D-031): work
found in mainline is work, and a ticket for it is about something real.

### Tests — actually run

`.venv/bin/python -m pytest` → **854 passed** in 148s, from 825. `tests/test_agent_opens_ticket.py`
is new: 29 tests. **The existing 825 needed no changes**, which is the evidence that the change is
as narrow as it claims.

> A later run of the same suite reported 870, because a **second, concurrent session** has
> uncommitted work in this tree (`constat/git/merge.py`, `tests/test_merge_on_accept.py`, and edits
> to `cli.py` and `constat/store/`). Those tests and that feature are not part of CON-64. 854 is
> the figure for this ticket, measured before that work appeared in a run here.

Mutation-checked with seven mutations, each caught by the test that names the property:

| Mutation | Caught by |
| --- | --- |
| Open the ticket whatever the search found | `test_the_refusal_leaves_no_ticket_behind` + 5 |
| `LANDED` does not count as recognition | `test_a_landed_only_reference_opens_a_ticket` |
| `open_if_absent` defaults to on | `test_gather_refuses_an_unknown_ticket_by_default` |
| An unreadable repository reported as a plain miss | `test_the_refusal_says_the_reference_may_not_be_absent` |
| `ticket_opened` always claims it opened one | `test_the_result_defaults_to_the_quieter_claim` + 2 |
| `get_payload` opens a ticket too | `test_get_payload_does_not_open_a_ticket` |
| The ticket guard stays in `collect` | `test_gather_evidence_opens_a_ticket_that_does_not_exist` + 5 |

One existing test, `test_mcp.py::test_an_unknown_ticket_is_an_error`, **still passes for a different
reason** — `nope` now fails because it matches no commits rather than because no ticket exists. It
gained a docstring saying so, since a reader would otherwise take it for coverage of the old
refusal.

### Verified through a real client, on a real repository

A fresh clone of `237feed-ui`, a workspace with `reader = mcp` and **no tickets**, driven over
stdio by an `mcp` `ClientSession` rather than in process:

- `gather_evidence(615)` → `ticket_opened: true`, status `landed`, and the ticket exists afterwards
- `gather_evidence(99999)` → `is_error`, *"matched no commits: searched 1 repository(ies)"*, and
  `ticket list` still shows only 615
- `gather_evidence(615)` again → `ticket_opened: false`, run 2, no `AlreadyRegistered`

### Known issues and what was left undone

- **Who opened a ticket is not recorded.** A person and an agent are indistinguishable afterwards.
  That needs a column on `ticket` and a schema 10 migration, and by the argument that closed this
  ticket a ticket's origin is not a governance fact. Deliberate, and cheap to add later.
- **The live workspace was not touched.** Verification used a throwaway clone and a throwaway
  workspace. The real workspace at `~/.constat` holds 3 repositories and 5 tickets and is still at
  schema 9 — this ticket added no migration, so there is nothing to run.
- **Still no real reading.** This removes the last structural obstacle to the MCP loop and says
  nothing about the quality of what comes out of it. That is the next task.
- **A decision-number collision was resolved by renumbering this one.** This ticket originally took
  `D-063`, which a concurrent uncommitted session was already using for a different decision —
  merging a ticket's branch into mainline on acceptance (`constat/git/merge.py`), which amends
  product rule 7's read-only posture. Opening a ticket is now **D-063**; `D-063` is reserved for
  that session, and its `DECISIONS.md` entry is still to be written by it. Nothing of theirs was
  touched here, including the `D-063` citation at `constat/operations.py:1174`.
- **`DECISIONS.md` has a gap until that entry lands.** The log jumps D-061 → D-063. That is the
  correct state for an append-only log with a number reserved, not an error to tidy up.

---

## CON-68 — done when: *`rule accept` needs no `--by`, and the record says how the name came* ✅

`D-061` records the decision. `--by` was mandatory with no default, on the reasoning that a decision
with no decider is not a decision — that reasoning survives. What did not survive examination is the
idea that *typing* the name made it stronger.

### What changed

| File | Change |
| --- | --- |
| `constat/git/adapter.py` | `configured_identity()` — git's `user.name` / `user.email`, read-only. Returns None rather than raising. |
| `constat/store/schema.py` | **schema 9**: `rule_proposal_decision.attribution`, with the 8 → 9 migration. |
| `constat/store/acceptance.py`, `constat/store/proposals.py` | the decision carries its attribution; `decided_attribution` on the stored proposal. |
| `constat/cli.py` | `--by` optional on `rule accept` / `rule reject`; the inference, the refusal, and `recorded as:` in the output. |
| `ARCHITECTURE.md`, `README.md`, `USAGE.md` | the acceptance commands no longer carry a mandatory flag. |

Every view that shows who decided shows which — the queue, `rule proposals --all`, and
`rule history`, where it matters most because that is the audit view.

### Tests — actually run

`.venv/bin/python -m pytest` → **825 passed** in 135s, from 812. `tests/test_decider_identity.py` is
new: 13 tests. Mutation-checked with five mutations, each caught by its named test — including
recording an inferred name as `stated`, and falling back to `$USER`.

Two tests that asserted `--by` was required were **rewritten rather than deleted**. The property
worth keeping was never the flag: it is that no decision is stored without a decider, and that the
record says how the name was obtained.

### Three things worth keeping straight

- **`inferred` is not weaker than `stated`.** Nothing here proves who ran the command; an agent with
  shell access can run either form. The recorded distinction is narrower: whether a person asserted
  this name or a machine supplied it. Product rule 3, applied to the decision rather than to the
  claim it approves.
- **git config, not `$USER` or the OS login.** Those name an account — `padjis` is not who decided
  anything, while `user.name` is what this person already chose to be called in a record of who did
  what. With no git identity at all it refuses, naming both ways out.
- **A naming collision, found by hitting it.** `StoredRuleProposal.attribution` already meant who
  *read* the evidence (D-057). The decider's is `decided_attribution`. Two different people, two
  different questions.

### Known issues and what was left undone

- **The inferred name depends on the working directory**, because git's own precedence does — a
  local `user.name` wins inside a repository. That is the right answer rather than a quirk; it is
  the name git would put on a commit made there. It does mean one person can appear under two
  names, which is why the record says the name was inferred.
- **No real decision has been made through the inferred path on the real workspace.** The migration
  and the commands are tested; the 8 → 9 migration has not been run against the live workspace the
  way CON-60's and CON-54's were.
- **D-055 is untouched.** An MCP `accept` tool is no more acceptable than it was: the objection was
  the agent accepting its own proposal, and inference does nothing about that. CON-58.

---

## CON-66 — done when: *the MCP loop is one command, and both paths define a rule identically* ✅

Also raises **CON-67**.

### What changed

| File | Change |
| --- | --- |
| `constat/ai/guidance.py` | **new** — what a business rule is, held once. |
| `constat/ai/providers/anthropic.py` | `SYSTEM` imports the shared guidance instead of restating it. |
| `constat/mcp.py` | two prompts, `document` and `review`, with their arguments. |

```
/mcp__constat__document 615    gather, read, submit
/mcp__constat__review 615      summarise what is waiting
```

A tool is what the model chooses to call; a prompt is what the *user* invokes. The friction of
describing the loop in a sentence every time had no principle behind it, unlike the refusals — it
was simply a part of MCP this server did not implement.

### The second half matters more than the slash command

**The MCP path had no equivalent of the provider's system prompt.** Tool descriptions can say what a
tool does; they are a poor place to explain what a business rule *is*, and nothing on this path was
explaining it at all. An agent asked to propose rules had the shape of the reply and no guidance on
what belonged in it.

The guidance leads with the failure it exists to prevent: *"A transfer above the daily limit is
refused"* is a rule; *"the LIMIT constant changed from 100 to 250"* is not. Restating the diff is
the most common way to get this wrong, and nothing was warning against it.

Two prose blocks maintained in parallel would drift, and then the catalogue would record which path
happened to be configured rather than what is true. A test asserts the shared text appears in both.

### Tests — actually run

`.venv/bin/python -m pytest` → **812 passed**, from 803. Eleven new tests cover the prompt list, the
arguments, the shared guidance, and that **no prompt can instruct acceptance**. `review` says so
explicitly, because the natural shape of "summarise what is waiting" is to end with a
recommendation — and a recommendation from the thing that wrote the proposal is not a review.
`document` likewise tells the agent to report a refusal rather than work around it, so nobody
reaches for `--accept-scan-findings` on a model's initiative.

### Known issues and what was left undone

- **The guidance is still unvalidated.** It is now shared by both paths, which means a flaw in it is
  shared too. No real API call has ever been made, so whether this prose produces better readings is
  unknown.
- **CON-67 is raised from a stated expectation**, not built: a rule has a title summarising it and
  details characterising it, and across iterations a detail may be added, removed, edited or
  unchanged. Most of that exists under worse names — `statement` is the title, `behaviours` are the
  details — and the tracking does not exist, though `rule_version_behaviour` already holds the data
  CON-61 would read. The one real decision is recorded in the ticket: with a detail stored as a bare
  string, an edit cannot be told from a removal plus an addition, so either details get a surrogate
  id as rules did at D-050, or only added/removed/unchanged are reported. Guessing is not an option
  (product rule 1).
- **CON-64 still blocks the path this ticket smoothed.** `/mcp__constat__document 615` is one
  command, and it still fails unless someone ran `constat ticket add 615` at the CLI first.
  **Closed 2026-11-14 by D-063** — `gather_evidence` opens the ticket.

---

## D-060 — who reads the evidence is a workspace setting (2026-11-13) ✅

A day of using D-059 found the flaw in it. The refusal was right; the way it had to be answered
was not.

### What went wrong

`--no-provider` on every invocation was the signal for "something else will read this". That
punished the **recommended** workflow: on MCP the host supplies the model, so having no provider is
correct rather than a fault, and a user on that path met a refusal on every ticket. The first
version of the message did not list MCP among the ways forward at all — it offered a user doing
exactly the right thing a choice between buying API credits and working by hand.

The modelling error underneath: how evidence gets read is a property of a *setup*, not of an
invocation. Nobody alternates between an agent and a provider from one ticket to the next. A flag
passed every single time is a configuration value wearing a flag's clothes.

### What changed

| File | Change |
| --- | --- |
| `constat/store/settings.py` | **new** — `Settings`, `reader`, and the validation. |
| `constat/store/schema.py` | **schema 8**: a `setting` table, with the 7 → 8 migration. |
| `constat/cli.py` | `init --reader`, a new `config reader` command, and the gate now consults the setting. |
| `README.md`, `USAGE.md` | the loop no longer carries a flag; both also gained the venv-activation note after `pip: command not found` was hit twice. |

### Tests — actually run

`.venv/bin/python -m pytest` → **798 passed**, from 782. `tests/test_reader_setting.py` is new: 16
tests. Mutation-checked with five mutations, each caught by its named test — ignoring the setting,
flipping the default to `mcp`, migrating existing workspaces to `mcp`, letting `--no-provider`
silently reconfigure the workspace, and accepting an invalid reader.

### Two decisions inside this one

- **`setting` is the only table here that is not append-only.** A setting says how the workspace is
  operated and never what anyone decided, so a change history would imply an authority it does not
  have. A test asserts a second write replaces rather than appends.
- **Existing workspaces migrate to `provider`, not `mcp`.** Setting them to `mcp` would silently
  switch off a refusal someone may be relying on. A migration must not change behaviour on a guess.

### Known issues

- **CON-64 is still open.** `gather_evidence` cannot open a ticket, so `constat ticket add <REF>`
  remains a required manual step before an agent can do anything — surprising, and the next thing
  to remove from that path. **Closed 2026-11-14 by D-063.**
- **Readings still accumulate on recompute** (noted under CON-56's successor work). Re-running a
  ticket adds proposals rather than superseding them, and accepting one does not retire its
  duplicates.
- **D-059 was amended one day after landing.** Worth noting as a pattern rather than an incident:
  it was designed from the complaint and not from using the result, and the gap showed within a
  day of real use.

---

## Catalogue made read-only, and the provider gate (2026-11-12) ✅

Two changes from the same session, both prompted by questions rather than by a ticket.

### `Catalogue` has no write surface

`add_rule`, `add_behaviour` and `add_anchor` existed on `Catalogue` and **no command reached
them** — a rule is created by `Review.accept` and nothing else (D-048). They were a writable door
into the governance store that production could not use and nothing guarded. They now live in
`tests/helpers.py` as `seed_rule`/`seed_behaviour`/`seed_anchor`, and a test pins the class surface
to exactly `find`, `list`, `rules_matching`, `unmatched_paths`, so they cannot return as a
convenience.

`_rule_id` and two imports went with them as orphans. `TestDeclaring` (10 tests) also went: it
asserted the validation *inside* those methods — duplicate names, unknown rules, unknown aliases —
on a path production never took, so keeping it would have meant testing test code. The four tests
in it that were about the *store* survive as `TestTheCatalogueCannotBeEmptied`, including the new
surface assertion. Net: −10 tests, +1.

The name-keyed duplicate guard in `add_rule` went too. `test_the_schema_no_longer_makes_a_name_unique`
had already recorded it as a leftover of the pre-D-050 model, so both halves are now gone rather
than one.

### A rule-generating command refuses without a provider (D-059)

Asked for directly: the step that should generate rules did not fail when it could not. D-041 had
already made a *misconfigured* provider fail loudly — an unimplemented name and a missing
credential both exit 5 — and the case left succeeding was nothing configured at all.

| | Before | Now |
| --- | --- | --- |
| `CONSTAT_AI_PROVIDER=openai` | exit 5 | exit 5, same message |
| `CONSTAT_AI_PROVIDER=anthropic`, no key | exit 5 | exit 5, same message |
| unset | exit 0, "no rules identified" | **exit 5**, naming three ways forward |
| unset, `--no-provider` | — | exit 0, evidence only |

**The refusal is at the command boundary, not in `gather`.** 77 library tests call `gather` without
a provider because they are about evidence; moving the refusal there would make the library unusable
without a key and would break the MCP server, where having no provider is the design. `ticket add`
checks *before* creating the ticket, because a refusal that left an opened ticket behind would be
worse than no ticket — `ticket add` then refuses to open it again.

`CLAUDE.md` is amended in place, with the reason, since this changes a stated prohibition. The
guarantee underneath is unchanged.

### Tests — actually run

`.venv/bin/python -m pytest` → **781 passed** (779 → 770 after the catalogue change → 781 with the
gate and its tests). 35 CLI setup calls across six test files gained `--no-provider`: they gather
evidence rather than generate rules, so saying so is correct rather than a workaround.

Mutation-checked, four mutations on the gate: letting the null provider through fails 3+,
ignoring `--no-provider` fails 3+, running the gate after the ticket is created fails
`test_the_refusal_leaves_no_ticket_behind`, and absorbing D-041's message into the new one fails
`test_a_misconfigured_provider_still_fails_differently`.

### Known issues

- **The default change breaks scripted `document` calls.** Anyone running it in a pipeline gets
  exit 5 until they add `--no-provider` or configure a provider. Deliberate — a script quietly
  producing documents with no rules in them was not doing what its author believed — but it is a
  breaking change to the CLI.
- **Seeding writes rows directly.** `seed_rule` bypasses the acceptance path, so the fixtures still
  do not exercise how a rule really comes to exist. Tests that *are* about that use
  `Review.accept`; the rest are about reading, where it does not matter.

---

## CON-57 — done when: *a document is published through the credential gate* ✅

`constat publish <REF>` writes a ticket's stored document to a documentation target. `D-058`
records the decision; `PRODUCT_SPEC.md` § 6.2 and `ARCHITECTURE.md` § 6 both had to be amended
first, because both asserted Constat never writes outside its workspace.

### What changed

| File | Change |
| --- | --- |
| `constat/publish/port.py` | **new** — the `Target` protocol, `PublishedRef`, and `NotYetReadable` for targets that cannot yet read decisions back. |
| `constat/publish/targets/git_pages.py` | **new** — the default target. Clones, writes `<REF>.md`, commits, pushes. Derives the wiki URL from the remote by host, or refuses. |
| `constat/ai/scanning.py` | `scan_document` and `guard_publication` — a third entry point sharing `_scan_line`, plus `DocumentFinding`. |
| `constat/git/adapter.py` | `remote_url()`, beside `resolve_default_branch`. Returns None rather than raising: a repository with no remote is valid. |
| `constat/operations.py` | `publish_document()`, `detect_target()`, `PublishResult`. |
| `constat/errors.py` | `PublishError` and five subtypes, including `PublishRecordFailed`. |
| `constat/cli.py` | `constat publish`, exit code **6**. |

### Tests — actually run

`.venv/bin/python -m pytest` → **779 passed** in 124s (from 747). `tests/test_publishing.py` is
new: 32 tests, against a real bare repository over `file://`. No network and no credential; the
assertions are against what landed in the target rather than a mock's call log, because a mock
would happily record a push git would have rejected.

Mutation-checked, seven mutations, each caught by the test that names the property:

| Mutation | Caught by |
| --- | --- |
| The credential gate is skipped | `test_a_credential_in_the_document_refuses` + 3 |
| An unknown host falls back to GitHub's convention | `test_an_unknown_host_refuses` |
| A missing remote is guessed at | `test_a_repository_with_no_remote_refuses` |
| The operation is recorded before the write | `test_the_page_is_written_and_committed` + 2 |
| A reference is used as a path unsanitised | `test_a_reference_cannot_escape_the_page_directory` |
| `read_decisions` returns nothing instead of raising | `test_a_target_cannot_report_decisions_yet` |
| The temporary clone is left behind | `test_publishing_leaves_no_temporary_clone_behind` + 1 |

### Two things found by running it rather than by reasoning

- **A crash after a successful push.** A missing `import json` made the operation recording fail
  *after* the page was live, so the user saw a traceback over a published document. Fixed, and the
  recording is now wrapped: a failure there raises `PublishRecordFailed`, whose message says the
  document **was** published. Every other failure says "nothing has been published", and a user
  who cannot tell the difference has to assume the worst — which for a document carrying a
  credential is the difference between rotating a key and not.
- **An empty repository publishes fine.** A test was written expecting it to fail with "the wiki
  has never been created". Git clones an empty repository, commits on an unborn branch and pushes,
  so Constat makes the first commit — which is the right behaviour. The error message said
  something untrue and was corrected; the test now asserts the success, and a separate test covers
  the genuinely missing repository.

### Verified by hand

Against the rewound clone of this repository used for CON-60, publishing to a local bare repo:
the page landed with the right content and commit subject; republishing unchanged content made no
second commit; a credential in the body refused with exit 6 and left the wiki untouched; a
repository with no remote and one on `git.internal.example` both refused with exit 6. Detection
against this repository's own remote yields
`https://github.com/padjis/constat.wiki.git (derived from origin (github.com))`.

### Known issues and what was left undone

- **Only `git-pages` exists.** Confluence, GitBook and GitLab docs are CON-59, behind the same
  port. The port's shape is therefore informed by exactly one implementation.
- **`read_decisions` raises on every target.** Acceptance is still CLI-only, which is half of what
  the original question asked for. CON-58.
- **No real hosted wiki has been published to.** Every test and every manual check used a local
  bare repository over `file://`. Authentication, the `.wiki.git` convention on a real GitHub repo,
  and push permissions are untested against a real host.
- **Nothing reads the publication record.** The `publish_document` operation rows exist and no
  command shows them, so "where has this document been published" is not answerable yet — the same
  shape of gap as CON-61.
- **The diagrams are unverified.** `ARCHITECTURE.md` § 2 and § 2.1 both changed and I cannot
  render mermaid here. Two earlier attempts at diagram edits in this repository broke rendering, so
  these need a look in GitHub's preview before being trusted.

### Next smallest task

**CON-58** — read decisions back with their channel and verification, as planned. Still true and
still more valuable first: configure a key and run one real ticket through the provider, because
publishing documents built on unvalidated readings bakes in whatever the prompt gets wrong.

---

## CON-60 — done when: *a provider fills the review queue on its own* ✅

**Also closes CON-42.** `CONSTAT_AI_PROVIDER=anthropic` makes `constat ticket add 622` gather the
evidence, read it, and store rule proposals in one command. `D-057` records the decision.

### What changed

| File | Change |
| --- | --- |
| `constat/ai/providers/anthropic.py` | **new** — the first real provider. Streams the payload with adaptive thinking, hands the reply to the existing `parse`, returns the model id the response carried. |
| `constat/ai/providers/__init__.py` | **new** — the package, documenting why the SDK import sits inside the factory. |
| `constat/ai/settings.py` | `PROVIDERS` and `CREDENTIAL_ENV` are no longer empty. `CONSTAT_AI_MODEL` overrides a default of `claude-opus-5`. |
| `constat/ai/provider.py` | `Interpretation.model_attested`, defaulting to `False`. |
| `constat/errors.py` | `ProviderFailed` — a call that did not complete, under `ProviderError`. |
| `constat/store/schema.py` | **schema 7**: `rule_proposal.model_attested`, with the 6 → 7 migration. |
| `constat/store/proposals.py` | `record(model_attested=...)`, and one `attribution` property both display sites now use. |
| `constat/operations.py` | `gather` passes the flag through; the document's queue reads `item.attribution`. |
| `constat/cli.py` | same for `rule proposals`; the epilogue no longer claims nothing is interpreted. |
| `constat/mcp.py` | `model_is_self_reported` is derived rather than hardcoded `True`. |
| `pyproject.toml` | `[ai]` extra. `dev` deliberately omits it. |
| `ARCHITECTURE.md` | § 2.1's "Constat never calls a model" is now scoped to the MCP path; integrity rules 9 and 10 added. |

### Tests — actually run

`.venv/bin/python -m pytest` → **747 passed** in 112s (from 742 before this ticket, 723 before
CON-56). `tests/test_provider_anthropic.py` is new: 23 tests.

**No key, no network, no cost.** The transport is injected, so `interpret` and the real `parse`
run against canned replies. Where the SDK's own shape matters, a fake `anthropic` module is put in
`sys.modules`. The `anthropic` package is not installed in this venv and is not in `dev`.

Mutation-checked, five mutations, each caught by the test that names the property:

| Mutation | Caught by |
| --- | --- |
| The transport swallows a failure and returns an empty reply | `test_an_sdk_exception_becomes_ProviderFailed` |
| Record the requested model instead of the resolved one | `test_the_response_model_is_what_is_recorded` + 2 more |
| `record(model_attested=True)` by default | `test_the_default_is_the_weaker_claim` + 2 more |
| The reply text keeps thinking blocks | `test_the_reply_text_skips_thinking_blocks` |
| `attribution` drops the caveat unconditionally | `test_a_submitted_reading_keeps_it` + 1 more |

One mutation proved nothing on the first attempt — breaking the error handling inside
`_sdk_transport` failed no test, because every test injected its own transport. That gap was real,
not a flaw in the check, and `TestTheSdkTransport` now covers it.

### Verified on a real repository

This repository, cloned with mainline rewound six commits so `CON-44` had evidence ahead of it:

- payload **54,056 bytes**, 8 file paths, commit fields sent are `['body', 'files', 'sha', 'subject']` — no author field exists to leak
- the grounded rule stored and shown as `read by anthropic (claude-opus-5-20260114)`, no caveat
- the ungrounded one discarded: *"no anchor grounded in the evidence supplied"*
- accepted → rule 1 version 1; regenerating with no provider shows it as an impacted rule
- the string `emmanuel` **is** in the payload, in diff content (`--by emmanuel` in this repo's own
  docs and tests). That is evidence, not identity: redaction strips commit metadata, and scrubbing
  names out of file content would destroy the thing being reviewed.

The 6 → 7 migration was also run against a pre-existing schema-6 workspace holding a rule
proposal: the row survived and kept `model_attested = 0`, so its caveat stayed.

### Known issues and what was left undone

- **No real API call has ever been made.** Every test and every verification used an injected or
  faked transport. The request shape is asserted against the SDK's documented interface, not
  against the service. The first real call is the first genuine test of it.
- **Structured outputs are not used.** `output_config` would make `MalformedResponse` unreachable
  on this path. `parse` still has to run for grounding, so this is an improvement rather than a
  simplification — worth a ticket, not done here.
- **No retry, no backoff, no rate-limit handling.** A 429 is a `ProviderFailed` and the run stops.
  Correct but blunt; a long multi-repository ticket may want better.
- **Cost is unmeasured.** A 54 KB payload is roughly 14k input tokens, so a few cents per ticket on
  Opus 5 — estimated from payload size, not observed on a bill.
- **The prompt is unvalidated.** `SYSTEM` has never been run against a real model, so how good the
  readings are is entirely unknown. That is the next thing worth learning, and it needs a key.

### Next smallest task

**CON-57** — a publishing port and the default target, as planned. Alternatively, and arguably
more valuable first: configure a key, run `ticket add` against one real ticket, and read what comes
back. Everything structural is in place; the quality of the readings is the one thing no test here
can tell you.

---

## CON-56 — done when: *the document shows the catalogue and the queue, not just the run* ✅

Closing **CON-09**'s core.

| Item | Status |
| --- | --- |
| `CatalogueView` + `catalogue_view()` — impacted rules, unclaimed paths, queue | ✅ D-056 |
| Business section first; evidence under `## Evidence` | ✅ product rule 8 |
| The run's own result labelled **"This run:"** | ✅ closes the lie |
| Rendering takes no workspace — a pure function of stored structure | ✅ asserted on the signature |
| Rule proposals stored *before* the body is rendered | ✅ the queue no longer lags a run |
| Plain Markdown; usable as a PR body; queue as a task list | ✅ |
| `bound_for_pr` — business half never trimmed, omission stated | ✅ D-023's rule, one level up |
| Unclaimed paths one per line, never abbreviated | ✅ D-038, D-039 |

### Tests run

```
.venv/bin/python -m pytest  →  723 passed in 83.16s
```

26 new tests. One existing test was rewritten — see below.

### Mutation-checked

| Regression | Result |
| --- | --- |
| Render from the run instead of stored state | **11 tests failed** |
| Unscope the run's note | **1 test failed** |
| Truncate silently instead of stating the omission | **3 tests failed** |

The third needed a second attempt: my first edit produced an `IndentationError`, so the run reported
zero failures because the module would not import. A mutation that does not compile proves nothing,
and `grep -c FAILED` does not distinguish that from a passing suite.

### The bug was a lie, not a gap

`constat document 622 --show` printed *"no rules were identified"* while the catalogue held rule 1
at version 3 and that ticket had rule proposals waiting. The body rendered from the current run's
`Interpretation`, so a run with no provider reported on the ticket as though nothing were known.
That is product rule 1's failure mode appearing in the product's own output.

### Two defects found while building it

- **The queue lagged a run behind.** Rule proposals were stored *after* the document was rendered,
  so a reader saw "1 rule proposed" and an empty queue in the same document. `gather` now stores
  before rendering.
- **The note said "the evidence above".** The evidence moved below it in the restructure.

### Verified on both real subjects

| Subject | Document | Fits a PR body | Business signals |
| --- | --- | --- | --- |
| B, 8 commits | 5,095 chars | yes | impacted rule named, 29 unclaimed paths listed |
| A, 30 commits | 21,218 chars | yes | coverage reported |

Subject B surfaced the readability problem: 29 unclaimed paths comma-joined into one paragraph is
unreadable in a document and worse in a pull request. One per line now, and never abbreviated —
"and N more" would hide exactly the coverage gap D-038 requires to stay visible.

---

## CON-50 — done when: *an MCP client can drive the loop; acceptance is never exposed* ✅

| Item | Status |
| --- | --- |
| `constat/mcp.py`, `constat mcp` — stdio transport | ✅ D-055 |
| Four tools: gather, payload, submit, list queue | ✅ |
| **No `accept` or `reject` tool**, asserted on the live tool list | ✅ the point of the ticket |
| The `mcp` SDK is an optional extra | ✅ D-003's promise holds |
| No tool reimplements an operation | ✅ gates hold by construction |
| Constat's errors keep their message through `ToolError` | ✅ |
| Instructions tell the model nothing it submits is accepted | ✅ |
| Verified through a real client over stdio | ✅ not only in process |

### Tests run

```
.venv/bin/python -m pytest  →  697 passed in 69.30s
```

22 new tests. The existing 675 needed no changes.

### Mutation-checked

| Regression | Result |
| --- | --- |
| Expose an `accept_rule_proposal` tool "for convenience" | **3 tests failed** |
| Let a `ConstatError` escape instead of becoming a `ToolError` | **4 tests failed** |

### The test that matters asserts an absence

A model that could call `accept` would make "no proposal becomes official without an explicit human
decision" unenforceable — not by malice, but because the tool would be there. An absence is the
easiest property to lose, so the tool list is checked against the **live server** rather than by
reading the source: a tool added by a decorator anywhere shows up.

### A wrapper that lost the reason

Letting a `ConstatError` escape gets it wrapped as an unexpected crash, and a client sees "Error
executing tool get_payload" with the refusal gone. `ToolError` — the SDK's "a failure you
anticipated" — keeps the message, which for this product is the part worth sending: *remove the
credential and rotate it*.

### Two things the SDK taught me rather than my memory

`mcp` 2.x renamed `FastMCP` to `MCPServer`, and the client-side `CallToolResult` field is
`is_error`, not `isError`. Both found by running it against a real client — which is the argument
for that end-to-end test existing rather than trusting the in-process shortcut.

---

## CON-55 — done when: *a reading can claim to revise a rule rather than duplicate it* ✅

| Item | Status |
| --- | --- |
| The payload carries the catalogue — id, name, statement, anchors | ✅ D-054, the missing input |
| A reply may name `revises: <rule_id>` | ✅ |
| An invented claim is rejected like an invented anchor | ✅ symmetric on purpose |
| A boolean is not a rule id | ✅ `True` is an `int` in Python |
| Overlap is reported as a candidate, never applied | ✅ D-050 |
| A claimed revision is not also flagged | ✅ it already decided |
| The catalogue in the payload carries no identity | ✅ D-040 unaffected |

### Tests run

```
.venv/bin/python -m pytest  →  675 passed
```

20 new tests. The existing 655 needed no changes.

### Mutation-checked

| Regression | Result |
| --- | --- |
| Ignore the `revises` claim entirely | **8 tests failed** |
| The payload stops carrying the catalogue | **4 tests failed** |
| Auto-pick the overlapping candidate | **3 tests failed** |

### The missing piece was an input, not logic

A reading had never been shown what exists, so every reading claimed to be new and the second
reading of a rule created a duplicate — CON-43's failure arriving by a different route. Adding the
catalogue to the payload is most of the fix; validating the claim is the rest.

### An honest limit, and how it surfaced

Overlap is **identical glob string**, not glob intersection. A rule anchored to `rules.py` and a
reading anchored to `**/*.py` overlap in reality and are not flagged. Widening it means comparing
globs for intersection, which has no exact answer in general, and a warning that fired on every
broad glob would be noise.

It surfaced because a test I wrote had an `or` escape hatch — `assert candidates == {} or
possible_duplicates == 1` — which could not fail. Replacing it with the real expectation is what
exposed the narrowness. An assertion with an alternative branch is usually a sign the expected
behaviour was not actually understood.

---

## CON-44 — done when: *a reviewer accepts or rejects rule changes individually* ✅

Closing most of **CON-43** with it.

| Item | Status |
| --- | --- |
| `rule_version` + behaviours and anchors; schema 6 with a migration | ✅ D-053 |
| `rule accept` / `rule reject` / `rule history` | ✅ |
| Accepting baselines a frozen version pointing at the reading accepted | ✅ traceable to a diff |
| A revision adds version N+1 rather than duplicating the rule | ✅ CON-43's done-when |
| A name may change between versions; the rule stays one rule | ✅ D-050 |
| Rejecting changes nothing and is not a dead end | ✅ D-036 |
| `rule_version` append-only by trigger | ✅ |
| `--by` has no default | ✅ no automatic approvals, in the parser |

### Tests run

```
.venv/bin/python -m pytest  →  655 passed in 54.62s
```

30 new tests. The existing 625 needed no changes.

### Mutation-checked

| Regression | Result |
| --- | --- |
| Ignore the revision claim — every acceptance creates a new rule | **6 tests failed** |
| Rejecting baselines a version anyway | **2 tests failed** |
| `rule_version` loses its append-only triggers | **2 tests failed** |

### Why a revision is a version and not a duplicate

`revises_rule_id` is the reading's *claim* (D-050), and a human accepting the reading accepts the
claim with it. Acceptance is therefore the only place the claim takes effect — which is what makes
a wrong claim a rejectable interpretation rather than a corrupted identity.

### A guard the database made unreachable

A claim to revise a nonexistent rule cannot even be recorded: the foreign key refuses it at write
time. The acceptance-time guard stays anyway, and the test says why — if the key were ever
relaxed, the alternative is silently creating a *new* rule when the reviewer accepted a revision.

### Verified on the real workspace

Migrated v5 → v6 with its 8 operations intact, then the reading stored from Subject B's evidence
was accepted into rule 1, version 1 — with `rule history` showing the chain back to the rule
proposal and the run.

### What is left of CON-43

The *finding* half. `candidates_for` locates rules by anchor overlap, but nothing calls it, so
every submitted reading still claims to be new. CON-55.

---

## CON-52 — done when: *a reply produced anywhere becomes grounded, stored rule proposals* ✅

| Item | Status |
| --- | --- |
| `submit_reply`, `rule submit`, `rule proposals` | ✅ D-052 |
| Evidence **re-gathered**, never taken from the caller | ✅ the load-bearing part |
| An unusable reply is an error, not an empty result | ✅ exit 5 |
| Parsing happens before the run opens — no empty events | ✅ |
| `provider` / `model` recorded as self-reported | ✅ D-045 |
| Discards reported **before** the kept count | ✅ D-046 |
| Nothing accepted; the catalogue is untouched | ✅ asserted |
| The document body is not rewritten | ✅ `document` writes it, submit does not |

### Tests run

```
.venv/bin/python -m pytest  →  625 passed in 57.13s
```

31 new tests. The existing 594 needed no changes.

### Mutation-checked

| Regression | Result |
| --- | --- |
| Trust a caller-supplied payload instead of re-gathering | **13 tests failed** |
| Auto-accept submitted readings into the catalogue | **2 tests failed** |
| Let the two glob matchers diverge again | **4 tests failed** |

### Why re-gathering is the load-bearing part

If the payload came from the caller, a reply could ship a payload that makes any anchor look
grounded — the check would be verifying the reply against itself. Grounding only means something
when it is checked against evidence Constat can see.

### A false rejection, caught by a test rather than in use

`**/rules.py` is the most natural way to write "this file anywhere", and plain `fnmatch` never
matches it against a root-level file — so a correct anchor was being discarded as ungrounded.
Grounding and catalogue matching now share `constat/globs.py`; two matchers that disagreed would
accept a rule proposal at submit time and then never match it to a change.

This is the same failure as a false credential positive, one layer up: a rejection that is wrong
teaches people to stop reading rejections.

### Verified end to end on a real subject

Subject B: a 195 KB payload exported, a reply submitted naming one real path and one invented one.
The grounded reading was stored, the invented anchor discarded with its reason, and the catalogue
was still empty afterwards.

---

## CON-51 — done when: *a rule proposal survives the run that produced it* ✅

With CON-53 (withdraw the manual rule commands) landing alongside it.

| Item | Status |
| --- | --- |
| `rule_proposal` + behaviours, anchors, decisions; schema 5 with a migration | ✅ D-051 |
| Append-only: `UPDATE` and `DELETE` abort by trigger | ✅ readings and decisions both |
| A decision does not mutate the reading | ✅ separate table, as `document_version` |
| Changing one's mind appends; both stay visible | ✅ latest displays |
| Self-reported reader recorded (`provider`, `model`) | ✅ D-045 — a claim, not a fact |
| `revises_rule_id` nullable — a claim, not a key | ✅ D-050 |
| `gather` persists what the provider returned | ✅ survives the next regeneration |
| `rule` cannot be deleted | ✅ trigger (D-048) |
| `rule add` / `behaviour` / `anchor` / `remove` gone | ✅ CON-53 |
| `rule.name` lost `UNIQUE` | ✅ in the schema — see the honest limit below |

### Tests run

```
.venv/bin/python -m pytest  →  594 passed in 44.13s
```

30 new tests. Eight CLI tests covering the removed commands went with them, and two catalogue
withdrawal tests became "removal is now impossible".

### Mutation-checked

| Regression | Result |
| --- | --- |
| The append-only triggers removed | **5 tests failed** |
| `gather` stops persisting what the provider returned | **3 tests failed** |
| The migration forgets to copy `behaviour` rows | **1 test failed** |

### The riskiest migration so far

Dropping `rule.name`'s `UNIQUE` needs a table rebuild, and `rule` is the parent of `behaviour` and
`anchor` with `ON DELETE CASCADE` — so dropping the parent alone would have silently emptied the
catalogue. All three are rebuilt, children dropped first, renames last so the new children's
foreign keys are rewritten to match.

Verified on a real v4 workspace: migrated to 5 with its **8 operations and 1 run** intact, and the
four `rule_proposal*` tables usable afterwards rather than merely present.

### An honest limit: half the change landed

`Catalogue` is still **name-keyed**. `add_rule` keeps an application-level duplicate guard and
`find` looks up by name, so two rules cannot share a name *through the API* even though the schema
now allows it. That guard is a leftover of the pre-D-050 model and goes when the catalogue becomes
id-keyed and versioned (CON-43, with CON-44). The test asserts the schema rather than the API, and
says why — rather than asserting a behaviour that does not exist yet.

---

## CON-54 — done when: *one run per invocation, with its operations attached* ✅

| Item | Status |
| --- | --- |
| `run` table and `operation.run_id`; schema 4 with a migration | ✅ D-049 |
| One run per gather, whatever the repository count | ✅ asserted with three |
| Every operation a run writes belongs to it — no orphans | ✅ |
| A scan override joins the run whose evidence it let through | ✅ one event, not two |
| An export opens a run **only** when it accepted findings | ✅ no empty events |
| Pre-schema-4 rows keep `run_id` NULL | ✅ no fabricated provenance |

### Tests run

```
.venv/bin/python -m pytest  →  561 passed in 37.65s
```

19 new tests. The existing 542 needed one change: the migration test asserted `schema_version == 3`
as a literal, and now asserts against `SCHEMA_VERSION` so a future bump that forgets its migration
fails there rather than quietly rewriting the expectation.

### Mutation-checked

| Regression | Result |
| --- | --- |
| A run opened per repository instead of per invocation | **5 tests failed** |
| The migration creates `run` but forgets `operation.run_id` | **4 tests failed** |

### Verified on a real workspace

A workspace built at schema 3 by the previous commit: opened, migrated to 4, kept its **7**
pre-run operation rows NULL, and a fresh gather opened run 1 with its operation attached.

### A fixture of mine tripped a real guard

Registering three repositories failed as a duplicate. `make_subject` seeds byte-identical history,
and identical content committed in the same second yields the same root commit — so D-025's
identity check refused the second one. The guard was right and the fixture was lazy; the helper
now varies each root. Worth noting because it is the third time this session a test problem has
been my assumption about a fixture rather than a fault in the code.

---

## CON-49 — done when: *the payload can be handed out, and only through the gate* ✅

| Item | Status |
| --- | --- |
| `guard_release` — one chokepoint for every egress path | ✅ D-047 |
| `constat document <ref> --payload` — redacted payload as JSON on stdout | ✅ |
| Export refuses **unconditionally**; `gather` with no provider still only reports | ✅ the asymmetry |
| `collect()` shared, so both paths see identical evidence | ✅ asserted equal |
| Export writes nothing but an override record | ✅ |
| Override recorded under its own kind, distinct from a send override | ✅ `scan_override_export` |
| `--payload` with `--show` is a usage error | ✅ exit 2 |

### Tests run

```
.venv/bin/python -m pytest  →  542 passed in 33.63s
```

22 new tests. The existing 520 needed no changes.

### The hole this closed, on real data

| Subject | Result |
| --- | --- |
| B, 8 commits, 33 files | Exports cleanly — ~195 KB, and no identity field on the commit type at all |
| A, 30 commits | **Refused, exit 5, zero bytes on stdout** — it has real credentials in the window |

Before this, `--payload` would have handed Subject A's credentials to a third-party model. The
gate was keyed on a provider being configured, and an export has no provider.

**Mutation-checked:** reverting the export to the provider-only gate fails 3 tests, including the
one asserting stdout stayed empty.

### Why it raises instead of returning a flag

A caller that forgets to check a boolean still sends the payload. A caller that forgets to catch
an exception does not. Any future egress path — a submit echo, an MCP resource, a debug dump —
inherits the obligation, and the answer is "call `guard_release`" rather than "remember D-040 and
D-044".

### A test that asserted nothing, again

The CLI test for "the export does not fill the document" originally checked the body was empty.
`ticket add` already fills it (CON-34), so the assertion was vacuous. Rewritten to compare the
body before and after — the property is that the export does not *change* it. Second time this
session an assertion has been hollow rather than wrong; both times the fixture had more state than
I assumed.

---

## CON-42 — in progress: the trust boundary landed, the provider did not 🟡

| Item | Status |
| --- | --- |
| `constat/ai/parsing.py` — `parse`, `ParseResult`, `Rejection` | ✅ D-046 |
| An unusable reply raises `MalformedResponse`, never returns empty | ✅ exit 5 |
| Every anchor checked against paths actually in the payload | ✅ the property with teeth |
| An ungrounded or unanchored proposal is rejected whole, with a reason | ✅ |
| Rejections reach the `Interpretation`, the document and the CLI | ✅ |
| A rejection carries only the name and reason, never the model's prose | ✅ |
| Code fences unwrapped; bare-string anchors accepted | ✅ pragmatism about real replies |
| A provider in the registry, and a prompt | ⬜ reshaped by D-045 into CON-49 / CON-50 |

### Tests run

```
.venv/bin/python -m pytest  →  520 passed in 30.26s
```

50 new tests. The existing 470 needed no changes.

### Mutation-checked

| Regression | Result |
| --- | --- |
| A bad reply swallowed as "no rules found" | **14 tests failed** |
| The anchor-grounding check removed | **3 tests failed** |
| Rejections never rendered into the document | **2 tests failed** |

### Anchor grounding is the part worth keeping

A model will propose a rule anchored to a plausible-sounding path whether or not that path was in
the payload. Storing it would mean Constat had **invented its own evidence** — the inverse of
product rule 2. The check costs nothing, so it is made, and it is deliberately fatal to the whole
proposal: keeping the grounded half of a two-anchor rule would silently narrow a claim the model
meant more broadly, which is a different claim rather than a smaller one.

### Verified on both real subjects

| | Grounding paths | Grounded reply | Invented anchor | Prose reply |
| --- | --- | --- | --- | --- |
| Subject B, 8 commits | 30 | kept | rejected | refused |
| Subject A, 30 commits | 72 | kept | rejected | refused |

### One test that was passing for the wrong reason

The first version of the rejection-rendering tests called `render` with an empty findings tuple.
`render` returns early when nothing was searched, so both assertions ran against the "no
repositories are registered" branch and told me nothing. Caught because the assertion failed, not
because I checked — worth remembering that an early return makes a downstream assertion vacuous
rather than false.

---

## CON-45 — done when: *a payload containing a credential is refused rather than sent* ✅

| Item | Status |
| --- | --- |
| `constat/ai/scanning.py` — detectors, `scan`, rendered section, refusal message | ✅ |
| Known formats only; entropy scoring rejected with a reason | ✅ D-044 |
| `PayloadRefused` in the `ProviderError` family, exit 5 | ✅ |
| Refusal before `interpret` **and** before the document is written | ✅ asserted |
| Scan runs on every run; refusal only where a provider would receive it | ✅ |
| `--accept-scan-findings`, one run only, recorded as `human_decision` | ✅ on `document` and `ticket add` |
| Override recorded as a `scan_override` operation | ✅ |
| A finding never carries the matched text | ✅ four tests |
| An empty scan is not presented as proof of cleanliness | ✅ asserted on the wording |

### Tests run

```
.venv/bin/python -m pytest  →  470 passed in 51.61s
```

67 new tests. The existing 403 needed no changes.

### Mutation-checked

| Regression | Result |
| --- | --- |
| The refusal gate made unreachable | **4 tests failed** |
| `SecretFinding` made to carry the matched text | **4 tests failed** — including the persisted-document one |
| Scanning restricted to the provider path | **1 test failed** |

The second matters most. A scanner that records what it found would copy the credential into the
workspace and from there into every frozen version of the document, outliving the repository it
came from.

### Real evidence changed the implementation twice

| Pass | Result | Consequence |
| --- | --- | --- |
| First, 8 commits, ~3,100 diff lines | One **false positive** — a `token`-named variable assigned an expression | The code-expression rule exists because of it |
| Second, 30 commits, a different stack | **True positives** | The feature justified itself before it had a provider to protect |

After the fix, the first sample scans clean. A "bare identifier" rejection rule was tried in
between and removed — a real credential and a variable name are the same shape — so character-class
variety does that work, with a stricter threshold for unquoted values.

**Nothing identifying what was found is recorded in this repository**, by the owner's instruction.
Findings belong in a workspace document, not in public project files; the test fixtures use
synthetic lines and published documentation examples for the same reason.

### The honest part

A passphrase of one character class, a base64 credential beginning with `+`, and anything with no
recognisable shape all go undetected. That is the price of refusals being believable: the second
time a false refusal happens, the override stops being read.

---

## CON-46 — done when: *a built wheel contains the package and imports* ✅

| Item | Status |
| --- | --- |
| `pyproject.toml` — discovery instead of an explicit `packages` list | ✅ D-042 |
| `tests/test_packaging.py` — configuration, wheel contents, wheel import | ✅ 6 tests |
| Every package directory on disk is asserted to match an include pattern | ✅ walks the tree, no hardcoded list |

Found while verifying CON-41's "no new dependency" claim, not while looking for it. From CON-04
onwards the wheel contained nine modules and no subpackages at all; a wheel install would have
failed at the first `from .store import …`. Invisible for five tickets because the development
install is editable and imports from the working tree.

### The test was harder than the fix, and twice gave a false pass

The fix is one line. Making it *provable* took two attempts, and both failures made a broken wheel
look fine — which is why they are written down in D-042 rather than left in a commit message:

| False pass | Why |
| --- | --- |
| In-tree build | setuptools stages into `build/` and never cleans it, so earlier builds' modules are included regardless of configuration. With the defect restored, an in-tree build still produced a **complete** wheel. |
| Import probe | The editable install's `.pth` meta path finder claims `constat.*` from the working tree, ahead of `sys.path`. The probe loaded `cli` from the wheel and `store` from the repository, passing against a wheel with no `store` in it. |

Now the wheel is built from a staged copy of the source, and the probe runs with `-S` so `.pth`
files are skipped and the unpacked wheel is the only `constat` available.

**Mutation-checked:** with the explicit list restored, 5 of the 6 tests fail.

### Tests run

```
.venv/bin/python -m pytest  →  403 passed in 41.85s
```

---

## CON-41 — done when: *a provider can be configured; absent one, no rules were identified* ✅

| Item | Status |
| --- | --- |
| `constat/ai/provider.py` — `Provider` protocol, `Interpretation`, `NullProvider` | ✅ |
| `constat/ai/redaction.py` — the privacy boundary (D-040) | ✅ |
| `constat/ai/settings.py` — provider resolved from the environment, registry empty | ✅ |
| `RuleProposal` in `models.py`, provenance pinned to `ai_interpretation` | ✅ cannot be relabelled |
| The document's rules section, always present | ✅ `## Business rules` |
| "No rules were identified" never written as "none exist" | ✅ asserted on the wording |
| Credentials from the environment only, never stored | ✅ workspace records provider, not key |
| A misconfigured provider is refused, not nulled (D-041) | ✅ exit code 5 |
| The provider resolves **before** any repository is read | ✅ test watches the collector |
| `ticket add` reports the rules state too | ✅ it gathers, so it must say |
| No new dependency, no HTTP, no API call | ✅ `dependencies` unchanged |

### Tests run

```
.venv/bin/python -m pytest  →  397 passed in 37.94s
```

57 new tests. The existing 340 needed no changes.

### Mutation-checked, because a privacy test that cannot fail is worthless

Two deliberate regressions were introduced and the suite re-run:

| Regression | Result |
| --- | --- |
| `scrub_message` and `scrub_diff` turned into identity functions | **6 tests failed** |
| Provider resolution moved after evidence collection | **1 test failed** |

The second one is the reason that test watches `_collect_repository` rather than the document: the
document is written at the end either way, so asserting on it would have passed while the
regression shipped.

### Verified against the real subjects

Both subjects registered; `ticket add 622` and `ADR-0019` report `landed` / `not_found` with the
rules section present and honest. `CONSTAT_AI_PROVIDER=anthropic` exits **5** and names what is
available, rather than quietly producing an empty rule section.

For a payload with real content, Subject B was cloned and its last 8 commits made pending ahead of
mainline:

| Measure | Value |
| --- | --- |
| Commits in the payload | 8 |
| Files | 33 |
| Payload size | 186,636 chars (~47,000 tokens) |
| Address-shaped strings surviving | **0** |
| Author/committer fields on the payload type | **none exist** |

### Two honest limits

**The masking paths were not exercised by real data.** That range needed zero redactions —
identity was absent *structurally*, because the type has nowhere to put it. The trailer-stripping
and diff-masking code was exercised only by fixtures. It rests on anticipating the case, the same
way D-021 rests on asking the right question rather than on an observed discrepancy.

**Secret scanning is not solved and is not claimed to be.** Commit messages and diffs do leave the
machine — that is the product — but a payload containing a leaked credential would be sent as
readily as anything else. Raised as **CON-45**, to land with or before CON-42.

### A wrinkle left behind

`ticket add` gathers, so a provider fault there leaves the ticket open with an empty document. It
is recoverable — `constat document <ref>` once the environment is fixed — and consistent with the
living-document model (D-029), but it is not transactional in the way CON-33's ticket-and-document
creation is.

---

## CON-40 — done when: *rules, behaviours and anchors persist and report coverage* ✅

Committed as `b576795`.

| Item | Status |
| --- | --- |
| `constat/store/catalogue.py` — `Catalogue` | ✅ |
| `rule` / `behaviour` / `anchor` tables; schema v3 with a v2→v3 migration | ✅ |
| `Rule`, `Behaviour`, `Anchor` in `constat/models.py` | ✅ |
| `constat rule add / behaviour / anchor / list / show / remove` | ✅ |
| Rules matched to changed paths by anchor glob | ✅ `rules_matching` |
| Paths claimed by **no** rule reported explicitly | ✅ `unmatched_paths` |
| A rule with no anchors says so — it can never be matched | ✅ stated in `rule show` |
| Generated rules carry `ai_interpretation`, not `requirement_ref` | ✅ corrected by D-039 |

### Tests run

```
.venv/bin/python -m pytest  →  340 passed in 16.42s
```

30 new tests (24 catalogue, 6 CLI), plus the v2→v3 migration covered in `tests/test_workspace.py`.

### The rule model settled here, over six decisions in one day

This was the session where the rule model stopped being a code problem. The sequence matters:

- **D-035** — a rule is a *business statement*; a behaviour is *a way the app handles a business
  case*. Neither can be read out of code. That is what made every code-signal approach a dead end,
  not an implementation difficulty.
- **D-034** — feature flags removed. A flag is a *control over* behaviour, not a statement of it,
  and its live value is not even in the repository.
- **D-038** — SQL migrations removed for the same reason, dissolving D-010's "deterministic spine"
  entirely. A migration is at most *evidence that* a rule exists.
- **D-036** — rejection means **inconclusive** (another PR is expected), not "the write-up is
  wrong" and not "this must never ship".
- **D-037** — accepted rules migrate into the baseline. This unifies CON-14, CON-15 and drift:
  `NEW` and `CHANGED` are relative to what has been *approved*, not to what exists.
- **D-039** — rules are generated and maintained by AI, reversing D-038's authorship the same day
  it was taken.

### The reversal is the entry worth re-reading

D-038 chose a hand-declared catalogue to avoid API cost before validation. D-039 reversed it
hours later, and the reason is not convenience: a hand-maintained catalogue contains only the
rules someone remembered to declare, and drifts from the code **by construction** — the exact
disease this product treats. The `rule` CLI commands survive as a bootstrap and test path, which
is how the catalogue is exercised with no provider configured. They are not the intended way to
author rules, and the command help says so.

### What this costs, stated rather than discovered later

D-039 is the roadmap's top risk made concrete. The plan says postpone AI API calls until the
workflow is validated, and validation stands at **zero discovery conversations** (CON-26).
Evidence is already 2000–4000 diff lines per range per repository. Proceeding is a deliberate
choice.

### The functions that matter most

`unmatched_paths`. A catalogue only knows the rules it holds, and an AI pass will miss rules too,
so changed files claimed by no rule must stay prominent rather than being quietly absent. Coverage
reporting is the thing that keeps an incomplete catalogue honest.

---

## CON-34 — done when: *an operation produces a document with evidence from each repository* ✅

| Item | Status |
| --- | --- |
| `constat document <ref>` gathers across the registered set | ✅ |
| `ticket add` fills the document immediately (D-033) | ✅ |
| Evidence collected per commit, not as one cumulative diff (D-033) | ✅ |
| Repositories searched but contributing nothing still appear | ✅ |
| `landed` / `not_found` / `pending` distinguished in the body | ✅ |
| Each run records an operation per repository | ✅ |
| `ticket show` reports stored state, never a fresh search | ✅ |

### Tests run

```
.venv/bin/python -m pytest  →  308 passed
```

### The trap the tests build

A ticket's commits need not be contiguous. Diffing the first commit's parent against the last
would attribute whatever else landed between them to the ticket, so a test constructs exactly
that — ticket work, an unrelated commit, more ticket work — and asserts the unrelated file never
appears.

### Hazard left behind: CON-39

The body is regenerated on every run. That is safe only while it is entirely machine-derived; the
moment a reviewer can edit it (CON-12), regeneration destroys their work. Must be solved before
review ships.

---

## CON-33 — done when: *a ticket owns exactly one living document* ✅

| Item | Status |
| --- | --- |
| `constat ticket add / list / show` | ✅ |
| Ticket and document created in one transaction | ✅ asserted no orphan is reachable |
| A second document for one ticket is impossible | ✅ schema `UNIQUE` |
| References stored verbatim — four shapes exist in the subjects | ✅ |
| No ticket title; schema v2 migration drops the column (D-032) | ✅ |
| Attribution by branch name and by commit message (D-030) | ✅ |
| Search window is everything ahead of mainline (D-031) | ✅ |
| `pending` / `landed` / `not_found` kept distinct | ✅ |
| The ref a commit was found on is recorded as evidence | ✅ |

### Tests run

```
.venv/bin/python -m pytest  →  286 passed
```

38 new tests, including five that migrate a real version-1 workspace.

### On the real subjects

`ticket add 622` against Subject A reports **`landed`** — correctly, since every branch there is
zero commits ahead of mainline. That is the honest answer rather than the convenient one, and it
is why the fixture builds the `pending` shape itself.

Token-boundary matching earned its place on real data: ticket 622 matched a commit whose *subject*
never mentions it, because its body contains `(#622)`. The same pattern correctly refuses `6220`
and `1622`.

---

## CON-32 — done when: *a registered repository survives a restart and is readable* ✅

| Item | Status |
| --- | --- |
| `constat repo add / list / remove` | ✅ |
| Identity and default branch resolved and stored at registration | ✅ |
| Default branch from `origin/HEAD`, never from the checked-out branch | ✅ CON-36 delivered here |
| Duplicate detection by identity, not path | ✅ |
| Registration reuses the Git layer's errors | ✅ |
| `remove` leaves the repository on disk untouched | ✅ asserted |
| Exit 3 for repository problems, 4 for workspace problems | ✅ |

### Tests run

```
.venv/bin/python -m pytest  →  248 passed
```

33 new tests. The clone fixture matters: `origin/HEAD` only exists in a clone, so a `git init`
repository exercises the refusal path and a clone exercises the resolution path.

### The two refusals

**No default-branch guessing.** Falling back to HEAD's symref would let `repo add` run from a
feature branch and silently make that branch the baseline for every future comparison. Verified
against reality: both subjects resolve automatically; this repository, created with `git init`,
is refused and told to pass `--default-branch` or run `git remote set-head`.

**No duplicate by identity.** A second clone at another path is the same repository (D-025). The
error names the existing alias and the shared root commit rather than just saying "duplicate".

---

## CON-31 — done when: *a restart does not lose repositories, tickets or documents* ✅

| Item | Status |
| --- | --- |
| `constat/store/` — SQLite workspace, versioned schema | ✅ |
| `constat init`, reporting the workspace it used | ✅ |
| Refuses to overwrite an existing workspace | ✅ exit 4 |
| Refuses a newer *or* older schema rather than guessing | ✅ |
| Append-only `document_version`, enforced by triggers | ✅ UPDATE and DELETE both abort |
| One document per ticket, enforced by `UNIQUE` | ✅ |
| Foreign keys on (SQLite defaults them off) | ✅ |
| Operations recorded against documents | ✅ table in place |
| Exit code 4 for workspace errors, distinct from 2 and 3 | ✅ |

### Tests run

```
.venv/bin/python -m pytest  →  215 passed
```

36 new tests. The append-only ones assert the triggers actually fire: a trigger that does not is
worse than no trigger, because it looks like protection.

### One bug the tests caught

Opening a non-database file leaked a raw `sqlite3.DatabaseError` traceback instead of a Constat
error. Fixed in the connection wrapper — "fail clearly" is the standard the project set itself,
and a stack trace does not meet it.

### Design note

Immutability is enforced **by the database**, not by application code. `document_version` rejects
`UPDATE` and `DELETE` outright, so a future bug cannot rewrite an approval by forgetting to call
the right helper. Same reasoning for one-document-per-ticket, the decision `CHECK`, and foreign
keys: ARCHITECTURE.md section 5 rules belong where they cannot be bypassed.

---

## Build roadmap — 20 focused work sessions

At 1–2 hours per day, one independently testable outcome per session. This is a working sequence,
**not a deadline promise** — take longer when a milestone needs it.

Session *N* is ticket `CON-NN` in [BACKLOG.md](BACKLOG.md), which also carries the non-session
legal and validation work (`CON-21` onwards) and the per-ticket design notes.

### Phase 1 — Foundation (sessions 1–4)

| # | Session | Done when | Status |
| --- | --- | --- | --- |
| 01 | Create the repository and working agreement | A documented empty project with clear scope and rules. | ✅ `b092b62` |
| 02 | Create the Python project skeleton | The CLI installs and runs locally; tests execute. | ✅ |
| 03 | Add configuration and input validation | Helpful errors; no silent defaults for important inputs. | ✅ |
| 04 | Read a local Git repository | Tests cover valid, invalid and missing repositories/revisions. | ✅ `184fa0b` |

### Phase 2 — Evidence engine (sessions 5–7)

| # | Session | Done when | Status |
| --- | --- | --- | --- |
| 05 | Compare two revisions | A deterministic change summary for two revisions. | ✅ `6e3b07d` |
| 06 | Collect inspectable evidence | Evidence records can be traced back to Git. | ✅ `eb957b6` |
| 07 | Define the change data model | Stable, tested structured output. | ✅ `24d3746` — top-level object revised by D-029 |

### Phase 3 — Meaning and reporting (sessions 8–11)

| # | Session | Done when | Status |
| --- | --- | --- | --- |
| 08 | ~~Classify changes conservatively~~ | — | 🔁 **superseded by CON-40…43.** Classification by code signal was dissolved: D-034 removed flags, D-038 removed migrations, D-035 established that a rule is a business statement no signal can produce. |
| 09 | Generate the first report | A developer can understand the report without reading raw command output. | ⬜ |
| 10 | Separate facts from interpretation | Every claim has a provenance type; unsupported claims are visibly uncertain. | ⬜ |
| 11 | Strengthen quality with tests | The report remains safe and useful across realistic Git cases. | ⬜ |

### Phase 4 — Human governance and history (sessions 12–15)

| # | Session | Done when | Status |
| --- | --- | --- | --- |
| 12 | Implement review decisions | No proposal becomes official without an explicit human decision. | ⬜ |
| 13 | Persist proposals and decisions | A restart does not lose review history. | ⬜ |
| 14 | Create immutable approved baselines | A later approval creates a new version; previous content remains recoverable. | ⬜ |
| 15 | Compare against the last approved baseline | A reviewer can see what is new since the last approved state. | ⬜ |

### Phase 5 — GitHub and realistic demonstration (sessions 16–20)

| # | Session | Done when | Status |
| --- | --- | --- | --- |
| 16 | Read GitHub repository metadata | Constat can identify the GitHub repository and map it to its local clone. | ⬜ |
| 17 | Link pull requests to change proposals | A proposal can be traced to its originating PR. | ⬜ |
| 18 | Add traceability references | A reviewer can navigate from a proposal to its supporting artefacts. | ⬜ |
| 19 | Run a realistic multi-change scenario | A repeatable demo shows the product-level value, not just a Git diff. | ⬜ |
| 20 | Package the MVP and document limits | A new person can run the demo and understand what Constat does and does not do. | ⬜ |

---

## First seven days

| Day | Task | Status |
| --- | --- | --- |
| 1 | Create an empty Git repository named `constat`. | ✅ |
| 2 | Add the project charter, product specification and working agreement. | ✅ |
| 3 | Have Claude Code review the documents, identify ambiguities and propose a small architecture. **Do not implement.** | ✅ 10 ambiguities recorded in `PRODUCT_SPEC.md` § 11; architecture proposed in `ARCHITECTURE.md` |
| 4 | Choose the first sample Git repository. Prefer a small project you own and can safely analyse. | ✅ Subjects A and B — D-009 |
| 5 | Agree on the first CLI command and its acceptance criteria. | ✅ Session 03 — every command has stated acceptance criteria |
| 6 | Implement the CLI skeleton and tests. | ✅ Session 02 |
| 7 | Review the result, update project status, conduct the first two discovery conversations. | ⬜ |

## Validation track

Running in parallel with building — see `PRODUCT_SPEC.md` § 10.

| Window | Goal | Status |
| --- | --- | --- |
| Weeks 1–2 | 5–10 discovery conversations | ⬜ 0 of 5–10 held |
| Weeks 3–5 | One design partner, prototype validation | ⬜ |
| Weeks 6–8 | Two pilot commitments | ⬜ |

**Reminder from the roadmap:** do not wait until the software is finished to discover whether anyone
needs it. The Day 7 task includes the first two discovery conversations — that is the real deadline
for starting this track.

---

## The first milestone

Not "build the platform". It is:

> Show one team a trustworthy, evidence-backed explanation of a real software change, let them
> approve it, and prove that the approved knowledge can be carried forward without losing history.
