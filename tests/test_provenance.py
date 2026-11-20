"""Every claim carries a provenance type, and the gaps are named (CON-10, D-094).

`PRODUCT_SPEC` § 6.3 #3 is the last MVP acceptance criterion with a real gap:
"the report links each important claim to inspectable evidence, or clearly
labels it as an inference". Seven provenance types were declared at CON-07 and
two were ever written.

The useful half of this ticket turned out to be **naming what is not
produced**. `models.ProvenanceType` promised that CON-10 would "extend the
taxonomy"; three of its members have no producer at all, and a reader who finds
`assumption` in the taxonomy is entitled to know nothing writes it.

Three properties carry these tests:

1. **The legend covers every member of the taxonomy.** Generated from the two
   dictionaries, so a type that gains or loses a producer cannot leave a legend
   behind describing the old shape.
2. **`unknown` has a producer now.** An unreadable repository is tagged, because
   "could not be read" and "contributed nothing" are different claims and only
   one of them is a finding.
3. **A rule's parts do not share one provenance**, and the document says so: the
   statement is a reading, the anchors are paths that exist, and a message is a
   quotation whose truth is checkable and unchecked here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.ai import Interpretation
from constat.models import Anchor, Example, Message, ProvenanceType, RuleProposal
from constat.operations import (
    PRODUCED_PROVENANCE,
    UNPRODUCED_PROVENANCE,
    collect,
    gather,
    provenance_legend,
    render,
)
from constat.store import Registry, TicketStore, Workspace

from helpers import commit_file, git
from test_runs import distinct_subject


REFERENCE = "615"


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        TicketStore(ws).add(REFERENCE)
        yield ws


def _reading(messages: tuple[str, ...] = ()) -> Interpretation:
    return Interpretation(
        provider="mcp",
        model="claude-opus-5",
        proposals=(
            RuleProposal(
                name="daily-limit",
                statement="A transfer above the daily limit is refused.",
                examples=(Example(situation="A transfer of 600", outcome="Refused"),),
                messages=tuple(Message(text=m) for m in messages),
                anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
                area="payments",
            ),
        ),
    )


# -- the legend ---------------------------------------------------------------


class TestTheLegend:
    def test_it_covers_every_member_of_the_taxonomy(self) -> None:
        """The property that stops the two halves drifting apart. A type added
        to `ProvenanceType` with no entry in either dictionary fails here,
        which is the only way the legend stays true."""
        text = "\n".join(provenance_legend())

        for member in ProvenanceType:
            assert f"`{member.value}`" in text, member.value

    def test_the_two_dictionaries_partition_the_taxonomy(self) -> None:
        """No type is in both, and none is in neither."""
        produced = set(PRODUCED_PROVENANCE)
        unproduced = set(UNPRODUCED_PROVENANCE)

        assert produced & unproduced == set()
        assert produced | unproduced == {m.value for m in ProvenanceType}

    def test_it_says_which_types_nothing_writes(self) -> None:
        """The useful half of the ticket. An enum member nobody writes is a
        promise the code does not keep."""
        text = "\n".join(provenance_legend())

        assert "produced by nothing today" in text
        for name in ("test_evidence", "requirement_ref", "assumption"):
            assert f"`{name}`" in text

    def test_it_gives_a_reason_for_each_gap(self) -> None:
        """A gap with no reason reads as an oversight rather than a limit."""
        assert "nothing runs tests" in UNPRODUCED_PROVENANCE["test_evidence"]
        assert "CON-18" in UNPRODUCED_PROVENANCE["requirement_ref"]
        assert "reading or an admission" in UNPRODUCED_PROVENANCE["assumption"]


class TestTheDocumentCarriesIt:
    def test_the_legend_is_in_every_document(self, workspace) -> None:
        """Unconditional, because a document whose labels are explained only
        sometimes teaches a reader to ignore them."""
        gather(workspace, REFERENCE)

        body = render(REFERENCE, collect(workspace, REFERENCE))

        assert "## How to read this" in body
        assert "`observed_fact`" in body

    def test_it_is_there_with_no_interpretation_at_all(self, workspace) -> None:
        """The evidence-only document is the one most likely to be read as
        plain fact, so it needs the legend most."""
        gather(workspace, REFERENCE)

        body = render(REFERENCE, collect(workspace, REFERENCE), None)

        assert "## How to read this" in body

    def test_it_comes_last(self, workspace) -> None:
        """Reference rather than content: it must not push the business view
        down the page."""
        gather(workspace, REFERENCE)

        body = render(REFERENCE, collect(workspace, REFERENCE))

        assert body.index("## How to read this") > body.index("## Evidence")


# -- unknown has a producer ---------------------------------------------------


class TestUnknownIsProduced:
    def test_an_unreadable_repository_is_tagged(self, workspace, tmp_path) -> None:
        """`unknown`'s first real producer. "Could not be read" and
        "contributed nothing" are different claims, and only the second is a
        finding (product rule 1)."""
        import shutil

        gone = distinct_subject(tmp_path, "gone", "x\n")
        Registry(workspace).add(str(gone), alias="gone")
        shutil.rmtree(gone)

        body = render(REFERENCE, collect(workspace, REFERENCE))

        assert "`unknown` — could not be read" in body
        assert "Nothing below is a statement about this repository" in body

    def test_a_readable_repository_is_not_tagged_unknown(self, workspace) -> None:
        """The distinction has to cut both ways or it says nothing."""
        gather(workspace, REFERENCE)

        body = render(REFERENCE, collect(workspace, REFERENCE))

        assert "`unknown` — could not be read" not in body


# -- a rule's parts differ ----------------------------------------------------


class TestARulesPartsDoNotShareOneProvenance:
    def test_the_statement_is_named_as_a_reading(self, workspace) -> None:
        gather(workspace, REFERENCE)

        body = render(REFERENCE, collect(workspace, REFERENCE), _reading())

        assert "`ai_interpretation`" in body
        assert "statement, behaviours and examples are a reading" in body

    def test_anchors_are_named_as_observed(self, workspace) -> None:
        """An anchor is a path somebody can look at, which is a different kind
        of claim from the sentence about it."""
        gather(workspace, REFERENCE)

        body = render(REFERENCE, collect(workspace, REFERENCE), _reading())

        assert "Anchors are `observed_fact`" in body

    def test_a_message_is_named_as_an_unchecked_quotation(self, workspace) -> None:
        """The honest label. A message's truth is mechanically checkable
        (CON-91) and this document has not checked it, so it must not be
        presented as verified."""
        gather(workspace, REFERENCE)

        body = render(
            REFERENCE,
            collect(workspace, REFERENCE),
            _reading(messages=("Failed to start upload",)),
        )

        assert "quotations of what the" in body
        assert "this document has not" in body

    def test_a_rule_with_no_messages_makes_no_claim_about_them(
        self, workspace
    ) -> None:
        gather(workspace, REFERENCE)

        body = render(REFERENCE, collect(workspace, REFERENCE), _reading())

        assert "this document has not" not in body
