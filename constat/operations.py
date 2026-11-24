"""Operations: gathering evidence for a ticket across the registered set.

An operation reads every registered repository, resolves the ticket's commit
set (D-030, D-031), collects bounded evidence for it, and expands the ticket's
document. Each run is recorded — what ran, against which repository, when, and
what it contributed — because a document whose contents cannot be attributed
is the failure this product exists to prevent (D-029).

**Evidence is collected per commit, not as one cumulative diff.** A ticket's
commits need not be contiguous, so there is no single revision range that
means "this ticket's effect". Diffing the first commit's parent against the
last would sweep in whatever else landed between them. Per-commit collection
costs some duplication — a file touched three times appears three times — but
each hunk stays attributable to the commit that made it, which is the whole
point of provenance (product rule 3).
"""

from __future__ import annotations

import json
import sqlite3

from dataclasses import dataclass, field, replace

from .ai import (
    NULL_PROVIDER_NAME,
    Interpretation,
    Provider,
    ProviderPayload,
    Rejection,
    KnownRule,
    PendingProposal,
    SecretFinding,
    describe_scan,
    guard_release,
    parse,
    redact,
    scan,
)
from .ai import MCP_READER_NOTE
from .ai.redaction import scrub_message
from .ai import resolve as resolve_provider
from .ai.scanning import DocumentFinding, guard_publication
from .errors import PublishRecordFailed
from .publish import Awaiting, AREA_PREFIX, AREAS_DIRECTORY, REVIEWS_DIRECTORY, INDEX_REFERENCE, STATE_REFERENCE, is_generated, PublishedRef, Target
from .publish.decisions import DecisionLine, DecisionsRead
from .publish.targets.git_pages import GitPages
from .publish.targets.git_pages import detect as git_pages_detect
from .errors import (
    InvalidInput,
    PayloadRefused,
    ReferenceMatchedNothing,
    RepositoryError,
)
from .evidence import DEFAULT_LIMITS, EvidenceBundle, ExcerptLimits, collect_evidence
import re

from .git.adapter import (
    is_merge,
    MainlineRef,
    Repository,
    Revision,
    discover_repository,
    contains_commit,
    resolve_mainline,
    resolve_revision,
    search_text,
)
from .git.diff import compare_revisions, summarise_state
from .models import RegisteredRepository, Rule
from .store import READER_MCP, Settings
from .store import Catalogue, Registry, Review, RuleProposals, TicketStore, Workspace
from .store import CatalogueHistory, Release, Releases, VersionAtPoint
from .store import Requirements
from .store.workspace import utc_now
from .git.merge import MergeResult, merge_ticket_branch
from .tickets import (
    TicketMatch,
    TicketStatus,
    branches_naming,
    find_ticket_commits,
)


@dataclass(frozen=True)
class CommitEvidence:
    """One attributed commit and the evidence for what it changed."""

    sha: str
    subject: str
    attribution: str
    found_on: tuple[str, ...]
    bundle: EvidenceBundle | None
    error: str | None = None


@dataclass(frozen=True)
class RepositoryFindings:
    """What one repository contributed, including nothing."""

    repository: RegisteredRepository
    status: TicketStatus
    match: TicketMatch
    commits: tuple[CommitEvidence, ...] = ()
    error: str | None = None
    mainline: MainlineRef | None = None
    """Which ref the work was measured against, and how stale it is (CON-76).

    None only when the repository could not be read, because then nothing was
    measured. Carried rather than re-derived at render time: the document must
    report the ref the comparison actually used, not the one it would resolve
    to now."""

    @property
    def contributed(self) -> bool:
        return bool(self.commits)


@dataclass(frozen=True)
class OperationResult:
    reference: str
    findings: tuple[RepositoryFindings, ...]
    body: str
    interpretation: Interpretation | None = None
    scan_findings: tuple[SecretFinding, ...] = ()
    scan_accepted: bool = False
    run_id: int | None = None
    """The run this result belongs to. A rule proposal reads the evidence one
    run gathered (D-046), so the caller needs the identity, not just the
    body."""

    ticket_opened: bool = False
    """Whether this run opened the ticket rather than finding it (D-063).

    A caller that asked to gather and silently got a new ticket as well should
    be told, so the agent can say it. Defaults to the quieter claim."""

    @property
    def repositories_searched(self) -> int:
        return len(self.findings)

    @property
    def repositories_contributing(self) -> int:
        return sum(1 for f in self.findings if f.contributed)


def _evidence_for_commit(
    repo: Repository, sha: str, limits: ExcerptLimits
) -> EvidenceBundle:
    """Evidence for a single commit, relative to its first parent.

    First parent rather than a merge base: for a merge commit this yields what
    the merge brought in, which is what the merge contributed.
    """
    parent = resolve_revision(repo, f"{sha}^")
    target = resolve_revision(repo, sha)
    summary = compare_revisions(repo, parent, target)
    return collect_evidence(repo, summary, limits)


def _collect_repository(
    entry: RegisteredRepository, reference: str, limits: ExcerptLimits
) -> RepositoryFindings:
    try:
        repo = discover_repository(entry.local_path)
    except RepositoryError as exc:
        from .tickets import TicketMatch as _Match

        return RepositoryFindings(
            repository=entry,
            status=TicketStatus.NOT_FOUND,
            match=_Match(repository_alias=entry.alias, status=TicketStatus.NOT_FOUND),
            error=str(exc),
        )

    # Mainline is the remote-tracking ref where there is one (CON-76). The
    # local branch is one checkout's last pull, and measuring against it makes
    # a shipped ticket read as pending.
    mainline = resolve_mainline(repo, entry.default_branch)
    match = find_ticket_commits(repo, reference, mainline.ref, entry.alias)
    if match.status is not TicketStatus.PENDING:
        # Landed and not-found both contribute no evidence, but they are
        # different answers and the document must say which (D-031).
        return RepositoryFindings(
            repository=entry, status=match.status, match=match, mainline=mainline
        )

    collected = []
    for commit in match.commits:
        try:
            bundle = _evidence_for_commit(repo, commit.sha, limits)
            error = None
        except RepositoryError as exc:
            # A root commit has no parent. Record the reason rather than
            # dropping the commit, which would under-report silently.
            bundle, error = None, str(exc)
        collected.append(
            CommitEvidence(
                sha=commit.sha,
                subject=commit.subject,
                attribution=commit.attribution.value,
                found_on=commit.found_on,
                bundle=bundle,
                error=error,
            )
        )

    return RepositoryFindings(
        repository=entry,
        status=match.status,
        match=match,
        commits=tuple(collected),
        mainline=mainline,
    )


PRODUCED_PROVENANCE = {
    "observed_fact": "Read directly from a repository: a commit, a path, a diff excerpt.",
    "requirement_ref": "A requirement or issue a person said this work answers. Supplied, never fetched: Constat does not read what is at the other end.",
    "ai_interpretation": "A reading of that evidence. Carries no authority until a person accepts it.",
    "unknown": "Constat could not determine this. Not a finding, and never read as one.",
    "human_decision": "A person's acceptance, rejection or retirement, with their name as they gave it.",
}
"""The provenance types Constat actually produces, and what each means here.

Five of the seven in `ProvenanceType` since CON-18 gave `requirement_ref` its
first producer. The remaining two have **no producer** (see
`UNPRODUCED_PROVENANCE`): nothing runs tests, and `assumption` has none either
— every inference Constat makes is either a reading (`ai_interpretation`) or an
admission (`unknown`), and nothing in between has turned out to need a third
word.

`requirement_ref` is produced only by a person running `constat ticket
requirement`. Nothing on the provider or MCP path can write one, which is the
boundary that keeps the label meaningful: a reference a model supplied would be
`ai_interpretation` dressed as external evidence.
"""

UNPRODUCED_PROVENANCE = {
    "test_evidence": "nothing runs tests, and no test result is read (no ticket owns this yet)",
    "assumption": "every inference is either a reading or an admission, so this has no distinct producer",
}
"""Declared in the taxonomy and written by nothing (CON-10, D-094).

Stated rather than quietly carried. An enum member nobody writes is a promise
the code does not keep, and a reader who finds `assumption` in the taxonomy is
entitled to know that no path produces it — PRODUCT_SPEC § 7.1 now says so too.
"""


def provenance_legend(reference: str | None = None) -> list[str]:
    """How to read the provenance labels, generated from the taxonomy.

    Built from the dictionaries above rather than written out, so a type that
    gains or loses a producer cannot leave a legend behind that still describes
    the old shape. A test asserts the legend covers every member of
    `ProvenanceType` — which is what stops the two halves drifting apart.
    """
    linking_from = reference
    lines = [
        "## How to read this",
        "",
        "Every claim above is one of these, and the distinction is the point "
        "(product rule 3):",
        "",
    ]
    for name, meaning in PRODUCED_PROVENANCE.items():
        lines.append(f"- `{name}` — {meaning}")
    lines += [
        "",
        "Three types in the taxonomy are produced by nothing today, and are "
        "listed so their absence is not mistaken for their having been checked:",
        "",
    ]
    for name, why in UNPRODUCED_PROVENANCE.items():
        lines.append(f"- `{name}` — {why}")
    lines += [
        "",
        # The way back out (CON-110). This page is one ticket's evidence; a
        # reader who wants what the product does, rather than what this change
        # touched, had no path to it at all.
        f"The whole catalogue is on [the product as it stands]"
        f"({_page_link(STATE_REFERENCE, frm=linking_from)}), and every page "
        f"published from this workspace is listed in the "
        f"[index]({_page_link(INDEX_REFERENCE, frm=linking_from)}).",
        "",
    ]
    return lines


def describe_age(moment, now=None) -> str:
    """How long ago `moment` was, in words a reader can act on.

    Deliberately coarse — "3 days ago", not a duration to the second. The
    reader's question is "is this old enough to matter", and false precision
    invites a confidence the number does not carry.
    """
    from datetime import datetime, timezone

    now = now or datetime.now(timezone.utc)
    seconds = max(0, int((now - moment).total_seconds()))
    if seconds < 90:
        return "just now"
    for size, unit in ((86400, "day"), (3600, "hour"), (60, "minute")):
        if seconds >= size:
            count = seconds // size
            return f"{count} {unit}{'s' if count != 1 else ''} ago"
    return "just now"


def describe_branching(signal) -> tuple[str, ...]:
    """What was seen about this repository's branching model (CON-97, D-076).

    Returns nothing when the repository looks trunk-based, because a reassuring
    paragraph on every `repo add` is how a warning stops being read. When there
    is something to say it says three things in order: **what Constat will
    treat as shipped**, **what it saw**, and **what would go wrong** — in that
    order, because the consequence is the part that makes the first two worth
    reading.

    A warning and never a refusal (D-076). The signal is a naming convention,
    and refusing on a convention would reject a legitimate repository that
    happens to use the word.
    """
    if not signal.looks_like_git_flow:
        return ()

    lines = [
        f"Constat will treat {signal.mainline} as the product as shipped.",
        "",
    ]

    if signal.integration_is_default:
        lines.append(
            f"This repository's default branch is {signal.default_branch!r}, "
            "which is the name Git Flow gives the branch work is integrated "
            "into *before* release."
        )
    for name, count in signal.ahead_of_mainline:
        lines.append(
            f"Branch {name!r} carries {count} commit(s) that {signal.mainline} "
            "does not, and its name is one teams give the branch they release "
            "from."
        )

    lines.extend(
        [
            "",
            f"If you do release from {signal.mainline}, nothing here is "
            "wrong. If you release from somewhere else, Constat will report "
            "work as shipped when it has only been integrated — and `constat "
            "state` would present unreleased behaviour as the product's "
            "current behaviour.",
            "",
            "Constat supports trunk-based development: one mainline, and that "
            "mainline is what is shipped. Pass --default-branch to name a "
            "different one. See LIMITS.md section 3.",
        ]
    )
    return tuple(lines)


def describe_freshness(entry, now=None) -> str:
    """What a reader must know about how current this repository's copy is
    (CON-38, D-093).

    **Stated for every repository, judged for none.** There is no staleness
    threshold here and there should not be: "older than a week is stale" is a
    judgement about somebody's release cadence, and D-027 asked for disclosure
    rather than a verdict — the same posture CON-76 took for mainline drift,
    which reports counts and leaves the conclusion to a person.

    A local path is read where it is, so there is nothing to be stale. Saying
    so anyway costs one clause and stops the absence of a fetch time reading as
    a missing field.
    """
    if entry.cache_path is None:
        return "Read in place, so as current as the checkout on disk."
    if entry.last_fetched_at is None:
        # Registered before CON-35 populated the column, which cannot happen
        # today — no path writes a cache without a fetch time. Reported rather
        # than assumed current, because an unknown age is not a recent one.
        return (
            "Read from a cache whose last fetch was never recorded, so how old "
            "this is cannot be said."
        )
    return (
        f"Read from a cache fetched {describe_age(entry.last_fetched_at, now)} "
        f"({entry.last_fetched_at.isoformat(timespec='seconds')}). Nothing "
        "refreshes it on its own, so the evidence below is as old as that — "
        "`constat repo fetch` brings it up to date."
    )


PR_BODY_LIMIT = 65_536
"""GitHub's pull-request body limit.

The rendered document has to work as a PR body, and GitHub **truncates a longer
one silently** — which is the failure D-023 refuses for diff excerpts, one
level up. So Constat bounds it itself and states the omission.

A real 30-commit document measures about 21 KB, so this bites only on large
tickets. Stated rather than discovered on the day it does.
"""

EVIDENCE_HEADING = "## Evidence"


def bound_for_pr(body: str, reference: str, limit: int = PR_BODY_LIMIT) -> str:
    """Trim a document to fit a pull-request body, saying what was dropped.

    The **business half is never trimmed** — it is the half a reviewer decides
    from. Only the evidence goes, and it goes wholesale with a pointer to the
    command that shows it in full, the same contract every truncated excerpt
    carries (D-023).
    """
    if len(body) <= limit:
        return body

    head, _, tail = body.partition(EVIDENCE_HEADING)
    omitted = len(tail) + len(EVIDENCE_HEADING)
    notice = [
        EVIDENCE_HEADING,
        "",
        f"**Omitted here: {omitted} characters of evidence.** The full document "
        f"exceeds the {limit}-character limit for a pull-request body, which "
        "would otherwise be truncated silently.",
        "",
        f"See it in full with `constat document {reference} --show`.",
        "",
        "---",
        "",
        "The business section above is complete and was not trimmed.",
        "",
    ]
    bounded = head + "\n".join(notice)
    # The notice itself must fit. If the business half alone exceeds the limit,
    # say so rather than returning something a forge will cut mid-sentence.
    if len(bounded) > limit:
        return (
            f"# Ticket {reference}\n\n"
            f"This document is {len(body)} characters and does not fit a "
            f"pull-request body ({limit}). Read it with "
            f"`constat document {reference} --show`.\n"
        )
    return bounded


@dataclass(frozen=True)
class CatalogueView:
    """What the workspace holds about rules, as the document shows it.

    Passed *into* `render` rather than letting it reach for a workspace:
    rendering stays a pure function of stored structure (ARCHITECTURE.md § 2),
    so it can never discover a fact the store does not already hold.
    """

    impacted: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Current rule name -> the changed paths its anchors matched."""
    unclaimed: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Repository alias -> changed paths no rule claims. The catalogue's
    failure mode, and it must stay visible (D-038, D-039)."""
    queue: tuple = ()
    """Rule proposals awaiting a human decision."""
    rule_count: int = 0
    """Rules in the catalogue, impacted or not — so "no rules were identified"
    can never be printed next to a catalogue that holds some."""


def _changed_paths(finding: RepositoryFindings) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                excerpt.path
                for commit in finding.commits
                if commit.bundle is not None
                for excerpt in commit.bundle.excerpts
            }
        )
    )


def catalogue_view(
    workspace: Workspace,
    reference: str,
    findings: tuple[RepositoryFindings, ...],
) -> CatalogueView:
    """Read what the workspace knows about rules for this ticket.

    Exists because the document used to render rules from the *current run's*
    interpretation, so a ticket whose catalogue held three rules still printed
    "no rules were identified" — a statement about configuration presented as a
    statement about the code, which is product rule 1's failure mode.
    """
    catalogue = Catalogue(workspace)
    impacted: dict[str, list[str]] = {}
    unclaimed: dict[str, tuple[str, ...]] = {}

    for finding in findings:
        paths = _changed_paths(finding)
        if not paths:
            continue
        alias = finding.repository.alias
        for name, matched in catalogue.rules_matching(alias, paths).items():
            impacted.setdefault(name, []).extend(matched)
        missing = catalogue.unmatched_paths(alias, paths)
        if missing:
            unclaimed[alias] = missing

    return CatalogueView(
        impacted={
            name: tuple(sorted(dict.fromkeys(paths)))
            for name, paths in sorted(impacted.items())
        },
        unclaimed=unclaimed,
        queue=RuleProposals(workspace).undecided(reference),
        rule_count=len(catalogue.list()),
    )


def _render_catalogue(view: CatalogueView) -> list[str]:
    """What the workspace knows about rules touched by this change.

    The business half of the document (product rule 8). It reports *code*
    being touched, never what a behaviour now does — that remains a reviewer's
    call (D-035, D-038).
    """
    lines: list[str] = []

    if view.impacted:
        lines += [
            f"{len(view.impacted)} rule(s) in the catalogue have anchors in what "
            "this ticket changed. That their implementation was touched is an "
            "observed fact; whether their behaviour changed is for a reviewer "
            "to say.",
            "",
        ]
        for name, paths in view.impacted.items():
            listed = ", ".join(f"`{path}`" for path in paths)
            lines.append(f"- **{name}** — matched {listed}")
        lines.append("")
    elif view.rule_count:
        lines += [
            f"None of the {view.rule_count} rule(s) in the catalogue has an "
            "anchor in what this ticket changed.",
            "",
        ]

    if view.unclaimed:
        total = sum(len(paths) for paths in view.unclaimed.values())
        lines += [
            f"**{total} changed path(s) are claimed by no rule.** A catalogue "
            "only knows the rules it holds, so this is where it is incomplete "
            "rather than where nothing happened (D-038).",
            "",
        ]
        # One per line rather than a comma-joined run: a real ticket produced
        # 29 of these, and a single paragraph of 29 paths is not readable in a
        # document or a pull request. Never abbreviated with "and N more" —
        # coverage is the thing that has to stay prominent (D-038, D-039).
        for alias, paths in sorted(view.unclaimed.items()):
            lines.append(f"In `{alias}`:")
            lines.append("")
            lines += [f"- `{path}`" for path in paths]
            lines.append("")

    if view.queue:
        lines += [
            f"{len(view.queue)} rule proposal(s) await a human decision. None "
            "carries any authority until accepted (D-036, D-037).",
            "",
        ]
        for item in view.queue:
            revises = (
                f", claiming to revise rule {item.revises_rule_id}"
                if item.revises_rule_id is not None
                else ""
            )
            if item.is_repair:
                # Distinct from a revision and from a new rule (D-065). The
                # business audience reading this needs to know the difference
                # between "we now do this" and "we always said we did this,
                # and had stopped".
                revises = (
                    ", a rule the product already held and the code was "
                    "violating"
                )
            # A GitHub task list, because this document also has to work as a
            # pull-request body. Ticking a box is still inert: a tick is not
            # attributable to anyone, where a committed line in the decisions
            # file is (D-106). The `#N` is what a reviewer writes there.
            lines.append(f"- [ ] `#{item.id}` **{item.proposal.name}**{revises}")
            lines.append(f"  {item.proposal.statement}")
            lines.append(f"  Read by {item.attribution}.")
        lines += [
            "",
            "Ticking a box above records nothing yet — a tick says nothing "
            "about who made it. To decide, write one line per proposal in the "
            "`decisions/` file beside this page, using the `#N` above:",
            "",
            "    1: approved",
            "    2: rejected — the limit is per account, not per customer",
            "",
            "Who decided is taken from your commit, so do not write your "
            "name. Or decide at the command line with `constat rule accept "
            "<ID> --by <who>`.",
            "",
        ]

    return lines


def _render_rejections(interpretation: Interpretation) -> list[str]:
    """List proposals the provider offered and the parser discarded.

    Omitting these would show a reviewer two rules when the provider offered
    eight, which misstates what the pass did. The reasons matter too: an
    ungrounded anchor means the model invented a path, and a reviewer should
    know that happened.
    """
    if not interpretation.rejections:
        return []

    lines = [
        f"{len(interpretation.rejections)} proposal(s) returned by "
        f"{interpretation.describe()} were **discarded** before reaching this "
        "document, for the reasons given. They are listed because a silently "
        "shortened list would misstate what the pass produced.",
        "",
    ]
    lines += [f"- {rejection.describe()}" for rejection in interpretation.rejections]
    lines.append("")
    return lines


def _render_rules(
    interpretation: Interpretation, view: CatalogueView | None = None
) -> list[str]:
    """Render the rules section, which always appears.

    An absent section would be read as "there are no rules here" — the one
    thing Constat must never imply (product rule 1). So the section is
    unconditional and its note carries the distinction between *no rules were
    identified* and *no rules exist*.
    """
    lines = ["## Business rules", ""]
    if view is not None:
        lines += _render_catalogue(view)

    if not interpretation.identified_rules:
        # Scoped to *this run*. Without the qualifier the note read as a
        # statement about the ticket, while the catalogue beside it held rules.
        note = (
            interpretation.note
            or "No rules were identified. That is not a statement that none exist."
        )
        lines += [f"**This run:** {note}", ""]
        return lines + _render_rejections(interpretation)

    lines += [
        f"**This run:** {len(interpretation.proposals)} rule(s) proposed by "
        f"{interpretation.describe()}. Every one is an interpretation, not a "
        "finding: proposals carry no authority until a human accepts them "
        "individually (D-036, D-039).",
        "",
    ]
    for proposal in interpretation.proposals:
        lines.append(f"### {proposal.name}")
        lines.append("")
        lines.append(f"{proposal.statement}")
        lines.append("")
        # The parts of a rule do not share one provenance, and saying they do
        # was the gap CON-10 closed. A statement is a reading; an anchor is a
        # path somebody can look at; a message is a quotation whose truth is
        # checkable and has not been checked here.
        lines.append(f"Provenance: `{proposal.provenance.value}` — the")
        lines.append("statement, behaviours and examples are a reading of the")
        lines.append("evidence. Anchors are `observed_fact`: the paths exist,")
        if proposal.messages:
            lines.append("verified below. Messages are quotations of what the")
            lines.append("product shows a user — `constat message verify`")
            lines.append("checks them against the code; this document has not.")
        else:
            lines.append("verified below.")
        lines.append("")
        if proposal.behaviours:
            lines.append("Behaviours:")
            lines.append("")
            for behaviour in proposal.behaviours:
                lines.append(f"- {behaviour.description}")
            lines.append("")
        if proposal.messages:
            lines.append("Messages the user sees:")
            lines.append("")
            for message in proposal.messages:
                lines.append(f"- > {message.text}")
            lines.append("")
        lines += example_table(proposal.examples)
        if proposal.anchors:
            lines.append("Anchors:")
            lines.append("")
            for anchor in proposal.anchors:
                scope = f"{anchor.repository_alias}:" if anchor.repository_alias else ""
                lines.append(f"- `{scope}{anchor.path_glob}`")
            lines.append("")
        else:
            lines += [
                "No anchors proposed, so this rule can never be matched to a "
                "future change.",
                "",
            ]
    return lines + _render_rejections(interpretation)


def render(
    reference: str,
    findings: tuple[RepositoryFindings, ...],
    interpretation: Interpretation | None = None,
    scan_section: list[str] | None = None,
    view: CatalogueView | None = None,
    requirements: tuple = (),
) -> str:
    """Render the machine-derived part of a document.

    Every searched repository appears, including those that contributed
    nothing. Silence about a repository is indistinguishable from "no changes
    there", and the two are not the same claim.

    `interpretation` and `scan_section` are optional only so the evidence
    rendering stays callable on its own. When either is absent its section is
    omitted entirely rather than rendered as empty, because an empty section is
    itself a claim.
    """
    lines: list[str] = [f"# Ticket {reference}", ""]

    if not findings:
        lines += [
            "No repositories are registered, so nothing was searched.",
            "",
            "This is not a statement that the ticket changed nothing.",
        ]
        return "\n".join(lines)

    contributing = [f for f in findings if f.contributed]
    lines += [
        f"{len(findings)} repository(ies) searched; "
        f"{len(contributing)} contributed evidence.",
        "",
    ]

    # Business view first, evidence under its own heading. The two must not be
    # conflated (product rule 8): one says what this means, the other says what
    # it rests on.
    if interpretation is not None:
        lines += _render_rules(interpretation, view)

    lines += ["## Evidence", ""]

    for finding in findings:
        entry = finding.repository
        lines.append(f"### {entry.alias}")
        lines.append("")
        measured = (
            finding.mainline.describe()
            if finding.mainline is not None
            else f"`{entry.default_branch}`"
        )
        lines.append(f"Measured against {measured}.")
        lines.append("")
        # Unstated staleness is the same class of failure as unstated
        # truncation (D-023, D-027): a document that reads as current while
        # resting on a week-old cache is confidently wrong about the present.
        lines.append(describe_freshness(entry))
        claimed = finding.match.claimed_by_another
        if claimed:
            # The branch carried them; their messages say they belong to
            # another ticket. Named, because the rule that excluded them is a
            # heuristic and a reader must be able to disagree with it
            # (CON-121).
            lines.append("")
            lines.append(
                f"{len(claimed)} commit(s) excluded: carried by this ticket's "
                "branch but naming another ticket — "
                + ", ".join(
                    f"`{sha[:12]}` ({other})" for sha, _subject, other in claimed
                )
                + ". A branch cut from an integration branch inherits its "
                "unmerged work; this is that work, not this ticket's."
            )

        own = finding.match.excluded_own_commits
        if own:
            # Stated, not performed silently. Every other omission in this
            # product says so, and evidence that quietly disagrees with
            # `git log` is worse than evidence with a line of explanation
            # (CON-75).
            lines.append("")
            lines.append(
                f"{len(own)} commit(s) excluded: made by Constat when landing "
                "this ticket, so not the team's implementation evidence — "
                + ", ".join(f"`{sha[:12]}`" for sha in own)
                + "."
            )
        if finding.mainline is not None and finding.mainline.has_unpushed:
            lines.append("")
            lines.append(
                f"{finding.mainline.ahead} commit(s) on this clone's "
                f"`{finding.mainline.branch}` are not on "
                f"`{finding.mainline.ref}`. Mainline is the shared ref, so "
                "work that exists only locally reads below as not yet landed."
            )
        if finding.mainline is not None and finding.mainline.is_stale:
            # Stated rather than silently absorbed. Nothing Constat can write
            # closes this gap — only a fetch does, and fetching is not its
            # business on a gather — so the document says how old the picture
            # is (CON-76, and CON-38's posture for caches).
            lines.append("")
            lines.append(
                f"This clone has not caught up with `{finding.mainline.ref}`. "
                "Work already merged there can still appear below as not yet "
                "landed."
            )
        lines.append("")

        if finding.error:
            # Tagged `unknown`, which is the type's first real producer. An
            # unreadable repository is not a repository that contributed
            # nothing: the second is a finding and the first is an admission,
            # and a reader must be able to tell them apart (product rule 1).
            lines += [
                f"`unknown` — could not be read: {finding.error}. Nothing below "
                "is a statement about this repository.",
                "",
            ]
            continue

        if finding.status is TicketStatus.LANDED:
            lines += [
                # The ref the comparison used, not the branch name: saying
                # "already in `main`" under "measured against `origin/main`"
                # invites the reader to check the wrong ref (CON-76).
                f"Already in `{finding.mainline.ref if finding.mainline else entry.default_branch}` "
                f"({finding.match.commit_count} commit(s)). Outside the window "
                "Constat documents, so no evidence was gathered here — which is "
                "not the same as finding nothing.",
                "",
            ]
            continue

        if finding.status is TicketStatus.NOT_FOUND:
            lines += [
                "No commits reference this ticket. That means the reference "
                "matched nothing here, not that the ticket changed nothing.",
                "",
            ]
            continue

        refs = sorted({r for c in finding.commits for r in c.found_on})
        if refs:
            lines += ["Found on: " + ", ".join(f"`{r}`" for r in refs), ""]

        for commit in finding.commits:
            lines.append(f"#### `{commit.sha[:12]}` {commit.subject}")
            lines.append("")
            lines.append(f"Attributed by {commit.attribution.replace('_', ' ')}.")
            lines.append("")

            if commit.error or commit.bundle is None:
                lines += [f"No diff available: {commit.error}", ""]
                continue

            bundle = commit.bundle
            if not bundle.excerpts:
                lines += ["No file changes in this commit.", ""]
                continue

            lines.append(f"{len(bundle.excerpts)} file(s) changed:")
            lines.append("")
            for excerpt in bundle.excerpts:
                name = (
                    f"{excerpt.previous_path} → {excerpt.path}"
                    if excerpt.previous_path
                    else excerpt.path
                )
                lines.append(f"- `{name}` ({excerpt.change_type.name.lower()})")
            lines.append("")
            lines.append(bundle.completeness_note())
            lines.append("")

    if scan_section:
        lines += scan_section

    lines += ["---", ""]
    if interpretation is not None and interpretation.identified_rules:
        lines.append(
            "Evidence above is observed fact; the rules are "
            "`ai_interpretation`. The two are kept separate on purpose "
            "(product rule 3), and neither is approved: this document carries "
            "no authority until a human approves a version of it."
        )
    else:
        lines.append(
            "Observed facts only. Nothing here is classified, interpreted or "
            "approved: every excerpt records the command that regenerates it, "
            "and this document carries no authority until a human approves a "
            "version of it."
        )

    # Before the legend, because the legend now advertises `requirement_ref`
    # as a type Constat produces (CON-18) — and a label explained in the key
    # but never appearing in a document would be misleading in the other
    # direction from the gap it closed.
    if requirements:
        lines += _requirements_section(requirements)

    # Last, because it is reference rather than content — and unconditional,
    # because a document whose labels are explained only sometimes teaches a
    # reader to ignore them (CON-10).
    lines.append("")
    lines += provenance_legend(reference)
    return "\n".join(lines)


def _requirements_section(requirements: tuple) -> list[str]:
    """The requirements a person said this work answers (CON-18).

    **Its own section, kept away from the evidence.** Product rule 3 asks that
    implementation evidence, requirements, AI interpretation and human approval
    stay distinguishable, and a supplied pointer sitting among observed facts
    would read as something Constat had checked.

    Every line says *supplied* rather than *verified*, because that is the only
    claim available: Constat never opens the artefact, so it does not know
    whether the requirement says what the reference implies — or whether it
    still exists.
    """
    lines = ["", "## Supplied requirements", ""]
    lines.append(
        "Pointers a person attached to this work. Provenance "
        "`requirement_ref`: **supplied, not verified** — Constat did not open "
        "any of these and does not know what they say."
    )
    lines.append("")
    for requirement in requirements:
        target = f"[{requirement.label}]({requirement.uri})" if requirement.uri else f"`{requirement.label}`"
        lines.append(
            f"- {target} — supplied by {requirement.supplied_by} "
            f"({requirement.attribution}) on "
            f"{requirement.created_at[:10]}"
        )
    return lines


def known_rules(workspace: Workspace) -> tuple[KnownRule, ...]:
    """The catalogue as a provider sees it.

    Without this a reading has never been shown what exists, so every reading
    claims to be new and the second reading of a rule creates a duplicate —
    the failure CON-43 exists to prevent (D-050).
    """
    rows = workspace.execute(
        "SELECT id, name, statement, area FROM rule ORDER BY id"
    ).fetchall()
    rules = []
    for row in rows:
        anchors = workspace.execute(
            "SELECT path_glob FROM anchor WHERE rule_id = ? ORDER BY path_glob",
            (row["id"],),
        ).fetchall()
        examples = workspace.execute(
            "SELECT situation, outcome FROM example WHERE rule_id = ? ORDER BY id",
            (row["id"],),
        ).fetchall()
        rules.append(
            KnownRule(
                rule_id=row["id"],
                name=row["name"],
                statement=row["statement"],
                anchors=tuple(a["path_glob"] for a in anchors),
                examples=tuple((e["situation"], e["outcome"]) for e in examples),
                area=row["area"],
            )
        )
    return tuple(rules)


def pending_readings(workspace: Workspace, reference: str) -> tuple[PendingProposal, ...]:
    """This ticket's review queue, as a reading sees it (CON-70).

    Scoped to the ticket rather than the workspace: a duplicate only matters
    against the evidence being read now, and showing a reading every undecided
    proposal in the workspace would bury the one that matters.

    Separate from `known_rules` because the payload keeps them apart — a
    catalogue rule invites a revision, a pending proposal invites silence.
    """
    proposals = RuleProposals(workspace)
    return tuple(
        PendingProposal(
            proposal_id=stored.id,
            name=stored.proposal.name,
            statement=stored.proposal.statement,
            anchors=tuple(a.path_glob for a in stored.proposal.anchors),
        )
        for stored in proposals.undecided(reference)
    )


def mainline_files(
    workspace: Workspace, aliases: tuple[str, ...] | None = None
) -> dict[str, frozenset[str]]:
    """The files at each registered repository's mainline, for grounding.

    The second ground an anchor may rest on (D-072): a rule can be anchored
    where it lives even when the ticket being read did not touch it. Before
    CON-71 the only ground was the ticket's own diff, so a rule whose home was
    not in that diff could not be proposed at all — and once a ticket landed,
    *no* rule could be proposed for it, because a landed ticket contributes no
    evidence (D-031).

    **Not part of the payload.** A reader is told the rule in the guidance
    rather than handed every path in the product: the live workspace holds 922
    files across three repositories, and sending that to a provider on every
    gather would cost real money to say what a sentence says.

    A repository that cannot be read contributes nothing and is skipped
    silently *here* — the caller already reports unreadable repositories from
    `collect`, and a second complaint from the grounding layer would say
    nothing new.
    """
    files: dict[str, frozenset[str]] = {}
    for entry in Registry(workspace).list():
        if aliases is not None and entry.alias not in aliases:
            continue
        try:
            repo = discover_repository(entry.local_path)
            mainline = resolve_mainline(repo, entry.default_branch)
            revision = resolve_revision(repo, mainline.ref)
            files[entry.alias] = frozenset(summarise_state(repo, revision).paths)
        except RepositoryError:
            continue
    return files


def collect(
    workspace: Workspace,
    reference: str,
    limits: ExcerptLimits = DEFAULT_LIMITS,
    require_ticket: bool = True,
) -> tuple[RepositoryFindings, ...]:
    """Read every registered repository for a ticket. Writes nothing.

    Shared by `gather` and `export_payload` so the two cannot disagree about
    what a ticket's evidence is.

    `require_ticket=False` searches for a reference no ticket exists for yet.
    Only `gather` asks for that, and only to decide whether the reference is
    real enough to open one (D-063) — the search is read-only either way, so
    the guard is about who is allowed to act on the result, not about safety.
    """
    if require_ticket:
        TicketStore(workspace).document(reference)  # NotRegistered if unknown
    registry = Registry(workspace)
    return tuple(
        _collect_repository(entry, reference, limits) for entry in registry.list()
    )


@dataclass(frozen=True)
class ExportResult:
    """A payload cleared to leave the process, and what the scan found."""

    payload: ProviderPayload
    scan_findings: tuple[SecretFinding, ...] = ()
    accepted: bool = False
    run_id: int | None = None
    """Set only when a run was recorded — an export that found nothing to
    accept made no decision, and so is not an event."""


def export_payload(
    workspace: Workspace,
    reference: str,
    limits: ExcerptLimits = DEFAULT_LIMITS,
    accept_scan_findings: bool = False,
) -> ExportResult:
    """Produce the payload for something outside this process to read.

    **This is the second front door** (D-045). Whatever reads the result — an
    agent, an MCP client, a person with a clipboard — is outside Constat, so
    the payload is leaving: redaction applies, and the credential gate applies
    *unconditionally*, not only when a provider is configured.

    That is the one asymmetry with `gather`. A local run that sends nothing can
    tolerate a false positive; an export cannot, because by the time it has
    printed, it has left.

    Writes nothing except an override record when findings were accepted — an
    override nobody can see afterwards is the same as no scan (D-044).
    """
    findings = collect(workspace, reference, limits)
    payload = redact(
        reference,
        findings,
        known_rules(workspace),
        pending_readings(workspace, reference),
    )
    scan_findings = guard_release(payload, accepted=accept_scan_findings)

    accepted = bool(scan_findings)
    run_id = None
    if accepted:
        # Only recorded when there is something to record. An export that
        # found nothing made no decision, so inventing a run for it would put
        # an empty event in the audit trail.
        run_id = open_run(workspace, reference, "export_payload")
        _record_scan_override(
            workspace, reference, scan_findings, "scan_override_export", run_id
        )

    return ExportResult(
        payload=payload,
        scan_findings=scan_findings,
        accepted=accepted,
        run_id=run_id,
    )


@dataclass(frozen=True)
class SubmitResult:
    """What a submitted reply produced."""

    run_id: int
    stored: tuple[int, ...] = ()
    rejections: tuple[Rejection, ...] = ()
    candidates: dict[int, tuple[int, ...]] = field(default_factory=dict)
    """Rule proposal id -> rules its anchors overlap, for readings that claimed
    to be new. A warning to the reviewer, never a decision (D-050)."""
    pending_candidates: dict[int, tuple[int, ...]] = field(default_factory=dict)
    """Rule proposal id -> *undecided* rule proposals its anchors overlap
    (CON-70). Kept apart from `candidates` because the reviewer's next move
    differs: an overlapping catalogue rule may want a revision, an overlapping
    pending proposal wants one of the two collapsed before either is
    accepted."""
    new_areas: dict[int, tuple[str, tuple[str, ...]]] = field(default_factory=dict)
    """Rule proposal id -> (the area it coined, the areas already declared).

    Reported, never refused (CON-88, D-064's posture). A new area is often
    correct — the product grows — and refusing one would make Constat the
    authority on how someone's business is organised. What it must not do is
    let "ads" slip in beside "advertising" unremarked, because nothing
    afterwards can tell a synonym from a distinction, and merging two areas is
    a rename across frozen versions."""

    @property
    def stored_count(self) -> int:
        return len(self.stored)

    @property
    def possible_duplicates(self) -> int:
        return len(self.candidates)

    @property
    def possible_pending_duplicates(self) -> int:
        return len(self.pending_candidates)


def submit_reply(
    workspace: Workspace,
    reference: str,
    text: str,
    provider: str = "external",
    model: str | None = None,
    limits: ExcerptLimits = DEFAULT_LIMITS,
) -> SubmitResult:
    """Turn a reply produced outside Constat into stored rule proposals.

    The inbound half of D-045: `export_payload` hands the evidence out, this
    takes the reading back. Everything after the reply is the same as the
    provider path — the same `parse`, the same anchor grounding, the same
    append-only storage — because `parse` takes `(text, payload)` and does not
    care where the text came from (D-046).

    **The evidence is re-gathered rather than trusted.** Grounding has to be
    checked against what Constat can see now, not against whatever the caller
    claims it read; a caller who could supply the payload could also supply a
    payload that makes any anchor look grounded.

    **No credential gate here.** The payload is rebuilt locally to check
    grounding and is never transmitted, so there is nothing to refuse. The gate
    belongs on egress (D-047), and applying it to an inbound path would refuse
    a reply about evidence the user already, knowingly, exported.

    **Nothing is accepted.** Everything stored is pending a human decision
    (D-036, D-037); this fills the review queue and never writes to the
    catalogue.
    """
    findings = collect(workspace, reference, limits)
    payload = redact(
        reference,
        findings,
        known_rules(workspace),
        pending_readings(workspace, reference),
    )

    # Raises MalformedResponse for an unusable reply, rather than storing
    # nothing and letting that read as "no rules were identified" (D-046).
    result = parse(text, payload, mainline_files(workspace))

    run_id = open_run(workspace, reference, "submit_reply")
    # Before the readings are stored, so a proposal never exists with its
    # evidence pointer missing (D-073).
    record_run_evidence(workspace, run_id, findings)
    return _store_readings(
        workspace,
        run_id,
        result.proposals,
        result.rejections,
        provider,
        model,
        reference,
    )


def _store_readings(
    workspace: Workspace,
    run_id: int,
    readings: tuple,
    rejections: tuple,
    provider: str,
    model: str | None,
    reference: str,
) -> SubmitResult:
    """Store grounded readings and report what a reviewer needs to know.

    Shared by `submit_reply` and `baseline_area` deliberately. The two differ
    in what the reading is *about* and in nothing after that: the duplicate
    warnings, the coined-area report and the append-only storage must behave
    identically, or the queue becomes a record of which command happened to be
    used.
    """
    proposals = RuleProposals(workspace)
    stored = []
    candidates: dict[int, tuple[int, ...]] = {}
    pending_candidates: dict[int, tuple[int, ...]] = {}
    new_areas: dict[int, tuple[str, tuple[str, ...]]] = {}
    declared = Catalogue(workspace).areas()
    for proposal in readings:
        proposal_id = proposals.record(
            run_id=run_id,
            proposal=proposal,
            provider=provider,
            model=model,
            revises_rule_id=proposal.revises_rule_id,
        )
        stored.append(proposal_id)

        if proposal.revises_rule_id is None:
            # The reading claims to be new. Anchor overlap cannot decide that
            # for it (D-050) — one file routinely implements several rules —
            # but a reviewer about to accept a duplicate needs to see the
            # candidates rather than discover them later.
            overlapping = proposals.candidates_for(proposal.anchors)
            if overlapping:
                candidates[proposal_id] = overlapping

            # And the queue, which `candidates_for` cannot see: it reads the
            # `anchor` table, where only accepted rules appear. Two readings of
            # one ticket used to produce two identical proposals and no
            # warning (CON-70).
            also_pending = proposals.pending_candidates_for(
                proposal.anchors, exclude=proposal_id
            )
            if also_pending:
                pending_candidates[proposal_id] = also_pending

        # Checked for every reading, revision or not: a revision can coin a
        # synonym just as easily as a new rule can.
        if proposal.area is not None and proposal.area not in declared:
            new_areas[proposal_id] = (proposal.area, declared)

    return SubmitResult(
        run_id=run_id,
        stored=tuple(stored),
        rejections=tuple(rejections),
        candidates=candidates,
        pending_candidates=pending_candidates,
        new_areas=new_areas,
    )


def _document_id(workspace: Workspace, reference: str) -> int:
    return workspace.execute(
        "SELECT d.id FROM document d JOIN ticket t ON t.id = d.ticket_id "
        "WHERE t.reference = ?",
        (reference,),
    ).fetchone()["id"]


@dataclass(frozen=True)
class EvidenceCommit:
    """A commit a run read, as the record keeps it (D-073)."""

    sha: str
    subject: str
    repository_alias: str | None
    repository_identity: str | None

    @property
    def short_sha(self) -> str:
        return self.sha[:12]


@dataclass(frozen=True)
class BaselineResult:
    """What a baseline of one area produced (CON-89)."""

    area: str
    reference: str
    submitted: SubmitResult
    opened_ticket: bool = False
    """Whether the reference was opened here rather than found (D-063's
    posture). A cold-start baseline supplies its own reference, and the user
    should be told a ticket now exists under it."""
    read_from: tuple[tuple[str, str], ...] = ()
    """(repository alias, mainline revision) for each repository read.

    The baseline's answer to "which *now* did you describe". A claim about the
    present that cannot name the revision it described is not inspectable
    (product rule 2), and unlike a ticket there is no commit set to point at —
    so the pointer is mainline itself."""
    out_of_area: tuple[Rejection, ...] = ()
    """Readings refused because they named a different area than the one being
    baselined. Refused rather than re-filed: `baseline advertising` is a
    statement of scope, and quietly accepting a rule about payouts would make
    the command's own argument meaningless."""


def baseline_area(
    workspace: Workspace,
    area: str,
    reference: str,
    text: str,
    provider: str = "external",
    model: str | None = None,
) -> BaselineResult:
    """Store a reading that documents an area as it behaves now (CON-89).

    **The difference from `submit_reply` is what the reading is *about*.** A
    submitted reply describes what a ticket changed; a baseline describes what
    already exists, so there is no delta to read and no payload Constat can
    usefully supply — the reader has the repository and reads it directly. What
    Constat does here is what only it can do: ground every anchor, record which
    revision was described, and store the result as proposals nobody has
    accepted.

    **Grounding needs nothing new.** With no ticket evidence in the payload,
    every anchor is checked against mainline, which D-072 already allows and
    records as `grounded_in='mainline'`. A baseline's anchors are therefore the
    weaker of the two grounds *by construction*, which is correct: this ticket
    is not the evidence that anything changed, because nothing did.

    **Why it still hangs off a reference.** The chain
    `ticket -> document -> run -> rule_proposal` is `NOT NULL` at every link,
    and a proposal must point at a run. Rather than rebuild nine tables to let
    a run belong to an area, a baseline is submitted against the ticket that
    occasioned it — which is how a baseline actually arises, since an
    undocumented area is normally discovered while documenting a change. With
    no occasioning ticket the caller supplies a reference, which is opened
    here. The cost is stated rather than hidden: such a reference appears in
    `ticket list` without being a unit of work.
    """
    tickets = TicketStore(workspace)
    opened = tickets.find(reference) is None
    if opened:
        # Opened rather than refused, the posture D-063 set for gathering: a
        # cold-start baseline has no occasioning ticket, so refusing here would
        # make the first baseline in a workspace impossible.
        tickets.add(reference)

    # Collected for the mainline grounding map and for the revision pointers.
    # Not for a payload: there is none (see above).
    mainline = mainline_files(workspace)
    read_from = _mainline_revisions(workspace)

    payload = redact(
        reference,
        (),
        known_rules(workspace),
        pending_readings(workspace, reference),
    )
    result = parse(text, payload, mainline)

    # Scope is the command's argument, so a reading about another area is out
    # of scope rather than mis-filed. Partitioned before anything is stored:
    # storing then reporting would leave the reviewer a proposal to decide
    # that the baseline never claimed.
    in_area, out_of_area = [], []
    for proposal in result.proposals:
        if proposal.area is not None and proposal.area != area:
            out_of_area.append(
                Rejection(
                    proposal.name,
                    f"names area {proposal.area!r}, but this is a baseline of "
                    f"{area!r}. Baseline that area separately.",
                )
            )
        else:
            in_area.append(proposal.model_copy(update={"area": area}))

    run_id = open_run(workspace, reference, "baseline")
    _record_mainline_evidence(workspace, run_id, read_from)
    # Only the parse's rejections go in here. An out-of-scope reading is not
    # ungrounded or malformed — it is a correct reading of the wrong area — and
    # folding the two together would report it twice and mislabel it the second
    # time. It travels on `out_of_area`, which says what it actually was.
    submitted = _store_readings(
        workspace, run_id, tuple(in_area), result.rejections,
        provider, model, reference,
    )
    return BaselineResult(
        area=area,
        reference=reference,
        submitted=submitted,
        opened_ticket=opened,
        read_from=read_from,
        out_of_area=tuple(out_of_area),
    )


def _mainline_revisions(workspace: Workspace) -> tuple[tuple[str, str], ...]:
    """Each registered repository's mainline revision, or why it was not read.

    An unreadable repository is reported rather than skipped, for D-070's
    reason: its files are absent from the grounding map, so a rule that lives
    there would be refused as ungrounded — and silence would make that look
    like the rule being wrong rather than the repository being unreadable.
    """
    revisions = []
    for entry in Registry(workspace).list():
        try:
            repo = discover_repository(entry.local_path)
            mainline = resolve_mainline(repo, entry.default_branch)
            revision = resolve_revision(repo, mainline.ref)
            revisions.append((entry.alias, revision.sha))
        except RepositoryError as exc:
            revisions.append((entry.alias, f"unreadable: {exc}"))
    return tuple(revisions)


def _record_mainline_evidence(
    workspace: Workspace, run_id: int, read_from: tuple[tuple[str, str], ...]
) -> None:
    """Record which revision of each repository a baseline described (D-073).

    The same table a ticket's commits go in, because it answers the same
    question — what did this reading rest on — and a reviewer looking back must
    not have to know which kind of run produced a pointer to resolve it.
    """
    rows = [
        (run_id, alias, None, sha, "(mainline at the time of the baseline)")
        for alias, sha in read_from
        if not sha.startswith("unreadable:")
    ]
    if not rows:
        return
    with workspace.transaction() as ws:
        for row in rows:
            ws.execute(
                "INSERT OR IGNORE INTO run_commit "
                "(run_id, repository_alias, repository_identity, sha, subject) "
                "VALUES (?, ?, ?, ?, ?)",
                row,
            )


def record_run_evidence(
    workspace: Workspace, run_id: int, findings: tuple[RepositoryFindings, ...]
) -> int:
    """Write down which commits this run read, and return how many.

    Called once per run, because every reading of that run read the same
    evidence. A rule version reaches it through
    `rule_version -> rule_proposal -> run`, which is why this is stored against
    the run rather than copied onto each proposal.

    Nothing is stored for a run that read nothing — a landed ticket contributes
    no evidence (D-031), and an empty pointer set is the honest record of that.
    """
    rows = [
        (
            run_id,
            finding.repository.alias,
            finding.repository.identity,
            commit.sha,
            # Scrubbed, even though this never leaves the machine. The
            # redaction boundary exists because identity in a store is a
            # disclosure waiting to happen (`ai/redaction.py`), and a subject
            # can carry an address. Over-masking a pointer costs nothing; the
            # SHA is what resolves it.
            scrub_message(commit.subject),
        )
        for finding in findings
        for commit in finding.commits
    ]
    if not rows:
        return 0

    with workspace.transaction() as ws:
        for run, alias, identity, sha, subject in rows:
            ws.execute(
                "INSERT OR IGNORE INTO run_commit "
                "(run_id, repository_id, repository_identity, repository_alias, "
                " sha, subject) VALUES "
                "(?, (SELECT id FROM repository WHERE alias = ?), ?, ?, ?, ?)",
                (run, alias, identity, alias, sha, subject),
            )
    return len(rows)


def evidence_for_run(workspace: Workspace, run_id: int) -> tuple[EvidenceCommit, ...]:
    """The commits a run read. Empty when it read none, or predates D-073."""
    rows = workspace.execute(
        "SELECT sha, subject, repository_alias, repository_identity "
        "FROM run_commit WHERE run_id = ? ORDER BY repository_alias, sha",
        (run_id,),
    ).fetchall()
    return tuple(
        EvidenceCommit(
            sha=row["sha"],
            subject=row["subject"],
            repository_alias=row["repository_alias"],
            repository_identity=row["repository_identity"],
        )
        for row in rows
    )


def evidence_for_proposal(
    workspace: Workspace, proposal_id: int
) -> tuple[EvidenceCommit, ...]:
    """The commits behind one reading, through the run that gathered them."""
    row = workspace.execute(
        "SELECT run_id FROM rule_proposal WHERE id = ?", (proposal_id,)
    ).fetchone()
    return () if row is None else evidence_for_run(workspace, int(row["run_id"]))


def evidence_for_version(
    workspace: Workspace, rule_version_id: int
) -> tuple[EvidenceCommit, ...]:
    """The commits an accepted rule version rests on (D-073).

    The question product rule 2 asks of a governance record: what evidence is
    this claim based on. Resolved through the reading rather than copied onto
    the version, because `run_commit` is itself append-only history — a
    reference to an immutable row is as durable as a duplicate of it, and does
    not create two places for the same fact to live.
    """
    row = workspace.execute(
        "SELECT p.run_id FROM rule_version v "
        "JOIN rule_proposal p ON p.id = v.from_rule_proposal_id "
        "WHERE v.id = ?",
        (rule_version_id,),
    ).fetchone()
    return () if row is None else evidence_for_run(workspace, int(row["run_id"]))


def open_run(workspace: Workspace, reference: str, kind: str) -> int:
    """Record that a run happened, and return its identity.

    A gather writes one `operation` row per repository, so no operation row
    answers "which run produced this". A rule proposal is a reading of the
    evidence one run gathered (D-046), so it needs a single thing to point at.
    """
    document_id = _document_id(workspace, reference)
    with workspace.transaction() as ws:
        cursor = ws.execute(
            "INSERT INTO run (document_id, kind, started_at) VALUES (?, ?, ?)",
            (document_id, kind, utc_now()),
        )
        return int(cursor.lastrowid)


def _record_scan_override(
    workspace: Workspace,
    reference: str,
    scan_findings: tuple[SecretFinding, ...],
    kind: str,
    run_id: int,
) -> None:
    """Record that a human let credential findings through.

    Against the document rather than a repository: the decision was about the
    payload as a whole. Locations are kept so the override stays auditable; the
    matched text never is.
    """
    with workspace.transaction() as ws:
        ws.execute(
            "INSERT INTO operation "
            "(document_id, run_id, repository_id, kind, ran_at, summary, payload) "
            "VALUES (?, ?, NULL, ?, ?, ?, ?)",
            (
                _document_id(workspace, reference),
                run_id,
                kind,
                utc_now(),
                f"accepted {len(scan_findings)} credential-scan finding(s)",
                "\n".join(f.describe() for f in scan_findings),
            ),
        )


def _open_for_reference(
    workspace: Workspace,
    reference: str,
    findings: tuple[RepositoryFindings, ...],
) -> None:
    """Open a ticket for a reference the repositories recognise (D-063).

    `LANDED` counts as recognition even though it contributes no evidence: the
    work was found, in mainline, which is a different answer from "no such
    reference" (D-031) and a ticket for it is about something real.

    A repository that could not be read is not evidence of absence. It reports
    `NOT_FOUND` with an `error` set, which is indistinguishable by status from
    a genuine miss, so a reference seen by nothing and unreadable somewhere is
    refused with both counts named rather than resolved by assuming the
    unreadable one would also have missed.
    """
    recognised = [
        f
        for f in findings
        if f.status in (TicketStatus.PENDING, TicketStatus.LANDED)
    ]
    if recognised:
        TicketStore(workspace).add(reference)
        return

    if not findings:
        # Nothing was searched, so "matched no commits" would blame the
        # reference for the registry being empty. The distinction matters for
        # the same reason the unreadable-repository one does: absence of
        # evidence is not evidence of absence.
        raise ReferenceMatchedNothing(
            f"no repositories are registered, so {reference!r} could not be "
            "looked for. Register one with `constat repo add <path>`, or open "
            f"the ticket anyway with `constat ticket add {reference} "
            "--even-if-absent`."
        )

    unreadable = [f for f in findings if f.error is not None]
    coverage = f"searched {len(findings)} repository(ies)"
    if unreadable:
        coverage += (
            f", of which {len(unreadable)} could not be read "
            f"({', '.join(f.repository.alias for f in unreadable)}) — so this "
            "is not a statement that the reference is absent from those"
        )
    raise ReferenceMatchedNothing(
        f"reference {reference!r} matched no commits: {coverage}. No ticket "
        "was opened: a reference that matches nothing is more often a typo "
        "than a ticket, and an empty ticket cannot be opened again. Open one "
        f"deliberately with `constat ticket add {reference} --even-if-absent` "
        "if it should exist anyway."
    )


def gather(
    workspace: Workspace,
    reference: str,
    limits: ExcerptLimits = DEFAULT_LIMITS,
    provider: Provider | None = None,
    accept_scan_findings: bool = False,
    open_if_absent: bool = False,
) -> OperationResult:
    """Run the gathering operation for a ticket and expand its document.

    The provider is resolved **before** any repository is read, so a
    misconfiguration fails immediately rather than after the expensive part.
    With none configured this is the null provider and nothing leaves the
    machine.

    The payload is scanned for credentials on every run, and refused if any are
    found *and* a provider would actually receive it (CON-45). Scanning always
    but refusing only at the point of transmission keeps two things true at
    once: a false positive cannot block a local run that sends nothing, and the
    scanner is not dead code until a provider exists.

    `accept_scan_findings` overrides the refusal for this run only. It is
    recorded in the document and as an operation, because an override nobody
    can see afterwards is indistinguishable from no scan at all.

    `open_if_absent` opens the ticket when the reference is unknown but the
    repositories recognise it (D-063). The search has to run first for that
    decision to be possible, which is why the ticket guard moved out of
    `collect`. Off by default: the CLI keeps its refusal, because a person who
    mistypes a reference should be told rather than handed a new ticket.
    """
    if provider is None:
        provider = resolve_provider()

    opening = open_if_absent and TicketStore(workspace).find(reference) is None
    findings = collect(workspace, reference, limits, require_ticket=not opening)
    if opening:
        # After the search and before anything is written. Every later step
        # needs the document to exist, and none of them has run yet.
        _open_for_reference(workspace, reference, findings)

    # Redaction happens on the real path rather than only where a provider
    # exists. A privacy boundary first exercised by the code that needs it is
    # a boundary first tested in production.
    payload = redact(
        reference,
        findings,
        known_rules(workspace),
        pending_readings(workspace, reference),
    )

    sends_payload = provider.name != NULL_PROVIDER_NAME
    if sends_payload:
        # Refused before `interpret`, and before the document is written. A
        # partially updated document would be worse than none: it would record
        # evidence as if the run had succeeded.
        scan_findings = guard_release(payload, accepted=accept_scan_findings)
    else:
        # Nothing is transmitted, so nothing is refused — but the scan still
        # runs and is still reported (D-044).
        scan_findings = scan(payload)

    accepted = bool(scan_findings) and sends_payload and accept_scan_findings
    now = utc_now()
    scan_section = describe_scan(
        payload,
        scan_findings,
        sent=sends_payload,
        accepted=accepted,
        accepted_at=now if accepted else None,
    )

    interpretation = provider.interpret(payload, mainline_files(workspace))

    # A workspace that reads through an agent has no provider *by design*, so
    # the null provider's "no AI provider is configured" would report a fault
    # to someone whose setup is correct (D-060). Scoped to the note, because
    # everything else about the run is identical.
    if not interpretation.ran and Settings(workspace).reader == READER_MCP:
        interpretation = replace(interpretation, note=MCP_READER_NOTE)

    document_id = _document_id(workspace, reference)
    run_id = open_run(workspace, reference, "gather_evidence")
    record_run_evidence(workspace, run_id, findings)

    # Stored *before* the document is rendered, so the body shows the queue a
    # reviewer actually faces — including what this run just proposed. Storing
    # afterwards left the queue a run behind: a reader saw "1 rule proposed"
    # and an empty queue in the same document.
    #
    # Still a separate write from the body, because a reading has to survive
    # the next regeneration of the prose it appears in (D-048). Rendering it is
    # display; this is the record.
    proposals = RuleProposals(workspace)
    for proposal in interpretation.proposals:
        proposals.record(
            run_id=run_id,
            proposal=proposal,
            provider=interpretation.provider,
            model=interpretation.model,
            model_attested=interpretation.model_attested,
            revises_rule_id=proposal.revises_rule_id,
        )

    view = catalogue_view(workspace, reference, findings)
    body = render(
        reference,
        findings,
        interpretation,
        scan_section,
        view,
        requirements=Requirements(workspace).for_ticket(reference),
    )

    with workspace.transaction() as ws:
        ws.execute(
            "UPDATE document SET body = ?, updated_at = ? WHERE id = ?",
            (body, now, document_id),
        )
        if accepted:
            # Recorded against the document rather than a repository: the
            # decision was about the payload as a whole. The locations are kept
            # so the override stays auditable; the matched text never is.
            ws.execute(
                "INSERT INTO operation "
                "(document_id, run_id, repository_id, kind, ran_at, summary, payload) "
                "VALUES (?, ?, NULL, 'scan_override', ?, ?, ?)",
                (
                    document_id,
                    run_id,
                    now,
                    f"accepted {len(scan_findings)} credential-scan finding(s)",
                    "\n".join(f.describe() for f in scan_findings),
                ),
            )
        for finding in findings:
            repository_id = ws.execute(
                "SELECT id FROM repository WHERE alias = ?",
                (finding.repository.alias,),
            ).fetchone()["id"]
            ws.execute(
                "INSERT INTO operation "
                "(document_id, run_id, repository_id, kind, ran_at, summary) "
                "VALUES (?, ?, ?, 'gather_evidence', ?, ?)",
                (
                    document_id,
                    run_id,
                    repository_id,
                    now,
                    f"{finding.status.value}: {len(finding.commits)} commit(s)",
                ),
            )

    return OperationResult(
        reference=reference,
        findings=findings,
        body=body,
        interpretation=interpretation,
        scan_findings=scan_findings,
        scan_accepted=accepted,
        run_id=run_id,
        ticket_opened=opening,
    )


@dataclass(frozen=True)
class PublishResult:
    """What a publication did, including what it was allowed to carry."""

    ref: PublishedRef
    run_id: int | None
    """The run this publication was recorded against, or `None` for the state
    page, which belongs to no ticket and so records no operation (CON-106)."""
    scan_findings: tuple[DocumentFinding, ...] = ()
    scan_accepted: bool = False


def render_review(workspace: Workspace, reference: str) -> str:
    """A ticket's page: the proposals awaiting a verdict, and nothing else.

    **Not the stored document, and that is the change** (CON-114). The
    document is the technical view — files changed, diffs, which repository
    contributed what — and it stays at the terminal, where `document --show`
    prints it and `rule show` reaches the evidence a rule rests on.

    Publishing it did two things wrong at once. It put paths in a repository
    whose other pages carry none (D-117 separated them; this removes the
    reason to). And it looked like an archive without being one: the page is
    rewritten on every run, and once the ticket lands it regenerates with no
    diffs at all, because a landed ticket contributes no evidence (D-031).
    The durable record is the `run_commit` pointer in the workspace (CON-79).

    What a reviewer needs in order to decide is the statement, the id to write
    a verdict against, and who read it. That is this page.
    """
    proposals = RuleProposals(workspace)
    queue = proposals.undecided(reference)
    decided = tuple(
        item for item in proposals.for_ticket(reference) if item.decision
    )

    lines = [f"# {reference}", ""]

    if queue:
        lines += [
            f"**{len(queue)} rule proposal(s) await a decision.** None carries "
            "any authority until accepted (D-036, D-037).",
            "",
        ]
        for item in queue:
            lines.append(f"- `#{item.id}` **{item.proposal.name}**")
            previous = (
                getattr(
                    Catalogue(workspace).by_id(item.revises_rule_id),
                    "statement",
                    None,
                )
                if item.revises_rule_id is not None
                else None
            )
            if previous is None:
                lines.append(f"  {item.proposal.statement}")
            else:
                # Both statements, because "is this a change and is the change
                # right" is the reviewer's whole question (CON-120).
                lines.append(f"  **was** — {previous}")
                lines.append(f"  **now** — {item.proposal.statement}")
            lines.append(f"  Read by {item.attribution}.")
        lines += [
            "",
            "To decide, write one line per proposal in the `decisions/` file "
            "beside this page, using the `#N` above:",
            "",
            "    1: approved",
            "    2: rejected — the limit is per account, not per customer",
            "",
            "Who decided is taken from your commit, so do not write your "
            "name.",
            "",
        ]
    else:
        lines += [
            "**Every proposal from this ticket is decided.** This page is a "
            "record of what was read and what became of it.",
            "",
        ]

    if decided:
        lines += ["## Decided", ""]
        for item in decided:
            lines.append(
                f"- `#{item.id}` **{item.proposal.name}** — {item.decision}"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "The evidence this reading rests on is not published. It is a pointer "
        "to a commit rather than a copy of a diff, held in the workspace where "
        "`constat rule show` and `constat document` reach it — a page of diffs "
        "would look like an archive and is not one, because it is rewritten on "
        "every run.",
        "",
        f"What the product does is on [the product as it stands]"
        f"({_page_link(STATE_REFERENCE, frm=reference)}); every page is in the "
        f"[index]({_page_link(INDEX_REFERENCE, frm=reference)}).",
        "",
    ]
    return "\n".join(lines)


def publish_document(
    workspace: Workspace,
    reference: str,
    target: Target | None = None,
    *,
    repository: str | None = None,
    accept_scan_findings: bool = False,
) -> PublishResult:
    """Publish a ticket's stored document to a documentation target (D-058).

    The one path in Constat that writes outside the workspace, and the only
    one reached by its own command. `gather` cannot publish and acceptance
    does not publish, because "it published when I did not expect it to" is
    not recoverable by apologising.

    **It publishes what is stored, and renders nothing.** The body comes from
    the `document` row, so what lands on the page is what `document --show`
    shows. Re-rendering here would let a published page differ from the one a
    reviewer was shown, and D-056 made the document a function of stored state
    precisely so those two cannot diverge.

    **The gate runs before the target is touched.** A refusal must leave
    nothing behind — no clone, no commit, no partial page — so the scan
    happens first and `PublicationRefused` is raised before anything is
    written.

    **The operation is recorded after the write succeeds.** An operation row
    for a publication that failed would claim a disclosure that never
    happened, which is worse than no record at all.
    """
    if reference.startswith(AREA_PREFIX):
        raise InvalidInput(
            f"{reference!r} starts with {AREA_PREFIX!r}, which is reserved "
            "for area pages (CON-111). `constat publish` writes those, one "
            "per area the catalogue holds."
        )

    if reference.startswith(RELEASE_PREFIX):
        raise InvalidInput(
            f"{reference!r} starts with {RELEASE_PREFIX!r}, which is reserved "
            "for release pages (CON-112). `constat publish` writes those, "
            "from the releases this workspace has declared."
        )

    if reference in (STATE_REFERENCE, INDEX_REFERENCE):
        # Reserved, because every page is named from a reference and a ticket
        # called this would silently overwrite a generated one (CON-106,
        # CON-110).
        what = (
            "the catalogue is published to"
            if reference == STATE_REFERENCE
            else "lists every other page"
        )
        raise InvalidInput(
            f"{reference!r} is the page that {what}, so a ticket cannot be "
            "published over it. `constat publish` writes both, with no "
            "reference."
        )

    # The review rendering, not the stored document (CON-114). The document
    # is the technical view and stays at the terminal.
    body = render_review(workspace, reference)

    # First, and before any target exists: a refusal has to leave the world
    # untouched (D-047, D-058).
    scan_findings = guard_publication(body, accepted=accept_scan_findings)

    if target is None:
        target = detect_target(repository, workspace)

    # The ids the reviewer has to write, so they do not have to be copied off
    # the page (CON-115). Strings, because a decision may also be written
    # against a rule citation and the file takes either.
    catalogue = Catalogue(workspace)
    awaiting = tuple(
        Awaiting(
            id=str(item.id),
            name=item.proposal.name,
            statement=item.proposal.statement,
            # What this would replace, when the proposal claims to revise a
            # rule. A claim rather than a key (D-050) — if the rule it names
            # is gone, the reviewer is shown no "before" rather than a
            # guessed one.
            previous=(
                getattr(catalogue.by_id(item.revises_rule_id), "statement", None)
                if item.revises_rule_id is not None
                else None
            ),
        )
        for item in RuleProposals(workspace).undecided(reference)
    )
    ref = target.publish(reference, body, awaiting)

    accepted = bool(scan_findings) and accept_scan_findings
    try:
        run_id = open_run(workspace, reference, "publish_document")
        document_id = _document_id(workspace, reference)
        with workspace.transaction() as ws:
            ws.execute(
                "INSERT INTO operation "
                "(document_id, run_id, repository_id, kind, ran_at, summary, payload) "
                "VALUES (?, ?, NULL, 'publish_document', ?, ?, ?)",
                (
                    document_id,
                    run_id,
                    utc_now(),
                    ref.describe(),
                    json.dumps(
                        {
                            "target": ref.target,
                            "location": ref.location,
                            "revision": ref.revision,
                            "characters": len(body),
                            "scan_findings": len(scan_findings),
                            "scan_accepted": accepted,
                        }
                    ),
                ),
            )
    except Exception as exc:  # noqa: BLE001 - the write already happened
        # The document is published. Nothing can un-publish it, so the one
        # thing this must not do is fail in a way that reads as "nothing left
        # the machine" — a user who believes that will not rotate a key or
        # delete a page. Found by a real failure: a missing import crashed
        # here *after* a successful push, and the traceback sat on top of a
        # page that was already live.
        raise PublishRecordFailed(
            f"the document WAS published to {ref.describe()}, but recording "
            f"the publication in the workspace failed: {exc}. The page is "
            "live; only Constat's own record of it is missing, so `ticket "
            "show` will not list this publication."
        ) from exc

    return PublishResult(
        ref=ref,
        run_id=run_id,
        scan_findings=scan_findings,
        scan_accepted=accepted,
    )


@dataclass(frozen=True)
class PublishedPage:
    """A page this workspace has published, and when it last did (CON-110)."""

    reference: str
    location: str
    published_at: str


def published_pages(
    workspace: Workspace, target: str | None = None
) -> tuple[PublishedPage, ...]:
    """Every ticket page this workspace has published, most recent first.

    **The first thing to read the publication record.** `publish_document` has
    written an `operation` row since D-058 and nothing has ever read one back,
    so "where has this document been published" was unanswerable — a gap this
    file has recorded since CON-57.

    `target` filters to one documentation target. Without it the index on one
    target listed pages published to another — a link into nothing, on a page
    that claims in its own last line to list only what was published (CON-119).
    The record has always held the target in its location; nothing read it.

    Only ticket pages. The catalogue page records no operation, by the
    narrowing D-110 stated: it belongs to no ticket and `operation.document_id`
    is `NOT NULL`. It is added to the index by the renderer instead, because
    the index is written at the moment it is published and therefore knows.
    """
    rows = workspace.execute(
        "SELECT t.reference AS reference, o.ran_at AS ran_at, o.payload AS payload "
        "FROM operation o "
        "JOIN document d ON d.id = o.document_id "
        "JOIN ticket t ON t.id = d.ticket_id "
        "WHERE o.kind = 'publish_document' "
        "ORDER BY o.ran_at DESC"
    ).fetchall()

    seen: dict[str, PublishedPage] = {}
    for row in rows:
        # Most recent first, so the first sighting of a reference is the one
        # that counts: a page republished ten times is one page.
        if row["reference"] in seen:
            continue
        location = ""
        if row["payload"]:
            location = json.loads(row["payload"]).get("location", "")
        if target is not None and not location.startswith(f"{target} ::"):
            continue
        seen[row["reference"]] = PublishedPage(
            reference=row["reference"],
            location=location,
            published_at=row["ran_at"],
        )
    return tuple(seen.values())


def area_page(name: str) -> str:
    """The reference an area is published under (CON-111)."""
    return f"{AREA_PREFIX}{name}"


def area_prefixes(areas: tuple[str, ...]) -> dict[str, str]:
    """A short letter prefix per area, derived and never stored (CON-118).

    Initials for a multi-word area, the first two letters for a single-word
    one, uppercased, letters only. Collisions are broken by lengthening the
    loser deterministically, so the mapping depends on the set of areas and
    on nothing else — two runs over the same catalogue agree.

    **Derived at render on purpose.** D-081 made the citation `R-7` flat
    because an area is mutable (D-079) and an identifier encoding a mutable
    fact becomes a false claim the moment that fact changes. That reasoning is
    unchanged, which is why this is a *label* and not a citation: `R-7` is
    still what the rule is called, still what `rule show` takes, still what
    survives the rule being re-filed. The prefix is a reading aid that is
    recomputed every time and is allowed to change.
    """
    def letters(area: str) -> str:
        words = [w for w in re.split(r"[^A-Za-z]+", area) if w]
        if not words:
            return "X"
        if len(words) == 1:
            return words[0][:2].upper()
        return "".join(w[0] for w in words).upper()

    taken: dict[str, str] = {}
    out: dict[str, str] = {}
    for area in areas:
        base = letters(area)
        candidate = base
        source = "".join(w for w in re.split(r"[^A-Za-z]+", area) if w).upper()
        extra = len(base)
        while candidate in taken and extra < len(source):
            # Lengthen from the area's own letters rather than appending a
            # number: a number beside a number reads as part of it.
            candidate = source[: extra + 1]
            extra += 1
        suffix = 2
        while candidate in taken:
            candidate = f"{base}{suffix}"
            suffix += 1
        taken[candidate] = area
        out[area] = candidate
    return out


def area_labels(state: ProductState) -> dict[str, str]:
    """`R-13` -> `AR-2`: the label a rule is shown under on its area page.

    Numbered within the area by citation order, so a rule keeps its number as
    long as the area's membership below it does not change. A rule with no
    area gets none — it is not in an area, and inventing a prefix for the
    absence of one would be the false claim D-081 names.
    """
    labels: dict[str, str] = {}
    prefixes = area_prefixes(tuple(state.by_area()))
    for area, states in state.by_area().items():
        if area == UNPLACED:
            continue
        for position, item in enumerate(states, start=1):
            if item.rule.ref:
                labels[item.rule.ref] = f"{prefixes[area]}-{position}"
    return labels


def render_rule(
    item: RuleState,
    *,
    frm: str | None = None,
    labels: dict[str, str] | None = None,
) -> list[str]:
    """One accepted rule, as the business half reads it (CON-116).

    The single place a rule becomes prose. It was two — `render_state` and
    `render_area` emitted the same citation, statement, read-from line and
    examples table — and only one of them was taught which directory it was
    writing from, so every "read from" on every area page resolved nowhere.
    That is the third value this afternoon derived in two places and drifted.

    Carries no file, class or method: this is the business explanation, and
    the evidence view is the review page it links to (D-115, D-118).
    """
    lines: list[str] = []
    label = (labels or {}).get(item.rule.ref or "")
    # The label leads because it is what a reader of this page sees around
    # them; the citation follows because it is what survives (D-081) and what
    # every command takes.
    if label:
        cite = f"`{label}` (`{item.rule.ref}`) "
    else:
        cite = f"`{item.rule.ref}` " if item.rule.ref else ""
    lines.append(f"- {cite}**{item.rule.name}** — {item.rule.statement}")

    if item.references:
        linked = ", ".join(
            f"[{reference}]({_page_link(reference, frm=frm)})"
            for reference in item.references
        )
        lines.append(f"  - read from {linked}")

    for message in item.rule.messages:
        cite = f"`{message.ref}` " if message.ref else ""
        lines.append(f"  - shows {cite}> {message.text}")

    if item.rule.examples:
        lines.append("")
        lines += [
            f"  {line}" if line else ""
            for line in example_table(item.rule.examples)
        ]
    else:
        # Said rather than left blank. A rule nobody can check is a gap in the
        # documentation, and a reader scanning for verifiable rules should see
        # which ones are not.
        lines.append(
            "  - no examples, so nothing here can be checked case by case"
        )
    return lines


def render_area(
    area: str,
    states: tuple[RuleState, ...],
    labels: dict[str, str] | None = None,
) -> str:
    """One area as a page (CON-111).

    The business explanation, narrowed to one part of the product, so a team
    can be sent a link to their own rules rather than to the whole catalogue.
    Carries no file, class or method, for the reason D-115 gave: this is the
    business half, and the evidence half is the ticket page each rule links
    to.
    """
    lines = [f"# {area}", ""]
    if not states:
        return "\n".join(lines + ["No rule is filed under this area.", ""])

    lines += [
        f"{len(states)} rule(s) a person has accepted. **Nothing on this page "
        "can be decided** — a rule awaiting a verdict is on its ticket's page.",
        "",
    ]
    for item in states:
        lines += render_rule(item, frm=area_page(area), labels=labels)
        lines.append("")

    lines += [
        "---",
        "",
        f"Every area is on [the product as it stands]"
        f"({_page_link(STATE_REFERENCE, frm=area_page(area))}); every page is "
        f"in the [index]({_page_link(INDEX_REFERENCE, frm=area_page(area))}).",
        "",
    ]
    return "\n".join(lines)


def render_emptied_area(area: str) -> str:
    """A page for an area that no longer holds a rule (CON-111).

    **Rewritten, never deleted or left as it was.** An area empties when the
    last rule filed under it is re-accepted elsewhere — there is no rename, so
    this is the only way it happens. Leaving the old page would serve rules
    that are no longer filed here to anyone holding the link, with nothing on
    the page saying so; deleting it would break the link instead. Saying what
    happened keeps the URL resolving and stops the page claiming to be
    current.
    """
    return "\n".join([
        f"# {area}",
        "",
        "**No rule is filed under this area any more.**",
        "",
        "Rules that were here have been re-filed elsewhere or retired. Nothing "
        "has been lost: every rule the catalogue has ever held is still in it, "
        f"on [the product as it stands]"
        f"({_page_link(STATE_REFERENCE, frm=area_page(area))}).",
        "",
        "This page is kept so a link to it still resolves. It is not current, "
        "and it is not a record of what the area used to contain — that is "
        "what `rule history` is for.",
        "",
        f"Every page is listed in the "
        f"[index]({_page_link(INDEX_REFERENCE, frm=area_page(area))}).",
        "",
    ])


RELEASE_PREFIX = "release-"
"""Reserved for release pages (CON-112).

A release name is free text, never interpreted (D-102), so a release page is
named by prefixing rather than by parsing. The prefix is reserved for the same
reason the two whole names are: every page is named from a reference, and a
ticket called `release-2026.11` would silently overwrite one.
"""


def release_page(name: str) -> str:
    """The reference a release is published under."""
    return f"{RELEASE_PREFIX}{name}"


def render_release(reading: ReleaseReading) -> str:
    """One release as a page (CON-112).

    The same three kinds of claim `release show` keeps apart (D-103), said on
    a page rather than at a terminal: `agreed` is a **fact**, `stood` is a
    **reconstruction** derived from it, and neither says the release shipped.
    A page is read by people who were not in the conversation, so the basis is
    printed rather than assumed.
    """
    release = reading.release
    lines = [
        f"# Release {release.name}",
        "",
        f"Declared by {release.declared_by} on {release.created_at[:10]}.",
        "",
        "## Agreed for this release",
        "",
    ]

    if not reading.agreed:
        lines += [
            "Nothing has been agreed for it yet. A rule version is attached to "
            "a release when it is accepted, with `rule accept <ID> --release "
            f"{release.name}`, and never afterwards — the version is frozen.",
            "",
        ]
    else:
        lines += [
            f"{len(reading.agreed)} rule version(s). This is a **fact**: "
            "somebody accepted each of these for this release.",
            "",
        ]
        for version in reading.agreed:
            cite = version.ref or f"rule {version.rule_id}"
            lines.append(
                f"- `{cite}` v{version.version_no} **{version.name}** — "
                f"{version.statement}"
            )
        lines.append("")

    if reading.is_reconstructable:
        lines += [
            "## The catalogue as it then stood",
            "",
            f"{len(reading.stood)} rule version(s), **reconstructed** rather "
            "than recorded: nothing was snapshotted at the time, so this is "
            "assembled from what had been accepted by then. Each says which "
            "release it was agreed for, because a rule untouched since an "
            "earlier one still stood then and reading it as part of this "
            "release would be wrong.",
            "",
        ]
        for version in reading.stood:
            cite = version.ref or f"rule {version.rule_id}"
            origin = (
                f"agreed for {version.agreed_for}"
                if version.agreed_for
                else "no release recorded"
            )
            lines.append(
                f"- `{cite}` v{version.version_no} **{version.name}** "
                f"— {origin}"
            )
        lines.append("")

    lines += [
        "## What this page does not say",
        "",
        "**It does not say this release shipped.** No ship is recorded "
        "anywhere in Constat, and a release name is never parsed for ordering "
        "— so \"what was in effect at release X\" has no answer here. What "
        "the product does *now* is verified against mainline, on "
        f"[the product as it stands]({_page_link(STATE_REFERENCE)}).",
        "",
        f"Every page is listed in the [index]({_page_link(INDEX_REFERENCE)}).",
        "",
    ]
    return "\n".join(lines)


def publish_areas(
    workspace: Workspace,
    target: Target | None = None,
    *,
    repository: str | None = None,
    accept_scan_findings: bool = False,
) -> tuple[PublishResult, ...]:
    """Publish a page per area, and tombstone the ones that emptied (CON-111).

    The target is asked what it already holds, because nothing in the
    workspace remembers an area that no longer exists: an area is free text
    frozen on an accepted version, so when the last rule moves away the area
    simply stops being in `Catalogue.areas()`.
    """
    state = product_state(workspace)
    grouped = state.by_area()
    labels = area_labels(state)

    if target is None:
        target = detect_target(repository, workspace)

    results = []
    current = set()
    for area, states in grouped.items():
        reference = area_page(area)
        # Compared as *page names*, never as references. An area is free text,
        # so "app install" is the reference `area-app install` and the file
        # `area-app-install.md` — comparing the two forms tombstoned every
        # area with a space in it the instant after writing it.
        current.add(_page_link(reference))
        body = render_area(area, states, labels)
        scan_findings = guard_publication(body, accepted=accept_scan_findings)
        ref = target.publish(reference, body)
        results.append(
            PublishResult(
                ref=ref,
                run_id=None,
                scan_findings=scan_findings,
                scan_accepted=bool(scan_findings) and accept_scan_findings,
            )
        )

    for stale in target.references_published(AREA_PREFIX):
        # Compared as resolved paths. The reference Constat wrote and the one
        # rebuilt from a filename differ whenever an area name needed
        # sanitising — `area-app install` against `area-app-install` — and
        # they resolve to the same page.
        if _page_link(stale) in current:
            continue
        # An area this target has a page for and the catalogue no longer
        # holds. Rewritten rather than deleted: the link keeps resolving and
        # the page stops claiming to be current.
        # The stem, not the area's name: sanitising is one-way, so the exact
        # name cannot be recovered from the filename and the page must not
        # pretend otherwise.
        body = render_emptied_area(stale[len(AREA_PREFIX):])
        # Scanned like every other egress, though it carries no evidence:
        # one gate on every exit is the property, not one gate where it
        # seemed likely to matter (D-047).
        scan_findings = guard_publication(body, accepted=accept_scan_findings)
        ref = target.publish(stale, body)
        results.append(
            PublishResult(ref=ref, run_id=None, scan_findings=scan_findings)
        )

    return tuple(results)


def publish_releases(
    workspace: Workspace,
    target: Target | None = None,
    *,
    repository: str | None = None,
    accept_scan_findings: bool = False,
) -> tuple[PublishResult, ...]:
    """Publish a page for every declared release (CON-112).

    All of them, every time, for the reason the catalogue is refreshed: a
    release page that lags is read as current. A workspace with no releases
    publishes nothing and that is not a failure — `release list` says in terms
    that no declared release is not a statement that nothing shipped.
    """
    releases = Releases(workspace).list()
    if not releases:
        return ()

    if target is None:
        target = detect_target(repository, workspace)

    results = []
    for release in releases:
        body = render_release(read_release(workspace, release.name))
        scan_findings = guard_publication(body, accepted=accept_scan_findings)
        ref = target.publish(release_page(release.name), body)
        results.append(
            PublishResult(
                ref=ref,
                run_id=None,
                scan_findings=scan_findings,
                scan_accepted=bool(scan_findings) and accept_scan_findings,
            )
        )
    return tuple(results)


def render_index(
    pages: tuple[PublishedPage, ...],
    releases: tuple[Release, ...] = (),
    areas: tuple[str, ...] = (),
) -> str:
    """The page that says what else is here (CON-110).

    Built from the publication record rather than from the ticket list, so it
    names pages that **have** been published rather than pages that could be.
    A ticket whose document nobody published is absent, which is the honest
    answer: there is no page to link to.
    """
    lines = [
        "# What is documented here",
        "",
        f"- [The product as it stands]({_page_link(STATE_REFERENCE)}) — every "
        "rule a person has accepted, by area. Nothing on it can be decided.",
        "",
    ]

    if areas:
        lines += [
            "## By area",
            "",
            "The same rules, split by the part of the product they describe.",
            "",
        ]
        for area in areas:
            lines.append(f"- [{area}]({_page_link(area_page(area))})")
        lines.append("")

    if releases:
        lines += [
            "## By release",
            "",
            "What was agreed for a named release, and how the catalogue then "
            "stood. Neither says the release shipped.",
            "",
        ]
        for release in releases:
            lines.append(
                f"- [{release.name}]({_page_link(release_page(release.name))})"
            )
        lines.append("")

    if not pages:
        lines += [
            "No ticket pages have been published from this workspace yet. "
            "`constat review <REF>` writes one, carrying that ticket's "
            "evidence and the proposals awaiting a decision.",
            "",
        ]
        return "\n".join(lines)

    lines += [
        "## By ticket",
        "",
        "One page per piece of work, carrying the readings taken from it and "
        f"nothing else, under `{REVIEWS_DIRECTORY}/`. **The evidence is not "
        "published** — it is a pointer to a commit held in the workspace, and "
        "a page of diffs would look like an archive without being one. A "
        "verdict is written in the `decisions/` file beside the page it "
        "belongs to.",
        "",
        "| Ticket | Last published |",
        "| --- | --- |",
    ]
    for page in pages:
        when = page.published_at[:10]
        lines.append(
            f"| [{page.reference}]({_page_link(page.reference)}) | {when} |"
        )
    lines += [
        "",
        f"{len(pages)} page(s). This index is written from Constat's own "
        "record of what it published, so a page removed from the target by "
        "hand is still listed here — and a page it never published is not, "
        "however much the work exists.",
        "",
    ]
    return "\n".join(lines)


def publish_index(
    workspace: Workspace,
    target: Target | None = None,
    *,
    repository: str | None = None,
    accept_scan_findings: bool = False,
) -> PublishResult:
    """Publish the index of pages (CON-110).

    Written whenever anything else is, for the same reason the catalogue is:
    an index that lags is worse than none, because it is read as complete.
    Records no operation, on D-110's narrowing — it belongs to no ticket.
    """
    # Resolved before the body is rendered, because the index lists the pages
    # published *to this target* and cannot know which that is otherwise
    # (CON-119).
    if target is None:
        target = detect_target(repository, workspace)

    body = render_index(
        published_pages(workspace, getattr(target, "url", None)),
        Releases(workspace).list(),
        tuple(product_state(workspace).by_area()),
    )
    scan_findings = guard_publication(body, accepted=accept_scan_findings)

    ref = target.publish(INDEX_REFERENCE, body)
    return PublishResult(
        ref=ref,
        run_id=None,
        scan_findings=scan_findings,
        scan_accepted=bool(scan_findings) and accept_scan_findings,
    )


def publish_state(
    workspace: Workspace,
    target: Target | None = None,
    *,
    repository: str | None = None,
    accept_scan_findings: bool = False,
) -> PublishResult:
    """Publish the catalogue itself, as `constat state` renders it (CON-106).

    **Why this exists.** A ticket document is an *impact* view: it answers
    which rules have anchors in what that ticket changed (D-035, D-038). For a
    landed ticket, or one opened for a baseline, the honest answer is "none" —
    so until now a workspace could hold an accepted catalogue that `publish`
    could not reach, and the audience the documentation is *for* had nowhere
    to read it. The document was never wrong; the catalogue simply had no
    publication.

    **Two page kinds, for product rule 8's two audiences.** This page is the
    business explanation and carries no evidence section; the ticket page is
    the technical evidence view and carries no catalogue. Conflating them was
    the thing that rule forbids.

    **Nothing on this page can be decided**, and it says so. It shows rules a
    person has already accepted, so there is no proposal here to approve — the
    approval loop (D-105, D-106) stays on ticket pages, where the proposals
    are.

    **No operation is recorded**, and that is a deliberate narrowing rather
    than an oversight. An `operation` row requires a document, and this page
    belongs to no ticket. The alternative was a schema change to make a
    publication documentless, which buys nothing today: the page is derived
    from accepted rule versions, and each of those already carries the
    decision that created it. What is lost is the ability to answer "when was
    the state page last published", and that is stated rather than hidden.
    """
    body = render_state(product_state(workspace)) + _STATE_PAGE_NOTE

    # Before any target exists, as in `publish_document`: a refusal has to
    # leave the world untouched (D-047, D-058).
    scan_findings = guard_publication(body, accepted=accept_scan_findings)

    if target is None:
        target = detect_target(repository, workspace)

    ref = target.publish(STATE_REFERENCE, body)
    return PublishResult(
        ref=ref,
        run_id=None,
        scan_findings=scan_findings,
        scan_accepted=bool(scan_findings) and accept_scan_findings,
    )


_STATE_PAGE_NOTE = """
---

Every rule above has been accepted by a person. **Nothing on this page can be
decided** — there is no proposal here to approve or reject. A rule awaiting a
decision appears on its ticket's page, which is where a verdict is written.

This page is rewritten in full each time it is published. Nothing written into
it survives, so write a decision where decisions are read instead.
"""


def detect_target(
    repository: str | None = None, workspace: Workspace | None = None
) -> Target:
    """The target to publish to: the configured one, else the remote's (CON-108).

    Three sources, in this order — `--target` on the command (handled by the
    caller, which passes a `Target` and never reaches here), then the
    workspace setting, then the repository's remote. Each is more specific
    than the next, and the command says which it used rather than leaving it
    to be inferred.

    **The remote stays the fallback**, so a workspace that has configured
    nothing still works on its first run. An unrecognised host still refuses
    rather than guessing (D-058): a configured target widens where you can
    publish, never how willing Constat is to guess.

    `repository` defaults to the working directory, which is what "the page
    tool of the current repository" means in practice: the document may span
    several registered repositories, so no one of them is the obvious anchor,
    while the repository someone is standing in is unambiguous.
    """
    if workspace is not None:
        configured = Settings(workspace).target
        if configured is not None:
            return GitPages(configured)
    return git_pages_detect(discover_repository(repository or "."))


# -- recording decisions read from a documentation target ---------------------


@dataclass(frozen=True)
class DecisionOutcome:
    """What became of one line a reviewer wrote.

    Every line gets one of these, including the ones nothing was done with. A
    refusal that is not reported is the failure mode this whole channel exists
    to avoid: a reviewer who approved a rule and was told nothing believes the
    approval is recorded (D-041).
    """

    line: DecisionLine
    outcome: str
    """`accepted`, `rejected`, `already` or `refused`."""

    detail: str | None = None
    """Why it was refused, or what already stood. None when it was recorded."""

    rule_id: int | None = None
    version_no: int | None = None

    @property
    def recorded(self) -> bool:
        return self.outcome in ("accepted", "rejected")

    def describe(self) -> str:
        said = f"{self.line.reference}: {self.line.verdict}"
        who = self.line.decided_by or "an unattributed line"
        if self.recorded:
            where = (
                f" — rule {self.rule_id} version {self.version_no}"
                if self.rule_id is not None
                else ""
            )
            return (
                f"{said} → recorded as {self.outcome}{where}  "
                f"[{who}, {self.line.verification}]"
            )
        return f"{said} → {self.outcome}: {self.detail}"


@dataclass(frozen=True)
class DecisionsRecorded:
    """What one pass over a target's decision file recorded, and what it did not."""

    read: DecisionsRead
    outcomes: tuple[DecisionOutcome, ...] = ()

    @property
    def recorded(self) -> tuple[DecisionOutcome, ...]:
        return tuple(o for o in self.outcomes if o.recorded)

    @property
    def already(self) -> tuple[DecisionOutcome, ...]:
        return tuple(o for o in self.outcomes if o.outcome == "already")

    @property
    def refused(self) -> tuple[DecisionOutcome, ...]:
        return tuple(o for o in self.outcomes if o.outcome == "refused")

    @property
    def unrecorded(self) -> bool:
        """Did a human decide something this pass could not record?

        Drives the exit code. An unreadable line counts: somebody wrote it
        meaning to decide, and Constat holds no decision for it.
        """
        return bool(self.refused or self.read.unreadable)


def record_read_decisions(
    workspace: Workspace,
    reference: str,
    target: Target | None = None,
    *,
    repository: str | None = None,
) -> DecisionsRecorded:
    """Record the decisions a reviewer wrote in the target (CON-58, D-106).

    **This is the amendment to D-055 arriving with its mechanism**, as D-089
    required. An approval made outside the CLI now counts as a human decision,
    and the distinction D-055 was protecting is untouched: what is forbidden is
    a *model* accepting, not a channel. Every decision here exists because a
    person committed a line to a repository — an act no agent performs by
    calling a tool, and there is still no acceptance tool on any MCP surface.

    **Identity is never taken from the text.** `decided_by` is the commit
    author `git blame` reports, recorded with `attribution='commit'`, and a
    line nothing can attribute is refused rather than credited to whoever ran
    the command. That is why this path takes no `--by`.

    **Idempotent on `(proposal, commit)`.** Reading the same target twice
    records nothing the second time; the database holds that constraint, and
    the lookup here only buys a readable report instead of an `IntegrityError`.
    A reviewer who rewrites a verdict in a *new* commit has made a new
    decision, which is reported rather than applied — a recorded decision is
    append-only, and overturning one is `rule retire`'s job, not a quiet
    second write.

    **One pass refuses per line, never in bulk.** A file with one bad line and
    four good ones records the four. Stopping at the first refusal would make a
    typo swallow decisions that were perfectly readable.
    """
    if target is None:
        target = detect_target(repository, workspace)

    read = target.read_decisions(reference)

    # Counted before anything is recorded: two lines for one proposal is an
    # ambiguity, and recording whichever came first would pick a verdict on a
    # reviewer's behalf. Both are refused and reported (product rule 1).
    mentions: dict[str, int] = {}
    for line in read.decisions:
        mentions[line.reference] = mentions.get(line.reference, 0) + 1

    proposals = RuleProposals(workspace)
    review = Review(workspace)
    outcomes: list[DecisionOutcome] = []

    for line in read.decisions:
        outcomes.append(
            _record_one_decision(proposals, review, reference, line, mentions)
        )

    return DecisionsRecorded(read=read, outcomes=tuple(outcomes))


def _refused(line: DecisionLine, detail: str) -> DecisionOutcome:
    return DecisionOutcome(line=line, outcome="refused", detail=detail)


def _record_one_decision(
    proposals: RuleProposals,
    review: Review,
    reference: str,
    line: DecisionLine,
    mentions: dict[str, int],
) -> DecisionOutcome:
    """Record one line, or say why not. Every branch here is a refusal a
    reviewer can act on, which is why each carries what to do about it."""
    if line.commit is None or not line.decided_by:
        return _refused(
            line,
            "git could not say who wrote this line, so there is no attested "
            "decider. Commit the line and read again",
        )

    if mentions.get(line.reference, 0) > 1:
        return _refused(
            line,
            f"{line.reference} is decided more than once in this file. Leave "
            "one line per rule proposal — picking one would choose a verdict "
            "for you",
        )

    if not line.reference.isdigit():
        # `R-7` cites a rule in the catalogue; a decision is taken on the
        # *proposal* that would become a version of it. Accepting `R-7` would
        # have to guess which pending reading was meant.
        return _refused(
            line,
            f"`{line.reference}` is a rule citation, not a rule proposal id. "
            "Decisions are written against the `#N` shown beside each rule in "
            "the review queue on the page",
        )

    proposal_id = int(line.reference)
    stored = proposals.find(proposal_id)
    if stored is None:
        return _refused(
            line,
            f"there is no rule proposal {proposal_id} in this workspace. "
            "Nothing is recorded under a guess at which one was meant",
        )

    if stored.reference != reference:
        # The decision file is per ticket. A line naming another ticket's
        # proposal is either a mistake or a reviewer reading the wrong page,
        # and recording it would decide something nobody was looking at.
        return _refused(
            line,
            f"rule proposal {proposal_id} belongs to ticket "
            f"{stored.reference}, not {reference}. Decide it on that ticket's "
            "page",
        )

    standing = proposals.decision_from(proposal_id, line.commit)
    if standing is not None:
        return DecisionOutcome(
            line=line,
            outcome="already",
            detail=(
                f"recorded as {standing['decision']} on "
                f"{standing['decided_at']} from this same commit"
            ),
        )

    if stored.is_decided:
        return _refused(
            line,
            f"rule proposal {proposal_id} is already {stored.decision} "
            f"({stored.decided_by_description}). A recorded decision is "
            "append-only — retire the rule rather than deciding it twice",
        )

    verdict = "accepted" if line.verdict == "approved" else "rejected"
    shared = {
        "decided_by": line.decided_by,
        "rationale": line.reason,
        "attribution": "commit",
        "channel": "git_pages",
        "verification": line.verification,
        "source_commit": line.commit,
        "source_line": line.line_no,
    }

    try:
        if verdict == "rejected":
            review.reject(proposal_id, **shared)
            return DecisionOutcome(line=line, outcome="rejected")
        acceptance = review.accept(proposal_id, **shared)
    except sqlite3.IntegrityError:
        # The unique index is the real enforcement, and it fires even if the
        # lookup above raced or was wrong. Reported as what it is rather than
        # as a crash.
        return DecisionOutcome(
            line=line,
            outcome="already",
            detail="already recorded from this commit",
        )

    return DecisionOutcome(
        line=line,
        outcome="accepted",
        rule_id=acceptance.rule_id,
        version_no=acceptance.version_no,
    )


# -- landing a ticket's work ---------------------------------------------------


@dataclass(frozen=True)
class Landing:
    """What accepting a rule proposal did to the registered repositories.

    Always a tuple of results, one per repository, even when only one of them
    knows the ticket. A ticket spans repositories (D-027) and "nothing to
    merge in the other two" is information a reviewer needs rather than noise
    to suppress: it is the difference between a one-repository change and a
    merge that silently reached only one of several.
    """

    reference: str
    results: tuple[MergeResult, ...]

    @property
    def landed(self) -> tuple[MergeResult, ...]:
        return tuple(r for r in self.results if r.landed)

    @property
    def refusals(self) -> tuple[MergeResult, ...]:
        return tuple(r for r in self.results if r.is_refusal)

    @property
    def changed_anything(self) -> bool:
        return bool(self.landed)


def land_ticket(workspace: Workspace, reference: str) -> Landing:
    """Merge the ticket's branch into mainline in every registered repository.

    Reached only when `merge_on_accept` is on (D-062). The caller checks the
    setting: this function does the work it is asked to do, and a function
    that silently did nothing because of a setting it read itself would be
    impossible to test honestly.

    The branch comes from `branches_naming` — the same branch-name attribution
    D-030 already uses to decide which commits belong to a ticket. Nothing is
    merged on the strength of a name a user typed into this command.
    """
    results: list[MergeResult] = []

    for entry in Registry(workspace).list():
        try:
            repo = discover_repository(entry.local_path)
        except RepositoryError as exc:
            # Unreadable is not "nothing to merge". A repository that cannot
            # be opened may well hold the ticket's branch, and reporting it as
            # a clean no-op would claim the ticket had landed everywhere.
            results.append(
                MergeResult(
                    repository_alias=entry.alias,
                    source_branch=None,
                    target_branch=entry.default_branch,
                    outcome="repository_unreadable",
                    detail=f"could not read {entry.source}: {exc}",
                )
            )
            continue

        results.append(
            merge_ticket_branch(
                repo,
                alias=entry.alias,
                branches=branches_naming(repo, reference),
                target_branch=entry.default_branch,
                reference=reference,
            )
        )

    return Landing(reference=reference, results=tuple(results))


# -- the current picture of the product ---------------------------------------


@dataclass(frozen=True)
class RepositoryState:
    """One repository as it stands, and how current that picture is.

    `revision` is the SHA the mainline ref resolved to when this was read.
    Pinned rather than implied: a picture of "now" that cannot say which commit
    it described is not inspectable (product rule 2), and two runs a day apart
    are different pictures.
    """

    alias: str
    mainline: MainlineRef | None
    revision: str | None
    fetched_at: datetime | None = None
    """When this repository's cache was last fetched, or None for a local path
    read in place (CON-38). A picture of "now" assembled from a stale cache is
    a picture of whenever that cache was fetched."""
    file_count: int = 0
    claimed_files: int = 0
    error: str | None = None

    @property
    def readable(self) -> bool:
        return self.error is None

    @property
    def claimed_share(self) -> float:
        """Files claimed by at least one rule, as a fraction.

        Reported because the honest headline of a young catalogue is how
        little of the product it describes. Two rules over a thousand files is
        a 0.2% picture, and a view that hid that would flatter itself (D-038).
        """
        return 0.0 if not self.file_count else self.claimed_files / self.file_count


@dataclass(frozen=True)
class ReleaseReading:
    """What can be said about a release, separated by how it is known (CON-87).

    Three fields and three different kinds of claim, kept apart on purpose:

    - `agreed` is a **fact** — the versions somebody accepted for this release.
    - `stood` is a **reconstruction** at `moment`, which is itself derived from
      `agreed`. Nothing was snapshotted at the time; that is what the ticket
      asked for and also what a reader must be told.
    - nothing here says the release **shipped**. That is not recorded (CON-86),
      and `constat state` is the view that verifies current behaviour against
      mainline (D-087).
    """

    release: Release
    agreed: tuple[VersionAtPoint, ...]
    moment: str | None
    stood: tuple[VersionAtPoint, ...]

    @property
    def is_reconstructable(self) -> bool:
        """False when no version has been agreed for this release.

        A release is declared before the work is decided, so this is ordinary
        rather than broken — and falling back to "now" would answer a different
        question with the confidence of this one.
        """
        return self.moment is not None


def read_release(workspace, name: str) -> ReleaseReading:
    """A release, what was agreed for it, and the catalogue as it then stood.

    The release is resolved first, so an unknown name refuses with the declared
    ones named rather than returning an empty reading that reads like "that
    release had no rules".
    """
    release = Releases(workspace).require(name)
    history = CatalogueHistory(workspace)
    moment = history.moment_of(release.name)
    return ReleaseReading(
        release=release,
        agreed=history.agreed_for(release.name),
        moment=moment,
        stood=() if moment is None else history.as_at(moment),
    )


def describe_release_basis(reading: ReleaseReading) -> tuple[str, ...]:
    """How the reconstruction was arrived at, in the reader's words.

    Printed with the answer rather than in a footnote. A reader who believes
    they are seeing a stored snapshot of a release boundary would be wrong
    twice over: nothing was stored, and there is no boundary — release names
    are not parsed, so no release precedes another (D-102).
    """
    if not reading.is_reconstructable:
        return (
            f"No rule version has been agreed for {reading.release.name!r}, so "
            "there is no point in time to reconstruct the catalogue at.",
            "",
            "A release is declared before the work is decided, so this is an "
            "ordinary state rather than a problem. It is not a statement that "
            "the release contained nothing.",
        )

    return (
        f"Reconstructed as the catalogue stood at {reading.moment}, which is "
        f"when the last of the {len(reading.agreed)} version(s) agreed for "
        f"{reading.release.name!r} was accepted.",
        "",
        "Nothing was snapshotted at the time — this is read back from the "
        "frozen versions, which is what makes it available at all. Release "
        "names are not parsed, so no release precedes another; the moment "
        "comes from when work was agreed, never from an ordering of names.",
        "",
        "It does not say the release shipped: that is not recorded. What the "
        "product does now is `constat state`, which verifies against mainline.",
    )


def _references_for(workspace: Workspace, catalogue: Catalogue, rule: Rule) -> tuple[str, ...]:
    """The tickets behind one rule, or nothing if it cannot be resolved.

    `Rule` carries no row id on purpose (CON-81), so the identifier has to be
    looked up — the same translation `rule history` needs.
    """
    rule_id = catalogue.identify(rule.ref or rule.name)
    if rule_id is None:
        return ()
    return Review(workspace).references_for(rule_id)


@dataclass(frozen=True)
class RuleState:
    """An accepted rule, and whether its anchors still exist in mainline."""

    rule: Rule
    matched: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Repository alias -> the paths in mainline its anchors match."""

    references: tuple[str, ...] = ()
    """The tickets whose readings became versions of this rule (CON-110).

    Carried so the catalogue can link a rule to the evidence behind it. Empty
    for a rule accepted before Constat kept the link, and the renderer says
    nothing rather than inventing a page that may not exist."""

    @property
    def holds(self) -> bool:
        return bool(self.matched)

    @property
    def matched_count(self) -> int:
        return sum(len(paths) for paths in self.matched.values())


@dataclass(frozen=True)
class ProductState:
    """Every accepted rule, measured against the current mainline of each
    registered repository (D-070).

    The product's business documentation, assembled rather than stored: this is
    computed on demand, so nothing here is frozen and nothing can drift from
    it. A stored baseline is what CON-15 needs and is deliberately not this.
    """

    repositories: tuple[RepositoryState, ...] = ()
    rules: tuple[RuleState, ...] = ()
    agreed: tuple[tuple[Rule, tuple[str, ...]], ...] = ()
    """(rule, the SHAs it rests on that mainline does not contain) — CON-96.

    **Accepted, and not yet the product's behaviour.** A rule accepted while
    its ticket was still unmerged describes work that has not shipped, and
    rendering it in the current picture is a false claim about the product
    (product rule 1) made by the one command whose purpose is to state the
    present.

    Verified rather than asserted: the check is whether the commits the rule
    was accepted on (D-073) are ancestors of the repository's mainline. That is
    a stronger claim than a release concept could make — D-085 notes a declared
    release's ship is asserted and unverifiable across a plural registered
    set."""
    unverifiable: tuple[Rule, ...] = ()
    """Rules whose shipping cannot be checked (CON-96).

    Three causes, none of which is "not shipped": no evidence pointer at all
    (accepted before schema 13, or a run that gathered none), or a pointer to a
    commit that no longer exists — a squash-merge or force-push destroys it,
    which is why D-073 keeps the subject beside the SHA.

    **Kept in the current picture and flagged**, never moved out of it. Moving
    them would assert they are *not* current behaviour, which is exactly as
    unsupported as asserting they are."""
    retired: tuple[tuple[Rule, str], ...] = ()
    """(rule, reason) for each retired rule (CON-83).

    Carried rather than dropped. A retired rule is out of the *current picture*
    by a human decision, and the picture says how many left and why — because
    "the product used to do this and deliberately stopped" is a fact a reader
    of business documentation needs, and silence would read as the rule never
    having existed."""
    areas: tuple[str, ...] = ()
    """Every declared business area (CON-88), including those with no rule yet.

    Carried on the state because it is the denominator coverage is measured
    against (CON-90): an area somebody declared and never documented is a
    stated gap, and counting only areas that already hold rules would make
    coverage always read 100%."""

    @property
    def holding(self) -> tuple[RuleState, ...]:
        return tuple(r for r in self.rules if r.holds)

    @property
    def unanchored(self) -> tuple[RuleState, ...]:
        """Rules whose anchors match nothing in mainline — retirement
        candidates, never retirements (D-070). A person decides, because
        nothing leaves the catalogue without a human decision (D-048)."""
        return tuple(r for r in self.rules if not r.holds)

    def by_area(self) -> dict[str, tuple[RuleState, ...]]:
        """Rules grouped by area, unplaced last.

        `(unplaced)` sorts to the end because it is a gap rather than a
        section: a reader scanning the documentation should meet the organised
        part first.
        """
        grouped: dict[str, list[RuleState]] = {}
        for state in self.holding:
            grouped.setdefault(state.rule.area or UNPLACED, []).append(state)
        order = sorted(grouped, key=lambda area: (area == UNPLACED, area))
        return {area: tuple(grouped[area]) for area in order}


UNPLACED = "(unplaced)"
"""What a rule with no area renders under. A heading rather than a silence, so
the gap is visible and someone can place it."""


def product_state(
    workspace: Workspace, aliases: tuple[str, ...] | None = None
) -> ProductState:
    """Read the current state of the product from mainline.

    Product-level by default (D-070): every registered repository, each pinned
    at its own mainline revision, because one ticket's work and one rule's
    anchors both cross repositories. `aliases` narrows the view without
    changing its shape.

    A repository that cannot be read is reported, not skipped. Its rules would
    otherwise silently look unanchored, which reads as "retire these" — the
    opposite of what an unreadable repository licenses anyone to conclude.
    """
    registry = Registry(workspace)
    entries = [
        entry
        for entry in registry.list()
        if aliases is None or entry.alias in aliases
    ]

    catalogue = Catalogue(workspace)
    retirements = catalogue.retirements()
    rules = [rule for rule in catalogue.list() if rule.ref not in retirements]
    retired = tuple(
        (rule, retirements[rule.ref])
        for rule in catalogue.list()
        if rule.ref in retirements
    )

    # ref -> the newest accepted version, for checking what each rule rests on.
    # The newest, because that is what the current picture renders: an earlier
    # version's evidence says nothing about whether today's statement shipped.
    newest = {
        row["ref"]: int(row["version_id"])
        for row in workspace.execute(
            "SELECT r.ref AS ref, v.id AS version_id FROM rule r "
            "JOIN rule_version v ON v.rule_id = r.id "
            "WHERE r.ref IS NOT NULL AND v.version_no = ("
            "  SELECT MAX(version_no) FROM rule_version WHERE rule_id = r.id)"
        ).fetchall()
    }
    readable_at: dict[str, tuple] = {}

    repositories: list[RepositoryState] = []
    matches: dict[str, dict[str, tuple[str, ...]]] = {rule.name: {} for rule in rules}

    for entry in entries:
        try:
            repo = discover_repository(entry.local_path)
            mainline = resolve_mainline(repo, entry.default_branch)
            revision = resolve_revision(repo, mainline.ref)
            state = summarise_state(repo, revision)
        except RepositoryError as exc:
            repositories.append(
                RepositoryState(
                    alias=entry.alias,
                    mainline=None,
                    revision=None,
                    error=str(exc),
                )
            )
            continue

        matching = catalogue.rules_matching(entry.alias, state.paths)
        for name, paths in matching.items():
            matches[name][entry.alias] = paths

        readable_at[entry.alias] = (repo, revision.sha)
        claimed = {path for paths in matching.values() for path in paths}
        repositories.append(
            RepositoryState(
                alias=entry.alias,
                mainline=mainline,
                revision=revision.sha,
                fetched_at=entry.last_fetched_at if entry.cache_path else None,
                file_count=state.file_count,
                claimed_files=len(claimed),
            )
        )

    in_picture, agreed, unverifiable = _partition_by_shipping(
        workspace, rules, newest, readable_at
    )

    return ProductState(
        repositories=tuple(repositories),
        rules=tuple(
            RuleState(
                rule=rule,
                matched=matches[rule.name],
                references=_references_for(workspace, catalogue, rule),
            )
            for rule in in_picture
        ),
        agreed=agreed,
        unverifiable=unverifiable,
        retired=retired,
        areas=catalogue.areas(),
    )


def _partition_by_shipping(
    workspace: Workspace,
    rules: list[Rule],
    newest: dict[str, int],
    readable_at: dict[str, tuple],
):
    """Split rules into in-effect, agreed-but-unshipped, and uncheckable (CON-96).

    The defect this fixes: a rule accepted while its ticket was unmerged
    rendered as the product's current behaviour. `rule accept` has no
    pending/landed guard and deliberately gets none — refusing the acceptance
    would stop a reviewer deciding about work they can see, which is the normal
    case. What is wrong is *presenting* it as shipped, so the fix is a state in
    the view rather than a gate on the decision.

    **A rule is in effect unless something says otherwise.** A commit that is
    present and not an ancestor of mainline is that something; a commit that
    cannot be found is not, and nor is an absent pointer. Both of those are
    reported as uncheckable and stay in the picture, because moving them out
    would assert they are not current behaviour — as unsupported as the claim
    being fixed.
    """
    # `in_picture` holds everything the current view renders: rules verified as
    # shipped *and* rules whose shipping cannot be checked. Only `agreed` is
    # excluded, because only there is there positive evidence that the work has
    # not landed. An earlier version of this excluded the uncheckable ones too
    # — contradicting the paragraph above, and caught by the tests.
    in_picture: list[Rule] = []
    agreed: list[tuple[Rule, tuple[str, ...]]] = []
    unverifiable: list[Rule] = []

    for rule in rules:
        version_id = newest.get(rule.ref) if rule.ref else None
        if version_id is None:
            in_picture.append(rule)
            unverifiable.append(rule)
            continue

        commits = evidence_for_version(workspace, version_id)
        if not commits:
            in_picture.append(rule)
            unverifiable.append(rule)
            continue

        unshipped: list[str] = []
        checked = False
        for commit in commits:
            target = readable_at.get(commit.repository_alias or "")
            if target is None:
                continue
            repo, revision = target

            # A merge introduces no change of its own — the work is in its
            # parents — and under a Git Flow-shaped workflow the same work is
            # merged twice: once onto the integration branch and once onto
            # mainline, as two commits with identical parents. The
            # integration one can never be an ancestor of mainline, so
            # checking it reported every such rule as unshipped forever while
            # its work was in mainline (D-121).
            #
            # Skipped rather than counted as shipped. If a rule's evidence is
            # *all* merges nothing is checked, and it falls through to
            # uncheckable below — which is the honest answer, not a verdict.
            if is_merge(repo, commit.sha):
                continue

            answer = contains_commit(repo, commit.sha, revision)
            if answer == "no":
                unshipped.append(commit.sha)
                checked = True
            elif answer == "yes":
                checked = True

        if unshipped:
            agreed.append((rule, tuple(unshipped)))
        elif checked:
            in_picture.append(rule)
        else:
            in_picture.append(rule)
            unverifiable.append(rule)

    return in_picture, tuple(agreed), tuple(unverifiable)


PLACEHOLDER = re.compile(
    r"<[^<>]{1,60}>|\{[^{}]{0,60}\}|%[sdfr]|%\([^)]{1,40}\)[sdfr]|\$\{?[A-Za-z_]\w*\}?"
)
"""The forms a product uses for a value it fills in at runtime.

Deliberately several, because a catalogue spans repositories and languages, and
a message's placeholder style belongs to whatever wrote it."""

MIN_FRAGMENT = 12
"""Shorter than this and a fragment stops being evidence.

"Refused" appears in every codebase; finding it proves nothing, and reporting
that as a verified message would be the confident-wrong answer this product
exists to avoid."""


def literal_fragment(text: str) -> str | None:
    """The longest part of a message that could be searched for literally.

    Two things make a stored message unsearchable as a whole, and both are
    normal rather than exceptional:

    **Placeholders.** `The following files have already been uploaded: <names>`
    exists in the code as a format string, so the full text appears nowhere.
    **Line breaks.** `git grep` is line-oriented (see `adapter.search_text`),
    so a needle spanning a newline matches nothing.

    So the message is cut at both, and the longest remaining run is the needle.
    Returns None when nothing long enough survives — a message that is almost
    entirely placeholder cannot be verified this way, and saying so is the
    honest answer.
    """
    pieces = [
        piece.strip()
        for line in text.splitlines()
        for piece in PLACEHOLDER.split(line)
    ]
    longest = max(pieces, key=len, default="")
    return longest if len(longest) >= MIN_FRAGMENT else None


@dataclass(frozen=True)
class MessageCheck:
    """Whether one stored message's wording is present in the product."""

    ref: str | None
    text: str
    fragment: str | None
    """The needle actually searched for — the longest literal run of the
    message. Reported because a reader has to know what was checked: a match
    on a fragment is evidence the wording exists, not proof the whole string
    does."""
    found_in: tuple[tuple[str, str], ...] = ()
    """(repository alias, path) for each place the fragment was found."""
    unreadable: tuple[str, ...] = ()
    """Repositories that could not be read, so silence about them means
    nothing."""

    @property
    def verified(self) -> bool:
        return bool(self.found_in)

    @property
    def checkable(self) -> bool:
        return self.fragment is not None


def verify_messages(workspace: Workspace) -> tuple[MessageCheck, ...]:
    """Check each stored message's wording against the product (CON-91).

    A stored message is otherwise a *claim*: Constat holds it because a reading
    said so. This is the strongest verification available without running
    anything — the text is either in the code or it is not.

    **Found nowhere is reported, never refused.** A message can be assembled
    from fragments, translated, held in a resource file, or built by a
    formatter this cannot see. Refusing a true message because the search was
    naive is the worse error, and D-064's posture for duplicates applies here
    unchanged: report, and let a person decide.
    """
    rows = workspace.execute(
        "SELECT ref, text FROM message ORDER BY id"
    ).fetchall()
    if not rows:
        return ()

    targets = []
    unreadable = []
    for entry in Registry(workspace).list():
        try:
            repo = discover_repository(entry.local_path)
            mainline = resolve_mainline(repo, entry.default_branch)
            targets.append((entry.alias, repo, resolve_revision(repo, mainline.ref)))
        except RepositoryError:
            unreadable.append(entry.alias)

    checks = []
    for row in rows:
        fragment = literal_fragment(row["text"])
        found: list[tuple[str, str]] = []
        if fragment is not None:
            for alias, repo, revision in targets:
                for path in search_text(repo, revision.sha, fragment):
                    found.append((alias, path))
        checks.append(
            MessageCheck(
                ref=row["ref"],
                text=row["text"],
                fragment=fragment,
                found_in=tuple(found),
                unreadable=tuple(unreadable),
            )
        )
    return tuple(checks)


def example_table(examples, heading: str = "Examples") -> list[str]:
    """A rule's worked cases as a Markdown table (CON-80).

    One function, because the ticket document and the product state both show
    examples and a reviewer comparing them must not be reading two formats.

    Returns `[]` when there are none, deliberately rather than an empty table
    with a "none" row: the callers say what an absence *means*, and they do not
    all mean the same thing. On a rule proposal it means the reading offered
    none; on a rule accepted before schema 14 it means examples did not exist
    yet. Neither means the rule has no cases.
    """
    rows = tuple(examples)
    if not rows:
        return []
    out = [f"{heading}:", "", "| Situation | Outcome |", "| --- | --- |"]
    for example in rows:
        out.append(f"| {_cell(example.situation)} | {_cell(example.outcome)} |")
    out.append("")
    return out


def _cell(text: str) -> str:
    """Make text safe inside a Markdown table cell.

    A pipe in a situation would split the row and silently move the rest of the
    sentence into a column that does not exist — a rendering bug that reads as
    Constat having dropped half the example.
    """
    return text.replace("|", "\\|").replace("\n", " ")


def _page_link(reference: str, *, frm: str | None = None) -> str:
    """The path a reference is published at, relative to the page linking to it.

    Derived the same way the target derives it, and deliberately duplicated
    rather than imported: `GitPages.page_for` sanitises a reference so it
    cannot become a path, and a renderer that guessed differently would emit
    links that resolve nowhere. Kept in step by a test that asserts the two
    agree.

    `frm` is the reference of the page doing the linking. It matters because a
    ticket page lives in `evidence/` (CON-113): a link from there to the root
    needs `../`, and one that forgot would resolve nowhere — the whole reason
    the two derivations are tested against each other.
    """
    def _safe(text: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]", "-", text).strip("-.") or "document"

    if reference.startswith(AREA_PREFIX):
        page = f"{AREAS_DIRECTORY}/{_safe(reference[len(AREA_PREFIX):])}.md"
    elif is_generated(reference):
        page = f"{_safe(reference)}.md"
    else:
        page = f"{REVIEWS_DIRECTORY}/{_safe(reference)}.md"

    # A page in a folder reaches the root through `../`. A link that forgot
    # which folder it was written from would resolve nowhere, which is the
    # whole reason the renderer and the target are tested against each other.
    nested = frm is not None and (
        frm.startswith(AREA_PREFIX) or not is_generated(frm)
    )
    return f"../{page}" if nested else page


def render_state(state: ProductState) -> str:
    """Render the current picture as Markdown.

    The same split the ticket document uses (product rule 8): what the product
    does, then what that rests on. Here the evidence half is which revision of
    which repository was read, and how much of it no rule describes.
    """
    lines: list[str] = ["# The product as it stands", ""]

    readable = [r for r in state.repositories if r.readable]
    if not state.repositories:
        return "\n".join(
            lines
            + [
                "No repositories are registered, so there is nothing to measure "
                "the catalogue against. This is not a statement that the product "
                "has no rules.",
                "",
            ]
        )

    lines += ["## Read from", ""]
    for repo in state.repositories:
        if not repo.readable:
            lines.append(f"- **{repo.alias}** — could not be read: {repo.error}")
            continue
        assert repo.mainline is not None and repo.revision is not None
        lines.append(
            f"- **{repo.alias}** at `{repo.mainline.ref}` "
            f"`{repo.revision[:12]}` — {repo.file_count} file(s), "
            f"{repo.claimed_files} claimed by a rule "
            f"({repo.claimed_share:.1%})"
        )
        if repo.mainline.is_stale:
            lines.append(
                f"  - this clone is {repo.mainline.behind} commit(s) behind "
                f"`{repo.mainline.ref}`, so the picture may be out of date"
            )
        if repo.mainline.has_unpushed:
            lines.append(
                f"  - {repo.mainline.ahead} local commit(s) are not on "
                f"`{repo.mainline.ref}` and are not described here"
            )
        if not repo.mainline.from_remote:
            lines.append(
                "  - no remote-tracking ref, so this is only as current as "
                "this clone"
            )
        if repo.fetched_at is not None:
            # A picture of "now" assembled from a cache fetched a week ago is a
            # picture of last week, and this view's whole claim is to be of the
            # revisions it names (CON-38).
            lines.append(
                f"  - read from a cache fetched {describe_age(repo.fetched_at)}; "
                "nothing refreshes it on its own"
            )
    lines.append("")

    if not state.rules and not state.retired and not state.agreed:
        lines += [
            "The catalogue holds no rules, so there is nothing to describe yet. "
            "A rule enters only as an accepted rule proposal (D-048).",
            "",
        ]
        return "\n".join(lines)

    if not state.rules:
        # Distinct from the sentence above, and the distinction matters: a
        # catalogue nobody has filled, one whose every rule a person retired,
        # and one whose every rule is agreed but unshipped are three different
        # claims about the product. Only the first is an empty catalogue.
        held = len(state.retired) + len(state.agreed)
        lines += [
            f"No rule currently describes the product, and the catalogue holds "
            f"{held} — retired or agreed but not yet shipped, listed below. "
            "This is not an empty catalogue.",
            "",
        ]

    grouped = state.by_area()
    if grouped:
        # An index of areas, not a listing of rules (CON-116). Every rule used
        # to appear here *and* on its area page, identically — one catalogue
        # rendered twice, which is how an area page came to carry a link that
        # resolved nowhere while the copy here was correct.
        lines += [
            "## Business rules, by area",
            "",
            f"{sum(len(v) for v in grouped.values())} rule(s) across "
            f"{len(grouped)} area(s). Each area has its own page.",
            "",
        ]
        for area, states in grouped.items():
            lines.append(
                f"- [{area}]({_page_link(area_page(area))}) — "
                f"{len(states)} rule(s)"
            )
        lines.append("")

    if state.agreed:
        lines += [
            "## Agreed, not yet shipped",
            "",
            f"{len(state.agreed)} rule(s) were accepted on work that is **not "
            "in mainline**. They are not above, because the picture above is "
            "what the product does and these describe what it will do. "
            "Verified rather than assumed: the commits each rule was accepted "
            "on are not ancestors of the repository's mainline.",
            "",
        ]
        for rule, unshipped in state.agreed:
            cite = f"`{rule.ref}` " if rule.ref else ""
            shown = ", ".join(sha[:12] for sha in unshipped[:3])
            more = "" if len(unshipped) <= 3 else f" and {len(unshipped) - 3} more"
            lines.append(f"- {cite}**{rule.name}** — {rule.statement}")
            lines.append(f"  - rests on {shown}{more}, not in mainline")
        lines.append("")

    if state.unverifiable:
        lines += [
            "## Shipping not checked",
            "",
            f"{len(state.unverifiable)} rule(s) above could not be checked "
            "against mainline: either no commit was recorded for them — "
            "accepted before Constat kept evidence pointers, or read from a "
            "ticket that contributed none — or the commit no longer exists, "
            "which a squash-merge or a force-push does. **They are left in the "
            "picture above**, because moving them out would assert they are "
            "not current behaviour, and that is exactly as unsupported as "
            "asserting they are.",
            "",
        ]
        for rule in state.unverifiable:
            cite = f"`{rule.ref}` " if rule.ref else ""
            lines.append(f"- {cite}**{rule.name}**")
        lines.append("")

    if state.retired:
        lines += [
            "## Retired",
            "",
            f"{len(state.retired)} rule(s) are retired: a person decided each "
            "no longer describes the product. They are out of the picture "
            "above and stay in the record, because \"the product used to do "
            "this and deliberately stopped\" is something a reader of business "
            "documentation needs to be able to find.",
            "",
        ]
        for rule, reason in state.retired:
            cite = f"`{rule.ref}` " if rule.ref else ""
            lines.append(f"- {cite}**{rule.name}** — retired: {reason}")
        lines.append("")

    if state.unanchored:
        lines += [
            "## Rules whose anchors are gone",
            "",
            f"{len(state.unanchored)} rule(s) are anchored to paths that no "
            "longer exist in mainline. **Retirement candidates, not "
            "retirements** — a rule leaves the picture only by a human "
            "decision (D-070), and an unreadable repository above would "
            "produce this symptom too.",
            "",
        ]
        for item in state.unanchored:
            area = item.rule.area or UNPLACED
            cite = f"`{item.rule.ref}` " if item.rule.ref else ""
            lines.append(
                f"- {cite}**{item.rule.name}** ({area}) — {item.rule.statement}"
            )
            anchors = ", ".join(f"`{a.path_glob}`" for a in item.rule.anchors)
            lines.append(f"  - anchored to {anchors or '(nothing)'}")
        lines.append("")

    claimed = sum(r.claimed_files for r in readable)
    total = sum(r.file_count for r in readable)
    documented = {s.rule.area for s in state.holding if s.rule.area}
    # An area whose only rules are agreed-but-unshipped is **not** an area
    # nobody has written a rule for, and rendering them alike said "an area
    # with no rule is an intention" about an area that had one. Found by the
    # demo on first run (CON-20), which is the sort of thing a document read
    # end to end shows and a unit test does not.
    pending_areas = {rule.area for rule, _ in state.agreed if rule.area}
    empty = tuple(
        a for a in state.areas if a not in documented and a not in pending_areas
    )
    waiting = tuple(
        a for a in state.areas if a not in documented and a in pending_areas
    )

    lines += ["## What this does not describe", ""]

    # Areas first, files second, and the order is the point (CON-90). Coverage
    # in files measures the catalogue against the code, which is the wrong
    # denominator for business documentation: a product can be fully described
    # by thirty rules over a thousand files, and "970 files are claimed by no
    # rule" would report that as a failure for ever. Areas are the denominator
    # a reader actually has an opinion about.
    if state.areas:
        lines.append(
            f"**{len(documented)} of {len(state.areas)} declared business "
            f"area(s) hold a rule.**"
        )
        if empty:
            named = ", ".join(f"*{a}*" for a in empty)
            lines.append("")
            lines.append(
                f"Declared and undocumented: {named}. An area with no rule is "
                "an intention, not documentation."
            )
        if waiting:
            named = ", ".join(f"*{a}*" for a in waiting)
            lines.append("")
            lines.append(
                f"Declared, with every rule agreed and not yet shipped: {named}. "
                "Not the same as undocumented — the work exists and has not "
                "landed."
            )
        lines.append("")
        lines.append(
            "This counts only areas somebody has named. Parts of the product "
            "nobody has declared are not counted here at all, and that is the "
            "larger gap: the catalogue cannot measure what it has never been "
            "told about."
        )
    else:
        lines.append(
            "No business areas are declared, so there is no structure to "
            "measure coverage against. This is not a statement that the "
            "product has none."
        )

    lines += [
        "",
        f"As a technical figure, {total - claimed} of {total} file(s) across "
        "the registered repositories are claimed by no rule. A low share is "
        "expected and is not itself a gap — most files implement no business "
        "rule of their own — but the catalogue only knows the rules it holds, "
        "so this is where it is incomplete rather than where nothing happens "
        "(D-038).",
        "",
    ]
    return "\n".join(lines)
