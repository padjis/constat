"""Landing a ticket's branch when a rule proposal is accepted (D-062).

Two things are under test and they are separable on purpose:

* the **setting**, which decides whether anything is attempted at all, and
* the **merge**, which must refuse rather than resolve whenever the repository
  is not in a state it can land cleanly.

Every refusal gets its own test, and each one asserts that **mainline on the
remote is unchanged** rather than merely that a non-zero code came back. "It
reported a conflict" and "it reported a conflict and pushed nothing" are
different claims, and only the second is the one that matters.

The remote is a bare repository on disk. That is not a stand-in for a real
remote: a push to a bare repository exercises the same ref update, and it
keeps the tests free of a network and of credentials.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.errors import InvalidInput
from constat.git.adapter import discover_repository
from constat.git.merge import merge_ticket_branch, sole_branch
from constat.operations import land_ticket
from constat.store import Registry, Settings, Workspace
from helpers import commit_file, git


# -- fixtures -----------------------------------------------------------------


def _bare_remote(tmp_path: Path, name: str = "origin.git") -> Path:
    bare = tmp_path / name
    bare.mkdir()
    git(bare, "init", "--bare", "--initial-branch=main", "--quiet")
    return bare


def _clone(tmp_path: Path, bare: Path, name: str = "work") -> Path:
    clone = tmp_path / name
    git(tmp_path, "clone", "--quiet", str(bare), name)
    # Written into the clone's own config rather than relied on from the
    # machine: committer_identity reads git's real precedence, so a test that
    # depended on the developer's global config would pass or fail by accident.
    git(clone, "config", "user.name", "Test Fixture")
    git(clone, "config", "user.email", "fixture@example.invalid")
    return clone


@pytest.fixture
def remote_and_clone(tmp_path: Path) -> tuple[Path, Path]:
    """A bare remote with `main`, and a clone with a branch naming ticket 615.

    The branch touches a different file from the one mainline moves on, so the
    default case merges cleanly and a conflict has to be arranged deliberately.
    """
    bare = _bare_remote(tmp_path)
    clone = _clone(tmp_path, bare)

    commit_file(clone, "README.md", "first\n", "First commit")
    git(clone, "push", "--quiet", "origin", "main")

    git(clone, "checkout", "--quiet", "-b", "feat/615-no-ads")
    commit_file(clone, "ads.py", "ENABLED = False\n", "Turn off ads (615)")
    git(clone, "push", "--quiet", "origin", "feat/615-no-ads")

    git(clone, "checkout", "--quiet", "main")
    return bare, clone


def _mainline(bare: Path) -> str:
    return git(bare, "rev-parse", "refs/heads/main")


def _subjects(bare: Path) -> list[str]:
    return git(bare, "log", "--format=%s", "refs/heads/main").splitlines()


# -- the setting --------------------------------------------------------------


class TestSetting:
    def test_defaults_to_off(self, tmp_path: Path) -> None:
        """A workspace that never answered the question does not push.

        The default is the whole safety story for existing workspaces, so it
        is asserted rather than assumed.
        """
        with Workspace.create(tmp_path / "ws") as workspace:
            assert Settings(workspace).merge_on_accept is False

    def test_turning_it_on_and_off(self, tmp_path: Path) -> None:
        with Workspace.create(tmp_path / "ws") as workspace:
            settings = Settings(workspace)
            settings.set_merge_on_accept("on")
            assert settings.merge_on_accept is True
            settings.set_merge_on_accept("off")
            assert settings.merge_on_accept is False

    def test_a_value_that_is_neither_is_refused(self, tmp_path: Path) -> None:
        """Not coerced. `set_merge_on_accept("yes")` must not read as on."""
        with Workspace.create(tmp_path / "ws") as workspace:
            with pytest.raises(InvalidInput):
                Settings(workspace).set_merge_on_accept("yes")
            assert Settings(workspace).merge_on_accept is False


# -- choosing the branch ------------------------------------------------------


class TestSoleBranch:
    def test_local_and_remote_refs_are_one_branch(self) -> None:
        """branches_naming finds the same branch twice. That is not ambiguity."""
        branch, why = sole_branch(
            ("refs/heads/feat/615-no-ads", "refs/remotes/origin/feat/615-no-ads"),
            "main",
        )
        assert branch == "feat/615-no-ads"
        assert why == ""

    def test_two_different_branches_refuse(self) -> None:
        branch, why = sole_branch(
            ("refs/heads/feat/615-no-ads", "refs/heads/fix/615-again"), "main"
        )
        assert branch is None
        assert "several branches" in why

    def test_mainline_is_not_a_candidate(self) -> None:
        """A reference inside mainline's own name must not merge main into main."""
        branch, why = sole_branch(("refs/heads/release-615",), "release-615")
        assert branch is None
        assert "no branch" in why


# -- the merge ----------------------------------------------------------------


class TestMerge:
    def test_a_clean_merge_lands_on_the_remote(
        self, remote_and_clone: tuple[Path, Path]
    ) -> None:
        bare, clone = remote_and_clone
        before = _mainline(bare)

        result = merge_ticket_branch(
            discover_repository(clone),
            alias="237feed",
            branches=("refs/remotes/origin/feat/615-no-ads",),
            target_branch="main",
            reference="615",
        )

        assert result.outcome == "merged"
        assert result.landed
        assert _mainline(bare) != before
        assert "Merge feat/615-no-ads for 615" in _subjects(bare)
        assert "Turn off ads (615)" in _subjects(bare)

    def test_the_registered_repository_is_not_touched(
        self, remote_and_clone: tuple[Path, Path]
    ) -> None:
        """The merge happens in a throwaway clone, never where you work.

        Asserted on the working tree because that is what a user would lose:
        the clone sits on `main` with the branch's file absent, and a merge
        performed in place would create it.
        """
        bare, clone = remote_and_clone
        head_before = git(clone, "rev-parse", "HEAD")

        merge_ticket_branch(
            discover_repository(clone),
            alias="237feed",
            branches=("refs/remotes/origin/feat/615-no-ads",),
            target_branch="main",
            reference="615",
        )

        assert git(clone, "rev-parse", "HEAD") == head_before
        assert not (clone / "ads.py").exists()

    def test_a_conflict_refuses_and_pushes_nothing(
        self, remote_and_clone: tuple[Path, Path]
    ) -> None:
        """The integrity rule of this feature: a conflict leaves mainline alone."""
        bare, clone = remote_and_clone
        # Mainline changes the same file the branch added, in a different way.
        commit_file(clone, "ads.py", "ENABLED = True\n", "Ads back on")
        git(clone, "push", "--quiet", "origin", "main")
        before = _mainline(bare)

        result = merge_ticket_branch(
            discover_repository(clone),
            alias="237feed",
            branches=("refs/remotes/origin/feat/615-no-ads",),
            target_branch="main",
            reference="615",
        )

        assert result.outcome == "conflict"
        assert result.is_refusal
        assert "ads.py" in result.detail
        assert _mainline(bare) == before

    def test_an_already_merged_branch_is_not_a_refusal(
        self, remote_and_clone: tuple[Path, Path]
    ) -> None:
        """Nothing to do is a normal state, not a failure of the acceptance."""
        bare, clone = remote_and_clone
        git(clone, "merge", "--quiet", "--no-ff", "-m", "Merge early", "feat/615-no-ads")
        git(clone, "push", "--quiet", "origin", "main")
        before = _mainline(bare)

        result = merge_ticket_branch(
            discover_repository(clone),
            alias="237feed",
            branches=("refs/remotes/origin/feat/615-no-ads",),
            target_branch="main",
            reference="615",
        )

        assert result.outcome == "already_merged"
        assert result.is_refusal is False
        assert _mainline(bare) == before

    def test_a_local_only_branch_is_refused(
        self, remote_and_clone: tuple[Path, Path]
    ) -> None:
        """A branch that was never pushed cannot be merged on the remote."""
        bare, clone = remote_and_clone
        git(clone, "branch", "feat/616-local-only")
        before = _mainline(bare)

        result = merge_ticket_branch(
            discover_repository(clone),
            alias="237feed",
            branches=("refs/heads/feat/616-local-only",),
            target_branch="main",
            reference="616",
        )

        assert result.outcome == "branch_not_on_remote"
        assert _mainline(bare) == before

    def test_no_remote_is_refused_rather_than_merged_in_place(
        self, tmp_path: Path
    ) -> None:
        """Without a remote there is nowhere to land, and in-place is not it."""
        repo = tmp_path / "solo"
        repo.mkdir()
        git(repo, "init", "--initial-branch=main", "--quiet")
        git(repo, "config", "user.name", "Test Fixture")
        git(repo, "config", "user.email", "fixture@example.invalid")
        commit_file(repo, "README.md", "first\n", "First commit")
        git(repo, "checkout", "--quiet", "-b", "feat/615-no-ads")
        commit_file(repo, "ads.py", "off\n", "Turn off ads (615)")
        git(repo, "checkout", "--quiet", "main")
        head_before = git(repo, "rev-parse", "refs/heads/main")

        result = merge_ticket_branch(
            discover_repository(repo),
            alias="solo",
            branches=("refs/heads/feat/615-no-ads",),
            target_branch="main",
            reference="615",
        )

        assert result.outcome == "no_remote"
        assert git(repo, "rev-parse", "refs/heads/main") == head_before

    def test_without_a_git_identity_nothing_is_committed(
        self, remote_and_clone: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A merge commit attributed to nobody is worse than a refused merge."""
        bare, clone = remote_and_clone
        git(clone, "config", "--unset", "user.name")
        git(clone, "config", "--unset", "user.email")
        # The machine's global config must not stand in for the repository's.
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(bare / "nonexistent-config"))
        monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(bare / "nonexistent-config"))
        before = _mainline(bare)

        result = merge_ticket_branch(
            discover_repository(clone),
            alias="237feed",
            branches=("refs/remotes/origin/feat/615-no-ads",),
            target_branch="main",
            reference="615",
        )

        assert result.outcome == "no_identity"
        assert _mainline(bare) == before

    def test_no_branch_naming_the_ticket_merges_nothing(
        self, remote_and_clone: tuple[Path, Path]
    ) -> None:
        bare, clone = remote_and_clone
        before = _mainline(bare)

        result = merge_ticket_branch(
            discover_repository(clone),
            alias="237feed",
            branches=(),
            target_branch="main",
            reference="999",
        )

        assert result.outcome == "no_branch"
        assert result.is_refusal is False
        assert _mainline(bare) == before


# -- across the registered repositories ---------------------------------------


class TestLandTicket:
    def test_every_repository_is_reported_not_just_the_one_that_merged(
        self, tmp_path: Path, remote_and_clone: tuple[Path, Path]
    ) -> None:
        """A ticket spans repositories, and "nothing here" is information.

        Two are registered and only one knows ticket 615. Reporting one line
        would leave a reviewer unable to tell a one-repository change from a
        merge that reached one of two repositories by mistake.
        """
        bare, clone = remote_and_clone
        other_bare = _bare_remote(tmp_path, "other.git")
        other = _clone(tmp_path, other_bare, "other")
        commit_file(other, "README.md", "unrelated\n", "First commit")
        git(other, "push", "--quiet", "origin", "main")

        with Workspace.create(tmp_path / "ws") as workspace:
            registry = Registry(workspace)
            registry.add(str(clone), alias="237feed", default_branch="main")
            registry.add(str(other), alias="other", default_branch="main")

            landing = land_ticket(workspace, "615")

        assert {r.repository_alias for r in landing.results} == {"237feed", "other"}
        by_alias = {r.repository_alias: r for r in landing.results}
        assert by_alias["237feed"].outcome == "merged"
        assert by_alias["other"].outcome == "no_branch"
        assert landing.refusals == ()
        assert "Turn off ads (615)" in _subjects(bare)

    def test_an_unreadable_repository_is_a_refusal_not_a_clean_no_op(
        self, tmp_path: Path, remote_and_clone: tuple[Path, Path]
    ) -> None:
        """It may hold the branch. Reporting it as "nothing to merge" would
        claim the ticket had landed everywhere when it had not."""
        bare, clone = remote_and_clone

        with Workspace.create(tmp_path / "ws") as workspace:
            Registry(workspace).add(str(clone), alias="237feed", default_branch="main")
            # Registered by path, then moved out from under the registration.
            clone.rename(tmp_path / "moved-away")

            landing = land_ticket(workspace, "615")

        assert [r.outcome for r in landing.results] == ["repository_unreadable"]
        assert len(landing.refusals) == 1
        assert landing.changed_anything is False


# -- through `rule accept` ----------------------------------------------------


def _a_proposal(ws_dir: Path, clone: Path) -> int:
    """A workspace with ticket 615, one undecided reading, and `clone` registered."""
    from constat.models import Anchor, Behaviour, RuleProposal
    from constat.operations import open_run
    from constat.store import RuleProposals, TicketStore

    with Workspace.create(ws_dir) as workspace:
        Registry(workspace).add(str(clone), alias="237feed", default_branch="main")
        TicketStore(workspace).add("615")
        run_id = open_run(workspace, "615", "submit_reply")
        return RuleProposals(workspace).record(
            run_id,
            RuleProposal(
                name="no-advertising-on-content-pages",
                statement="Content pages carry no third-party advertising.",
                behaviours=(Behaviour(description="Serve no ad slot"),),
                anchors=(Anchor(path_glob="ads.py", repository_alias="237feed"),),
            ),
            provider="claude",
            model="opus-5",
        )


def _accept(ws_dir: Path, proposal_id: int) -> int:
    from constat.cli import main

    return main(
        ["--workspace", str(ws_dir), "rule", "accept", str(proposal_id), "--by", "emmanuel"]
    )


def _was_accepted(ws_dir: Path, proposal_id: int) -> bool:
    from constat.store import RuleProposals

    with Workspace.open(ws_dir) as workspace:
        stored = RuleProposals(workspace).find(proposal_id)
        return stored is not None and stored.decision == "accepted"


class TestThroughRuleAccept:
    def test_with_the_setting_off_nothing_is_pushed(
        self, tmp_path: Path, remote_and_clone: tuple[Path, Path], capsys
    ) -> None:
        """The default path is unchanged: acceptance writes to the workspace only."""
        bare, clone = remote_and_clone
        ws_dir = tmp_path / "ws"
        proposal_id = _a_proposal(ws_dir, clone)
        before = _mainline(bare)

        assert _accept(ws_dir, proposal_id) == 0
        assert _mainline(bare) == before
        assert "landing" not in capsys.readouterr().out

    def test_with_the_setting_on_the_branch_lands(
        self, tmp_path: Path, remote_and_clone: tuple[Path, Path]
    ) -> None:
        bare, clone = remote_and_clone
        ws_dir = tmp_path / "ws"
        proposal_id = _a_proposal(ws_dir, clone)
        with Workspace.open(ws_dir) as workspace:
            Settings(workspace).set_merge_on_accept("on")

        assert _accept(ws_dir, proposal_id) == 0
        assert "Turn off ads (615)" in _subjects(bare)

    def test_a_failed_merge_does_not_unwind_the_acceptance(
        self, tmp_path: Path, remote_and_clone: tuple[Path, Path]
    ) -> None:
        """The integrity rule of D-062.

        A git conflict must not discard a human decision. The exit code says
        the merge did not happen; the catalogue says the acceptance did.
        """
        from constat.cli import EXIT_MERGE
        from constat.store import Catalogue

        bare, clone = remote_and_clone
        commit_file(clone, "ads.py", "ENABLED = True\n", "Ads back on")
        git(clone, "push", "--quiet", "origin", "main")
        before = _mainline(bare)

        ws_dir = tmp_path / "ws"
        proposal_id = _a_proposal(ws_dir, clone)
        with Workspace.open(ws_dir) as workspace:
            Settings(workspace).set_merge_on_accept("on")

        assert _accept(ws_dir, proposal_id) == EXIT_MERGE
        assert _mainline(bare) == before
        assert _was_accepted(ws_dir, proposal_id)
        with Workspace.open(ws_dir) as workspace:
            assert [r.name for r in Catalogue(workspace).list()] == [
                "no-advertising-on-content-pages"
            ]
