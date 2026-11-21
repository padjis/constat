"""A frozen version's behaviours and anchors can be read back (CON-61).

`rule_version_behaviour` and `rule_version_anchor` have been written on every
acceptance since CON-44 and nothing ever read them. `rule history` showed a
version's name, statement, decider and (since CON-79) its commits, and stopped
— so CON-14's criterion, "previous content remains recoverable", held for the
label and not for the substance. The data was on disk and unreachable.

**The property that matters is where the substance comes from.** `rule` holds
the current state and is rewritten by each acceptance; the version tables are
what a human agreed to at the time. Reading the live tables here would make
every historical version display the newest one's behaviours — and it would
look entirely right. `test_an_earlier_version_keeps_its_own_substance` is the
test that catches that, and it is the reason this file exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.models import Anchor, Behaviour, RuleProposal
from constat.operations import open_run
from constat.store import (
    Catalogue,
    Registry,
    Review,
    RuleProposals,
    TicketStore,
    Workspace,
)

from test_runs import distinct_subject


REFERENCE = "622"


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        TicketStore(ws).add(REFERENCE)
        yield ws


def _record(
    workspace,
    behaviours: tuple[str, ...],
    anchors: tuple[Anchor, ...],
    area: str | None = "payments",
    revises: int | None = None,
) -> int:
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    return RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name="daily-limit",
            statement="A transfer above the daily limit is refused.",
            behaviours=tuple(Behaviour(description=b) for b in behaviours),
            anchors=anchors,
            area=area,
            relation="revises" if revises else "establishes",
            revises_rule_id=revises,
        ),
        provider="mcp",
        revises_rule_id=revises,
    )


def _anchor(path: str, ground: str | None = "evidence") -> Anchor:
    return Anchor(path_glob=path, repository_alias="billing", grounded_in=ground)


# -- the substance is readable ------------------------------------------------


class TestReadingAVersion:
    def test_behaviours_come_back(self, workspace) -> None:
        review = Review(workspace)
        proposal = _record(
            workspace, ("Refuse it", "Explain the limit"), (_anchor("rules.py"),)
        )
        rule_id = review.accept(proposal, decided_by="emmanuel").rule_id

        version = review.versions(rule_id)[0]

        assert version["behaviours"] == ("Refuse it", "Explain the limit")

    def test_anchors_come_back_with_their_scope_and_ground(self, workspace) -> None:
        """`grounded_in` is part of what was accepted (D-072): looking back, a
        reviewer must be able to tell "the evidence showed this changed" from
        "this file existed"."""
        review = Review(workspace)
        proposal = _record(
            workspace,
            ("Refuse it",),
            (_anchor("rules.py", "mainline"),),
        )
        rule_id = review.accept(proposal, decided_by="emmanuel").rule_id

        anchors = review.versions(rule_id)[0]["anchors"]

        assert len(anchors) == 1
        assert anchors[0].path_glob == "rules.py"
        assert anchors[0].repository_alias == "billing"
        assert anchors[0].grounded_in == "mainline"

    def test_a_version_with_neither_says_so_rather_than_failing(
        self, workspace
    ) -> None:
        """A rule with no behaviours is a real state, and the audit view has to
        render it rather than treat the absence as an error."""
        review = Review(workspace)
        proposal = _record(workspace, (), (_anchor("rules.py"),))
        rule_id = review.accept(proposal, decided_by="emmanuel").rule_id

        version = review.versions(rule_id)[0]

        assert version["behaviours"] == ()
        assert len(version["anchors"]) == 1


# -- the property this file exists for ----------------------------------------


class TestHistoryIsNotRewritten:
    def test_an_earlier_version_keeps_its_own_substance(self, workspace) -> None:
        """The whole point of CON-61, and the mutation that would pass review.

        Reading behaviours from `rule` instead of `rule_version_behaviour`
        gives every version the newest one's substance. The output looks
        plausible, the history is a lie, and only a two-version test notices.
        """
        review = Review(workspace)
        first = _record(
            workspace,
            ("Refuse it", "Explain the limit"),
            (_anchor("rules.py"), _anchor("limits.py")),
        )
        rule_id = review.accept(first, decided_by="emmanuel").rule_id

        second = _record(
            workspace,
            ("Refuse it and notify the account holder",),
            (_anchor("rules.py"),),
            area="transfers",
            revises=rule_id,
        )
        review.accept(second, decided_by="emmanuel")

        v1, v2 = review.versions(rule_id)

        assert v1["behaviours"] == ("Refuse it", "Explain the limit")
        assert v2["behaviours"] == ("Refuse it and notify the account holder",)
        assert [a.path_glob for a in v1["anchors"]] == ["rules.py", "limits.py"]
        assert [a.path_glob for a in v2["anchors"]] == ["rules.py"]
        assert (v1["area"], v2["area"]) == ("payments", "transfers")

    def test_the_live_rule_follows_the_newest_version_only(self, workspace) -> None:
        """`rule` is the working view and is *supposed* to move. The test above
        is only meaningful if this one is also true."""
        from constat.store import Catalogue

        review = Review(workspace)
        first = _record(workspace, ("Refuse it",), (_anchor("rules.py"),))
        rule_id = review.accept(first, decided_by="emmanuel").rule_id
        second = _record(
            workspace, ("Refuse it and notify",), (_anchor("rules.py"),), revises=rule_id
        )
        review.accept(second, decided_by="emmanuel")

        current = Catalogue(workspace).find("daily-limit")

        assert [b.description for b in current.behaviours] == ["Refuse it and notify"]


# -- what a reviewer sees -----------------------------------------------------


class TestRuleHistoryOutput:
    def test_it_prints_the_substance_of_each_version(
        self, tmp_path: Path, capsys
    ) -> None:
        from constat.cli import main

        home = tmp_path / "cli-ws"
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            review = Review(ws)
            proposal = _record(
                ws, ("Refuse it", "Explain the limit"), (_anchor("rules.py"),)
            )
            rule_id = review.accept(proposal, decided_by="emmanuel").rule_id

        capsys.readouterr()
        with Workspace.open(home) as ws:
            cite = Catalogue(ws).by_id(rule_id).ref
        main(["--workspace", str(home), "rule", "history", cite])
        out = capsys.readouterr().out

        assert "behaviours (2):" in out
        assert "- Explain the limit" in out
        assert "anchors (1):" in out
        assert "rules.py  [billing, grounded in evidence]" in out

    def test_an_empty_evidence_pointer_does_not_claim_a_reason(
        self, tmp_path: Path, capsys
    ) -> None:
        """Two states look identical from zero rows: a version accepted before
        schema 13, and one whose run read nothing because the ticket had
        landed. The output must not assert either (D-031's posture)."""
        from constat.cli import main

        home = tmp_path / "cli-ws-2"
        with Workspace.create(home) as ws:
            Registry(ws).add(
                str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")),
                alias="billing",
            )
            TicketStore(ws).add(REFERENCE)
            proposal = _record(ws, ("Refuse it",), (_anchor("rules.py"),))
            rule_id = Review(ws).accept(proposal, decided_by="emmanuel").rule_id

        capsys.readouterr()
        with Workspace.open(home) as ws:
            cite = Catalogue(ws).by_id(rule_id).ref
        main(["--workspace", str(home), "rule", "history", cite])
        out = capsys.readouterr().out

        assert "gathered none, or it predates evidence pointers" in out
