"""The MCP server: Constat as a service an agent can drive (D-045).

Five tools, and the shape of that list is the governance model — **the number
is not the policy, the absence is.** It read "four tools" until CON-101 added
the baseline, and a list that cannot grow would make the next useful tool an
argument about a docstring rather than about acceptance.

**What is exposed.** Gathering evidence, reading the payload, submitting a
reading, listing the review queue, and documenting an area as it already
behaves — the two halves of the loop, two read-only views, and the way into an
empty catalogue. All of it is work an agent can usefully do.

**What is deliberately absent: acceptance.** There is no `accept` tool and no
`reject` tool. A model that could call `accept` would make "no proposal becomes
official without an explicit human decision" unenforceable, and the hard
prohibition in `CLAUDE.md` is that Constat must never mark a proposal approved
without a recorded human decision. Acceptance stays a human act at the CLI,
outside the agent's reach. That absence is tested, because a later release
adding one tool "for convenience" is exactly how this gets lost.

**Transport is stdio.** The client spawns Constat as a subprocess; nothing
listens on a port. That is what keeps this a local tool rather than the hosted
service `PRODUCT_SPEC.md` § 6.2 defers, and it means no authentication layer
is needed — which § 6.2 also defers.

**Every tool goes through the same code as the CLI.** No tool reimplements an
operation, so the gates hold here by construction: identity never crosses the
boundary (D-040), the credential gate fires on export (D-047), and a submitted
reading is grounded against re-gathered evidence (D-052).

**One precondition was removed rather than a tool added** (CON-64, D-063).
`gather_evidence` opens a ticket it does not find, because the loop above
cannot start otherwise and nothing here said so. The tool list is unchanged by
it — which is the argument for it. A reference matching no commits anywhere is
still refused, so the refusal it replaced survives where it was doing work.
"""

from __future__ import annotations

import json
from typing import Any

from .ai.guidance import (
    ANCHORS,
    for_baseline,
    EXAMPLES,
    MESSAGES,
    NOTHING_IS_ACCEPTED,
    REPLY_SHAPE,
    AREAS,
    PENDING,
    RELATIONS,
    REVISION,
    WHAT_A_RULE_IS,
)
from .ai import as_dict
from .errors import ConstatError
from .operations import baseline_area, export_payload, gather, submit_reply
from .store import Catalogue, RuleProposals, Workspace

SERVER_NAME = "constat"

INSTRUCTIONS = """\
Constat turns software changes into evidence-backed, human-approved knowledge.

The loop: gather_evidence collects what a ticket changed across the registered
repositories, opening the ticket if it is new; get_payload returns that
evidence, redacted, together with the rules already in the catalogue; you read
it and submit_rules stores what you concluded as rule proposals;
list_rule_proposals shows what is awaiting review.

Start with gather_evidence whether or not the ticket exists. A reference no
repository knows is refused rather than opened, so a refusal there means the
reference is wrong — report it rather than retrying.

There is a second way in, for an area that has no ticket because nothing
changed: baseline_area_tool stores a reading of how an area already behaves.
Constat supplies no evidence for that one — open the repository and read it
yourself — and every anchor rests on the product's mainline instead.

Nothing you submit is accepted. Every rule proposal waits for a human decision
at the command line, and there is no tool here that can make one. Anchors must
name paths present in the evidence supplied — a rule proposal anchored to
anything else is discarded, and you will be told why.
"""


def _anticipated(operation):
    """Run an operation, reporting Constat's own errors as anticipated ones.

    `ToolError` is the SDK's "a failure you saw coming": the call returns
    `is_error` with **this message** in the content. Letting a `ConstatError`
    escape instead gets it wrapped as an unexpected crash, and the client sees
    "Error executing tool get_payload" — which loses the only part that was
    worth sending.

    That matters here more than usual. These messages are the product's voice:
    "refusing to send evidence... remove the credential and rotate it", "no
    anchor grounded in the evidence supplied". A caller that cannot read the
    reason cannot act on it, and a governance tool whose refusals are opaque is
    not much of one.
    """
    from mcp.server.mcpserver.exceptions import ToolError

    try:
        return operation()
    except ConstatError as exc:
        raise ToolError(str(exc)) from None


def _text(payload: Any) -> str:
    """Tool results are text. JSON for anything structured."""
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, indent=2, default=str)


def build_server(workspace_home: str | None = None):
    """Construct the server. Separated so tests can drive the tools directly.

    The workspace is opened per call rather than held open: an MCP session can
    outlive any single operation, and a long-lived connection to a governance
    store is a lock waiting to be contended.
    """
    from mcp.server.mcpserver import MCPServer

    server = MCPServer(SERVER_NAME, instructions=INSTRUCTIONS)

    @server.tool(
        description=(
            "Gather evidence for a ticket across every registered repository "
            "and expand its document. Call this before get_payload. Reports "
            "every repository searched, including those that contributed "
            "nothing — silence about a repository is not the same as no "
            "changes there. If the ticket does not exist yet it is opened, "
            "but only when the repositories recognise the reference: one that "
            "matches no commits anywhere is refused rather than opened, "
            "because that is usually a typo."
        )
    )
    def gather_evidence(reference: str) -> str:
        """Collect what a ticket changed, opening the ticket if need be.

        `open_if_absent` is what makes the loop startable from here (CON-64,
        D-063). Without it the first step of the agent's own workflow failed
        on a clean workspace until a person ran `constat ticket add` at the
        command line — a prerequisite nothing in this interface mentioned.

        This grows no tool list. `EXPOSED_TOOLS` is the same four it was, and
        acceptance is as absent as ever: the change removes a precondition
        from a tool that already gathered, rather than granting a capability
        D-055 withheld.
        """

        def run() -> str:
          with Workspace.open(workspace_home) as workspace:
            result = gather(workspace, reference, open_if_absent=True)
            return _text(
                {
                    "reference": result.reference,
                    "ticket_opened": result.ticket_opened,
                    "run_id": result.run_id,
                    "repositories_searched": result.repositories_searched,
                    "repositories_contributing": result.repositories_contributing,
                    "repositories": [
                        {
                            "alias": f.repository.alias,
                            "status": f.status.value,
                            "commits": len(f.commits),
                            "error": f.error,
                        }
                        for f in result.findings
                    ],
                    "credential_scan_findings": len(result.scan_findings),
                }
            )

        return _anticipated(run)

    @server.tool(
        description=(
            "The redacted evidence for a ticket, plus the rules already in the "
            "catalogue. Author and committer identity is never included. If a "
            "credential is found in the evidence this refuses rather than "
            "returning it — remove and rotate it, or accept the findings at "
            "the command line."
        )
    )
    def get_payload(reference: str) -> str:
        """Read the evidence a reading should be based on."""

        def run() -> str:
            with Workspace.open(workspace_home) as workspace:
                return _text(as_dict(export_payload(workspace, reference).payload))

        return _anticipated(run)

    @server.tool(
        description=(
            "Submit what you concluded from the payload, as JSON: "
            '{"rules": [{"name", "statement", "behaviours": [...], '
            '"anchors": [{"path_glob", "repository_alias"}], "revises": <id>}]}. '
            "Every anchor must name a path present in the evidence; a rule "
            "proposal whose anchors are not grounded is discarded with a "
            "reason. `revises` names a catalogue rule this revises — omit it "
            "to propose a new rule. Nothing submitted is accepted."
        )
    )
    def submit_rules(
        reference: str,
        reply: str,
        provider: str = "mcp",
        model: str | None = None,
    ) -> str:
        """Turn a reading into stored rule proposals."""

        def run() -> str:
          with Workspace.open(workspace_home) as workspace:
            result = submit_reply(
                workspace, reference, reply, provider=provider, model=model
            )
            return _text(
                {
                    "run_id": result.run_id,
                    "stored": list(result.stored),
                    "discarded": [
                        {"name": r.name, "reason": r.reason} for r in result.rejections
                    ],
                    "possible_duplicates": {
                        str(k): list(v) for k, v in result.candidates.items()
                    },
                    # Separate key, not merged into the one above: those are
                    # catalogue rule ids, these are rule proposal ids, and a
                    # reader cannot tell which is which from the number
                    # (CON-70).
                    "possible_duplicate_proposals": {
                        str(k): list(v) for k, v in result.pending_candidates.items()
                    },
                    "accepted": False,
                    "note": (
                        "Stored and awaiting a human decision. There is no tool "
                        "that can accept these."
                    ),
                }
            )

        return _anticipated(run)

    @server.tool(
        description=(
            "Rule proposals recorded for a ticket. Undecided ones by default — "
            "the review queue. An empty queue is not a statement that the "
            "ticket has no rules."
        )
    )
    def list_rule_proposals(reference: str, include_decided: bool = False) -> str:
        """Read the review queue."""

        def run() -> str:
          with Workspace.open(workspace_home) as workspace:
            proposals = RuleProposals(workspace)
            stored = (
                proposals.for_ticket(reference)
                if include_decided
                else proposals.undecided(reference)
            )
            return _text(
                [
                    {
                        "id": item.id,
                        "name": item.proposal.name,
                        "statement": item.proposal.statement,
                        "anchors": [a.path_glob for a in item.proposal.anchors],
                        "revises_rule_id": item.revises_rule_id,
                        "decision": item.decision,
                        "read_by": item.provider,
                        "model": item.model,
                        "model_is_self_reported": not item.model_attested,
                        "run_id": item.run_id,
                    }
                    for item in stored
                ]
            )

        return _anticipated(run)

    @server.prompt(
        name="document",
        title="Document a ticket",
        description=(
            "Read a ticket's evidence and propose the business rules it "
            "changed. Gathers, reads the redacted payload, and stores what you "
            "conclude as proposals. Nothing is accepted — a person decides at "
            "the command line."
        ),
    )
    def document_prompt(reference: str) -> str:
        """The whole loop, as one invocation.

        A tool is something the model chooses to call; a prompt is something
        the *user* invokes, and clients surface it as a slash command. Until
        this existed, starting the loop meant describing it in a sentence
        every time — friction with no principle behind it, because an MCP
        server cannot initiate anything on its own.

        It is also where the MCP path finally gets what the provider path has
        in `SYSTEM`. Tool descriptions can say what a tool does; they are a
        poor place to explain what a business rule is, and nothing else here
        was saying it.
        """
        return (
            f"Work out what ticket {reference} changed, and propose the "
            "business rules it touches.\n\n"
            f"1. Call `gather_evidence` with reference `{reference}`. Report "
            "every repository it searched, including the ones that "
            "contributed nothing — silence about a repository is not the same "
            "as no changes there.\n"
            f"2. Call `get_payload` with reference `{reference}` and read it.\n"
            f"3. Call `submit_rules` with reference `{reference}` and your "
            "conclusions as JSON.\n"
            "4. Tell me what was stored and what was discarded, with the "
            "reasons.\n\n"
            f"{WHAT_A_RULE_IS}\n\n{EXAMPLES}\n\n{MESSAGES}\n\n{ANCHORS}\n\n{AREAS}\n\n"
            f"{RELATIONS}\n\n"
            f"{REVISION}\n\n"
            f"{PENDING}\n\n"
            f"{NOTHING_IS_ACCEPTED}\n\n"
            "The reply for step 3 is JSON in this shape:\n\n"
            f"{REPLY_SHAPE}\n\n"
            "If a refusal comes back — a credential in the evidence, an "
            "ungrounded anchor — tell me what it said rather than working "
            "around it. Those refusals are the product working."
        )

    @server.tool(
        description=(
            "Document an area of the product as it already behaves, with no "
            "ticket and no change to read. Constat supplies no evidence here: "
            "open the repository and read it yourself, then submit what you "
            "found. Every anchor must name a path that exists in some "
            "registered repository's mainline. A rule naming a different area "
            "is refused rather than re-filed. Nothing submitted is accepted."
        )
    )
    def baseline_area_tool(
        area: str,
        reply: str,
        reference: str | None = None,
        provider: str = "mcp",
        model: str | None = None,
    ) -> str:
        """Store a reading that describes an area as it stands (CON-89).

        **The tool D-080 left unbuilt.** That decision chose the agent-driven
        shape *because* an agent has the repository and can read it directly —
        and then left documenting an area reachable only from the command line,
        which made the reasoning and the surface disagree.

        A thin wrapper, as ARCHITECTURE § 2 requires of every tool here: the
        scope refusal, the mainline grounding, the revision pointers and the
        append-only storage are all `operations.baseline_area`, unchanged. The
        only thing added is a door.

        `reference` defaults to the cold-start form the CLI uses, so an agent
        documenting an area in a fresh workspace needs nothing from a person
        first — and the result says the reference was opened, because a
        reference that is not a unit of work should not appear in `ticket list`
        unannounced.
        """

        def run() -> str:
          with Workspace.open(workspace_home) as workspace:
            chosen = reference or f"baseline-{area.strip().replace(' ', '-')}"
            result = baseline_area(
                workspace,
                area=area,
                reference=chosen,
                text=reply,
                provider=provider,
                model=model,
            )
            submitted = result.submitted
            return _text(
                {
                    "area": result.area,
                    "reference": result.reference,
                    "opened_reference": result.opened_ticket,
                    "run_id": submitted.run_id,
                    "stored": list(submitted.stored),
                    "described_at": [
                        {"repository": alias, "revision": revision}
                        for alias, revision in result.read_from
                    ],
                    "discarded": [
                        {"name": r.name, "reason": r.reason}
                        for r in submitted.rejections
                    ],
                    # Kept apart from `discarded`: an out-of-scope reading is a
                    # correct reading of the wrong area, not a malformed one,
                    # and reporting them together mislabelled it (D-080).
                    "out_of_area": [
                        {"name": r.name, "reason": r.reason}
                        for r in result.out_of_area
                    ],
                    "new_areas": {
                        str(k): {"area": v[0], "already_declared": list(v[1])}
                        for k, v in submitted.new_areas.items()
                    },
                    "accepted": False,
                    "note": (
                        "Every anchor rests on mainline, because nothing here "
                        "is evidence that anything changed. Stored and "
                        "awaiting a human decision."
                    ),
                }
            )

        return _anticipated(run)

    @server.prompt(
        name="baseline",
        title="Document an area as it already behaves",
        description=(
            "Read an area of the product directly and write down the business "
            "rules it already holds. No ticket, no change — and nothing is "
            "accepted."
        ),
    )
    def baseline_prompt(area: str) -> str:
        """The baseline loop, with the guidance a tool description cannot hold.

        `for_baseline` reuses `WHAT_A_RULE_IS`, `EXAMPLES`, `MESSAGES` and
        `ANCHORS` unchanged, because a rule from a baseline and a rule from a
        ticket go in one catalogue and must mean the same thing (D-045, CON-66).

        **The declared areas are named here**, and that gap was worth closing.
        `baseline_area` builds a payload carrying the catalogue — areas and all
        — but uses it only to ground anchors and spot duplicates, and never
        returns it. So an agent documenting an area could not see which areas
        already existed, which is exactly what D-079 relies on to stop "ads"
        arriving beside "advertising". The ticket path gets this from
        `get_payload`; this path had nothing.
        """
        declared: tuple[str, ...] = ()
        awaiting: tuple[str, ...] = ()
        try:
            with Workspace.open(workspace_home) as workspace:
                declared = Catalogue(workspace).areas()
                # Pending areas matter as much as declared ones here. An area
                # is declared by acceptance (D-079), so two baselines run back
                # to back would both be told "no areas yet" and the second
                # would coin the synonym the first had already avoided.
                awaiting = tuple(
                    sorted(
                        {
                            p.proposal.area
                            for p in RuleProposals(workspace).across_workspace(
                                "awaiting"
                            )
                            if p.proposal.area and p.proposal.area not in declared
                        }
                    )
                )
        except ConstatError:
            # A prompt that refused because there is no workspace yet would be
            # worse than one with a sentence missing: everything below is still
            # correct, and `constat init` is the fix.
            declared = ()

        parts: list[str] = []
        if declared:
            parts.append(
                "already has "
                + ", ".join(f"**{name}**" for name in declared)
            )
        if awaiting:
            parts.append(
                "has readings awaiting a decision in "
                + ", ".join(f"**{name}**" for name in awaiting)
            )

        if parts:
            existing = (
                f"The catalogue {' and '.join(parts)}. If **{area}** is one of "
                "them under another name, say so rather than coining a second "
                "heading — merging two areas later means renaming across "
                "frozen versions.\n\n"
            )
        else:
            existing = (
                f"The catalogue has no areas yet, so **{area}** would be the "
                "first — an area is declared when a rule in it is accepted, "
                "not by proposing one.\n\n"
            )

        return (
            f"Document the **{area}** area of this product as it behaves "
            "today.\n\n"
            "1. Open the repositories and read the code for that area "
            "yourself. Constat supplies no evidence for a baseline, because "
            "there is no change to read.\n"
            f"2. Call `baseline_area_tool` with area `{area}` and your "
            "conclusions as JSON.\n"
            "3. Tell me what was stored, what was discarded, and anything "
            "reported as out of the area.\n\n"
            f"{existing}"
            f"{for_baseline(area)}"
        )

    @server.prompt(
        name="review",
        title="Review a ticket's rule proposals",
        description=(
            "Summarise what is waiting for a decision on a ticket, so a "
            "person can decide. Read-only: accepting is not possible here."
        ),
    )
    def review_prompt(reference: str) -> str:
        """Read the queue and explain it. Deliberately cannot decide."""
        return (
            f"Call `list_rule_proposals` with reference `{reference}` and "
            "summarise what is waiting for a decision.\n\n"
            "For each one, say what the rule claims, where it is anchored, "
            "and whether it claims to revise an existing rule. Note which "
            "readings are self-reported — the model named in a proposal is "
            "what the reader claimed, not something Constat established, "
            "unless it says otherwise.\n\n"
            "An empty queue means nothing has read this ticket's evidence "
            "yet. It is not a statement that the ticket has no rules.\n\n"
            "Do not recommend accepting or rejecting anything, and do not "
            "describe any of them as approved. You cannot accept — there is "
            "no tool for it here by design. Finish by telling me the command: "
            "`constat rule accept <ID> --by <who>`."
        )

    return server


# The tools this server exposes. Named here so a test can assert the list
# rather than trust that nobody added `accept` — the absence is the policy.
EXPOSED_TOOLS = (
    "gather_evidence",
    "get_payload",
    "submit_rules",
    "list_rule_proposals",
    "baseline_area_tool",
)

EXPOSED_PROMPTS = ("document", "review", "baseline")
"""The prompts this server exposes, as slash commands in a client.

A tool is something the model chooses to call; a prompt is something the user
invokes. Until these existed, starting the loop meant typing a sentence every
time — an MCP server cannot initiate anything, so the user has to, and making
that one command rather than a paragraph is the whole of CON-66.

Neither prompt may instruct acceptance. `review` says so explicitly, because
the natural shape of "summarise what is waiting" is to end with a
recommendation, and a recommendation from the thing that wrote the proposal is
not a review."""

FORBIDDEN_TOOLS = ("accept", "reject", "approve", "decide")
"""Never exposed. A model that could accept would make "no proposal becomes
official without an explicit human decision" unenforceable."""


def serve(workspace_home: str | None = None) -> None:
    """Run the server on stdio until the client disconnects."""
    build_server(workspace_home).run(transport="stdio")
