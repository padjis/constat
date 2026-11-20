# What Constat does not do

Version 1 · 2026-11-20 · the honest half of CON-20

`README.md` says what Constat is for and `USAGE.md` says how to run it. This says what it does
**not** do, what it has **not verified**, and where it states an intention it does not yet meet.

It exists because every one of these is recorded somewhere in `DECISIONS.md` — twenty-eight
entries as of this version — and a reader should not have to assemble them. Nothing here is a bug report. Each
item is a decision, with the entry that made it.

---

## 1. It will not decide anything

| | |
| --- | --- |
| **Nothing is accepted without a person** | No tool, flag, setting or MCP call can accept a rule proposal. Acceptance is reachable only from the command line, and a test asserts the live MCP tool list to keep it that way. D-048, D-055 |
| **A rejection means inconclusive, not wrong** | So a later reading of better evidence is expected rather than precluded. D-036 |
| **Nothing is retired automatically** | A rule whose anchors have vanished is a *candidate*, never a retirement. A person decides, with a reason. D-070, D-084 |
| **Nothing judges staleness** | Cache age and mainline drift are reported with numbers and no verdict. "Older than a week is stale" is a judgement about your release cadence, not a fact about your repository. D-093, CON-76 |

## 2. It will not write to your code

Read-only against every repository it reads, with two stated exceptions and one that is not an
exception at all:

| | |
| --- | --- |
| `merge_on_accept` | **Off by default.** With it on, accepting a rule merges the ticket's branch into the default branch and pushes. The merge happens in a temporary clone; the registered repository is never written to; every ambiguity refuses. D-062 |
| `constat publish` | Writes one Markdown page to a documentation target. Never to a subject repository, never a code push, never a pull-request comment. D-058 |
| The remote cache | Cloning a registered URL writes **inside the workspace** (`~/.constat/cache/`). Nothing is written to the remote: it is a read whose result was kept. D-092 |

No credentials are ever stored. Git's own helpers supply them, and a URL needing authentication
Constat cannot provide fails as a clone failure with git's message.

## 3. It assumes trunk-based development

**One mainline per repository, and that mainline is what is shipped.** If your default branch is not
your production line, Constat draws a confident wrong picture — `README.md` has the table of how each
model breaks. In short: Git Flow, long-lived parallel release lines, environment branches and
fork-based workflows are out of scope today. D-076

**Product rule 6 is therefore unmet.** "Release streams are distinct" is an invariant the product
states and the code does not hold. It is intended work rather than a deferred maybe (D-090, CON-99),
and until it lands the limit stands.

## 4. What it cannot check

| Claim | Why not |
| --- | --- |
| **Whether a rule is true** | Nothing verifies that a statement describes the product. Gates check that a sentence is business language and that its anchors exist; the truth is the reviewer's whole job. D-066, D-077 |
| **Whether an example's outcome is right** | Same reason, said again because it is the most tempting thing to pretend. A test deliberately stores a plausible-but-wrong example. D-077 |
| **Commercial disclosure** | Publication refuses credentials, internal hostnames, addresses, connection strings and described weaknesses. It does **not** detect a real customer, price or volume: a figure with a currency is what a business rule legitimately says, so a detector would refuse "a transfer above 500 euros is refused". D-095 |
| **A credential with no recognisable shape** | The scan knows published formats. A passphrase of one character class is not detected, and an empty scan is not a clean bill of health. D-044 |
| **A rule accepted after its ticket landed** | A landed ticket contributes no evidence, so there is no pointer to check against mainline. Reported as *shipping not checked* rather than silently trusted. D-031, D-087 |
| **A message whose text is mostly placeholder** | Verification searches the longest literal run; below twelve characters there is nothing to search for, and it says so. D-083 |

## 5. What is declared and unused

| | |
| --- | --- |
| `test_evidence` | Nothing runs tests and no test result is read. No ticket owns it. D-094 |
| `requirement_ref` | Nothing ingests a requirement or an issue. Supplied traceability is CON-18. D-094 |
| `assumption` | Has no producer, and that is a finding rather than a gap: every inference is either a reading (`ai_interpretation`) or an admission (`unknown`). D-094 |
| `commit_set` selection | Reserved in the schema since CON-07. D-025 |

The three provenance types are kept in the taxonomy rather than removed, and every rendered document
lists them, so an absence is not mistaken for having been checked.

## 6. What a business reader cannot do

**Read, but not respond.** `constat publish` puts a document where a business audience can read it;
nothing brings their answer back. `read_decisions` raises `DecisionsNotReadable` on every target,
there is no comment path, and approval lives at the command line.

That is the largest functional gap in the product. Off-CLI approval **is** intended (D-089, CON-58),
and comments need a durable anchor model first (D-043, CON-39, CON-47, CON-48).

## 7. Deferred by decision

Web dashboard · multi-tenant SaaS · authentication · billing · Kubernetes · Kafka · graph database ·
multi-agent orchestration · automatic approval · any *required* AI API call. `PRODUCT_SPEC.md` § 6.2,
unchanged since 2026-11-08.

Also unbuilt, each with a ticket: forge metadata and pull-request linkage (CON-16, CON-17),
traceability references (CON-18), Confluence/GitBook/GitLab publishing backends (CON-59), and
providers other than Anthropic (CON-62, CON-63).

**A glossary is withdrawn rather than unbuilt** (D-100). A term's meaning lives in the rule that uses
it — its statement, its worked examples (D-077) and the exact message a user sees (D-082) — and a
definition in a second place can contradict a frozen version with nothing to detect it.

## 8. What has not been verified

| | |
| --- | --- |
| **The name** | No trademark register search and no attorney opinion. Whether `CONSTAT` is registrable in FR/EU, or descriptive for software that produces findings, is **unanswered** — and `e-constat auto` is an existing French software product. The risk is accepted, not cleared. D-086 |
| **The problem** | Zero discovery conversations have been held. Every design judgement in this repository about what a business reader needs was made without one present. `DISCOVERY.md` holds the script; CON-26 holds the count, which is nought. D-088 |
| **The provider transport** | The Anthropic path is implemented and has never been billed. The MCP path is what has been exercised. D-057 |
| **An authenticated push** | `merge_on_accept` has only ever pushed to a bare repository on disk. Credential-helper behaviour and a protected-branch refusal are both untested. D-062 |
| **A shallow clone** | Nothing creates one. `git log` and `merge-base --is-ancestor` against a truncated history is the shape that produced the D-087 lesson — exit 128 is not an answer — so the behaviour is plausible, not known. D-099 |
| **A submodule** | Never exercised. A registered repository containing one is read as whatever `git` reports for a gitlink, which has not been looked at. D-099 |

## 9. What this project is

A **demonstration of practice**, not a product being taken to market (D-088). The decision log, the
test discipline, the mutation checks and the written reasoning are the artefact; the software is the
medium. `PRODUCT_SPEC.md` § 10's validation track is not the governing plan, and § 8's success
signals are not the measure.

The failure mode that creates — prose about rigour with nothing checking the rigour — is mitigated by
one rule: **Constat has to run on a real repository.** `demo.sh` is the smallest version of that, and
it has already found two defects that the test suite did not.

---

Everything above is a decision with an entry. If one of them is wrong, the entry is the thing to
argue with.
