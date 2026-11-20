"""A rule accepted on unshipped work is not current behaviour (CON-96, D-087).

The defect: `rule accept` has no pending/landed guard, so a rule accepted while
its ticket was still unmerged rendered in `constat state` as the product's
current behaviour — a false claim about the present, made by the one command
whose purpose is to state the present (product rule 1).

**The fix is a state in the view, not a gate on the decision.** Refusing the
acceptance would stop a reviewer deciding about work they can see, which is the
normal case; what is wrong is presenting the result as shipped.

Four properties carry these tests:

1. **Verified, not asserted.** The check is whether the commits a rule was
   accepted on (D-073) are ancestors of the repository's mainline. That is a
   stronger claim than a declared release could make — D-085 notes a release's
   ship is asserted and unverifiable across a plural registered set.
2. **In effect unless something says otherwise.** A commit present and not an
   ancestor is that something.
3. **A missing commit is not "not shipped".** A squash-merge or force-push
   destroys the object; the rule may well have shipped, and what is lost is the
   ability to check.
4. **Uncheckable rules stay in the picture and are flagged.** Moving them out
   would assert they are not current behaviour, which is exactly as
   unsupported as asserting they are.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.git.adapter import contains_commit, discover_repository
from constat.models import Anchor, RuleProposal
from constat.operations import open_run, product_state, render_state
from constat.store import Registry, Review, RuleProposals, TicketStore, Workspace

from helpers import commit_file, git


REFERENCE = "615"


def _repository(tmp_path: Path, alias: str) -> Path:
    """A clone with one shipped file on `origin/main` and a pending branch."""
    bare = tmp_path / f"{alias}.git"
    bare.mkdir()
    git(bare, "init", "--bare", "--quiet", "--initial-branch=main")
    clone = tmp_path / alias
    git(tmp_path, "clone", "--quiet", str(bare), alias)
    git(clone, "config", "user.name", "Test Fixture")
    git(clone, "config", "user.email", "fixture@example.invalid")
    commit_file(clone, "rules.py", "LIMIT = 100\n", "Initial limit")
    git(clone, "push", "--quiet", "origin", "main")
    return clone


@pytest.fixture
def shipped(tmp_path: Path):
    """A workspace whose ticket's work is on mainline."""
    clone = _repository(tmp_path, "billing")
    commit_file(clone, "rules.py", "LIMIT = 250\n", "615: raise the limit")
    git(clone, "push", "--quiet", "origin", "main")
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(str(clone), alias="billing", default_branch="main")
        TicketStore(ws).add(REFERENCE)
        yield ws, clone


@pytest.fixture
def pending(tmp_path: Path):
    """A workspace whose ticket's work is on a branch, not mainline."""
    clone = _repository(tmp_path, "billing")
    git(clone, "checkout", "--quiet", "-b", "feat/615-raise-limit")
    commit_file(clone, "rules.py", "LIMIT = 250\n", "615: raise the limit")
    git(clone, "push", "--quiet", "origin", "feat/615-raise-limit")
    git(clone, "checkout", "--quiet", "main")
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(str(clone), alias="billing", default_branch="main")
        TicketStore(ws).add(REFERENCE)
        yield ws, clone


def _gather_and_accept(workspace) -> int:
    """The real path: gather the ticket's evidence, then accept a reading."""
    from constat.operations import gather

    gather(workspace, REFERENCE)
    run_id = open_run(workspace, REFERENCE, "submit_reply")
    from constat.operations import record_run_evidence, collect

    record_run_evidence(workspace, run_id, collect(workspace, REFERENCE))
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
    return Review(workspace).accept(proposal_id, decided_by="a person").rule_id


# -- the ancestry check -------------------------------------------------------


class TestContainsCommit:
    def test_an_ancestor_is_yes(self, tmp_path: Path) -> None:
        clone = _repository(tmp_path, "billing")
        root = git(clone, "rev-list", "--max-parents=0", "HEAD")

        assert contains_commit(discover_repository(str(clone)), root, "HEAD") == "yes"

    def test_a_commit_off_the_line_is_no(self, tmp_path: Path) -> None:
        clone = _repository(tmp_path, "billing")
        git(clone, "checkout", "--quiet", "-b", "side")
        sha = commit_file(clone, "other.py", "x\n", "On a branch")
        git(clone, "checkout", "--quiet", "main")

        assert contains_commit(discover_repository(str(clone)), sha, "main") == "no"

    def test_a_missing_commit_is_unknown_not_no(self, tmp_path: Path) -> None:
        """The distinction the whole feature rests on. A squash-merge destroys
        the commit a rule points at; reporting that as "not shipped" would be
        a false claim about the product, not a cautious one."""
        clone = _repository(tmp_path, "billing")

        assert (
            contains_commit(discover_repository(str(clone)), "0" * 40, "HEAD")
            == "unknown"
        )


# -- the picture --------------------------------------------------------------


class TestShippedWork:
    def test_a_rule_whose_work_has_landed_is_current_behaviour(
        self, pending
    ) -> None:
        """The only path that produces a *verified* rule, and finding that out
        corrected this test.

        A rule accepted **after** its ticket landed can never be verified:
        D-031 means a landed ticket contributes no evidence, so no pointer is
        recorded and there is nothing to check against mainline. The lifecycle
        that works is the real one — accept while the work is pending, then let
        it land.
        """
        workspace, clone = pending
        _gather_and_accept(workspace)

        git(clone, "merge", "--quiet", "--no-ff", "-m", "Merge 615",
            "origin/feat/615-raise-limit")
        git(clone, "push", "--quiet", "origin", "main")

        state = product_state(workspace)

        assert [r.rule.name for r in state.rules] == ["daily-limit"]
        assert state.agreed == ()
        assert state.unverifiable == ()

    def test_it_is_not_flagged_in_the_render(self, pending) -> None:
        workspace, clone = pending
        _gather_and_accept(workspace)
        git(clone, "merge", "--quiet", "--no-ff", "-m", "Merge 615",
            "origin/feat/615-raise-limit")
        git(clone, "push", "--quiet", "origin", "main")

        rendered = render_state(product_state(workspace))

        assert "Agreed, not yet shipped" not in rendered
        assert "Shipping not checked" not in rendered

    def test_a_rule_accepted_after_landing_cannot_be_verified(
        self, shipped
    ) -> None:
        """Stated rather than hidden. D-031 is the cause: a landed ticket
        contributes no evidence, so there is no pointer, so shipping cannot be
        checked — and the rule stays in the picture flagged rather than being
        demoted on the strength of a missing record."""
        workspace, _clone = shipped
        _gather_and_accept(workspace)

        state = product_state(workspace)

        assert [r.rule.name for r in state.rules] == ["daily-limit"]
        assert [r.name for r in state.unverifiable] == ["daily-limit"]
        assert state.agreed == ()


class TestUnshippedWork:
    def test_a_rule_on_an_unmerged_branch_leaves_the_picture(self, pending) -> None:
        """The defect, fixed. Before this it rendered among the rules that
        describe the product, which is a false claim about the present."""
        workspace, _clone = pending
        _gather_and_accept(workspace)

        state = product_state(workspace)

        assert [r.rule.name for r in state.rules] == []
        assert [rule.name for rule, _ in state.agreed] == ["daily-limit"]

    def test_the_unshipped_commits_are_named(self, pending) -> None:
        """Evidence for the claim, as product rule 2 requires: a reviewer can
        check the SHA themselves."""
        workspace, clone = pending
        _gather_and_accept(workspace)

        _rule, unshipped = product_state(workspace).agreed[0]

        assert len(unshipped) == 1
        assert unshipped[0] == git(clone, "rev-parse", "origin/feat/615-raise-limit")

    def test_the_render_says_what_it_checked(self, pending) -> None:
        workspace, _clone = pending
        _gather_and_accept(workspace)

        rendered = render_state(product_state(workspace))

        assert "## Agreed, not yet shipped" in rendered
        assert "not in mainline" in rendered
        assert "what the product does and these describe what it will do" in rendered

    def test_it_moves_into_the_picture_once_the_work_lands(self, pending) -> None:
        """The property that makes this a view rather than a gate: nothing is
        re-accepted, nothing is re-read. The same rule becomes current
        behaviour because the work shipped."""
        workspace, clone = pending
        _gather_and_accept(workspace)
        assert product_state(workspace).agreed != ()

        git(clone, "merge", "--quiet", "--no-ff", "-m", "Merge 615",
            "origin/feat/615-raise-limit")
        git(clone, "push", "--quiet", "origin", "main")

        state = product_state(workspace)
        assert [r.rule.name for r in state.rules] == ["daily-limit"]
        assert state.agreed == ()


class TestCoverageDistinguishesPendingFromUndocumented:
    def test_an_area_whose_rule_is_unshipped_is_not_called_undocumented(
        self, pending
    ) -> None:
        """Found by the demo on first run (CON-20). An area whose only rules
        are agreed-but-unshipped had read as "an area with no rule is an
        intention" — said about an area that had one. The work exists and has
        not landed, which is a third thing."""
        workspace, _clone = pending
        _gather_and_accept(workspace)

        rendered = render_state(product_state(workspace))

        assert "every rule agreed and not yet shipped: *payments*" in rendered
        assert "Declared and undocumented: *payments*" not in rendered

    def test_an_area_with_no_rule_at_all_still_reads_as_undocumented(
        self, pending
    ) -> None:
        """The distinction has to cut both ways."""
        from constat.store import Areas

        workspace, _clone = pending
        Areas(workspace).declare("payouts", declared_by="a person")
        _gather_and_accept(workspace)

        rendered = render_state(product_state(workspace))

        assert "Declared and undocumented: *payouts*" in rendered


class TestWhatCannotBeChecked:
    def test_a_rule_with_no_evidence_pointer_stays_in_the_picture(
        self, shipped
    ) -> None:
        """Accepted before schema 13, or read from a ticket that contributed
        none. Moving it out would assert it is not current behaviour, which is
        exactly as unsupported as asserting it is."""
        workspace, _clone = shipped
        run_id = open_run(workspace, REFERENCE, "submit_reply")
        proposal_id = RuleProposals(workspace).record(
            run_id,
            RuleProposal(
                name="no-evidence",
                statement="A transfer above the daily limit is refused.",
                anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            ),
            provider="mcp",
        )
        Review(workspace).accept(proposal_id, decided_by="a person")

        state = product_state(workspace)

        assert "no-evidence" in [r.rule.name for r in state.rules]
        assert "no-evidence" in [r.name for r in state.unverifiable]
        assert state.agreed == ()

    def test_the_render_explains_why_it_could_not_check(self, shipped) -> None:
        workspace, _clone = shipped
        run_id = open_run(workspace, REFERENCE, "submit_reply")
        proposal_id = RuleProposals(workspace).record(
            run_id,
            RuleProposal(
                name="no-evidence",
                statement="A transfer above the daily limit is refused.",
                anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            ),
            provider="mcp",
        )
        Review(workspace).accept(proposal_id, decided_by="a person")

        rendered = render_state(product_state(workspace))

        assert "## Shipping not checked" in rendered
        assert "left in the picture above" in rendered
        assert "squash-merge or a force-push" in rendered

    def test_a_vanished_commit_is_not_reported_as_unshipped(
        self, pending
    ) -> None:
        """The failure mode that would have been worst: a squash-merge takes
        the commit away, and a naive check reads the missing object as "not in
        mainline" — demoting a rule that actually shipped."""
        workspace, clone = pending
        _gather_and_accept(workspace)

        # Destroy the branch and its commit, as a squash-merge would.
        git(clone, "push", "--quiet", "origin", "--delete", "feat/615-raise-limit")
        git(clone, "branch", "-D", "feat/615-raise-limit")
        git(clone, "reflog", "expire", "--expire=now", "--all")
        git(clone, "gc", "--prune=now", "--quiet")

        state = product_state(workspace)

        assert state.agreed == ()
        assert [r.name for r in state.unverifiable] == ["daily-limit"]
        assert "daily-limit" in [r.rule.name for r in state.rules]
