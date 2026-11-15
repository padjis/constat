"""The current picture of the product (CON-78, D-070).

`constat state` reads every accepted rule against the current mainline of every
registered repository. It is the product's business documentation: the
catalogue is the content, this is the reading of it.

Four properties carry these tests:

1. **It is pinned.** Each repository names the ref and the revision it was read
   at. A picture of "now" that cannot say which commit it described is not
   inspectable (product rule 2).
2. **Coverage is stated, not flattered.** A catalogue of two rules over 900
   files describes almost none of the product, and the view says so (D-038).
3. **A rule whose anchors are gone is flagged, never removed.** Nothing leaves
   the catalogue without a human decision (D-048, D-070).
4. **An unreadable repository is reported.** Its rules would otherwise look
   unanchored, which reads as "retire these" — the opposite of what an
   unreadable repository licenses anyone to conclude.

Computed, never stored: nothing here is frozen, so nothing can drift from it.
A stored baseline is CON-15 and deliberately not this.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constat.models import Anchor
from constat.operations import product_state, render_state
from constat.store import Registry, TicketStore, Workspace
from helpers import commit_file, git, seed_rule


@pytest.fixture
def product(tmp_path: Path):
    """Two repositories with a shared remote each, and a workspace.

    Real clones with remote-tracking refs, because mainline is the shared ref
    (D-068) and a fixture without one would exercise the fallback instead.
    """
    aliases = {}
    for alias, filename in (("billing", "rules.py"), ("web", "render.ts")):
        bare = tmp_path / f"{alias}.git"
        bare.mkdir()
        git(bare, "init", "--bare", "--quiet", "--initial-branch=main")
        clone = tmp_path / alias
        git(tmp_path, "clone", "--quiet", str(bare), alias)
        git(clone, "config", "user.name", "Test Fixture")
        git(clone, "config", "user.email", "fixture@example.invalid")
        commit_file(clone, filename, f"# {alias}\n", f"Initial ({alias})")
        commit_file(clone, "README.md", f"{alias}\n", "Readme")
        git(clone, "push", "--quiet", "origin", "main")
        aliases[alias] = clone

    with Workspace.create(tmp_path / "ws") as ws:
        for alias, clone in aliases.items():
            Registry(ws).add(str(clone), alias=alias, default_branch="main")
        TicketStore(ws).add("615")
        yield ws, aliases


# -- it is pinned and it states its coverage ----------------------------------


class TestWhatItReadFrom:
    def test_every_repository_is_pinned_at_a_revision(self, product) -> None:
        workspace, clones = product

        state = product_state(workspace)

        assert {r.alias for r in state.repositories} == {"billing", "web"}
        for repo in state.repositories:
            assert repo.mainline is not None and repo.mainline.ref == "origin/main"
            assert repo.revision == git(clones[repo.alias], "rev-parse", "origin/main")

    def test_the_rendering_names_the_ref_and_the_revision(self, product) -> None:
        workspace, clones = product

        body = render_state(product_state(workspace))

        sha = git(clones["billing"], "rev-parse", "origin/main")
        assert "`origin/main`" in body
        assert sha[:12] in body

    def test_coverage_is_reported_rather_than_flattered(self, product) -> None:
        """The honest headline of a young catalogue is how little it describes."""
        workspace, _clones = product
        seed_rule(
            workspace,
            "daily-limit",
            statement="A transfer above the daily limit is refused.",
            anchors=(("rules.py", "billing"),),
        )

        state = product_state(workspace)
        billing = next(r for r in state.repositories if r.alias == "billing")

        assert billing.file_count == 2
        assert billing.claimed_files == 1
        assert billing.claimed_share == 0.5
        assert "claimed by no rule" in render_state(state)

    def test_an_empty_catalogue_says_so_without_implying_emptiness(
        self, product
    ) -> None:
        workspace, _clones = product

        body = render_state(product_state(workspace))

        assert "catalogue holds no rules" in body
        assert "only as an accepted rule proposal" in body

    def test_no_registered_repositories_is_stated(self, tmp_path: Path) -> None:
        with Workspace.create(tmp_path / "bare-ws") as ws:
            body = render_state(product_state(ws))

        assert "No repositories are registered" in body
        assert "not a statement that the product has no rules" in body


# -- rules, grouped as documentation ------------------------------------------


class TestGrouping:
    def test_rules_are_grouped_by_area_with_unplaced_last(self, product) -> None:
        workspace, _clones = product
        seed_rule(
            workspace,
            "daily-limit",
            statement="A transfer above the daily limit is refused.",
            anchors=(("rules.py", "billing"),),
        )
        workspace.execute("UPDATE rule SET area = 'payments' WHERE name = 'daily-limit'")
        seed_rule(
            workspace,
            "no-ads",
            statement="Content pages carry no advertising.",
            anchors=(("render.ts", "web"),),
        )

        body = render_state(product_state(workspace))

        assert body.index("### payments") < body.index("### (unplaced)")
        assert "daily-limit" in body and "no-ads" in body

    def test_a_rule_spanning_two_repositories_appears_once(self, product) -> None:
        """Product-level, not per-repository (D-070). A rule anchored in two
        places is one rule with two homes, not two entries."""
        workspace, _clones = product
        seed_rule(
            workspace,
            "shared",
            statement="A statement is issued every month.",
            anchors=(("rules.py", "billing"), ("render.ts", "web")),
        )

        state = product_state(workspace)
        item = next(r for r in state.rules if r.rule.name == "shared")

        assert set(item.matched) == {"billing", "web"}
        assert render_state(state).count("**shared**") == 1

    def test_the_matched_paths_are_named(self, product) -> None:
        """Evidence for the claim that the rule still holds."""
        workspace, _clones = product
        seed_rule(
            workspace,
            "daily-limit",
            statement="A transfer above the daily limit is refused.",
            anchors=(("rules.py", "billing"),),
        )

        assert "`rules.py`" in render_state(product_state(workspace))


# -- anchors that no longer exist ---------------------------------------------


class TestRetirementCandidates:
    def test_a_rule_whose_file_is_gone_is_flagged(self, product) -> None:
        workspace, clones = product
        seed_rule(
            workspace,
            "daily-limit",
            statement="A transfer above the daily limit is refused.",
            anchors=(("rules.py", "billing"),),
        )
        git(clones["billing"], "rm", "--quiet", "rules.py")
        git(clones["billing"], "commit", "--quiet", "-m", "Remove the rules module")
        git(clones["billing"], "push", "--quiet", "origin", "main")

        state = product_state(workspace)

        assert [r.rule.name for r in state.unanchored] == ["daily-limit"]
        assert state.holding == ()

    def test_it_is_a_candidate_and_the_wording_says_so(self, product) -> None:
        """Flagged, never retired. A rule leaves the picture only by a human
        decision, and the report must not imply otherwise."""
        workspace, clones = product
        seed_rule(
            workspace,
            "daily-limit",
            statement="A transfer above the daily limit is refused.",
            anchors=(("gone.py", "billing"),),
        )

        body = render_state(product_state(workspace))

        assert "Retirement candidates, not" in body
        assert "human decision" in body
        assert "`gone.py`" in body

    def test_nothing_is_flagged_when_every_anchor_holds(self, product) -> None:
        """Disclosure is a signal, not a section on every document."""
        workspace, _clones = product
        seed_rule(
            workspace,
            "daily-limit",
            statement="A transfer above the daily limit is refused.",
            anchors=(("rules.py", "billing"),),
        )

        assert "anchors are gone" not in render_state(product_state(workspace))


# -- a repository that cannot be read -----------------------------------------


class TestUnreadableRepository:
    def test_it_is_reported_rather_than_skipped(self, product) -> None:
        workspace, clones = product
        clones["billing"].rename(clones["billing"].parent / "moved-away")

        state = product_state(workspace)
        billing = next(r for r in state.repositories if r.alias == "billing")

        assert billing.readable is False
        assert billing.error is not None
        assert "could not be read" in render_state(state)

    def test_the_report_warns_that_it_fakes_a_retirement_candidate(
        self, product
    ) -> None:
        """A rule anchored only in an unreadable repository matches nothing, so
        it appears as a retirement candidate. That is the one reading an
        unreadable repository must not be allowed to produce silently."""
        workspace, clones = product
        seed_rule(
            workspace,
            "daily-limit",
            statement="A transfer above the daily limit is refused.",
            anchors=(("rules.py", "billing"),),
        )
        clones["billing"].rename(clones["billing"].parent / "moved-away")

        body = render_state(product_state(workspace))

        assert "daily-limit" in body
        assert "an unreadable repository above would produce this symptom too" in body


# -- narrowing the view -------------------------------------------------------


class TestTheRepositoryFilter:
    def test_one_repository_can_be_asked_for(self, product) -> None:
        workspace, _clones = product

        state = product_state(workspace, ("billing",))

        assert [r.alias for r in state.repositories] == ["billing"]

    def test_an_unknown_alias_is_refused_not_rendered_empty(
        self, product, tmp_path: Path, capsys
    ) -> None:
        """A mistyped alias rendered as an empty picture would be a claim about
        the product rather than about the typo."""
        from constat.cli import main

        workspace, _clones = product
        # The fixture's connection stays open; the CLI opens its own against
        # the same file, which is what a second process does anyway.
        home = str(tmp_path / "ws")

        code = main(["--workspace", home, "state", "--repo", "nope"])

        assert code != 0
        assert "no registered repository named" in capsys.readouterr().err


# -- the structured form ------------------------------------------------------


class TestJson:
    def test_it_carries_the_revision_and_the_holds_flag(
        self, product, tmp_path: Path, capsys
    ) -> None:
        workspace, clones = product
        seed_rule(
            workspace,
            "daily-limit",
            statement="A transfer above the daily limit is refused.",
            anchors=(("rules.py", "billing"),),
        )
        from constat.cli import main

        home = str(tmp_path / "ws")
        capsys.readouterr()

        assert main(["--workspace", home, "state", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)

        billing = next(r for r in payload["repositories"] if r["alias"] == "billing")
        assert billing["revision"] == git(clones["billing"], "rev-parse", "origin/main")
        rule = next(r for r in payload["rules"] if r["name"] == "daily-limit")
        assert rule["holds"] is True
        assert rule["matched"]["billing"] == ["rules.py"]
