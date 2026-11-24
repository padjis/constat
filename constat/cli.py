"""Command-line entry point.

Thin by design: parse, validate, dispatch, render. No product logic lives here
(ARCHITECTURE.md section 2). Validation rules live in config.py; this module
only maps them onto argv and exit codes.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from . import __version__
from .git.adapter import configured_identity
from .errors import (
    AlreadyRegistered,
    InvalidInput,
    NotRegistered,
    ProviderError,
    ProviderRequired,
    PublishError,
    RepositoryError,
    WorkspaceError,
)
from .evidence import collect_evidence, describe_commit
from .models import Rule
from .store import OFF, ON, READER_MCP, READERS, SWITCH, Settings
from .store import (
    Areas,
    Catalogue,
    Checkpoints,
    Releases,
    Requirements,
    Review,
    Registry,
    RuleProposals,
    TicketStore,
    Workspace,
    database_path,
)
from .ai import MCP_READER_NOTE, NULL_PROVIDER_NAME, PROVIDER_ENV
from .ai import as_dict as payload_as_dict
from .ai import resolve as resolve_provider
from .operations import (
    baseline_area,
    describe_branching,
    describe_release_basis,
    detect_target,
    read_release,
    verify_messages,
    export_payload,
    gather,
    evidence_for_run,
    evidence_for_version,
    land_ticket,
    product_state,
    publish_document,
    publish_areas,
    publish_index,
    publish_releases,
    publish_state,
    record_read_decisions,
    render_state,
    submit_reply,
)
from .publish import GitPages
from .tickets import TicketStatus, find_ticket_commits
from .git import (
    compare_revisions,
    discover_repository,
    resolve_revision,
    summarise_state,
)

PROG = "constat"
DESCRIPTION = "Turn software changes into evidence-backed, human-approved knowledge."
EPILOGUE = (
    "Gathers a ticket's evidence across the registered repositories, renders a "
    "document from it, and keeps a catalogue of business rules. Rules are "
    "proposed by an AI reading of the evidence and accepted only by a person: "
    "set CONSTAT_AI_PROVIDER to have Constat do the reading itself, or submit "
    "one with `rule submit`. With no provider configured the evidence path "
    "still runs in full."
)

EXIT_OK = 0
EXIT_USAGE = 2  # argparse's own convention for a usage error; reused for bad input.
EXIT_REPOSITORY = 3  # the input was fine; the repository or revision was not.
EXIT_WORKSPACE = 4  # Constat's own stored state could not be opened or created.
EXIT_PROVIDER = 5  # the interpretation layer was misconfigured; nothing else was.
EXIT_PUBLISH = 6  # the document is fine; publishing it did not happen (D-058).
EXIT_MERGE = 7  # the acceptance is recorded and durable; the merge did not happen (D-062).
EXIT_DECISIONS = 8  # decisions were read; at least one could not be recorded (D-106).


def _describe_repository(repo) -> None:
    print(f"repository: {repo.root}")
    if repo.given != repo.root:
        # Git widens a subdirectory to its enclosing repository. Say so, rather
        # than letting the user believe only the subtree was read.
        print(f"  (given {repo.given}, which is inside this repository)")
    print(f"branch:     {repo.branch or '(detached HEAD)'}")


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser.

    Separated from main() so tests can inspect the parser without running it.
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=DESCRIPTION,
        epilog=EPILOGUE,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{PROG} {__version__}",
        help="show the version and exit",
    )

    parser.add_argument(
        "--workspace",
        metavar="PATH",
        help=(
            "workspace directory (default: $CONSTAT_HOME, else ~/.constat). "
            "The workspace in use is always reported, never assumed silently."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    rule = subparsers.add_parser(
        "rule",
        help="inspect the business rules in the catalogue",
        description=(
            "Inspect the rule catalogue. Read-only: a rule enters only as an "
            "accepted rule proposal and can never be removed (D-048). There is "
            "no human-authored path, and supersession replaces deletion."
        ),
    )
    rule_actions = rule.add_subparsers(dest="rule_action", metavar="ACTION")

    rule_actions.add_parser("list", help="list rules in the catalogue")

    rule_show = rule_actions.add_parser("show", help="show one rule")
    rule_show.add_argument("name", metavar="NAME")

    rule_submit = rule_actions.add_parser(
        "submit",
        help="turn a reply produced outside Constat into rule proposals",
        description=(
            "Parse a reply, check every anchor against the ticket's evidence, "
            "and store what survives as rule proposals awaiting a human "
            "decision. Nothing is accepted here: this fills the review queue "
            "and never writes to the catalogue."
        ),
    )
    rule_submit.add_argument("reference", metavar="REF")
    rule_submit.add_argument(
        "--from",
        dest="source",
        metavar="PATH",
        default="-",
        help="file to read the reply from (default: - for stdin)",
    )
    rule_submit.add_argument(
        "--provider",
        default="external",
        help=(
            "what produced the reply. Self-reported and unverified (D-045): "
            "recorded so a reviewer knows what to weigh, never as an observed "
            "fact."
        ),
    )
    rule_submit.add_argument(
        "--model", default=None, help="model name, also self-reported"
    )

    rule_accept = rule_actions.add_parser(
        "accept",
        help="accept a rule proposal, baselining a rule version",
        description=(
            "Accept one reading. This is the only way a rule enters or changes "
            "in the catalogue (D-048), and it is a human act — it baselines a "
            "frozen version that points back at the reading accepted."
        ),
    )
    rule_accept.add_argument("proposal_id", metavar="ID", type=int)
    rule_accept.add_argument(
        "--by", default=None, metavar="WHO", help='who is deciding. Omitted, it is taken from your git identity (user.name and user.email) and recorded as inferred rather than stated — neither is verified, and a reviewer is entitled to know which (D-061).'
    )
    rule_accept.add_argument("--rationale", default=None)
    rule_accept.add_argument(
        "--release",
        default=None,
        metavar="NAME",
        help=(
            "which declared release this version is agreed for. Optional — "
            "omitted, no release is recorded, which is not a claim that the "
            "version is unreleased. The name must already exist: "
            "`constat release declare` is the only place one comes from."
        ),
    )

    rule_reject = rule_actions.add_parser(
        "reject",
        help="reject a rule proposal as inconclusive",
        description=(
            "Reject one reading. Under D-036 this means inconclusive — another "
            "PR is expected — not that the rule is wrong. The catalogue is "
            "left untouched."
        ),
    )
    rule_reject.add_argument("proposal_id", metavar="ID", type=int)
    rule_reject.add_argument(
        "--by", default=None, metavar="WHO", help='who is deciding. Omitted, it is taken from your git identity (user.name and user.email) and recorded as inferred rather than stated — neither is verified, and a reviewer is entitled to know which (D-061).'
    )
    rule_reject.add_argument("--rationale", default=None)

    rule_retire = rule_actions.add_parser(
        "retire",
        help="record that a rule no longer describes the product",
        description=(
            "Retire a rule. A human decision in the same sense acceptance is: "
            "nothing retires a rule automatically, and a rule whose anchors "
            "have vanished is a candidate rather than a retirement (D-070). "
            "The rule, its versions, its citation and its evidence stay "
            "readable — this records a decision, it does not delete anything. "
            "It is final: if the behaviour comes back, accept a new rule."
        ),
    )
    rule_retire.add_argument(
        "rule",
        metavar="RULE",
        help="the rule's citation (R-7) or its name. A bare number is refused.",
    )
    rule_retire.add_argument(
        "--reason",
        required=True,
        metavar="WHY",
        help=(
            "why it no longer applies. Required: it is the only record of why "
            "the product stopped behaving this way, and a rule conditional on "
            "a business state that has lapsed cannot say so itself (D-071)."
        ),
    )
    rule_retire.add_argument(
        "--by", default=None, metavar="WHO",
        help="who is deciding. Taken from your git identity when omitted, and recorded as inferred rather than stated (D-061).",
    )

    rule_history = rule_actions.add_parser(
        "history", help="show every accepted version of a rule"
    )
    rule_history.add_argument(
        "rule",
        metavar="RULE",
        help="the rule's citation (R-7) or its name. A bare number is refused.",
    )

    rule_proposals = rule_actions.add_parser(
        "proposals",
        help="list the rule proposals awaiting a decision",
        description=(
            "With a reference, every reading for that ticket in full. With no "
            "reference, every reading in the workspace grouped by state — "
            'which is how "what is waiting?" gets asked without already '
            "knowing which tickets to name."
        ),
    )
    rule_proposals.add_argument(
        "reference",
        metavar="REF",
        nargs="?",
        default=None,
        help="a ticket reference. Omit it for the whole workspace.",
    )
    rule_proposals.add_argument(
        "--all",
        action="store_true",
        help="include rule proposals already decided (per-ticket view only)",
    )
    rule_proposals.add_argument(
        "--state",
        choices=("awaiting", "accepted", "rejected"),
        default=None,
        help=(
            "show only one state, in the workspace view. Omit for all three, "
            "grouped."
        ),
    )

    document = subparsers.add_parser(
        "document",
        help="gather evidence for a ticket across the registered repositories",
        description=(
            "Run the gathering operation for a ticket: resolve its commits in "
            "every registered repository, collect bounded evidence, and expand "
            "the ticket's document. The document is a draft and carries no "
            "authority until a human approves a version of it."
        ),
    )
    document.add_argument("reference", metavar="REF")
    document.add_argument(
        "--accept-scan-findings",
        action="store_true",
        help=(
            "send the evidence to the AI provider even though the credential "
            "scan found something. Recorded in the document as a human "
            "decision; applies to this run only."
        ),
    )
    document.add_argument(
        "--no-provider",
        action="store_true",
        help=(
            "do not have Constat read the evidence. **This is the flag to use "
            "with MCP**, where your agent does the reading. Without it, a "
            "command that would propose no rules because nothing is "
            "configured to read is refused rather than quietly reporting "
            "none (D-059)."
        ),
    )
    document.add_argument(
        "--show", action="store_true", help="print the document body"
    )
    document.add_argument(
        "--payload",
        action="store_true",
        help=(
            "print the redacted evidence payload as JSON, for a model outside "
            "Constat to read. Identity never crosses this boundary (D-040), "
            "and the credential scan refuses unconditionally here — unlike a "
            "local run, an export has left by the time it has printed."
        ),
    )

    review = subparsers.add_parser(
        "review",
        help="put a ticket's proposals where they are decided",
        description=(
            "Write the ticket's stored document to a documentation target, so "
            "the people who decide about a rule can read it where they work "
            "(CON-107). The page carries each rule proposal with its id, and "
            "`decisions/<REF>.md` beside it is where a reviewer writes a "
            "verdict. What lands is exactly what `document --show` prints — "
            "nothing is re-rendered here, and circulating a document approves "
            "nothing in it. The catalogue page is refreshed at the same time, "
            "so the record never lags behind what has been decided."
        ),
    )
    review.add_argument("reference", metavar="REF")
    review.add_argument(
        "--target",
        default=None,
        metavar="URL",
        help=(
            "the documentation repository to write to. Omit it to derive the "
            "target from the current repository's remote; an unrecognised host "
            "is refused rather than guessed at."
        ),
    )
    review.add_argument(
        "--repository",
        default=None,
        metavar="PATH",
        help="the repository whose remote names the target (default: the working directory)",
    )
    review.add_argument(
        "--read-decisions",
        action="store_true",
        help=(
            "read back the decisions a reviewer wrote in the target instead of "
            "writing anything. Reports them; records nothing. Works on any git "
            "repository — no forge API and no token."
        ),
    )
    review.add_argument(
        "--record-decisions",
        action="store_true",
        help=(
            "record what a reviewer wrote in the target against the "
            "catalogue, instead of writing a page. Who decided comes from the "
            "commit, so there is no --by here. Reading the same commit twice "
            "records nothing the second time."
        ),
    )
    review.add_argument(
        "--accept-scan-findings",
        action="store_true",
        help=(
            "write the page even though the credential scan found something "
            "in the document. Recorded as an operation. A published page "
            "cannot be recalled, so this is never the default."
        ),
    )

    publish = subparsers.add_parser(
        "publish",
        help="publish the catalogue as the record of what was agreed",
        description=(
            "Write the catalogue — what `constat state` renders — to a single "
            "page on the documentation target, so the people the "
            "documentation is for can read what the product does (D-110). It "
            "shows rules a person has already accepted, so nothing on it can "
            "be decided: a proposal awaiting a verdict is on its ticket's "
            "page, which `constat review <REF>` writes."
        ),
    )
    # Accepted only so the refusal can name `review`. Until CON-107 this
    # command took a reference, and argparse's "unrecognized arguments" tells
    # someone who learned the old form nothing about where it went — a
    # refusal that does not say what to do instead is a dead end.
    publish.add_argument("reference", metavar="REF", nargs="?", help=argparse.SUPPRESS)
    publish.add_argument(
        "--read-decisions", action="store_true", help=argparse.SUPPRESS
    )
    publish.add_argument(
        "--record-decisions", action="store_true", help=argparse.SUPPRESS
    )
    publish.add_argument(
        "--target",
        default=None,
        metavar="URL",
        help=(
            "the documentation repository to publish to. Omit it to derive the "
            "target from the current repository's remote; an unrecognised host "
            "is refused rather than guessed at."
        ),
    )
    publish.add_argument(
        "--repository",
        default=None,
        metavar="PATH",
        help="the repository whose remote names the target (default: the working directory)",
    )
    publish.add_argument(
        "--accept-scan-findings",
        action="store_true",
        help=(
            "publish even though the credential scan found something in the "
            "catalogue. A published page cannot be recalled, so this is never "
            "the default."
        ),
    )

    ticket = subparsers.add_parser(
        "ticket",
        help="manage tickets and their documents",
        description=(
            "A ticket owns exactly one living document. Constat expects a "
            "ticket's work to be already merged onto an integration or "
            "release branch, but not yet in mainline."
        ),
    )
    ticket_actions = ticket.add_subparsers(dest="ticket_action", metavar="ACTION")

    ticket_add = ticket_actions.add_parser("add", help="open a ticket")
    ticket_add.add_argument("reference", metavar="REF", help="e.g. 622, ABC-123")
    ticket_add.add_argument(
        "--even-if-absent",
        action="store_true",
        help=(
            "open it although no registered repository mentions the "
            "reference. For work that has not started, or is tracked somewhere "
            "Constat cannot see. Without this a reference nothing recognises "
            "is refused, because a typo becomes a permanent empty ticket the "
            "workspace then refuses to open again (D-063)."
        ),
    )
    ticket_add.add_argument(
        "--accept-scan-findings",
        action="store_true",
        help=(
            "as on `document`: send the evidence despite credential-scan "
            "findings. `ticket add` gathers, so it can be refused too."
        ),
    )
    ticket_add.add_argument(
        "--no-provider",
        action="store_true",
        help=(
            "open the ticket and gather its evidence without having Constat "
            "read it. **Use this with MCP** — your agent reads the evidence, "
            "so Constat needs no provider. `ticket add` gathers, so it is "
            "refused without one for the same reason `document` is (D-059)."
        ),
    )

    ticket_actions.add_parser("list", help="list tickets")
    ticket_requirement = ticket_actions.add_parser(
        "requirement",
        help="record a requirement or issue this ticket answers",
        description=(
            "Supply a pointer to the requirement, issue or specification this "
            "work answers, so a reviewer reading a rule proposal can navigate "
            "to what it came from. Constat does not fetch it: nothing is read "
            "at the other end, nothing is parsed, and no check is made that "
            "the URI resolves. The record says a person supplied it, which is "
            "what `requirement_ref` has always meant — never that it was "
            "verified. A model cannot write one: a reference from a provider "
            "would be an interpretation wearing the label of external "
            "evidence."
        ),
    )
    ticket_requirement.add_argument("reference", metavar="REF")
    ticket_requirement.add_argument(
        "label",
        metavar="LABEL",
        help="how you cite it — `REQ-14`, `JIRA-882`, `spec § 3.2`. Stored verbatim.",
    )
    ticket_requirement.add_argument(
        "--uri",
        default=None,
        metavar="URI",
        help="where a reviewer can find it. Recorded, never followed.",
    )
    ticket_requirement.add_argument(
        "--by", default=None, metavar="WHO",
        help="who supplied it. Taken from your git identity when omitted (D-061).",
    )

    ticket_show = ticket_actions.add_parser(
        "show", help="show a ticket and where its work was found"
    )
    ticket_show.add_argument("reference", metavar="REF")

    repo = subparsers.add_parser(
        "repo",
        help="manage the registered repositories",
        description="Add, list and remove the repositories in the workspace.",
    )
    repo_actions = repo.add_subparsers(dest="repo_action", metavar="ACTION")

    repo_add = repo_actions.add_parser(
        "add", help="register a local repository"
    )
    repo_add.add_argument(
        "path",
        metavar="PATH_OR_URL",
        help=(
            "a path to a Git repository, or a remote URL to clone into the "
            "workspace cache. Anything that is neither an openable path nor a "
            "recognised remote form is refused rather than guessed at."
        ),
    )
    repo_add.add_argument(
        "--name", metavar="ALIAS", help="alias (default: the directory name)"
    )
    repo_add.add_argument(
        "--default-branch",
        metavar="BRANCH",
        help=(
            "the branch every comparison is measured against. Resolved from "
            "refs/remotes/origin/HEAD when not given; never guessed from "
            "whichever branch happens to be checked out."
        ),
    )

    repo_actions.add_parser("list", help="list registered repositories")

    repo_fetch = repo_actions.add_parser(
        "fetch",
        help="refresh a cached remote from its origin",
        description=(
            "Fetch a registered remote again and record when. A local path has "
            "nothing to fetch — it is read where it is — and asking is refused "
            "rather than silently succeeding, because a recorded fetch time "
            "would then be a claim about a copy that does not exist."
        ),
    )
    repo_fetch.add_argument("alias", metavar="ALIAS")

    repo_remove = repo_actions.add_parser(
        "remove", help="unregister a repository (the repository itself is untouched)"
    )
    repo_remove.add_argument("name", metavar="ALIAS")

    subparsers.add_parser(
        "mcp",
        help="run as an MCP server on stdio",
        description=(
            "Expose gathering, the payload, submission and the review queue to "
            "an MCP client over stdio. Acceptance is deliberately not exposed: "
            "a model that could accept would make 'no proposal becomes official "
            "without an explicit human decision' unenforceable. Nothing listens "
            "on a port."
        ),
    )

    init = subparsers.add_parser(
        "init",
        help="create a workspace",
        description=(
            "Create the workspace that holds registered repositories, tickets "
            "and the immutable record of approvals. Refuses to overwrite an "
            "existing workspace."
        ),
    )
    init.add_argument(
        "--reader",
        choices=sorted(READERS),
        default=None,
        help=(
            "who reads the evidence: `mcp` if an agent will, through the MCP "
            "server, or `provider` if Constat should call a model itself "
            "(default). Change it later with `config reader`."
        ),
    )

    config = subparsers.add_parser(
        "config",
        help="show or change how this workspace is operated",
        description=(
            "Settings belong to a setup rather than to a run. They say how "
            "this workspace is operated and never what anyone decided, so "
            "unlike decisions they can be changed."
        ),
    )
    config_actions = config.add_subparsers(dest="config_action")
    config_reader = config_actions.add_parser(
        "reader", help="show or set who reads the evidence"
    )
    config_reader.add_argument(
        "value", nargs="?", choices=sorted(READERS), default=None,
        help="omit to show the current value",
    )
    config_merge = config_actions.add_parser(
        "merge-on-accept",
        help="show or set whether accepting a rule proposal lands the branch",
        description=(
            "When on, accepting a rule proposal merges the ticket's branch "
            "into each registered repository's default branch and pushes it "
            "(D-062). Off by default: acceptance otherwise writes to the "
            "workspace and nothing else, and this is the one setting that "
            "makes it change a repository other people share."
        ),
    )
    config_merge.add_argument(
        "value", nargs="?", choices=sorted(SWITCH), default=None,
        help="omit to show the current value",
    )
    config_target = config_actions.add_parser(
        "target",
        help="show or set where documentation is published",
        description=(
            "The documentation repository `review` and `publish` write to "
            "(CON-108). Unset, the target is derived from the current "
            "repository's remote by the `.wiki.git` convention — which is "
            "fine for one repository and awkward for a catalogue spanning "
            "several, where no single remote is the obvious home. `--target` "
            "on a command still wins over this for a one-off."
        ),
    )
    config_target.add_argument(
        "value", nargs="?", default=None,
        metavar="URL",
        help="omit to show the current value",
    )
    config_target.add_argument(
        "--unset",
        action="store_true",
        help=(
            "forget the configured target, so it is derived from the "
            "repository's remote again"
        ),
    )

    state = subparsers.add_parser(
        "state",
        help="show the product as it stands on mainline",
        description=(
            "Render the accepted business rules against the current mainline "
            "of every registered repository, grouped by business area. This is "
            "the product's business documentation (D-070): the catalogue is "
            "the content, and this is the reading of it. Computed on demand "
            "and stored nowhere, so it is always of the revisions it names and "
            "never a baseline to drift from."
        ),
    )
    state.add_argument(
        "--repo",
        dest="aliases",
        metavar="ALIAS",
        action="append",
        default=None,
        help=(
            "narrow to one registered repository; repeatable. Omit for the "
            "whole product, which is the point of the view."
        ),
    )
    state.add_argument(
        "--json",
        action="store_true",
        help="emit the structured state instead of the rendered document",
    )

    baseline = subparsers.add_parser(
        "baseline",
        help="document an area as it behaves now, with no ticket",
        description=(
            "Store a reading that describes an area of the product as it "
            "already behaves, rather than what a ticket changed. Constat "
            "supplies no evidence here: there is no delta to read, so the "
            "reader works from the repository directly. What this does is "
            "ground every anchor against mainline, record which revision was "
            "described, and store the result as rule proposals awaiting a "
            "human decision. Nothing is accepted."
        ),
    )
    baseline.add_argument("area", metavar="AREA")
    baseline.add_argument(
        "--from",
        dest="source",
        metavar="PATH",
        default="-",
        help="file to read the reading from (default: - for stdin)",
    )
    baseline.add_argument(
        "--as",
        dest="reference",
        default=None,
        metavar="REF",
        help=(
            "the reference this baseline is recorded under. Use the ticket "
            "that occasioned it, which is how an undocumented area is normally "
            "found. With no ticket, supply one and it is opened — it will "
            "appear in `ticket list` without being a unit of work."
        ),
    )
    baseline.add_argument(
        "--provider",
        default="external",
        help="what produced the reading. Self-reported and unverified (D-045).",
    )
    baseline.add_argument("--model", default=None, help="model name, also self-reported")

    checkpoint = subparsers.add_parser(
        "checkpoint",
        help="freeze the catalogue's current state, or see what changed since",
        description=(
            "A checkpoint is the last state of the product somebody agreed to: "
            "which rules stood, at which versions, when it was taken. "
            "`constat state` is computed and stored nowhere, which is what "
            "makes it always current and also what leaves nothing to compare "
            "against — this is the other half. `changes` reports what the "
            "catalogue has done since."
        ),
    )
    checkpoint_actions = checkpoint.add_subparsers(
        dest="checkpoint_action", metavar="ACTION"
    )
    checkpoint_actions.add_parser("list", help="list the checkpoints taken")
    checkpoint_take = checkpoint_actions.add_parser(
        "take", help="freeze the catalogue as it stands now"
    )
    checkpoint_take.add_argument(
        "--label",
        required=True,
        metavar="TEXT",
        help=(
            "how a person will refer to this state — a date, a release, a "
            "meeting. Required: a checkpoint nobody can name is one nobody "
            "will compare against."
        ),
    )
    checkpoint_take.add_argument(
        "--by", default=None, metavar="WHO",
        help="who took it. Taken from your git identity when omitted (D-061).",
    )
    checkpoint_changes = checkpoint_actions.add_parser(
        "changes", help="what the catalogue has done since a checkpoint"
    )
    checkpoint_changes.add_argument(
        "ref", metavar="REF", nargs="?", default=None,
        help="which checkpoint (default: the most recent)",
    )
    checkpoint_changes.add_argument(
        "--all",
        action="store_true",
        help="include rules that have not changed",
    )

    release = subparsers.add_parser(
        "release",
        help="declare a release, or list the ones declared",
        description=(
            "A release is a name for a group of rule versions, declared by a "
            "person. Constat never derives one from tags: a tag is not "
            "evidence that anything was released (D-009 found 777 "
            "machine-generated ones in a single repository). The name is "
            "stored verbatim and never parsed, so there is no ordering and no "
            "'latest' — several releases may be open at once. Agreeing a rule "
            "version for a release does not decide what the product currently "
            "does; that is verified against mainline."
        ),
    )
    release_actions = release.add_subparsers(
        dest="release_action", metavar="ACTION"
    )
    release_declare = release_actions.add_parser(
        "declare", help="declare a release in this workspace"
    )
    release_declare.add_argument(
        "name",
        metavar="NAME",
        help="what you call it — stored exactly as given and never interpreted",
    )
    release_declare.add_argument(
        "--by", default=None, metavar="WHO",
        help="who declared it. Taken from your git identity when omitted (D-061).",
    )
    release_actions.add_parser("list", help="list the declared releases")
    release_show = release_actions.add_parser(
        "show",
        help="what was agreed for a release, and how the catalogue then stood",
        description=(
            "Two different claims, kept apart. What was *agreed* for this "
            "release is a fact: the versions somebody accepted for it. How the "
            "catalogue *stood* is a reconstruction, read back from the frozen "
            "versions at the moment the last of those was accepted — nothing "
            "was snapshotted at the time. Neither says the release shipped: "
            "that is not recorded, and `constat state` is the view that "
            "verifies current behaviour against mainline."
        ),
    )
    release_show.add_argument("name", metavar="NAME")
    release_show.add_argument(
        "--agreed-only",
        action="store_true",
        help="just the versions agreed for it, without the reconstruction",
    )

    message = subparsers.add_parser(
        "message",
        help="list the user-facing messages, or check them against the code",
        description=(
            "Messages are the exact text the product shows a user, stored once "
            "and cited (M-7). `verify` searches every registered repository at "
            "its mainline for each message's wording: a message found nowhere "
            "is reported, never refused, because text can be assembled, "
            "translated or held in a resource file this cannot see."
        ),
    )
    message_actions = message.add_subparsers(dest="message_action", metavar="ACTION")
    message_actions.add_parser("list", help="list every stored message")
    message_actions.add_parser(
        "verify", help="check each message's wording against the code"
    )

    area = subparsers.add_parser(
        "area",
        help="list or declare business areas",
        description=(
            "Business areas are the headings the catalogue is organised under. "
            "Most are declared by accepting a rule that carries one — that is "
            "what makes an area exist. This command lists them, and declares "
            "one ahead of its first rule, which is what documenting a new area "
            "needs."
        ),
    )
    area_actions = area.add_subparsers(dest="area_action", metavar="ACTION")
    area_actions.add_parser("list", help="list every declared area")
    area_add = area_actions.add_parser(
        "add", help="declare an area before it has a rule"
    )
    area_add.add_argument("name", metavar="NAME")
    area_add.add_argument(
        "--by",
        default=None,
        metavar="NAME",
        help=(
            "who is declaring it. Inferred from git config when omitted, and "
            "recorded as inferred rather than stated (D-061)."
        ),
    )

    return parser


def _run_init(args: argparse.Namespace) -> int:
    try:
        with Workspace.create(args.workspace) as workspace:
            path = workspace.path
            version = workspace.schema_version
            if args.reader is not None:
                Settings(workspace).set_reader(args.reader)
            reader = Settings(workspace).reader
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE

    print(f"workspace:  {path}")
    print(f"schema:     version {version}")
    print(f"reader:     {reader}")
    print()
    print("Created. It holds registered repositories, tickets and documents.")
    print("Register a repository with `repo add`, then open a ticket.")
    if reader != READER_MCP:
        print()
        print("Reading through an MCP agent rather than a provider?")
        print("Run `constat config reader mcp` once, and Constat will not")
        print("ask for a provider of its own.")
    return EXIT_OK


def _report_submission(result) -> int:
    """Report a submission: what was stored, and what was discarded.

    Discards are printed first. A reader shown only the kept count has been
    told a shorter truth than the one that happened (D-046).
    """
    if result.rejections:
        print(f"{len(result.rejections)} discarded as ungrounded or malformed:")
        for rejection in result.rejections:
            print(f"    {rejection.describe()}")

    print(f"{result.stored_count} rule proposal(s) stored, run {result.run_id}")

    if result.candidates:
        print()
        print(
            f"{result.possible_duplicates} claimed to be new but overlap "
            "existing rules:"
        )
        for proposal_id, rules in sorted(result.candidates.items()):
            named = ", ".join(str(r) for r in rules)
            print(f"    [{proposal_id}] anchors overlap rule(s) {named}")
        print("  Anchor overlap is a candidate, not a verdict — one file often")
        print("  implements several rules. Check before accepting a duplicate.")

    if result.pending_candidates:
        print()
        print(
            f"{result.possible_pending_duplicates} overlap a rule proposal "
            "nobody has decided yet:"
        )
        for proposal_id, others in sorted(result.pending_candidates.items()):
            named = ", ".join(str(o) for o in others)
            print(f"    [{proposal_id}] anchors overlap rule proposal(s) {named}")
        print("  Two readings of one ticket can say the same thing (CON-70).")
        print("  Collapse them before accepting either, or the catalogue gets")
        print("  one rule twice. `rule reject` records the other as")
        print("  inconclusive, which is what a duplicate is.")

    if result.new_areas:
        print()
        print(
            f"{len(result.new_areas)} rule proposal(s) name a business area "
            "the catalogue does not have:"
        )
        for proposal_id, (area, declared) in sorted(result.new_areas.items()):
            print(f"    [{proposal_id}] new area: {area!r}")
            if declared:
                known = ", ".join(repr(a) for a in declared)
                print(f"        the catalogue has {known}")
        print("  A new area is often right — the product grows. What it must not")
        print("  be is a synonym: nothing afterwards can tell 'ads' from")
        print("  'advertising', and merging two areas means renaming across")
        print("  frozen versions. Accepting the rule declares the area with it.")

    if result.stored_count:
        print()
        print("None of them is accepted. They await a human decision —")
        print("see them with `constat rule proposals <REF>`.")
    return EXIT_OK


def _report_workspace_queue(proposals, state: str | None) -> int:
    """Every reading in the workspace, grouped by state then ticket (CON-98).

    Compact on purpose: one line per reading. The per-ticket view answers "what
    does this say" and prints statements, examples and messages; this one
    answers "what is waiting", and a page of detail per proposal would bury the
    only number a reader came for.

    Awaiting comes first because it is the only state anybody can act on.
    """
    found = proposals.across_workspace(state)
    if not found:
        if state is not None:
            print(f"No rule proposals in state {state!r}.")
        else:
            print("No rule proposals in this workspace.")
            print()
            print("That is not a statement that the product has no rules —")
            print("nothing has read any ticket's evidence yet.")
        return EXIT_OK

    order = ("awaiting", "accepted", "rejected")
    grouped: dict[str, list] = {name: [] for name in order}
    for item in found:
        grouped[item.decision or "awaiting"].append(item)

    print(f"{len(found)} rule proposal(s) across the workspace:")
    for name in order:
        items = grouped[name]
        if not items:
            continue
        print()
        print(f"{name} ({len(items)}):")
        # Grouped by ticket within a state, because a reviewer works through
        # one ticket at a time and a flat list by id interleaves them.
        by_ticket: dict[str, list] = {}
        for item in items:
            by_ticket.setdefault(item.reference or "(unknown ticket)", []).append(item)
        for reference, readings in sorted(by_ticket.items()):
            print(f"  {reference}")
            for item in readings:
                area = item.proposal.area or "(unplaced)"
                origin = " · from a baseline" if item.from_baseline else ""
                print(f"    [{item.id}] {item.proposal.name} — {area}{origin}")

    if grouped["awaiting"]:
        print()
        print("Only the awaiting ones can be acted on. See one in full with")
        print("`constat rule proposals <REF>`, then `rule accept` or")
        print("`rule reject` — which is the only door to either (D-048).")
    return EXIT_OK


def _print_requirements(workspace, reference: str) -> None:
    """What this ticket cites, for a reviewer about to decide (CON-18).

    Printed with the rule proposals rather than only on `ticket show`, because
    this is the moment the question "what was this supposed to do?" is actually
    being asked — and the answer existing somewhere else is not the same as a
    reviewer seeing it.
    """
    supplied = Requirements(workspace).for_ticket(reference)
    if not supplied:
        return
    print(f"  supplied requirements ({len(supplied)}) — not verified:")
    for requirement in supplied:
        print(f"    {requirement.describe()}")
    print()


def _report_proposals(
    proposals, reference: str, include_decided: bool, evidence=None, workspace=None
) -> int:
    stored = (
        proposals.for_ticket(reference)
        if include_decided
        else proposals.undecided(reference)
    )
    if not stored:
        scope = "rule proposals" if include_decided else "undecided rule proposals"
        print(f"No {scope} for {reference}.")
        print()
        print("That is not a statement that this ticket has no rules —")
        print("nothing has read its evidence yet.")
        return EXIT_OK

    if workspace is not None:
        _print_requirements(workspace, reference)
    print(f"{len(stored)} rule proposal(s) for {reference}:")
    for item in stored:
        state = item.decision or "awaiting a decision"
        print(f"  [{item.id}] {item.proposal.name} — {state}")
        print(f"      {item.proposal.statement}")
        area = item.proposal.area or "(unplaced)"
        print(f"      area: {area} — read by {item.attribution}, run {item.run_id}")
        if item.from_baseline:
            # A reviewer's question differs (CON-89): a reading from a ticket
            # says "this change established a rule", a baseline says "this is
            # how it already behaves". Accepting them has the same effect;
            # deciding them does not.
            print("      from a baseline — describes existing behaviour, not a change")
        if item.proposal.messages:
            # The most checkable thing in the reading, so it is in the queue
            # rather than one command away: a reviewer may be unsure whether a
            # rule is right, and is never unsure whether the screen says this.
            print(f"      messages ({len(item.proposal.messages)}):")
            for message in item.proposal.messages:
                print(f"        - \"{message.text}\"")
        if item.proposal.examples:
            # In the queue, not only in `rule show`: the examples are what a
            # reviewer decides *on*, so a queue that hid them would be asking
            # for a decision while withholding the evidence for it.
            print(f"      examples ({len(item.proposal.examples)}):")
            for example in item.proposal.examples:
                print(f"        - {example.situation}  →  {example.outcome}")
        else:
            print("      no examples — this reading offers nothing to check")
        if evidence is not None:
            commits = evidence.get(item.run_id, ())
            if commits:
                shown = ", ".join(c.short_sha for c in commits[:3])
                more = "" if len(commits) <= 3 else f" and {len(commits) - 3} more"
                print(f"      read from {shown}{more}")
            else:
                # Said out loud: a reading whose run gathered nothing rests on
                # evidence this workspace cannot show (D-073).
                print("      read from no commits — this run gathered none")
        if item.decided_by_description is not None:
            print(f"      {item.decision} by {item.decided_by_description}")
        if item.claims_to_revise:
            print(f"      claims to revise rule {item.revises_rule_id}")
        weak = [
            a for a in item.proposal.anchors if a.grounded_in == "mainline"
        ]
        if weak:
            # Said explicitly: an anchor grounded only in mainline means this
            # ticket is not the evidence that the rule's home changed (D-072).
            globs = ", ".join(a.path_glob for a in weak)
            if item.from_baseline:
                # The ground stays visible (product rule 3), but without the
                # clause about a ticket's changes: a baseline has none, so the
                # wording would imply a deficiency where mainline is the only
                # ground there can be.
                print(f"      anchored in mainline: {globs}")
            else:
                print(
                    f"      anchored in mainline, not in this ticket's changes: {globs}"
                )
        if item.is_repair:
            # Said explicitly rather than left to the statement. A repair
            # accepted as though it were new business knowledge loses the only
            # thing that made it worth reporting: that the product already
            # believed this and the code was not honouring it (D-065).
            print("      claims to REPAIR a rule the code was violating")
            print("      — accepting it writes down knowledge the product")
            print("      already had, rather than adding something new")
    return EXIT_OK


def _print_diff(diff) -> None:
    """What this version changed against the one before it (CON-67).

    Silent on the first version: it has nothing to differ from, and printing
    "4 added" there would read as a change when it is the rule arriving.
    """
    if diff is None or diff.is_first:
        return

    for label, changes in (("behaviours", diff.behaviours), ("examples", diff.examples)):
        moved = [c for c in changes if c.status not in ("unchanged", "unnumbered")]
        unnumbered = [c for c in changes if c.status == "unnumbered"]
        if not moved and not unnumbered:
            continue
        print(f"      changes to {label} since the previous version:")
        for change in moved:
            where = f"[{change.number}] "
            if change.status == "changed":
                print(f"        {where}changed: {change.was}")
                print(f"        {' ' * len(where)}     now: {change.text}")
            else:
                print(f"        {where}{change.status}: {change.text}")
        if unnumbered:
            # Honest about what cannot be compared, rather than comparing it
            # anyway: these were accepted before details were numbered.
            print(
                f"        {len(unnumbered)} detail(s) are not numbered "
                "(accepted before Constat numbered them) and are not compared"
            )

    if diff.rewording_is_indistinguishable:
        print(
            "      note: a detail's identity is its text, so a reworded one "
            "reads here as"
        )
        print(
            "      one removed and one added rather than as an edit (D-078)."
        )


def _print_rule(rule) -> None:
    # The citation leads, because it is what a reader takes away and quotes
    # elsewhere (CON-81). None only for a workspace older than schema 17.
    cite = f"{rule.ref}  " if rule.ref else ""
    print(f"{cite}{rule.name}")
    print(f"  area:       {rule.area or '(unplaced)'}")
    print(f"  statement:  {rule.statement}")
    if rule.behaviours:
        print(f"  behaviours ({len(rule.behaviours)}):")
        for behaviour in rule.behaviours:
            print(f"    - {behaviour.description}")
    else:
        print("  behaviours: none declared yet")
    if rule.messages:
        print(f"  messages ({len(rule.messages)}):")
        for message in rule.messages:
            cite = f"{message.ref}  " if message.ref else ""
            # Quoted, so the boundaries of the text are visible: trailing
            # space and punctuation are part of what a user sees.
            print(f"    - {cite}\"{message.text}\"")
    if rule.examples:
        print(f"  examples ({len(rule.examples)}):")
        for example in rule.examples:
            print(f"    - {example.situation}  →  {example.outcome}")
    else:
        # Two states this cannot tell apart, so it claims neither: a rule
        # accepted before examples existed (schema 14), and one whose reading
        # proposed none. Saying "none proposed" would assert the second.
        print("  examples: none recorded — nothing here can be checked case by case")
    if rule.anchors:
        print(f"  anchors ({len(rule.anchors)}):")
        for anchor in rule.anchors:
            scope = anchor.repository_alias or "any repository"
            # `grounded_in` is None for anchors recorded before D-072, which
            # reads as "not recorded" rather than as either ground.
            ground = f", grounded in {anchor.grounded_in}" if anchor.grounded_in else ""
            print(f"    - {anchor.path_glob}  [{scope}{ground}]")
    else:
        print("  anchors: none — this rule can never be matched to a change")


def _run_rule(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.rule_action is None:
        parser.parse_args(["rule", "--help"])
        return EXIT_USAGE

    try:
        with Workspace.open(args.workspace) as workspace:
            catalogue = Catalogue(workspace)

            if args.rule_action == "list":
                rules = catalogue.list()
                if not rules:
                    print("No rules in the catalogue.")
                    print()
                    print("A rule enters only as an accepted rule proposal")
                    print("(D-048), and nothing generates one until a provider")
                    print("or host is wired up. Evidence is still collected; no")
                    print("rule impact is reported. That is not the same as")
                    print("nothing changing.")
                    return EXIT_OK
                print(f"{len(rules)} rule(s):")
                # Grouped by area (D-070): the catalogue is the product's
                # business documentation, and a documentation set with no
                # organisation is a list nobody reads. `(unplaced)` last,
                # because it is a gap rather than a section.
                by_area: dict[str, list] = {}
                for rule in rules:
                    by_area.setdefault(rule.area or "(unplaced)", []).append(rule)
                for area in sorted(by_area, key=lambda a: (a == "(unplaced)", a)):
                    print(f"  {area}:")
                    for rule in by_area[area]:
                        unanchored = "" if rule.anchors else "  (no anchors)"
                        cite = f"{rule.ref} " if rule.ref else ""
                        print(
                            f"    {cite}{rule.name}: {rule.statement}{unanchored}"
                        )
                return EXIT_OK

            if args.rule_action == "submit":
                text = (
                    sys.stdin.read()
                    if args.source == "-"
                    else Path(args.source).read_text()
                )
                result = submit_reply(
                    workspace,
                    args.reference,
                    text,
                    provider=args.provider,
                    model=args.model,
                )
                return _report_submission(result)

            if args.rule_action == "accept":
                decided_by, attribution = _decider(args)
                result = Review(workspace).accept(
                    args.proposal_id,
                    decided_by=decided_by,
                    rationale=args.rationale,
                    attribution=attribution,
                    release=args.release,
                )
                verb = "created" if result.created_rule else "revised"
                # The citation, not just the row id: this is the moment a
                # person learns what to call the rule they just accepted
                # (CON-81).
                accepted_rule = Catalogue(workspace).by_id(result.rule_id)
                cite = (
                    accepted_rule.ref
                    if accepted_rule is not None and accepted_rule.ref
                    else f"rule {result.rule_id}"
                )
                print(
                    f"accepted: {cite} {verb}, "
                    f"version {result.version_no} baselined"
                )
                if attribution == "inferred":
                    print(f"  recorded as: {decided_by} (inferred from git config)")
                if result.release is not None:
                    # Said plainly, because what it does *not* mean is easy to
                    # assume: agreeing a version for a release records an
                    # intention, and what the product currently does is still
                    # verified against mainline (D-087).
                    print(f"  agreed for release: {result.release}")
                    print("  (a record of intent — what is shipped is still")
                    print("   verified against mainline)")
                print()
                print("The version is frozen and points back at the reading")
                print("you accepted. See it with `constat rule history "
                      f"{result.rule_id}`.")

                if not Settings(workspace).merge_on_accept:
                    return EXIT_OK

                # Ordered deliberately: the acceptance is already committed
                # above, so a failed merge below reports a missing merge
                # rather than putting the decision in doubt (D-062).
                reference = RuleProposals(workspace).reference_of(args.proposal_id)
                if reference is None:
                    print()
                    print("merge_on_accept is on, but this rule proposal has no")
                    print("ticket to land. Nothing was merged.")
                    return EXIT_MERGE
                return _report_landing(land_ticket(workspace, reference))

            if args.rule_action == "reject":
                decided_by, attribution = _decider(args)
                Review(workspace).reject(
                    args.proposal_id,
                    decided_by=decided_by,
                    rationale=args.rationale,
                    attribution=attribution,
                )
                print(f"rejected: rule proposal {args.proposal_id}")
                if attribution == "inferred":
                    print(f"  recorded as: {decided_by} (inferred from git config)")
                print()
                print("Recorded as inconclusive, not as wrong (D-036). The")
                print("catalogue is unchanged and another reading is expected.")
                return EXIT_OK

            if args.rule_action == "retire":
                decided_by, attribution = _decider(args)
                _, target_id = _resolve_rule(Catalogue(workspace), args.rule)
                retired = Review(workspace).retire(
                    target_id,
                    reason=args.reason,
                    decided_by=decided_by,
                    attribution=attribution,
                )
                rule = Catalogue(workspace).by_id(retired.rule_id)
                cite = rule.ref if rule is not None and rule.ref else f"rule {retired.rule_id}"
                print(f"retired: {cite} — {retired.reason}")
                if attribution == "inferred":
                    print(f"  recorded as: {decided_by} (inferred from git config)")
                print()
                print("Out of `constat state` from now on, and still in the")
                print("record: nothing is deleted. A retirement is final — if")
                print("the behaviour returns, accept a new rule for it.")
                return EXIT_OK

            if args.rule_action == "history":
                review = Review(workspace)
                target, target_id = _resolve_rule(Catalogue(workspace), args.rule)
                cite = target.ref or target.name
                versions = review.versions(target_id)
                if not versions:
                    print(f"{cite} has no accepted versions.")
                    return EXIT_OK
                diffs = {d.version_no: d for d in review.diffs(target_id)}
                print(f"{len(versions)} version(s) of {cite}:")
                for v in versions:
                    who = v["decided_by"] or "(unknown)"
                    # The audit view is where this matters most: a name taken
                    # from git config and a name a person typed are both
                    # unverified, and only one of them was asserted (D-061).
                    if v["attribution"] == "inferred":
                        who += " (inferred from git config)"
                    print(f"  v{v['version_no']}  {v['name']}")
                    print(f"      {v['statement']}")
                    print(
                        f"      accepted by {who} from rule proposal "
                        f"{v['from_rule_proposal_id']}"
                    )
                    # On its own line, and only for the channel that has
                    # something behind the name. A decision committed in the
                    # documentation target rendered like a CLI string would
                    # hide the difference this record exists to keep (D-106).
                    if v.get("channel") == "git_pages":
                        print(
                            "      decided in the documentation target, "
                            f"{v['verification']}, commit "
                            f"{str(v['source_commit'] or '')[:12]}"
                        )
                    # Only when there is one. Printing "release: none" on
                    # every version of every rule in a workspace that declares
                    # no releases would read as a gap rather than as the
                    # ordinary case (CON-85).
                    if v.get("release_name"):
                        print(f"      agreed for release: {v['release_name']}")
                    # The question product rule 2 asks of a governance record:
                    # what evidence is this based on (D-073). A version from
                    # before schema 13 has no pointer, and says so rather than
                    # printing nothing.
                    if v["area"]:
                        print(f"      area: {v['area']}")
                    # From the version, not the rule (CON-61). The live tables
                    # are rewritten by each acceptance, so reading them here
                    # would show every historical version the newest one's
                    # substance — and it would look right.
                    if v["behaviours"]:
                        print(f"      behaviours ({len(v['behaviours'])}):")
                        for description in v["behaviours"]:
                            print(f"        - {description}")
                    else:
                        print("      behaviours: none recorded in this version")
                    if v["messages"]:
                        print(f"      messages ({len(v['messages'])}):")
                        for message in v["messages"]:
                            cite = f"{message.ref}  " if message.ref else ""
                            print(f"        - {cite}\"{message.text}\"")
                    if v["examples"]:
                        print(f"      examples ({len(v['examples'])}):")
                        for example in v["examples"]:
                            label = (
                                f"[{example.number}] "
                                if example.number is not None
                                else ""
                            )
                            print(
                                f"        - {label}{example.situation}  →  "
                                f"{example.outcome}"
                            )
                    else:
                        print("      examples: none recorded in this version")
                    if v["anchors"]:
                        print(f"      anchors ({len(v['anchors'])}):")
                        for anchor in v["anchors"]:
                            scope = anchor.repository_alias or "any repository"
                            ground = (
                                f", grounded in {anchor.grounded_in}"
                                if anchor.grounded_in
                                else ""
                            )
                            print(
                                f"        - {anchor.path_glob}  [{scope}{ground}]"
                            )
                    else:
                        print("      anchors: none recorded in this version")
                    commits = evidence_for_version(workspace, v["id"])
                    if commits:
                        print(f"      read from {len(commits)} commit(s):")
                        for commit in commits:
                            where = commit.repository_alias or "(unknown repository)"
                            print(
                                f"        {commit.short_sha} in {where} — "
                                f"{commit.subject}"
                            )
                    else:
                        # Two states that cannot be told apart from an empty
                        # pointer set: a version accepted before schema 13, and
                        # one whose run genuinely read nothing because the
                        # ticket had landed (D-031, D-072). Asserting either
                        # would be claiming more than is known.
                        print(
                            "      evidence: no commits recorded — this "
                            "reading's run gathered none, or it predates "
                            "evidence pointers"
                        )
                    # Last in the version's block: it is a statement about the
                    # whole version, so it reads as a summary rather than as
                    # another field among the substance.
                    _print_diff(diffs.get(int(v["version_no"])))
                return EXIT_OK

            if args.rule_action == "proposals":
                if args.reference is None:
                    return _report_workspace_queue(
                        RuleProposals(workspace), args.state
                    )
                stored_for_report = RuleProposals(workspace).for_ticket(
                    args.reference
                )
                return _report_proposals(
                    RuleProposals(workspace),
                    args.reference,
                    args.all,
                    evidence={
                        item.run_id: evidence_for_run(workspace, item.run_id)
                        for item in stored_for_report
                    },
                    workspace=workspace,
                )

            if args.rule_action == "show":
                rule = catalogue.find(args.name)
                if rule is None:
                    print(f"{PROG}: error: no rule {args.name!r}.", file=sys.stderr)
                    return EXIT_WORKSPACE
                _print_rule(rule)
                return EXIT_OK

    except InvalidInput as exc:
        # Reached when no --by was given and no identity could be inferred
        # (D-061). A usage error: the command was well-formed, but it is
        # missing the one thing a decision cannot be recorded without.
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except ProviderError as exc:
        # A reply that cannot be parsed is a provider fault, not a workspace
        # one, and must never read as "no rules were identified" (D-046).
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_PROVIDER
    except RepositoryError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_REPOSITORY
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE

    parser.error(f"unknown rule action: {args.rule_action}")
    return EXIT_USAGE  # pragma: no cover


def _run_export(args: argparse.Namespace) -> int:
    """Print the redacted payload for something outside Constat to read.

    Everything about this path assumes the output leaves: the credential gate
    is unconditional, and the warning goes to stderr so stdout stays a clean
    JSON document a pipe can consume.
    """
    try:
        with Workspace.open(args.workspace) as workspace:
            result = export_payload(
                workspace,
                args.reference,
                accept_scan_findings=args.accept_scan_findings,
            )
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE
    except ProviderError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_PROVIDER
    except RepositoryError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_REPOSITORY

    print(json.dumps(payload_as_dict(result.payload), indent=2, default=str))

    if result.accepted:
        print(
            f"{PROG}: warning: {len(result.scan_findings)} credential-scan "
            "finding(s) were accepted and are present in this payload; "
            "recorded in the document as a human decision",
            file=sys.stderr,
        )
    return EXIT_OK


def _print_scan(result) -> None:
    """Report the credential scan.

    The clean case is printed too. A scan that only speaks when it fails
    cannot be told apart from a scan that never ran.
    """
    findings = result.scan_findings
    if not findings:
        print("  credential scan: no findings (known formats only)")
        return

    print(f"  credential scan: {len(findings)} possible credential(s) found")
    for finding in findings:
        print(f"    {finding.describe()}")
    if result.scan_accepted:
        print("  accepted via --accept-scan-findings and recorded in the document")
    else:
        print("  nothing was sent — no AI provider is configured")


def _print_interpretation(interpretation) -> None:
    """Report the rules outcome of a run.

    Shared by `document` and `ticket add`, which both gather. A user who only
    ever runs `ticket add` would otherwise never be told that no rules were
    identified, and would reasonably read the silence as "there are none".
    """
    if interpretation is None:
        return

    if interpretation.rejections:
        # Printed before the kept count: a reviewer who sees only the kept
        # number has been told a shorter truth than the one that happened.
        print(
            f"  {len(interpretation.rejections)} proposal(s) discarded as "
            "ungrounded or malformed"
        )

    if interpretation.identified_rules:
        print(
            f"  {len(interpretation.proposals)} rule(s) proposed by "
            f"{interpretation.describe()} — proposals, not findings"
        )
    elif interpretation.ran:
        print(
            f"  no rules identified by {interpretation.describe()} — "
            "not a finding that none exist"
        )
    elif interpretation.note == MCP_READER_NOTE:
        # Follows the note `gather` set rather than deciding again. The summary
        # line and the document body said different things when each worked it
        # out for itself, and the line is what most people read.
        print("  no rules identified — this workspace reads through an agent")
        print("  (ask your agent to propose this ticket's rules; nothing is wrong)")
    else:
        print("  no rules identified — no AI provider is configured")
        print("  (that is a statement about configuration, not about the code)")


def _run_mcp(args: argparse.Namespace) -> int:
    try:
        from .mcp import serve
    except ImportError:
        print(
            f"{PROG}: error: the MCP server needs an optional dependency. "
            "Install it with `pip install constat[mcp]`.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    serve(args.workspace)
    return EXIT_OK


def _refuse_without_a_provider(
    args: argparse.Namespace, workspace: Workspace | None = None
) -> None:
    """Refuse a rule-generating command when nothing can read the evidence.

    D-059. `gather` itself still runs with no provider — the library keeps the
    guarantee D-003 asked for, and the MCP server depends on it, because there
    the *host* supplies the model and Constat is correct to have none.

    What changed is the command boundary. Someone running `constat document
    622` is asking for a document with rules in it; answering "no rules were
    identified, because none were looked for" is true and useless. The
    refusal names the three ways to proceed rather than only objecting.

    A misconfigured provider already raised before this existed
    (`UnknownProvider`, `ProviderNotConfigured`). This covers the one case that
    did not: nothing configured at all.
    """
    if getattr(args, "no_provider", False):
        return

    # A workspace that reads through MCP has no provider *by design*: the host
    # supplies the model (D-045). Asking it to say so on every ticket was the
    # flaw D-060 fixes — the question belongs to the setup, and the setup
    # answered it once.
    if workspace is not None and Settings(workspace).reader == READER_MCP:
        return

    provider = resolve_provider()  # raises for a misconfigured one
    if provider.name != NULL_PROVIDER_NAME:
        return

    raise ProviderRequired(
        f"{PROVIDER_ENV} is not set, so nothing would read this ticket's "
        "evidence and no rules would be proposed. Refusing rather than "
        "writing a document that says no rules were identified, which is "
        "true and not what you asked for.\n"
        "  - using MCP? run `constat config reader mcp` once and this stops "
        "asking: your agent does the reading, so Constat is right to have no "
        "provider of its own,\n"
        "  - or set CONSTAT_AI_PROVIDER=anthropic (with ANTHROPIC_API_KEY) "
        "to have Constat read it,\n"
        "  - or read it yourself: `document <REF> --no-provider --payload` "
        "then `rule submit`."
    )


def _resolve_rule(catalogue: Catalogue, token: str) -> tuple[Rule, int]:
    """A rule from its citation or its name, never from a bare number (CON-103).

    **A bare integer is refused rather than guessed at.** Two different objects
    are addressed by small integers in this CLI: `rule accept 1` means proposal
    1, and the row id of a rule is also an integer. They are unrelated, and the
    queue prints proposal ids while every document, page and `state` output
    prints the citation — so a reviewer reading `R-1` and typing `1` is the
    expected mistake, not an exotic one.

    Taking the number as a row id would be worse than useless here: `ref` is a
    stored column precisely because `R-{id}` is a trap (CON-81), so a citation
    and a row id may diverge after any table rebuild, and `rule` has been
    rebuilt once already. The two coincide today only because the migration
    back-filled them that way. A command that silently retires the wrong rule
    once they diverge is the failure this refusal exists to prevent.
    """
    if token.isdigit():
        raise InvalidInput(
            f"{token!r} is a number, and a rule is named by its citation or "
            f"its name — try `R-{token}` or the rule's name. Proposal ids are "
            "the numbers in `rule proposals`; they address a different thing, "
            "and a rule's row id is not citable (CON-81)."
        )
    rule = catalogue.find(token)
    rule_id = catalogue.identify(token)
    if rule is None or rule_id is None:
        raise WorkspaceError(
            f"no rule {token!r}. `constat rule list` shows every citation and "
            "name in the catalogue."
        )
    return rule, rule_id


def _decider(args: argparse.Namespace) -> tuple[str, str]:
    """Who is deciding, and how that name was obtained (D-061).

    `--by` wins. Without it, git's configured identity is used and recorded as
    `inferred`. Neither is verified — nothing here proves who ran the command —
    so this is not a trust level; it is the difference between a name a person
    asserted and a name a machine supplied.

    With no git identity it refuses rather than falling back to `$USER` or the
    OS login. Those name an account, not a person, and "who accepted this
    rule" is the last question to answer with a guess.
    """
    if args.by is not None:
        return args.by, "stated"

    inferred = configured_identity()
    if inferred is None:
        raise InvalidInput(
            "no --by was given and git has no configured identity to infer "
            "one from, so there is nothing to record as the decider. Pass "
            "--by, or set user.name and user.email in git. Refusing rather "
            "than recording an account name: a decision needs a person."
        )
    return inferred, "inferred"


def _run_baseline(args: argparse.Namespace) -> int:
    """Store a baseline reading of one area."""
    reference = args.reference or f"baseline-{args.area.strip().replace(' ', '-')}"
    text = (
        sys.stdin.read() if args.source == "-" else Path(args.source).read_text()
    )
    try:
        with Workspace.open(args.workspace) as workspace:
            result = baseline_area(
                workspace,
                area=args.area,
                reference=reference,
                text=text,
                provider=args.provider,
                model=args.model,
            )
    except (InvalidInput, ProviderError) as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE

    print(f"baseline of {result.area!r}, recorded under {result.reference!r}")
    if result.opened_ticket:
        # Said plainly: this is the cost C accepted, and a reference that is
        # not a unit of work should not appear in `ticket list` unannounced.
        print(
            f"  opened {result.reference!r} as a reference — it is not a "
            "unit of work, and will appear in `ticket list`"
        )
    print()
    print("Described the product at:")
    for alias, revision in result.read_from:
        if revision.startswith("unreadable:"):
            # Reported, never skipped: an unreadable repository means a rule
            # living there would be refused as ungrounded, and silence would
            # make that look like the rule being wrong (D-070).
            print(f"  {alias} — {revision}")
        else:
            print(f"  {alias} at {revision[:12]}")
    print()
    print("A baseline documents what already exists, so every anchor rests on")
    print("mainline rather than on a change (D-072). Nothing here is evidence")
    print("that anything changed, because nothing did.")
    print()
    if result.out_of_area:
        print(f"{len(result.out_of_area)} reading(s) were out of scope:")
        for rejection in result.out_of_area:
            print(f"    {rejection.describe()}")
        print()
    return _report_submission(result.submitted)


def _run_checkpoint(args: argparse.Namespace) -> int:
    """Take a checkpoint, list them, or report what changed since one."""
    try:
        with Workspace.open(args.workspace) as workspace:
            checkpoints = Checkpoints(workspace)

            if args.checkpoint_action == "take":
                taken_by, attribution = _decider(args)
                taken = checkpoints.take(args.label, taken_by, attribution)
                print(f"took {taken.ref}: {taken.label}")
                print(f"  {taken.rule_count} rule(s) frozen as the agreed state")
                if attribution == "inferred":
                    print(f"  recorded as: {taken_by} (inferred from git config)")
                print()
                print("Retired rules are not in it: a checkpoint records the")
                print("product as it stood, and a rule a person had taken out")
                print("of the picture was not part of it.")
                return EXIT_OK

            if args.checkpoint_action == "changes":
                checkpoint = checkpoints.require(args.ref)
                return _report_changes(
                    checkpoint, checkpoints.changes_since(checkpoint), args.all
                )

            found = checkpoints.list()
            if not found:
                print("No checkpoints taken.")
                print()
                print("Take one with `constat checkpoint take --label ...` to")
                print("have something to compare the catalogue against. Until")
                print("then `constat state` is the only picture, and it is")
                print("always of now.")
                return EXIT_OK
            print(f"{len(found)} checkpoint(s):")
            for item in found:
                print(f"  {item.ref}  {item.label}")
                print(
                    f"      {item.rule_count} rule(s), taken {item.taken_at} "
                    f"by {item.taken_by}"
                )
    except InvalidInput as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except NotRegistered as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE
    return EXIT_OK


def _report_changes(checkpoint, changes, include_unchanged: bool) -> int:
    """What the catalogue has done since a checkpoint."""
    moved = [c for c in changes if c.status != "unchanged"]
    unchanged = [c for c in changes if c.status == "unchanged"]

    print(f"Since {checkpoint.ref} ({checkpoint.label}), taken {checkpoint.taken_at}:")
    print()
    if not moved:
        print("  nothing has changed.")
    for change in moved:
        cite = change.ref or change.name
        if change.status == "added":
            print(f"  {cite}  added — {change.name} (version {change.to_version})")
        elif change.status == "retired":
            print(f"  {cite}  retired — {change.detail}")
        else:
            print(
                f"  {cite}  revised — version {change.from_version} "
                f"to {change.to_version}: {change.name}"
            )
    print()
    if include_unchanged and unchanged:
        print(f"{len(unchanged)} unchanged:")
        for change in unchanged:
            print(f"  {change.ref or change.name}  {change.name}")
        print()
    print(
        f"{len(moved)} changed, {len(unchanged)} unchanged. A revision says the "
        "rule has a"
    )
    print("new accepted version, not what the new version says — see")
    print("`constat rule history <RULE_ID>` for the detail of what moved.")
    return EXIT_OK


def _run_message(args: argparse.Namespace) -> int:
    """List the stored messages, or check their wording against the code."""
    try:
        with Workspace.open(args.workspace) as workspace:
            if args.message_action == "verify":
                return _report_message_checks(verify_messages(workspace))

            rows = workspace.execute(
                "SELECT m.ref, m.text, COUNT(rm.rule_id) AS rules "
                "FROM message m "
                "LEFT JOIN rule_message rm ON rm.message_id = m.id "
                "GROUP BY m.id ORDER BY m.id"
            ).fetchall()
            if not rows:
                print("No messages yet.")
                print()
                print("A message enters the catalogue with the rule that shows")
                print("it. Most rules show the user nothing, so this being")
                print("empty is not a gap by itself.")
                return EXIT_OK
            print(f"{len(rows)} message(s):")
            for row in rows:
                cite = row["ref"] or "(uncited)"
                print(f'  {cite}  "{row["text"]}"')
                print(f"      shown by {row['rules']} rule(s)")
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE
    return EXIT_OK


def _report_message_checks(checks) -> int:
    """Say which messages were found in the code, and what was searched for."""
    if not checks:
        print("No messages to check.")
        return EXIT_OK

    found = [c for c in checks if c.verified]
    missing = [c for c in checks if c.checkable and not c.verified]
    unverifiable = [c for c in checks if not c.checkable]

    print(f"{len(checks)} message(s) checked against mainline:")
    print()
    for check in checks:
        cite = check.ref or "(uncited)"
        if check.verified:
            where = ", ".join(f"{alias}:{path}" for alias, path in check.found_in[:3])
            more = "" if len(check.found_in) <= 3 else f" and {len(check.found_in) - 3} more"
            print(f'  {cite}  found — {where}{more}')
        elif check.checkable:
            print(f'  {cite}  NOT FOUND — searched for "{check.fragment}"')
        else:
            # A message that is almost entirely placeholder has no run long
            # enough to be evidence. Saying so beats searching for "Refused"
            # and calling the result a verification.
            print(f"  {cite}  cannot be checked — no literal text long enough to search for")
    print()
    print(
        f"{len(found)} found, {len(missing)} not found, "
        f"{len(unverifiable)} not checkable."
    )
    if missing or unverifiable:
        print()
        print("Not found is a finding, not a verdict. A message can be")
        print("assembled from fragments, translated, or held in a resource")
        print("file this search cannot reach — so this says where to look,")
        print("and a person decides whether the wording is wrong.")
    unreadable = checks[0].unreadable if checks else ()
    if unreadable:
        print()
        print(
            f"Could not read: {', '.join(unreadable)}. A message living there "
            "would read as not found."
        )
    return EXIT_OK


def _run_release(args: argparse.Namespace) -> int:
    """Declare a release, or list the ones declared."""
    try:
        with Workspace.open(args.workspace) as workspace:
            releases = Releases(workspace)

            if args.release_action == "declare":
                declared_by, attribution = _decider(args)
                declared = releases.declare(args.name, declared_by)
                print(f"declared: {declared.name}")
                if attribution == "inferred":
                    print(
                        f"  recorded as: {declared_by} (inferred from git config)"
                    )
                print()
                print("Stored exactly as given and never parsed — no ordering,")
                print("no 'latest'. Agree a rule version for it with")
                print("`constat rule accept <ID> --release "
                      f"{declared.name!r}`.")
                return EXIT_OK

            if args.release_action == "show":
                reading = read_release(workspace, args.name)
                print(f"release: {reading.release.name}")
                print(f"  declared by: {reading.release.declared_by}")
                print(f"  declared at: {reading.release.created_at}")
                print()

                print(f"Agreed for it ({len(reading.agreed)}):")
                if not reading.agreed:
                    print("  nothing yet")
                for version in reading.agreed:
                    cite = version.ref or f"rule {version.rule_id}"
                    print(f"  {cite}  v{version.version_no}  {version.name}")
                    print(f"      {version.statement}")
                print()

                if args.agreed_only:
                    print("Agreed is a fact; it does not say the release")
                    print("shipped. That is not recorded.")
                    return EXIT_OK

                if reading.is_reconstructable:
                    print(f"The catalogue as it then stood ({len(reading.stood)}):")
                    for version in reading.stood:
                        cite = version.ref or f"rule {version.rule_id}"
                        # Which release each version came from, because a rule
                        # untouched since an earlier one still stood then and
                        # reading it as part of *this* release would be wrong.
                        origin = (
                            f"agreed for {version.agreed_for}"
                            if version.agreed_for
                            else "no release recorded"
                        )
                        print(
                            f"  {cite}  v{version.version_no}  {version.name}"
                            f"  [{origin}]"
                        )
                    print()

                for line in describe_release_basis(reading):
                    if not line:
                        print()
                        continue
                    for wrapped in textwrap.wrap(line, width=72):
                        print(wrapped)
                return EXIT_OK

            declared_releases = releases.list()
            if not declared_releases:
                print("No releases declared in this workspace.")
                print()
                print("That is not a statement that nothing has been released.")
                print("Constat never derives a release from a tag, so a release")
                print("exists here only once somebody declares one.")
                return EXIT_OK

            print(f"{len(declared_releases)} release(s), oldest first:")
            for declared in declared_releases:
                agreed = workspace.execute(
                    "SELECT COUNT(*) AS n FROM rule_version WHERE release_id = ?",
                    (declared.id,),
                ).fetchone()["n"]
                print(f"  {declared.name}")
                print(f"    declared by:    {declared.declared_by}")
                print(f"    declared at:    {declared.created_at}")
                print(f"    rule versions:  {agreed} agreed for it")
            print()
            print("Ordered by when each was declared, because sorting the names")
            print("would mean interpreting them. Agreeing a version for a")
            print("release records an intention; what the product currently")
            print("does is verified against mainline (D-087).")
            return EXIT_OK
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE
    except InvalidInput as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_USAGE


def _run_area(args: argparse.Namespace) -> int:
    """List the declared areas, or declare one ahead of its first rule."""
    try:
        with Workspace.open(args.workspace) as workspace:
            catalogue = Catalogue(workspace)

            if args.area_action == "add":
                declared_by, attribution = _decider(args)
                area = Areas(workspace).declare(args.name, declared_by)
                print(f"declared: {area.name}")
                if attribution == "inferred":
                    print(
                        f"  recorded as: {declared_by} (inferred from git config)"
                    )
                print()
                print("Declaring an area does not document it. A rule enters an")
                print("area only as an accepted rule proposal (D-048).")
                return EXIT_OK

            areas = catalogue.areas()
            if not areas:
                print("No business areas yet.")
                print()
                print("An area exists once a rule carries it, so this is empty")
                print("until the first rule is accepted. It is not a statement")
                print("that the product has no structure.")
                return EXIT_OK

            # Which are only declared matters: an area with no rule is an
            # intention, and reading it beside documented ones as though they
            # were alike would overstate the catalogue.
            with_rules = {
                row["area"]
                for row in workspace.execute(
                    "SELECT DISTINCT area FROM rule WHERE area IS NOT NULL"
                ).fetchall()
            }
            print(f"{len(areas)} business area(s):")
            for name in areas:
                count = len(
                    [r for r in catalogue.list() if r.area == name]
                )
                if name in with_rules:
                    print(f"  {name} — {count} rule(s)")
                else:
                    print(f"  {name} — declared, no rules yet")
    except InvalidInput as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE
    return EXIT_OK


def _run_state(args: argparse.Namespace) -> int:
    """Render the product's current state, or say why it could not be read."""
    try:
        with Workspace.open(args.workspace) as workspace:
            aliases = tuple(args.aliases) if args.aliases else None
            if aliases is not None:
                known = {entry.alias for entry in Registry(workspace).list()}
                unknown = sorted(set(aliases) - known)
                if unknown:
                    # Refused rather than rendered as an empty picture: a
                    # mistyped alias would otherwise read as "this repository
                    # contributes nothing", which is a claim about the product.
                    print(
                        f"{PROG}: error: no registered repository named "
                        f"{', '.join(repr(a) for a in unknown)}. Known: "
                        f"{', '.join(sorted(known)) or '(none)'}.",
                        file=sys.stderr,
                    )
                    return EXIT_WORKSPACE
            state = product_state(workspace, aliases)
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE

    if args.json:
        print(
            json.dumps(
                {
                    "repositories": [
                        {
                            "alias": r.alias,
                            "mainline": None if r.mainline is None else r.mainline.ref,
                            "revision": r.revision,
                            "files": r.file_count,
                            "claimed_files": r.claimed_files,
                            "error": r.error,
                        }
                        for r in state.repositories
                    ],
                    "rules": [
                        {
                            "name": item.rule.name,
                            "area": item.rule.area,
                            "statement": item.rule.statement,
                            "holds": item.holds,
                            "matched": {a: list(p) for a, p in item.matched.items()},
                        }
                        for item in state.rules
                    ],
                },
                indent=2,
            )
        )
        return EXIT_OK

    print(render_state(state))
    return EXIT_OK


def _run_config(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """Show or change a workspace setting."""
    if args.config_action is None:
        parser.parse_args(["config", "--help"])
        return EXIT_USAGE

    try:
        with Workspace.open(args.workspace) as workspace:
            settings = Settings(workspace)
            if args.config_action == "merge-on-accept":
                return _run_config_merge(settings, args.value)
            if args.config_action == "target":
                return _run_config_target(settings, args)
            if args.value is None:
                print(f"reader: {settings.reader}")
                if settings.reader == READER_MCP:
                    print(
                        "  An agent reads the evidence through `constat mcp`. "
                        "No provider is needed and none is asked for."
                    )
                else:
                    print(
                        "  Constat reads the evidence itself. A rule-generating "
                        "command refuses without CONSTAT_AI_PROVIDER set."
                    )
                return EXIT_OK

            settings.set_reader(args.value)
            print(f"reader: {args.value}")
            if args.value == READER_MCP:
                print(
                    "\n`ticket add` and `document` will no longer ask for a "
                    "provider. Your agent does the reading; accept or reject "
                    "here, where no tool can."
                )
            else:
                print(
                    "\nSet CONSTAT_AI_PROVIDER (and its key) so Constat can "
                    "read the evidence itself."
                )
            return EXIT_OK
    except InvalidInput as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE


def _run_config_target(settings: Settings, args: argparse.Namespace) -> int:
    """Show, set or forget where documentation is published (CON-108)."""
    if args.unset and args.value is not None:
        print(
            f"{PROG}: error: --unset forgets the target; a URL sets one. "
            "Pick one.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    if args.unset:
        settings.unset_target()
        print("target: not set")
        print(
            "  Derived from the current repository's remote, by the "
            "`.wiki.git` convention. An unrecognised host refuses rather "
            "than guessing."
        )
        return EXIT_OK

    if args.value is None:
        configured = settings.target
        if configured is None:
            print("target: not set")
            print(
                "  Derived from the current repository's remote, by the "
                "`.wiki.git` convention. An unrecognised host refuses rather "
                "than guessing."
            )
        else:
            print(f"target: {configured}")
            print("  `--target` on a command still overrides this.")
        return EXIT_OK

    settings.set_target(args.value)
    print(f"target: {settings.target}")
    print(
        "  `review` and `publish` write here unless `--target` says "
        "otherwise. Nothing was published by setting it."
    )
    return EXIT_OK


def _run_config_merge(settings: Settings, value: str | None) -> int:
    """Show or set `merge_on_accept`.

    Turning it on prints what it will do in the imperative, not "enabled".
    Someone who reads "merge_on_accept: on" and nothing else has not been told
    that `rule accept` will start pushing to branches other people pull from.
    """
    if value is None:
        print(f"merge_on_accept: {ON if settings.merge_on_accept else OFF}")
        if settings.merge_on_accept:
            print(
                "  Accepting a rule proposal merges the ticket's branch into "
                "each registered repository's default branch and pushes it."
            )
        else:
            print(
                "  Accepting a rule proposal records the decision and "
                "baselines a rule version. No repository is written to."
            )
        return EXIT_OK

    settings.set_merge_on_accept(value)
    print(f"merge_on_accept: {value}")
    if value == ON:
        print()
        print("`rule accept` will now push a merge commit to the default")
        print("branch of every registered repository that has a branch naming")
        print("the ticket. It never merges inside the repository you")
        print("registered — the merge is made in a temporary clone and lands")
        print("by pushing — and it refuses on a conflict rather than resolving")
        print("one. The acceptance is recorded either way.")
    else:
        print()
        print("Accepting a rule proposal is back to writing nothing outside")
        print("the workspace.")
    return EXIT_OK


def _report_landing(landing) -> int:
    """Print what the merge did, and exit non-zero only for a refusal.

    `already_merged` and `no_branch` are reported and exit 0: a ticket whose
    work is in mainline, or which never had a branch, is a normal state and
    not a failure of the command the user ran.
    """
    print()
    print(f"landing {landing.reference}:")
    for result in landing.results:
        print(f"  {result.describe()}")

    refusals = landing.refusals
    if not refusals:
        return EXIT_OK

    print()
    print(f"{len(refusals)} repository(ies) did not merge. The acceptance is")
    print("recorded and the rule version is baselined — only the merge is")
    print("missing, and re-running it is safe once the cause is fixed.")
    return EXIT_MERGE


def _report_decisions(workspace, args, target) -> int:
    """Report what a reviewer wrote in the target (CON-58).

    **Reports, never records.** D-089 intends an off-CLI approval to count as a
    human decision and says the amendment to D-055 lands with the mechanism
    that enforces it — so until that mechanism exists this prints what it found
    and names the command that would act on it. A reader must not be able to
    mistake "Constat has seen your approval" for "your approval is recorded".
    """
    resolved = target or detect_target(args.repository, workspace)
    read = resolved.read_decisions(args.reference)

    print(f"decisions for {read.reference}")
    print(f"  from: {read.location}")
    print()

    if not read.present:
        print("There is no decision file in the target.")
        print()
        print("That is not 'nobody has decided' — it means this ticket's")
        print("document has never been published there, so nobody has had")
        print("anywhere to write. Run `constat publish` first.")
        return EXIT_OK

    if not read.decisions and not read.unreadable:
        print("The decision file is there and empty.")
        print()
        print("Nobody has written a decision yet. The file was seeded once")
        print("when the document was published and Constat never writes it")
        print("again, so this is the reviewer's silence rather than a gap.")
        return EXIT_OK

    if read.decisions:
        print(f"{len(read.decisions)} decision(s) read:")
        for decision in read.decisions:
            print(f"  {decision.describe()}")
            if decision.decided_at:
                print(f"      {decision.decided_at}  {decision.commit[:12]}")
        print()
        # Said plainly, because the gradient is the whole reason this channel
        # is worth having and the words are easy to skim past.
        print("How each identity is evidenced:")
        print("  signed_commit      git checked the signature and was satisfied")
        print("  signed_unverified  signed, and this machine cannot check it —")
        print("                     the allowed-signers file lives with the signer")
        print("  git_commit         unsigned; the author is attested by history")
        print()

    if read.unreadable:
        print(f"{len(read.unreadable)} line(s) could not be read:")
        for number, text in read.unreadable:
            print(f"  line {number}: {text}")
        print()
        print("Reported rather than guessed at. A reviewer who wrote something")
        print("Constat cannot read has made a decision it does not have, and")
        print("silence would leave them believing it was recorded.")
        print()

    print("Nothing here is recorded. Record it with `constat publish")
    print(f"{read.reference} --record-decisions`, or decide at the command")
    print("line with `constat rule accept <ID> --by <WHO>`.")
    return EXIT_OK


def _record_decisions(workspace, args, target) -> int:
    """Record what a reviewer wrote in the target (CON-58, D-106).

    **Says what it recorded and what it did not, separately.** The refusals are
    the part that matters: a reviewer who wrote a decision Constat could not
    record is entitled to learn that from the command rather than from the
    rule never changing. They are also why this exits non-zero — a script that
    treats "read the decisions" as done when four of five landed would bury
    the one that did not.
    """
    result = record_read_decisions(
        workspace, args.reference, target, repository=args.repository
    )
    read = result.read

    print(f"decisions for {read.reference}")
    print(f"  from: {read.location}")
    print()

    if not read.present:
        print("There is no decision file in the target.")
        print()
        print("That is not 'nobody has decided' — it means this ticket's")
        print("document has never been published there, so nobody has had")
        print("anywhere to write. Run `constat publish` first.")
        return EXIT_OK

    if not read.decisions and not read.unreadable:
        print("The decision file is there and empty.")
        print()
        print("Nobody has written a decision yet, so there is nothing to")
        print("record. The file was seeded once when the document was")
        print("published and Constat never writes it again.")
        return EXIT_OK

    if result.recorded:
        print(f"{len(result.recorded)} decision(s) recorded:")
        for outcome in result.recorded:
            print(f"  {outcome.describe()}")
            print(f"      {outcome.line.commit[:12]}  line {outcome.line.line_no}")
        print()
        # Said once, here, because this is the moment the amendment in D-106
        # becomes visible: a decision nobody typed at this command line is now
        # in the catalogue, and the reader should know on what authority.
        print("Recorded on the authority of the commit that wrote each line,")
        print("never of a name typed in the file. An approval made here is")
        print("better evidenced than a CLI `--by` string, which nothing checks.")
        print()

    if result.already:
        print(f"{len(result.already)} decision(s) already recorded:")
        for outcome in result.already:
            print(f"  {outcome.describe()}")
        print()
        print("Reading a target twice is safe. These are the same decisions")
        print("from the same commits, not new ones.")
        print()

    if result.refused:
        print(f"{len(result.refused)} decision(s) could NOT be recorded:")
        for outcome in result.refused:
            print(f"  {outcome.describe()}")
        print()

    if read.unreadable:
        print(f"{len(read.unreadable)} line(s) could not be read at all:")
        for number, text in read.unreadable:
            print(f"  line {number}: {text}")
        print()

    if result.unrecorded:
        print("Somebody decided something that is not recorded. Fix the line")
        print("in the target and run this again, or decide it at the command")
        print("line — but do not assume it landed.")
        return EXIT_DECISIONS

    return EXIT_OK


def _run_review(args: argparse.Namespace) -> int:
    """Put a ticket's proposals where they are decided (CON-107).

    The act `publish <REF>` used to perform, under a name that says which of
    the two moments it is. A ticket page before any decision carries the
    queue and is a thing to circulate; the catalogue page after is a thing to
    keep. One verb for both made the first invisible — `LOOP.md` drew
    publishing only after the decision, which left the off-CLI approval path
    (D-105, D-106) unreachable from the documented loop.

    The decision flags live here rather than on `publish` because this is the
    only page that carries proposals. The catalogue page has none.

    Every failure path prints "nothing has been published" rather than a bare
    error. A user who cannot tell whether a document left the machine has to
    assume it did, and for a document that may carry a credential that is the
    difference between rotating a key and not.
    """
    try:
        with Workspace.open(args.workspace) as workspace:
            target = None
            if args.target is not None:
                target = GitPages(args.target)

            if args.read_decisions and args.record_decisions:
                # Two flags, two meanings, and no sensible union: one promises
                # it records nothing. Refusing beats guessing which the user
                # meant, since one of the guesses writes to the catalogue.
                print(
                    f"{PROG}: error: --read-decisions reports and records "
                    "nothing; --record-decisions records. Pick one.",
                    file=sys.stderr,
                )
                return EXIT_USAGE

            if args.record_decisions:
                recorded = _record_decisions(workspace, args, target)
                if recorded == EXIT_OK:
                    # Recording accepts rules, so the catalogue the record
                    # page shows has changed. Leaving it stale would publish
                    # a catalogue that disagrees with the decisions just read
                    # from the target it was published to.
                    _refresh_catalogue(args, target)
                return recorded

            if args.read_decisions:
                return _report_decisions(workspace, args, target)

            # Counted before publishing, while the workspace is open: this
            # is what tells a reader whether the page is a thing to decide on
            # or a record of decisions already taken.
            waiting = len(RuleProposals(workspace).undecided(args.reference))

            result = publish_document(
                workspace,
                args.reference,
                target,
                repository=args.repository,
                accept_scan_findings=args.accept_scan_findings,
            )
            # The ticket page is live from here on, so a failure refreshing
            # the catalogue must not read as "nothing was published".
            try:
                state_result = publish_state(
                    workspace,
                    target,
                    repository=args.repository,
                    accept_scan_findings=args.accept_scan_findings,
                )
                publish_index(
                    workspace,
                    target,
                    repository=args.repository,
                    accept_scan_findings=args.accept_scan_findings,
                )
            except (PublishError, ProviderError) as exc:
                print(f"published:  {result.ref.describe()}")
                print(
                    f"\n{PROG}: error: the ticket page is published; the "
                    f"catalogue page was not refreshed: {exc}. Run "
                    "`constat publish` to bring it up to date.",
                    file=sys.stderr,
                )
                return EXIT_PUBLISH
    except InvalidInput as exc:
        # The reserved catalogue page name, reached before any target exists.
        # A refusal must read as a refusal: a traceback here would look like a
        # crash on top of a page that was never written.
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except PublishError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_PUBLISH
    except ProviderError as exc:
        # A credential found in the document. Its own exit code so a script can
        # tell "refused to publish" from "could not reach the target".
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_PUBLISH
    except RepositoryError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_REPOSITORY
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE

    print(f"published:  {result.ref.describe()}")
    print(f"run:        {result.run_id}")
    print(f"catalogue:  {state_result.ref.describe()}")
    if result.scan_accepted:
        print(
            f"\n{len(result.scan_findings)} disclosure finding(s) were "
            "accepted and published anyway. Recorded as an operation. If a "
            "credential among them is real, rotate it — the page is readable "
            "now, and deleting it does not unpublish it."
        )
    else:
        # The clean case is stated, including what the scan does not cover. A
        # silent pass is read as proof, and this one is not (D-044's posture,
        # D-095's limit).
        print(
            "\nScanned for credentials, internal hostnames and addresses, "
            "connection strings and described weaknesses, and found none. "
            "**Commercial disclosure is not covered**: no generic detector "
            "exists for a real customer, price or volume, because a figure "
            "with a currency is what a business rule legitimately says."
        )
    if waiting:
        print(
            f"\ncirculated for review — {waiting} proposal(s) on this page "
            "await a decision. A reviewer writes one line per proposal in the "
            "`decisions/` file beside it and commits; record what they wrote "
            f"with `constat review {args.reference} --record-decisions`. Or "
            "decide here with `constat rule accept <ID>`."
        )
    else:
        print(
            "\npublished as a record — every proposal on this page is "
            "decided, so there is nothing on it awaiting a verdict."
        )
    return EXIT_OK


def _refresh_catalogue(args: argparse.Namespace, target) -> None:
    """Bring the catalogue page up to date, and never fail the caller.

    Called after decisions are recorded, because recording accepts rules and
    a record page that disagrees with the decisions just read from the target
    it was published to is worse than one that is merely old. Reported rather
    than raised: the decisions *are* recorded and durable by this point, and
    an error here must not read as though they were not (D-062's posture for
    the merge, applied to the page).
    """
    try:
        with Workspace.open(args.workspace) as workspace:
            result = publish_state(
                workspace,
                target,
                repository=args.repository,
                accept_scan_findings=args.accept_scan_findings,
            )
    except (PublishError, ProviderError, RepositoryError, WorkspaceError) as exc:
        print(
            f"\nThe decisions are recorded. The catalogue page was not "
            f"refreshed: {exc}. Run `constat publish` to bring it up to date.",
            file=sys.stderr,
        )
        return
    print(f"\ncatalogue:  {result.ref.describe()}")


def _run_publish(args: argparse.Namespace) -> int:
    """Publish the catalogue — the record of what was agreed (D-110).

    No reference: this page is the whole catalogue, not one ticket's reading.
    A proposal awaiting a verdict is on its ticket's page, which
    `constat review <REF>` writes, and the decision flags live there because
    that is the only page carrying proposals.
    """
    if args.reference is not None:
        print(
            f"{PROG}: error: `publish` writes the catalogue and takes no "
            f"reference. The page for {args.reference!r} is written by "
            f"`constat review {args.reference}`, which carries the proposals "
            "awaiting a decision and refreshes the catalogue with it.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    if args.read_decisions or args.record_decisions:
        print(
            f"{PROG}: error: decisions are read from a ticket's page, not "
            "from the catalogue — a verdict is written against a rule "
            "proposal and the catalogue page carries none. Use `constat "
            "review <REF> --read-decisions`.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    try:
        with Workspace.open(args.workspace) as workspace:
            target = None
            if args.target is not None:
                target = GitPages(args.target)

            result = publish_state(
                workspace,
                target,
                repository=args.repository,
                accept_scan_findings=args.accept_scan_findings,
            )
            areas = publish_areas(
                workspace,
                target,
                repository=args.repository,
                accept_scan_findings=args.accept_scan_findings,
            )
            releases = publish_releases(
                workspace,
                target,
                repository=args.repository,
                accept_scan_findings=args.accept_scan_findings,
            )
            # After the releases, so it lists pages that already exist.
            index = publish_index(
                workspace,
                target,
                repository=args.repository,
                accept_scan_findings=args.accept_scan_findings,
            )
    except PublishError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_PUBLISH
    except ProviderError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_PUBLISH
    except RepositoryError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_REPOSITORY
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE

    print(f"published:  {result.ref.describe()}")
    for area in areas:
        print(f"area:       {area.ref.describe()}")
    for release in releases:
        print(f"release:    {release.ref.describe()}")
    print(f"index:      {index.ref.describe()}")
    if result.scan_accepted:
        print(
            f"\n{len(result.scan_findings)} disclosure finding(s) were "
            "accepted and published anyway. If a credential among them is "
            "real, rotate it — the page is readable now, and deleting it does "
            "not unpublish it."
        )
    else:
        print(
            "\nScanned for credentials, internal hostnames and addresses, "
            "connection strings and described weaknesses, and found none. "
            "**Commercial disclosure is not covered**: no generic detector "
            "exists for a real customer, price or volume, because a figure "
            "with a currency is what a business rule legitimately says."
        )
    print(
        "\nThis is the catalogue: rules a person has already accepted. "
        "**Nothing on it can be decided** — a rule awaiting a decision is on "
        "its ticket's page, written by `constat review <REF>`. The page is "
        "rewritten in full each time, so nothing written into it survives."
    )
    print(
        "\nNo operation was recorded. This page belongs to no ticket, and an "
        "operation needs one — so `ticket show` will not list this "
        "publication. The rules on it each carry their own decision."
    )
    return EXIT_OK


def _run_document(args: argparse.Namespace) -> int:
    if args.payload and args.show:
        print(
            f"{PROG}: error: --payload and --show print different things; "
            "pick one",
            file=sys.stderr,
        )
        return EXIT_USAGE

    if args.payload:
        return _run_export(args)

    try:
        with Workspace.open(args.workspace) as workspace:
            _refuse_without_a_provider(args, workspace)
            result = gather(
                workspace,
                args.reference,
                accept_scan_findings=args.accept_scan_findings,
            )
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE
    except ProviderError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_PROVIDER
    except RepositoryError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_REPOSITORY

    if args.show:
        print(result.body)
        return EXIT_OK

    print(f"ticket {result.reference}: document updated")
    print(
        f"  {result.repositories_searched} repository(ies) searched, "
        f"{result.repositories_contributing} contributed evidence"
    )
    for finding in result.findings:
        detail = finding.error or f"{len(finding.commits)} commit(s)"
        print(f"    {finding.repository.alias}: {finding.status.value} — {detail}")

    _print_scan(result)
    _print_interpretation(result.interpretation)
    print()
    print("Use --show to print the document. It is a draft: nothing here is")
    print("approved, and approval is a separate, explicit step.")
    return EXIT_OK


def _run_ticket(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.ticket_action is None:
        parser.parse_args(["ticket", "--help"])
        return EXIT_USAGE

    try:
        with Workspace.open(args.workspace) as workspace:
            tickets = TicketStore(workspace)

            if args.ticket_action == "add":
                # Before the ticket exists. A refusal must leave nothing
                # behind: an opened ticket with no evidence and no rules is
                # worse than no ticket, because `ticket add` then refuses to
                # open it again (D-059).
                _refuse_without_a_provider(args, workspace)

                # The duplicate guard runs first either way, so the message
                # for an existing ticket does not depend on which path the
                # reference would have taken.
                if tickets.find(args.reference) is not None:
                    raise AlreadyRegistered(
                        f"ticket {args.reference!r} already exists. Its "
                        "document is where further operations accumulate; "
                        "opening it again would not create a second one."
                    )

                # CON-105: search before opening, so a reference no repository
                # knows is refused here as it already is on the agent path
                # (D-063). The reasoning there was that a mistyped reference at
                # a terminal should be a question rather than a new ticket —
                # and the terminal was the one place not asking.
                #
                # `--even-if-absent` keeps the deliberate case, which is real:
                # work that has not started, or is tracked somewhere Constat
                # cannot see. `USAGE.md` has always advertised it.
                if args.even_if_absent:
                    entry = tickets.add(args.reference)
                    print(f"opened ticket: {entry.reference}")
                    result = gather(
                        workspace,
                        entry.reference,
                        accept_scan_findings=args.accept_scan_findings,
                    )
                else:
                    # Opens inside `gather`, after the search and before
                    # anything is written — or raises ReferenceMatchedNothing
                    # and leaves no ticket behind.
                    result = gather(
                        workspace,
                        args.reference,
                        accept_scan_findings=args.accept_scan_findings,
                        open_if_absent=True,
                    )
                    print(f"opened ticket: {args.reference}")
                print(
                    f"  {result.repositories_searched} repository(ies) searched, "
                    f"{result.repositories_contributing} contributed evidence"
                )
                for finding in result.findings:
                    detail = finding.error or f"{len(finding.commits)} commit(s)"
                    print(
                        f"    {finding.repository.alias}: "
                        f"{finding.status.value} — {detail}"
                    )
                _print_scan(result)
                _print_interpretation(result.interpretation)
                print()
                print(f"Document written. See it with `constat document "
                      f"{args.reference} --show`.")
                print("It is a draft and carries no authority until approved.")
                return EXIT_OK

            if args.ticket_action == "list":
                entries = tickets.list()
                if not entries:
                    print("No tickets. Open one with `ticket add`.")
                    return EXIT_OK
                print(f"{len(entries)} ticket(s):")
                for entry in entries:
                    print(f"  {entry.reference}")
                return EXIT_OK

            if args.ticket_action == "requirement":
                supplied_by, attribution = _decider(args)
                supplied = Requirements(workspace).supply(
                    args.reference,
                    args.label,
                    supplied_by,
                    uri=args.uri,
                    attribution=attribution,
                )
                print(f"recorded: {supplied.label}")
                if supplied.uri:
                    print(f"  at:          {supplied.uri}")
                print(f"  on ticket:   {supplied.reference}")
                print(f"  supplied by: {supplied.supplied_by}")
                if attribution == "inferred":
                    print("               (inferred from git config)")
                print()
                print("Provenance `requirement_ref`: supplied, not verified.")
                print("Constat did not open it and does not know what it says.")
                return EXIT_OK

            if args.ticket_action == "show":
                entry = tickets.find(args.reference)
                if entry is None:
                    print(
                        f"{PROG}: error: no ticket {args.reference!r}.",
                        file=sys.stderr,
                    )
                    return EXIT_WORKSPACE
                document = tickets.document(entry.reference)
                operations = workspace.execute(
                    "SELECT o.kind, o.ran_at, o.summary, r.alias "
                    "FROM operation o "
                    "JOIN document d ON d.id = o.document_id "
                    "JOIN ticket tk ON tk.id = d.ticket_id "
                    "LEFT JOIN repository r ON r.id = o.repository_id "
                    "WHERE tk.reference = ? ORDER BY o.ran_at, r.alias",
                    (entry.reference,),
                ).fetchall()

                # Stored state only. Re-searching here would make `show`
                # disagree with the document it is describing.
                print(f"ticket:    {entry.reference}")
                print(f"opened:    {entry.created_at.isoformat()}")
                print(f"document:  {'empty' if document.is_empty else 'filled'}"
                      f", updated {document.updated_at.isoformat()}")
                print(f"operations: {len(operations)} recorded")
                for row in operations:
                    alias = row["alias"] or "(no repository)"
                    print(f"    {row['ran_at']}  {alias}  {row['summary']}")
                # The navigation CON-18 asked for: a reviewer reading a rule
                # proposal reaches the artefacts through its ticket.
                supplied = Requirements(workspace).for_ticket(entry.reference)
                if supplied:
                    print(f"requirements: {len(supplied)} supplied")
                    for requirement in supplied:
                        print(f"    {requirement.describe()}")
                        print(f"        supplied by {requirement.supplied_by}"
                              f" ({requirement.attribution}),"
                              " not verified")
                print()
                print(f"Run `constat document {entry.reference} --show` for the "
                      "document itself,")
                print(f"or `constat document {entry.reference}` to gather again.")
                return EXIT_OK
    except ProviderError as exc:
        # `ticket add` gathers, so it can hit a provider misconfiguration too.
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_PROVIDER
    except InvalidInput as exc:
        # `ticket requirement` refuses a duplicate label and an overlong one.
        # Without this the refusal arrived as a traceback, which is a crash
        # report where a sentence was meant — found by running it.
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE

    parser.error(f"unknown ticket action: {args.ticket_action}")
    return EXIT_USAGE  # pragma: no cover


def _run_repo(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.repo_action is None:
        parser.parse_args(["repo", "--help"])
        return EXIT_USAGE

    try:
        with Workspace.open(args.workspace) as workspace:
            registry = Registry(workspace)

            if args.repo_action == "add":
                entry = registry.add(args.path, args.name, args.default_branch)
                signal = registry.branching_of(entry)
                print(f"registered: {entry.alias}")
                print(f"  source:         {entry.source}")
                if entry.cache_path is not None:
                    # Said rather than left to be discovered: a clone exists,
                    # it is inside the workspace, and it is as old as the fetch
                    # time beside it.
                    print(f"  cached at:      {entry.cache_path}")
                    print(f"  fetched:        {entry.last_fetched_at}")
                print(f"  identity:       {entry.identity}")
                print(f"  default branch: {entry.default_branch}")
                # The ref actually read, not just the configured branch name
                # (CON-97). "default branch: main" is configuration; mainline
                # is what every answer about shipped behaviour is measured
                # against (D-028, D-068), and when it falls back to a local
                # branch that is a weaker claim a reader should see.
                print(f"  mainline:       {signal.mainline}")
                if not signal.from_remote:
                    print("                  (a local branch — no "
                          "remote-tracking ref for it)")
                print()
                print("Identity is the root commit, so this stays the same")
                print("repository if the checkout moves or is re-cloned.")
                if entry.cache_path is not None:
                    print()
                    print("A clone with no checkout, inside the workspace:")
                    print("`repo remove` deletes it, `repo fetch` refreshes it,")
                    print("and what it holds is as old as its last fetch.")
                # Said at registration, because this is the moment the choice
                # is being made (CON-97, D-076). A warning, never a refusal,
                # and `describe_branching` returns nothing for a repository
                # that looks trunk-based.
                warning = describe_branching(signal)
                if warning:
                    print()
                    print("Warning — this may not be trunk-based:")
                    # Wrapped here rather than in the sentences, because they
                    # interpolate branch names and commit counts and so cannot
                    # be hand-wrapped the way the rest of this output is.
                    for line in warning:
                        if not line:
                            print()
                            continue
                        for wrapped in textwrap.wrap(line, width=72):
                            print(f"  {wrapped}")
                return EXIT_OK

            if args.repo_action == "fetch":
                entry = registry.refresh(args.alias)
                print(f"fetched: {entry.alias}")
                print(f"  from:    {entry.source}")
                print(f"  fetched: {entry.last_fetched_at}")
                return EXIT_OK

            if args.repo_action == "list":
                entries = registry.list()
                if not entries:
                    print("No repositories registered. Add one with `repo add`.")
                    return EXIT_OK
                print(f"{len(entries)} repository(ies):")
                for entry in entries:
                    print(f"  {entry.alias}")
                    print(f"    source:         {entry.source}")
                    if entry.cache_path is not None:
                        print(f"    cached:         {entry.cache_path}")
                        print(f"    fetched:        {entry.last_fetched_at}")
                    print(f"    default branch: {entry.default_branch}")
                    print(f"    identity:       {entry.identity[:12]}")
                return EXIT_OK

            if args.repo_action == "remove":
                entry = registry.remove(args.name)
                print(f"unregistered: {entry.alias} ({entry.source})")
                print("The repository on disk is untouched; Constat only reads.")
                return EXIT_OK
    except WorkspaceError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_WORKSPACE
    except RepositoryError as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_REPOSITORY

    parser.error(f"unknown repo action: {args.repo_action}")
    return EXIT_USAGE  # pragma: no cover


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # With no subcommand, explain rather than doing nothing silently.
    if args.command is None:
        parser.print_help()
        return EXIT_OK

    if args.command == "mcp":
        return _run_mcp(args)

    if args.command == "init":
        return _run_init(args)

    if args.command == "config":
        return _run_config(args, parser)

    if args.command == "repo":
        return _run_repo(args, parser)

    if args.command == "ticket":
        return _run_ticket(args, parser)

    if args.command == "document":
        return _run_document(args)

    if args.command == "rule":
        return _run_rule(args, parser)

    if args.command == "review":
        return _run_review(args)

    if args.command == "publish":
        return _run_publish(args)

    if args.command == "baseline":
        return _run_baseline(args)

    if args.command == "checkpoint":
        if args.checkpoint_action is None:
            args.checkpoint_action = "list"
        return _run_checkpoint(args)

    if args.command == "message":
        if args.message_action is None:
            args.message_action = "list"
        return _run_message(args)

    if args.command == "area":
        if args.area_action is None:
            args.area_action = "list"
        return _run_area(args)

    if args.command == "release":
        if args.release_action is None:
            args.release_action = "list"
        return _run_release(args)

    if args.command == "state":
        return _run_state(args)

    # Unreachable while argparse validates the choice, but an explicit failure
    # beats falling off the end and returning None.
    parser.error(f"unknown command: {args.command}")
    return EXIT_USAGE  # pragma: no cover - parser.error raises SystemExit


if __name__ == "__main__":  # pragma: no cover - exercised via __main__.py
    sys.exit(main())
