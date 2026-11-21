# Constat

> Constat turns software changes into evidence-backed, human-approved knowledge about how a
> product behaves.

**Status: pre-MVP.** Phase 1 and 2 of the original roadmap are done; the project then moved to a workspace model (D-027 to D-030). The CLI reads a local Git repository, resolves
revisions, and reports file changes, commits and bounded diff evidence. It does **not** yet
classify anything, produce a report, or support review and baselines — see
[BACKLOG.md](BACKLOG.md) for what exists and what does not.

## What problem this addresses

Software changes are scattered across commits, pull requests, tests, issues, APIs, schemas and
multiple repositories. Technical release notes rarely explain the *impact* in language that product
owners, business analysts and engineering leaders can all use. Documentation goes stale, and
AI-generated explanations can sound confident without being supported by evidence. Teams need a
reviewable record of proposed changes and a trustworthy history of what was actually approved.

## What makes Constat different

- **Product-level view** — connect changes across several repositories to one capability or business
  feature.
- **Evidence first** — distinguish code facts, test results, requirements, AI interpretations and
  human decisions.
- **Governed evolution** — approved baselines are immutable; new AI output is a *proposal* until a
  human reviews it.
- **Release awareness** — preserve parallel release streams and show how behaviour evolves over time.

## The MVP, in one sentence

A local Python CLI that compares two revisions of one Git repository, assembles inspectable
evidence, emits a structured change proposal, lets a human edit/approve/reject it, and stores the
approved result as an immutable versioned baseline.

The MVP workflow:

| Step | Name | What happens |
| ---- | ---- | ------------ |
| 1 | Select | Choose a local Git repository and either two revisions (what changed) or one (what it does now). |
| 2 | Analyse | Collect changed files, commits, diff evidence and references. |
| 3 | Propose | Produce a structured explanation of the possible behaviour change. |
| 4 | Review | A human edits, approves or rejects the proposal. |
| 5 | Baseline | Store the approved version without overwriting history. |
| 6 | Compare later | Show what changed since the previous approved baseline. |

## What Constat assumes about your branching model

**Constat assumes trunk-based development: one mainline per repository, and that mainline is what
is shipped.** Mainline is the default branch's remote-tracking ref, resolved per repository and
never assumed to be `main` (D-028, D-068). Everything ahead of it is work in progress, whatever it
sits on — `develop`, `release/*` or an open ticket branch are all read the same way (D-031).
Rebasing and squash-merging are fine; neither is assumed against.

If your default branch is not your production line, Constat will draw a confident wrong picture:

| Your model | What goes wrong |
| --- | --- |
| **Git Flow** (`develop` for integration, `master`/`main` for production) | If `origin/HEAD` points at `develop`, "already landed" means merged to `develop`, and `constat state` presents unreleased behaviour as current product behaviour. If it points at `master`, the whole `develop` tree reads as never landed. Which you get depends on a repository setting, not on your workflow. |
| **Long-lived parallel release lines** (1.x and 2.x both supported) | There is one mainline, so behaviour shipped only in 1.x is either invisible or reads as unlanded. Those branches are treated as staging ahead of trunk, not as parallel production. |
| **Environment branches** (a `production` branch downstream of `main`) | The same inversion as Git Flow. |
| **Fork-based or patch/email workflows** | A ticket's work is not reachable from any ref in the registered clone, so it reads as matching nothing. |

This is a stated limit, not a bug to report. See
[D-076](DECISIONS.md) for the reasoning, including what it means for product rule 6.

## Explicitly out of scope for the MVP

Web dashboard, multi-tenant SaaS, authentication, billing, Kubernetes, Kafka, graph database,
multi-agent orchestration, automatic approval. These are added only when a validated user need
justifies them. See [ARCHITECTURE.md](ARCHITECTURE.md) § "After the MVP".

## Documents in this repository

| File | Purpose |
| ---- | ------- |
| [PRODUCT_SPEC.md](PRODUCT_SPEC.md) | What Constat is, the MVP scope, acceptance criteria, non-negotiable product rules, open questions. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | The smallest architecture that supports the MVP, and the shape to grow into later. |
| [DECISIONS.md](DECISIONS.md) | Dated decision log. Why things are the way they are. |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | Current state, the 20-session build roadmap, and the next single task. |
| [BACKLOG.md](BACKLOG.md) | Ticket register (`CON-NN`), including the non-code legal and validation work. |
| [LOOP.md](LOOP.md) | **The command loop, end to end** — which command, run by whom, and what happens when it refuses. Start here. |
| [USAGE.md](USAGE.md) | How to run it: the loop, the MCP setup, exit codes, and what each refusal means. |
| [CLAUDE.md](CLAUDE.md) | Working agreement for AI-assisted sessions. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute, and the required DCO sign-off. |
| [LICENSING_STRATEGY.md](LICENSING_STRATEGY.md) | Why Apache-2.0 + DCO, and what it means for a future sale. |
| [BRAND_NAME_REVIEW.md](BRAND_NAME_REVIEW.md) | Trademark, domain and positioning review of the working name. |
| [LIMITS.md](LIMITS.md) | **What Constat does not do**, cannot check, and has not verified. Read it before trusting anything above. |
| [DISCOVERY.md](DISCOVERY.md) | The discovery script (CON-26): who to ask, what to ask, and the assumptions it tests. |

## Getting started

Requires Python 3.11 or newer. One runtime dependency, Pydantic, for schema validation of
persisted records (D-026). Two optional extras: `mcp` for the agent surface, `ai` for a provider
Constat calls itself. Neither is needed for the evidence pipeline.

```bash
python3 -m venv .venv
source .venv/bin/activate          # or spell out .venv/bin/… every time
pip install -e ".[dev,mcp]"
constat --version
```

**Activate the virtual environment**, or `pip` and `constat` are not on your `PATH`. Without it
you get `pip: command not found` on a system with no global pip — NixOS, for instance — and
`constat: command not found` everywhere. The alternative is to spell out `.venv/bin/pip` and
`.venv/bin/constat`. An MCP config always needs the absolute path, because your client has neither
your `PATH` nor an activated venv.

Then the whole loop, with an agent doing the reading:

```bash
constat init --reader mcp         # your agent will read the evidence
constat repo add ~/git/billing --name billing
constat ticket add 622            # gathers evidence across every registered repository
#   …ask your agent to propose the rules this ticket changed…
constat rule proposals 622        # what it proposed, awaiting your decision
constat rule accept 1             # the only thing that creates a rule
constat publish 622               # to the repository's wiki, through the credential gate
```

`--reader` says who reads the evidence, once per workspace: `mcp` for an agent through the MCP
server, or `provider` for Constat calling a model itself with `CONSTAT_AI_PROVIDER`. Change it
later with `constat config reader`.

**[USAGE.md](USAGE.md) is the manual** — the three ways to have the evidence read, the MCP setup,
every exit code, and a table of what each refusal means. Start there.

**Or see the whole loop in one command.** `./demo.sh` builds a throwaway repository in a temporary
directory, runs gather → read → decide → publish-nothing against it, and prints what each step
demonstrates. It needs **no API key and no network**, and never touches your own `~/.constat`:

```bash
./demo.sh
```

It also shows the refusals, which are the product working rather than failing — an ungrounded
anchor and a statement that leaks code are both discarded with the reason named.

Run the tests:

```bash
python -m pytest
```

> **On NixOS** there is no system-wide `pip`. The `venv` above supplies one via `ensurepip`, so the
> commands work unchanged once activated — just don't expect `pip install` to work outside the
> virtual environment.

`analyse` and `snapshot` also still exist. They predate the ticket workflow and are not part of it:
`analyse` reports file-level changes between two revisions from the merge base (D-021), `snapshot`
lists the files present at one revision using no change vocabulary (D-022). Both bound their diff
excerpts and state every omission with the `git` command that regenerates it in full (D-023, D-024).

## Naming

In French law a *constat* is a formal written statement of observed fact — a `constat d'huissier` is
admissible evidence. That is what this product emits: observed facts, formally recorded, attested by
a named person, kept distinguishable from inference.

The project was briefly called "Claudine"; it was renamed on 2026-11-08 over a trademark conflict
with Anthropic's registered CLAUDE mark, before any commit was published. The reasoning is in
[BRAND_NAME_REVIEW.md](BRAND_NAME_REVIEW.md) (decision D-013).

⚠️ **The name is chosen but not cleared.** No USPTO, EUIPO or INPI search has been performed, and no
primary domain has been acquired — `constat.com`, `.ai`, `.dev` and `.io` were all registered as of
2026-11-08. Both are tracked in [DECISIONS.md](DECISIONS.md) open items.

## Licence

[Apache License 2.0](LICENSE). Contributions require a Developer Certificate of Origin sign-off —
see [CONTRIBUTING.md](CONTRIBUTING.md).
