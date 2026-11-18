"""The published schema.

These are the types that get persisted (CON-13), rendered (CON-09) and frozen
into approved baselines (CON-14). Pydantic applies here and nowhere else
(D-026): the Git adapter deals in frozen dataclasses, and `mapping.py`
translates between the two in one direction only.

Everything here is immutable once built. A proposal that could be edited in
place would make "history is durable" (product rule 5) unenforceable.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1
"""Bumped whenever the serialised shape changes in a way a reader must notice.

Versioned from the first release (D-008): a stored baseline is useless if the
schema that produced it cannot be identified.
"""

SHA_PATTERN = r"^[0-9a-f]{40}$"


class Frozen(BaseModel):
    """Base for every published model: immutable and strict.

    `extra="forbid"` matters more than it looks. Silently accepting an unknown
    field would let a typo'd key vanish from a governance record without
    anyone noticing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class SelectionKind(str, Enum):
    CHANGE = "change"
    STATE = "state"
    COMMIT_SET = "commit_set"
    """Reserved for CON-29. Declared now so adding it later is additive rather
    than a schema break."""


class ProvenanceType(str, Enum):
    """PRODUCT_SPEC.md section 7.1. Every claim carries exactly one.

    Only `observed_fact` is produced today — everything Constat currently
    emits is read directly from Git. The rest exist so CON-10 extends the
    taxonomy rather than inventing it.
    """

    OBSERVED_FACT = "observed_fact"
    TEST_EVIDENCE = "test_evidence"
    REQUIREMENT_REF = "requirement_ref"
    AI_INTERPRETATION = "ai_interpretation"
    ASSUMPTION = "assumption"
    UNKNOWN = "unknown"
    HUMAN_DECISION = "human_decision"


class RevisionRef(Frozen):
    """A revision, in both the form a machine needs and the form a human reads."""

    symbolic: str = Field(min_length=1)
    sha: str = Field(pattern=SHA_PATTERN)


class RepositoryRef(Frozen):
    """A repository, identified by something that survives being moved.

    `root_commits` is the identity (D-025). `local_path` is recorded for
    convenience and is explicitly *not* the identity: it changes on every
    clone.
    """

    root_commits: tuple[str, ...] = Field(min_length=1)
    local_path: str
    branch: str | None = None

    @property
    def identity(self) -> str:
        """The durable key. Smallest root commit, so the choice is stable."""
        return min(self.root_commits)


class RegisteredRepository(Frozen):
    """A repository in the workspace (D-027).

    ``identity`` is the root commit and is what duplicate detection uses: the
    same repository cloned twice under two aliases is still one repository,
    and two different paths can hold the same project (D-025).

    ``default_branch`` is stored rather than resolved per run, because it is
    the reference point for every comparison (D-028) and must not quietly
    change when someone checks out a feature branch.
    """

    alias: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_kind: Literal["local", "remote"]
    identity: str = Field(pattern=SHA_PATTERN)
    default_branch: str = Field(min_length=1)
    added_at: datetime
    cache_path: str | None = None
    last_fetched_at: datetime | None = None
    """When the local copy was last refreshed. None for a local path, which is
    always current. Unstated staleness is the same class of failure as
    unstated truncation (D-027)."""


class Behaviour(Frozen):
    """A distinct way the application handles a business case (D-035)."""

    description: str = Field(min_length=1)


class Example(Frozen):
    """One situation and what the product does with it (CON-80).

    This is what a business reader checks a rule *with*. A statement can be
    read and agreed with; an example can be disagreed with, which is the
    difference between documentation someone skims and documentation someone
    verifies. It is the business half of product rule 8, expressed as data.

    Two fields, deliberately, rather than a per-rule table of input columns. A
    reading gets re-run — twice on ticket 615 already — and a per-rule column
    schema would come back different each time, so one rule would accumulate
    three shapes of table that nobody could diff.

    **Nothing in Constat checks that `outcome` is correct.** Deciding that is
    the reviewer's entire job, and a gate that pretended to do it would be
    manufacturing the certainty product rule 1 forbids. What is checked is that
    both halves are present, that neither leaks code (D-066) and that the
    example is not the statement restated.
    """

    situation: str = Field(min_length=1)
    outcome: str = Field(min_length=1)


class Anchor(Frozen):
    """Where a rule is believed to be implemented.

    A path glob, optionally scoped to one repository. Evidence touching an
    anchor makes the rule impacted — which is a statement about *code*, not
    about meaning. What the behaviour now does is for the reviewer to say.
    """

    path_glob: str = Field(min_length=1)
    repository_alias: str | None = None
    grounded_in: Literal["evidence", "mainline"] | None = None
    """Which ground supports this anchor (D-072).

    `evidence` — the ticket being read changed this path. The strong case, and
    the only one that existed before CON-71.
    `mainline` — the path exists in the product's mainline but this ticket did
    not touch it. Verifiable, and a weaker claim *about this ticket*: the rule
    lives there, and this ticket is not the evidence that it changed.
    `None` — not recorded. Anchors written before CON-71, and anchors built
    outside `parse`.

    Kept apart because product rule 3 requires the provenance types to stay
    distinguishable, and these two are different claims. Collapsing them would
    let "the evidence shows this changed" and "this file exists" render
    alike."""


class Rule(Frozen):
    """A business rule held in the catalogue (D-038, authorship per D-039).

    `statement` is the rule in business language. Rules are generated and
    maintained by an AI pass rather than declared by people, so a stored rule
    carries `ai_interpretation` provenance — see `RuleProposal`. The `rule`
    CLI commands remain as a bootstrap and test path, which is how the
    catalogue is exercised with no provider configured.
    """

    name: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    created_at: datetime
    behaviours: tuple[Behaviour, ...] = ()
    examples: tuple[Example, ...] = ()
    """Worked cases, in the order they were proposed (CON-80).

    Empty is a real value and has two meanings a renderer must not conflate: a
    rule accepted before schema 14, which could not carry examples, and a rule
    whose reading proposed none. Neither is "this rule has no cases"."""
    anchors: tuple[Anchor, ...] = ()
    area: str | None = None
    """The business area this rule belongs to (D-070).

    Structure rather than decoration: the catalogue is the product's business
    documentation, and a documentation set with no organisation is a list
    nobody reads. Grouping by repository or directory would organise it by
    where the code lives, which is the one axis a business reader does not
    care about.

    None is a real value — "unplaced". A rule accepted before areas existed
    has no area, and a reading that cannot see where a rule belongs should say
    nothing rather than invent a heading."""


class RuleProposal(Frozen):
    """A rule an interpretation pass proposes. Not a rule yet.

    Deliberately a different type from `Rule`. A proposal has no `created_at`
    because it is not in the catalogue, and it carries no authority until a
    human accepts it (D-036, D-039). Collapsing the two would make it possible
    to store a proposal by mistake, which is precisely the "no automatic
    approvals" prohibition.

    `provenance` is pinned rather than defaulted: machine inference cannot be
    relabelled as anything else, least of all `requirement_ref`.
    """

    name: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    behaviours: tuple[Behaviour, ...] = ()
    examples: tuple[Example, ...] = ()
    """Worked cases this reading proposes (CON-80).

    Optional, like `area`: a reading that offers none is weaker rather than
    invalid, and refusing it would discard a rule a human might have accepted.
    The guidance asks for them; the parse does not require them."""
    anchors: tuple[Anchor, ...] = ()
    revises_rule_id: int | None = None
    """Which catalogue rule this reading claims to revise (D-050). A claim,
    not a key: a human accepting the reading accepts the claim with it, and a
    wrong one is rejectable rather than a corrupted identity. None means the
    reading claims to be new."""
    area: str | None = None
    """The business area this rule belongs to (D-070).

    Structure rather than decoration: the catalogue is the product's business
    documentation, and a documentation set with no organisation is a list
    nobody reads. Grouping by repository or directory would organise it by
    where the code lives, which is the one axis a business reader does not
    care about.

    None is a real value — "unplaced". A rule accepted before areas existed
    has no area, and a reading that cannot see where a rule belongs should say
    nothing rather than invent a heading."""

    relation: Literal["establishes", "revises", "repairs"] = "establishes"
    """How this reading stands to the catalogue (D-065).

    `establishes` — the evidence creates business knowledge that was not there.
    `revises` — it changes a rule already accepted; `revises_rule_id` names it.
    `repairs` — the rule was already true and the code was violating it. A bug
    fix is this case, and before CON-73 a reading had to pretend it was an
    establishment, which is how a repaired defect turned into invented business
    knowledge.

    A repair is still a proposal of the rule, because the valuable case is the
    rule nobody wrote down: "your catalogue is missing this, and production was
    breaking it". What makes it a repair is the claim *about the code*, which
    is why it lives here beside the statement and never inside it — product
    rule 3 keeps implementation evidence distinguishable from the rule."""
    provenance: Literal[ProvenanceType.AI_INTERPRETATION] = (
        ProvenanceType.AI_INTERPRETATION
    )


class Ticket(Frozen):
    """A unit of work, owning exactly one document (D-029).

    `reference` is stored verbatim. The real subjects contain `622`,
    `ADR-0019`, `plans/0015` and `repo#617`, so constraining the format would
    exclude references that already exist. Matching is the resolver's job
    (D-030), not the schema's.

    There is deliberately no title (D-032): it would be unverified free text
    in a product whose taxonomy has no category for one.
    """

    reference: str = Field(min_length=1)
    created_at: datetime


class Document(Frozen):
    """The living draft for a ticket.

    Mutable by design (D-029), but written **only by operations** (D-043). A
    human never edits the body: they comment, validate a rule or reject an
    implementation. Single authorship is what makes every sentence here
    attributable, which product rule 3 requires.

    Authority comes only from a frozen version, never from the draft.
    """

    ticket_reference: str = Field(min_length=1)
    body: str = ""
    created_at: datetime
    updated_at: datetime

    @property
    def is_empty(self) -> bool:
        return not self.body.strip()


class ChangeSelection(Frozen):
    """A closed range: what `target` introduced relative to `base`."""

    kind: Literal[SelectionKind.CHANGE] = SelectionKind.CHANGE
    base: RevisionRef
    target: RevisionRef
    merge_base: str = Field(pattern=SHA_PATTERN)
    """Where the comparison actually started (D-021). Part of the schema
    because a reviewer cannot verify the proposal without it."""

    def key_parts(self) -> tuple[str, ...]:
        return (self.kind.value, self.base.sha, self.target.sha, self.merge_base)


class StateSelection(Frozen):
    """An open range: what a single revision contains."""

    kind: Literal[SelectionKind.STATE] = SelectionKind.STATE
    revision: RevisionRef

    def key_parts(self) -> tuple[str, ...]:
        return (self.kind.value, self.revision.sha)


Selection = Annotated[
    Union[ChangeSelection, StateSelection], Field(discriminator="kind")
]


class CommitRecord(Frozen):
    """One commit. Author and committer are never collapsed (D-023)."""

    sha: str = Field(pattern=SHA_PATTERN)
    author_name: str
    author_email: str
    authored_at: datetime
    committer_name: str
    committer_email: str
    committed_at: datetime
    subject: str
    body: str = ""
    parent_shas: tuple[str, ...] = ()
    is_merge: bool = False


class FileChangeRecord(Frozen):
    """One file's change. A rename keeps both paths (never delete-plus-add)."""

    change_type: str
    path: str = Field(min_length=1)
    previous_path: str | None = None
    similarity: int | None = Field(default=None, ge=0, le=100)


class EvidenceRecord(Frozen):
    """A bounded excerpt, with the means to recover what was left out.

    `reproduce` is what makes bounding legitimate rather than lossy (D-023).
    """

    path: str = Field(min_length=1)
    previous_path: str | None = None
    change_type: str
    provenance: ProvenanceType = ProvenanceType.OBSERVED_FACT
    revision: str = Field(pattern=SHA_PATTERN)
    reproduce: str = Field(min_length=1)
    text: str = ""
    total_lines: int = Field(default=0, ge=0)
    truncated: bool = False
    omitted_lines: int = Field(default=0, ge=0)
    is_binary: bool = False
    omitted_reason: str | None = None


class Completeness(Frozen):
    """What was captured and what was not.

    Present on every proposal so a report can never imply completeness it does
    not have (D-023).
    """

    lines_captured: int = Field(default=0, ge=0)
    lines_omitted: int = Field(default=0, ge=0)
    files_without_excerpt: tuple[str, ...] = ()
    max_lines_per_file: int = Field(gt=0)
    max_lines_total: int = Field(gt=0)

    @property
    def is_complete(self) -> bool:
        return self.lines_omitted == 0 and not self.files_without_excerpt


class Proposal(Frozen):
    """A machine-generated description of a change or a state.

    A *proposal*, never a conclusion: nothing here is official product
    knowledge until a human decides (product rule 4). Review arrives at
    CON-12; until then every proposal is simply unreviewed.
    """

    schema_version: int = SCHEMA_VERSION
    proposal_id: UUID = Field(default_factory=uuid4)
    """Generated per run, never derived (D-025). Re-analysing a range creates
    a new proposal rather than colliding with an approved baseline."""

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    repository: RepositoryRef
    selection: Selection
    commits: tuple[CommitRecord, ...] = ()
    changes: tuple[FileChangeRecord, ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()
    completeness: Completeness | None = None

    @property
    def selection_key(self) -> str:
        """Deterministic key for "every proposal covering this selection".

        Identity is generated so history stays append-only; this key is how
        lookup stays idempotent anyway (D-025). CON-15 compares against the
        last approved baseline sharing this key.
        """
        parts = (self.repository.identity, *self.selection.key_parts())
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    @property
    def is_change(self) -> bool:
        return self.selection.kind is SelectionKind.CHANGE

    @property
    def claim_count(self) -> int:
        """Nothing is claimed beyond observed evidence yet.

        Interpretation arrives at CON-09/CON-10; until then a proposal states
        facts and nothing else.
        """
        return len(self.evidence)
