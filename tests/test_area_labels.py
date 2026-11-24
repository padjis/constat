"""A rule is shown under a short per-area label (CON-118).

`AR-2` on the *article retention* page, beside the citation it belongs to.
Asked for so a reader of one area's page sees rules numbered within that area
rather than scattered across a flat sequence.

**Derived at render, never stored, and never a citation.** D-081 made `R-7`
flat because an area is mutable by design (D-079) and an identifier encoding
a mutable fact becomes a false claim the moment that fact changes. That
reasoning is untouched: the label is recomputed on every render and is
allowed to change, while `R-7` is what the rule is called, what every command
takes, and what survives the rule being re-filed.

Four properties carry these tests:

1. **Deterministic.** The mapping depends on the set of areas and nothing
   else, so two runs over one catalogue agree.
2. **Collisions are broken, not ignored.** Two areas cannot share a prefix.
3. **A rule with no area gets no label**, because inventing a prefix for the
   absence of an area is the false claim D-081 names.
4. **It resolves.** A reader who quotes what the page showed them can type it
   back, or the label is decoration (CON-81's argument, applied to a label).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.operations import (
    area_labels,
    area_prefixes,
    gather,
    product_state,
    render_area,
)
from constat.store import Registry, Review, TicketStore, Workspace

from test_acceptance import a_reading, record
from test_runs import distinct_subject


@pytest.fixture
def subject(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        TicketStore(ws).add("622")
        gather(ws, "622")
        yield ws


def _accept_in(workspace, name: str, area: str | None) -> None:
    proposal = record(workspace, a_reading(name=name))
    Review(workspace).accept(proposal, decided_by="a person")
    workspace.execute("UPDATE rule SET area = ? WHERE name = ?", (area, name))


class TestThePrefix:
    def test_initials_for_a_multi_word_area(self) -> None:
        assert area_prefixes(("article retention",))["article retention"] == "AR"

    def test_two_letters_for_a_single_word_area(self) -> None:
        assert area_prefixes(("advertising",))["advertising"] == "AD"

    def test_two_areas_cannot_share_a_prefix(self) -> None:
        """Lengthened from the area's own letters rather than numbered: a
        number beside a number reads as part of it."""
        found = area_prefixes(("article pages", "article photos"))

        assert len(set(found.values())) == 2

    def test_it_is_deterministic(self) -> None:
        areas = ("app install", "article pages", "advertising")

        assert area_prefixes(areas) == area_prefixes(areas)

    def test_an_area_with_no_letters_still_gets_one(self) -> None:
        assert area_prefixes(("123",))["123"] == "X"


class TestTheLabel:
    def test_a_rule_is_numbered_within_its_area(self, subject) -> None:
        _accept_in(subject, "daily-limit", "payments")
        _accept_in(subject, "payout-threshold", "payments")

        labels = area_labels(product_state(subject))

        assert sorted(labels.values()) == ["PA-1", "PA-2"]

    def test_an_unplaced_rule_has_none(self, subject) -> None:
        """It is not in an area, and a prefix for the absence of one would be
        the false claim D-081 names."""
        _accept_in(subject, "daily-limit", None)

        assert area_labels(product_state(subject)) == {}

    def test_the_page_shows_the_label_and_the_citation(self, subject) -> None:
        """The label leads because it is what a reader of this page sees
        around them; the citation follows because it is what survives."""
        _accept_in(subject, "daily-limit", "payments")
        state = product_state(subject)

        body = render_area("payments", state.by_area()["payments"], area_labels(state))

        assert "`PA-1` (`R-1`)" in body

    def test_without_labels_the_citation_stands_alone(self, subject) -> None:
        """An area page rendered without the mapping is still correct, which
        is what keeps the label an aid rather than a dependency."""
        _accept_in(subject, "daily-limit", "payments")
        state = product_state(subject)

        body = render_area("payments", state.by_area()["payments"])

        assert "`R-1`" in body
        assert "PA-1" not in body


class TestItResolves:
    def test_a_label_names_the_same_rule_as_its_citation(
        self, subject, capsys
    ) -> None:
        from constat.cli import main

        _accept_in(subject, "daily-limit", "payments")
        home = str(Path(subject.path).parent)
        capsys.readouterr()

        assert main(["--workspace", home, "rule", "history", "PA-1"]) == 0
        by_label = capsys.readouterr().out
        assert main(["--workspace", home, "rule", "history", "R-1"]) == 0

        assert by_label == capsys.readouterr().out

    def test_an_unknown_label_is_refused(self, subject, capsys) -> None:
        from constat.cli import main

        _accept_in(subject, "daily-limit", "payments")
        capsys.readouterr()

        code = main(
            ["--workspace", str(Path(subject.path).parent),
             "rule", "history", "ZZ-9"]
        )

        assert code == 4
