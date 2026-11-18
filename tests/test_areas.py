"""Business areas are declared, and coverage is measured against them
(CON-88, CON-90).

D-070 made an area free text with no vocabulary, and recorded the drift into
"advertising / ads / monetisation" as expected and unsolved. This is what
solves it, and the solution is deliberately not a vocabulary:

1. **An area is declared by accepting a rule that carries it.** Acceptance
   freezes the area onto the version (D-070), so the catalogue already *is*
   the register. The `area` table holds only areas named ahead of their first
   rule, which is what a baseline needs (CON-89).
2. **A coined area is reported, never refused** — D-064's posture for
   duplicates. A new area is often right, because products grow; what it must
   not be is a silent synonym, since nothing afterwards can tell "ads" from
   "advertising" and merging two areas means renaming across frozen versions.
3. **Coverage is counted in areas, not files** (CON-90). Files are the wrong
   denominator for business documentation: a product can be fully described by
   thirty rules over a thousand files, and a file count would report that as a
   permanent failure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.errors import InvalidInput
from constat.models import Anchor, Example, RuleProposal
from constat.operations import open_run, product_state, render_state, submit_reply
from constat.store import (
    Areas,
    Catalogue,
    Registry,
    Review,
    RuleProposals,
    TicketStore,
    Workspace,
)
from constat.store.areas import MAX_AREA
from constat.store.schema import SCHEMA_VERSION

from helpers import rewind_workspace
from test_runs import distinct_subject


REFERENCE = "615"
STATEMENT = "A transfer above the daily limit is refused."


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        TicketStore(ws).add(REFERENCE)
        yield ws


def _accept(workspace, area: str | None, name: str = "daily-limit") -> int:
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    proposal_id = RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name=name,
            statement=STATEMENT,
            examples=(Example(situation="A transfer of 600", outcome="Refused"),),
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area=area,
        ),
        provider="mcp",
    )
    return Review(workspace).accept(proposal_id, decided_by="a person").rule_id


# -- what "declared" means ----------------------------------------------------


class TestTheDeclaredSet:
    def test_accepting_a_rule_declares_its_area(self, workspace) -> None:
        """The core of the design: the catalogue is the register. If this were
        a separate table a human had to fill first, acceptance would have to
        refuse an undeclared area — blocking a person mid-decision over a
        heading."""
        _accept(workspace, "payments")

        assert Catalogue(workspace).areas() == ("payments",)

    def test_an_unplaced_rule_declares_nothing(self, workspace) -> None:
        _accept(workspace, None)

        assert Catalogue(workspace).areas() == ()

    def test_an_area_can_be_declared_before_it_has_a_rule(self, workspace) -> None:
        """What a baseline needs (CON-89): open an area, then file rules under
        it. Without this an area could only come into being as a side effect of
        a rule, so an area new to the product would have nowhere to exist."""
        Areas(workspace).declare("payouts", declared_by="a person")

        assert Catalogue(workspace).areas() == ("payouts",)

    def test_both_sources_are_one_set(self, workspace) -> None:
        _accept(workspace, "payments")
        Areas(workspace).declare("payouts", declared_by="a person")

        assert Catalogue(workspace).areas() == ("payments", "payouts")

    def test_declaring_an_area_twice_is_refused(self, workspace) -> None:
        """Refused rather than ignored: someone declaring an area that exists
        has a different picture of the catalogue than the catalogue does, and
        succeeding silently would leave them with it."""
        areas = Areas(workspace)
        areas.declare("payouts", declared_by="a person")

        with pytest.raises(InvalidInput, match="already declared"):
            areas.declare("payouts", declared_by="a person")

    def test_declaring_an_area_a_rule_already_carries_is_refused(
        self, workspace
    ) -> None:
        _accept(workspace, "payments")

        with pytest.raises(InvalidInput, match="already exists"):
            Areas(workspace).declare("payments", declared_by="a person")

    def test_an_over_long_name_is_refused(self, workspace) -> None:
        with pytest.raises(InvalidInput, match=str(MAX_AREA)):
            Areas(workspace).declare("x" * (MAX_AREA + 1), declared_by="a person")

    def test_an_empty_name_is_refused(self, workspace) -> None:
        with pytest.raises(InvalidInput, match="needs a name"):
            Areas(workspace).declare("   ", declared_by="a person")

    def test_no_vocabulary_is_imposed(self, workspace) -> None:
        """Constat records what a person calls a part of their product.
        Refusing a heading for not being in a list would be deciding how
        someone's business is organised."""
        Areas(workspace).declare("réglementation carburant", declared_by="a person")

        assert "réglementation carburant" in Catalogue(workspace).areas()

    def test_listing_declared_areas_is_not_the_whole_set(self, workspace) -> None:
        """`Areas.list` is the typed-in subset; `Catalogue.areas` is the
        answer to "which areas exist". A caller must not get the first when it
        wants the second."""
        _accept(workspace, "payments")
        Areas(workspace).declare("payouts", declared_by="a person")

        assert [a.name for a in Areas(workspace).list()] == ["payouts"]
        assert Catalogue(workspace).areas() == ("payments", "payouts")


# -- a coined area is reported ------------------------------------------------


class TestCoinedAreas:
    def _reply(self, area: str) -> str:
        import json

        return json.dumps(
            {
                "rules": [
                    {
                        "name": "ad-free-pages",
                        "statement": "The install pages carry no advertising.",
                        "anchors": [
                            {"path_glob": "rules.py", "repository_alias": "billing"}
                        ],
                        "area": area,
                    }
                ]
            }
        )

    def test_a_new_area_is_reported(self, workspace) -> None:
        _accept(workspace, "advertising")

        result = submit_reply(workspace, REFERENCE, self._reply("ads"))

        assert len(result.new_areas) == 1
        coined, declared = next(iter(result.new_areas.values()))
        assert coined == "ads"
        assert declared == ("advertising",)

    def test_a_new_area_is_still_stored(self, workspace) -> None:
        """Reported, never refused. A new area is often correct, and refusing
        one would make Constat the authority on how a business is organised."""
        _accept(workspace, "advertising")

        result = submit_reply(workspace, REFERENCE, self._reply("ads"))

        assert result.stored_count == 1
        assert result.rejections == ()

    def test_an_existing_area_is_not_reported(self, workspace) -> None:
        _accept(workspace, "advertising")

        result = submit_reply(workspace, REFERENCE, self._reply("advertising"))

        assert result.new_areas == {}

    def test_an_area_declared_ahead_of_time_is_not_reported(
        self, workspace
    ) -> None:
        """The point of declaring one: a baseline opens the area, and the
        readings that follow are not flagged as coining it."""
        Areas(workspace).declare("advertising", declared_by="a person")

        result = submit_reply(workspace, REFERENCE, self._reply("advertising"))

        assert result.new_areas == {}

    def test_the_first_area_in_an_empty_catalogue_is_reported_with_none_known(
        self, workspace
    ) -> None:
        result = submit_reply(workspace, REFERENCE, self._reply("advertising"))

        coined, declared = next(iter(result.new_areas.values()))
        assert (coined, declared) == ("advertising", ())


# -- coverage by area ---------------------------------------------------------


class TestCoverageIsCountedInAreas:
    def test_documented_areas_are_counted_against_declared_ones(
        self, workspace
    ) -> None:
        _accept(workspace, "payments")
        Areas(workspace).declare("payouts", declared_by="a person")

        rendered = render_state(product_state(workspace))

        assert "1 of 2 declared business area(s) hold a rule" in rendered

    def test_an_area_with_no_rule_is_named_as_an_intention(self, workspace) -> None:
        _accept(workspace, "payments")
        Areas(workspace).declare("payouts", declared_by="a person")

        rendered = render_state(product_state(workspace))

        assert "Declared and undocumented: *payouts*" in rendered
        assert "an intention, not documentation" in rendered

    def test_the_file_count_is_demoted_but_kept(self, workspace) -> None:
        """Kept because it is a real figure, demoted because it is the wrong
        denominator: it would report a fully documented product as a
        permanent failure."""
        _accept(workspace, "payments")

        rendered = render_state(product_state(workspace))

        assert "As a technical figure" in rendered
        assert "A low share is expected and is not itself a gap" in rendered

    def test_the_undeclared_part_of_the_product_is_named_as_the_larger_gap(
        self, workspace
    ) -> None:
        """Honesty about the denominator itself: counting declared areas
        flatters a catalogue that has declared two of twenty, so the view says
        what it cannot measure."""
        _accept(workspace, "payments")

        rendered = render_state(product_state(workspace))

        assert "cannot measure what it has never been told about" in rendered

    def test_no_areas_says_so_rather_than_claiming_full_coverage(
        self, workspace
    ) -> None:
        _accept(workspace, None)

        rendered = render_state(product_state(workspace))

        assert "No business areas are declared" in rendered
        assert "not a statement that the product has none" in rendered


# -- the migration ------------------------------------------------------------


class TestMigrationFromSchema15:
    def _at_schema_15(self, home: Path, tmp_path: Path) -> None:
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            _accept(ws, "payments")

        rewind_workspace(home / "workspace.db", 15)

    def test_it_migrates_on_open(self, tmp_path: Path) -> None:
        self._at_schema_15(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            assert ws.schema_version == SCHEMA_VERSION
            assert Areas(ws).list() == ()

    def test_an_area_already_in_use_survives_the_migration(
        self, tmp_path: Path
    ) -> None:
        """Nothing is copied into the new table, and nothing needs to be: the
        area is on the accepted rule, which is what declares it. Copying would
        create a second source of truth that could disagree."""
        self._at_schema_15(tmp_path / "ws", tmp_path)

        with Workspace.open(tmp_path / "ws") as ws:
            assert Catalogue(ws).areas() == ("payments",)
            assert Areas(ws).list() == ()
