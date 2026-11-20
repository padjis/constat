"""The review queue can be read across the whole workspace (CON-98, D-096).

Every other query in `RuleProposals` is scoped to a ticket, so "what is
waiting?" required already knowing which tickets to name — which is how a
review queue stops being a queue. The states have been stored since CON-51 and
rendered per ticket since CON-52; only the cross-ticket read was missing.

Three properties carry these tests:

1. **No schema change was needed.** The data was there; the question could not
   be asked.
2. **A mistyped filter shows nothing, not everything.** Silently widening to
   the whole workspace is worse than returning none of it.
3. **Awaiting comes first and is the only actionable state**, and the view says
   so rather than leaving a reader to work it out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.models import Anchor, RuleProposal
from constat.operations import open_run
from constat.store import Registry, Review, RuleProposals, TicketStore, Workspace

from test_runs import distinct_subject


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        for reference in ("615", "628"):
            TicketStore(ws).add(reference)
        yield ws


def _record(workspace, reference: str, name: str, area: str | None = "payments") -> int:
    run_id = open_run(workspace, reference, "submit_reply")
    return RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name=name,
            statement="A transfer above the daily limit is refused.",
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area=area,
        ),
        provider="mcp",
    )


# -- the read -----------------------------------------------------------------


class TestReadingAcrossTheWorkspace:
    def test_it_finds_proposals_from_every_ticket(self, workspace) -> None:
        """The question that could not be asked before."""
        _record(workspace, "615", "daily-limit")
        _record(workspace, "628", "first-launch-works")

        found = RuleProposals(workspace).across_workspace()

        assert {p.proposal.name for p in found} == {
            "daily-limit",
            "first-launch-works",
        }

    def test_each_proposal_says_which_ticket_it_belongs_to(self, workspace) -> None:
        """Populated by the query rather than looked up per row: a second
        lookup per proposal would make "what is waiting?" cost one query per
        answer."""
        _record(workspace, "615", "daily-limit")
        _record(workspace, "628", "first-launch-works")

        found = RuleProposals(workspace).across_workspace()

        assert {p.reference for p in found} == {"615", "628"}

    def test_the_reference_is_populated_by_the_per_ticket_query_too(
        self, workspace
    ) -> None:
        """One field, every path, or a caller has to know which query filled
        it in."""
        _record(workspace, "615", "daily-limit")

        for_ticket = RuleProposals(workspace).for_ticket("615")

        assert for_ticket[0].reference == "615"

    def test_an_empty_workspace_returns_nothing(self, workspace) -> None:
        assert RuleProposals(workspace).across_workspace() == ()

    def test_order_is_oldest_first(self, workspace) -> None:
        first = _record(workspace, "615", "one")
        second = _record(workspace, "628", "two")

        found = RuleProposals(workspace).across_workspace()

        assert [p.id for p in found] == [first, second]


class TestFilteringByState:
    def _mixed(self, workspace) -> dict[str, int]:
        waiting = _record(workspace, "615", "waiting")
        accepted = _record(workspace, "615", "accepted-one")
        rejected = _record(workspace, "628", "rejected-one")
        review = Review(workspace)
        review.accept(accepted, decided_by="a person")
        review.reject(rejected, decided_by="a person")
        return {"awaiting": waiting, "accepted": accepted, "rejected": rejected}

    def test_awaiting_covers_anything_undecided(self, workspace) -> None:
        ids = self._mixed(workspace)

        found = RuleProposals(workspace).across_workspace("awaiting")

        assert [p.id for p in found] == [ids["awaiting"]]

    def test_accepted_and_rejected_are_separate(self, workspace) -> None:
        ids = self._mixed(workspace)
        proposals = RuleProposals(workspace)

        assert [p.id for p in proposals.across_workspace("accepted")] == [
            ids["accepted"]
        ]
        assert [p.id for p in proposals.across_workspace("rejected")] == [
            ids["rejected"]
        ]

    def test_no_filter_returns_all_three(self, workspace) -> None:
        self._mixed(workspace)

        assert len(RuleProposals(workspace).across_workspace()) == 3

    def test_an_unknown_state_returns_nothing_not_everything(
        self, workspace
    ) -> None:
        """A mistyped filter silently showing the whole workspace is worse than
        showing none of it: the first reads as an answer."""
        self._mixed(workspace)

        assert RuleProposals(workspace).across_workspace("pending") == ()


# -- the rendering ------------------------------------------------------------


class TestTheCommandLine:
    def _home(self, workspace) -> str:
        return str(Path(workspace.path).parent)

    def test_no_reference_lists_the_whole_workspace(self, workspace, capsys) -> None:
        from constat.cli import main

        _record(workspace, "615", "daily-limit")
        _record(workspace, "628", "first-launch-works")
        capsys.readouterr()

        code = main(["--workspace", self._home(workspace), "rule", "proposals"])

        out = capsys.readouterr().out
        assert code == 0
        assert "2 rule proposal(s) across the workspace" in out
        assert "615" in out and "628" in out

    def test_a_reference_still_gives_the_detailed_view(
        self, workspace, capsys
    ) -> None:
        """The per-ticket view answers "what does this say" and must not be
        replaced by the summary."""
        from constat.cli import main

        _record(workspace, "615", "daily-limit")
        capsys.readouterr()

        main(["--workspace", self._home(workspace), "rule", "proposals", "615"])

        out = capsys.readouterr().out
        assert "A transfer above the daily limit is refused." in out

    def test_proposals_are_grouped_by_state_then_ticket(
        self, workspace, capsys
    ) -> None:
        from constat.cli import main

        _record(workspace, "615", "waiting-one")
        accepted = _record(workspace, "628", "accepted-one")
        Review(workspace).accept(accepted, decided_by="a person")
        capsys.readouterr()

        main(["--workspace", self._home(workspace), "rule", "proposals"])

        out = capsys.readouterr().out
        assert out.index("awaiting (1)") < out.index("accepted (1)")

    def test_the_state_filter_narrows_it(self, workspace, capsys) -> None:
        from constat.cli import main

        _record(workspace, "615", "waiting-one")
        accepted = _record(workspace, "628", "accepted-one")
        Review(workspace).accept(accepted, decided_by="a person")
        capsys.readouterr()

        main(
            [
                "--workspace",
                self._home(workspace),
                "rule",
                "proposals",
                "--state",
                "awaiting",
            ]
        )

        out = capsys.readouterr().out
        assert "waiting-one" in out
        assert "accepted-one" not in out

    def test_it_says_only_awaiting_can_be_acted_on(self, workspace, capsys) -> None:
        """And names the only door to either decision (D-048)."""
        from constat.cli import main

        _record(workspace, "615", "waiting-one")
        capsys.readouterr()

        main(["--workspace", self._home(workspace), "rule", "proposals"])

        out = capsys.readouterr().out
        assert "Only the awaiting ones can be acted on" in out
        assert "rule accept" in out

    def test_an_empty_workspace_does_not_read_as_no_rules_existing(
        self, workspace, capsys
    ) -> None:
        """The distinction this product exists to keep: "nothing has read the
        evidence" is not "there are no rules"."""
        from constat.cli import main

        main(["--workspace", self._home(workspace), "rule", "proposals"])

        out = capsys.readouterr().out
        assert "No rule proposals in this workspace" in out
        assert "not a statement that the product has no rules" in out

    def test_a_baseline_reading_is_marked(self, workspace, capsys) -> None:
        """Compact, but not so compact that it loses what a reviewer needs to
        know before deciding (CON-89)."""
        from constat.cli import main
        from constat.operations import baseline_area

        baseline_area(
            workspace,
            "payments",
            "615",
            '{"rules":[{"name":"from-a-baseline",'
            '"statement":"A transfer above the daily limit is refused.",'
            '"anchors":[{"path_glob":"rules.py","repository_alias":"billing"}]}]}',
        )
        capsys.readouterr()

        main(["--workspace", self._home(workspace), "rule", "proposals"])

        assert "from a baseline" in capsys.readouterr().out
