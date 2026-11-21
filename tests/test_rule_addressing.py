"""A rule is named the same way by every command (CON-103).

Two different objects in this CLI are addressed by small integers, and until
this they could be confused silently:

- `rule accept 1` and `rule reject 1` mean **proposal** 1, the number printed
  in `rule proposals`;
- `rule retire 1` and `rule history 1` meant **rule row** 1, a number printed
  nowhere a reviewer looks.

Meanwhile `rule show R-1` worked and `rule history R-1` was a usage error. So a
reviewer who accepted proposal 1, read `R-1` in the output, and ran
`rule history 1` to check their work was shown a different object with nothing
to signal it — and `rule retire 1` would have retired one.

The two coincide **today** only because migration 17 back-filled `ref` as
`'R-' || id`. The schema says in terms that `R-{id}` is a trap and that is why
`ref` is a stored column: `rule` has been rebuilt once already, and a citation
that shifts is not a citation. These tests pin the behaviour before the drift
rather than after it.

Three properties carry these tests:

1. **A citation resolves, everywhere.** `R-7` works wherever a rule is named.
2. **A name resolves, everywhere.** The other form `rule show` already took.
3. **A bare number is refused**, never guessed at — including when a rule with
   that row id exists, which is the case that would otherwise do damage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.models import Anchor, RuleProposal
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


REFERENCE = "615"


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        TicketStore(ws).add(REFERENCE)
        yield ws


def _accept(workspace, name: str) -> int:
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    proposal_id = RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name=name,
            statement="A transfer above the daily limit is refused.",
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area="payments",
        ),
        provider="mcp",
    )
    return Review(workspace).accept(proposal_id, decided_by="a person").rule_id


def _cli(workspace, *argv: str) -> int:
    from constat.cli import main

    return main(["--workspace", str(Path(workspace.path).parent), *argv])


# -- the row id is reachable, but never from the command line -----------------


class TestTheCatalogueCanIdentifyARule:
    def test_a_citation_gives_the_row_id(self, workspace) -> None:
        rule_id = _accept(workspace, "daily-limit")

        assert Catalogue(workspace).identify("R-1") == rule_id

    def test_a_name_gives_the_row_id(self, workspace) -> None:
        rule_id = _accept(workspace, "daily-limit")

        assert Catalogue(workspace).identify("daily-limit") == rule_id

    def test_an_unknown_token_gives_nothing(self, workspace) -> None:
        _accept(workspace, "daily-limit")

        assert Catalogue(workspace).identify("R-99") is None

    def test_it_agrees_with_find(self, workspace) -> None:
        """Two resolvers, one resolution order, or `R-7` means two rules."""
        _accept(workspace, "daily-limit")
        _accept(workspace, "payout-threshold")

        catalogue = Catalogue(workspace)
        for token in ("R-1", "R-2", "daily-limit", "payout-threshold"):
            found = catalogue.find(token)
            by_id = catalogue.by_id(catalogue.identify(token))
            assert found.name == by_id.name


# -- history ------------------------------------------------------------------


class TestHistoryIsAddressedLikeEverythingElse:
    def test_a_citation_works(self, workspace, capsys) -> None:
        _accept(workspace, "daily-limit")
        capsys.readouterr()

        assert _cli(workspace, "rule", "history", "R-1") == 0
        assert "daily-limit" in capsys.readouterr().out

    def test_a_name_works(self, workspace, capsys) -> None:
        _accept(workspace, "daily-limit")
        capsys.readouterr()

        assert _cli(workspace, "rule", "history", "daily-limit") == 0
        assert "daily-limit" in capsys.readouterr().out

    def test_a_bare_number_is_refused(self, workspace, capsys) -> None:
        """Refused even though rule row 1 exists — that is the damaging case.

        A guess would succeed here and be wrong the day a rebuild moves the
        rowids, which is exactly when nobody would be looking for it.
        """
        _accept(workspace, "daily-limit")
        capsys.readouterr()

        assert _cli(workspace, "rule", "history", "1") == 2
        assert "is a number" in capsys.readouterr().err

    def test_the_refusal_names_both_accepted_forms(self, workspace, capsys) -> None:
        _accept(workspace, "daily-limit")
        capsys.readouterr()

        _cli(workspace, "rule", "history", "1")

        err = capsys.readouterr().err
        assert "R-1" in err
        assert "name" in err

    def test_the_output_cites_rather_than_counting_rows(
        self, workspace, capsys
    ) -> None:
        _accept(workspace, "daily-limit")
        capsys.readouterr()

        _cli(workspace, "rule", "history", "R-1")

        assert "version(s) of R-1" in capsys.readouterr().out


# -- retire -------------------------------------------------------------------


class TestRetireIsAddressedLikeEverythingElse:
    def test_a_citation_works(self, workspace, capsys) -> None:
        _accept(workspace, "daily-limit")
        capsys.readouterr()

        code = _cli(
            workspace, "rule", "retire", "R-1", "--reason", "gone", "--by", "a person"
        )

        assert code == 0
        assert "retired: R-1" in capsys.readouterr().out

    def test_a_name_works(self, workspace, capsys) -> None:
        _accept(workspace, "daily-limit")
        capsys.readouterr()

        code = _cli(
            workspace,
            "rule",
            "retire",
            "daily-limit",
            "--reason",
            "gone",
            "--by",
            "a person",
        )

        assert code == 0

    def test_a_bare_number_retires_nothing(self, workspace, capsys) -> None:
        """The one that justifies the ticket: a wrong guess here is destructive.

        Retirement is final by design — there is no reinstatement row — so a
        rule retired by mistake cannot be put back, only superseded by a new
        rule with a new citation.
        """
        _accept(workspace, "daily-limit")
        capsys.readouterr()

        code = _cli(
            workspace, "rule", "retire", "1", "--reason", "gone", "--by", "a person"
        )

        assert code == 2
        assert Catalogue(workspace).find("daily-limit") is not None
        assert "is a number" in capsys.readouterr().err

    def test_an_unknown_citation_retires_nothing(self, workspace, capsys) -> None:
        _accept(workspace, "daily-limit")
        capsys.readouterr()

        code = _cli(
            workspace, "rule", "retire", "R-99", "--reason", "gone", "--by", "a person"
        )

        # 4, not 2: the command was well formed and the catalogue does not hold
        # that rule — the same answer `rule show R-99` gives.
        assert code == 4
        assert Catalogue(workspace).find("daily-limit") is not None


# -- the proposal commands are deliberately unchanged -------------------------


class TestProposalIdsStayNumbers:
    """`accept` and `reject` address a proposal, which *is* numbered.

    The queue prints `[6]`, so the number is the thing a reviewer has in front
    of them. Changing these would break the one addressing scheme that was
    never ambiguous.
    """

    def test_accept_still_takes_a_number(self, workspace, capsys) -> None:
        run_id = open_run(workspace, REFERENCE, "submit_reply")
        proposal_id = RuleProposals(workspace).record(
            run_id,
            RuleProposal(
                name="daily-limit",
                statement="A transfer above the daily limit is refused.",
                anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
                area="payments",
            ),
            provider="mcp",
        )
        capsys.readouterr()

        code = _cli(
            workspace, "rule", "accept", str(proposal_id), "--by", "a person"
        )

        assert code == 0
        assert Catalogue(workspace).find("daily-limit") is not None

    def test_a_citation_is_not_a_proposal(self, workspace) -> None:
        """`rule accept R-1` must not quietly address a rule."""
        with pytest.raises(SystemExit) as raised:
            _cli(workspace, "rule", "accept", "R-1", "--by", "a person")

        assert raised.value.code == 2
