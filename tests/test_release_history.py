"""The catalogue read as it stood at a past release (CON-87, D-103).

The ticket asked for "the rules **in effect** at a named past release". Two
words of that are not deliverable, and these tests pin what replaced them:

1. **"In effect" is not knowable**, because nothing records that a release
   shipped (CON-86). The view answers "as the catalogue stood" — a fact about
   what people agreed — and never "what the product did", which is `constat
   state` and is verified against mainline (D-087).
2. **"At a release" has no ordering**, because a release name is stored
   verbatim and parsed by nothing (D-102). A release is turned into a *moment*
   — the latest acceptance among its own versions — and the reconstruction is
   anchored to that.

The reconstruction itself carries three properties a naive query would get
wrong, and each has a test: the newest version *at or before* the moment rather
than the newest version; a rule accepted later is absent; a rule retired later
is present.

And one refusal: a release with no versions agreed yields no moment, and does
not fall back to "now".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.errors import NotRegistered
from constat.models import Anchor, RuleProposal
from constat.operations import describe_release_basis, open_run, read_release
from constat.store import (
    CatalogueHistory,
    Registry,
    Releases,
    Review,
    RuleProposals,
    TicketStore,
    Workspace,
)

from test_runs import distinct_subject


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")),
            alias="billing",
        )
        TicketStore(ws).add("402")
        yield ws


def _accept(
    workspace,
    name: str,
    release: str | None = None,
    revises: int | None = None,
    statement: str = "A transfer above the daily limit is refused.",
):
    """Submit a reading and accept it, which is the only way in (D-048)."""
    run_id = open_run(workspace, "402", "submit_reply")
    proposal_id = RuleProposals(workspace).record(
        run_id,
        RuleProposal(
            name=name,
            statement=statement,
            anchors=(Anchor(path_glob="rules.py", repository_alias="billing"),),
            area="payments",
            relation="revises" if revises else "establishes",
            revises_rule_id=revises,
        ),
        provider="mcp",
    )
    return Review(workspace).accept(
        proposal_id, decided_by="A Reviewer", release=release
    )


# -- what was agreed, as a fact -----------------------------------------------


class TestWhatWasAgreed:
    def test_it_lists_the_versions_agreed_for_a_release(self, workspace):
        Releases(workspace).declare("2026.11", "A Reviewer")
        _accept(workspace, "daily-limit", release="2026.11")

        agreed = CatalogueHistory(workspace).agreed_for("2026.11")

        assert [v.name for v in agreed] == ["daily-limit"]

    def test_a_version_agreed_for_another_release_is_not_included(self, workspace):
        releases = Releases(workspace)
        releases.declare("2026.11", "A Reviewer")
        releases.declare("2026.12", "A Reviewer")
        _accept(workspace, "daily-limit", release="2026.11")
        _accept(workspace, "sign-in-locks", release="2026.12")

        agreed = CatalogueHistory(workspace).agreed_for("2026.11")

        assert [v.name for v in agreed] == ["daily-limit"]

    def test_a_release_with_nothing_agreed_is_empty_not_an_error(self, workspace):
        """A release is declared before the work is decided, so this is the
        ordinary first state of every release."""
        Releases(workspace).declare("2026.11", "A Reviewer")

        assert CatalogueHistory(workspace).agreed_for("2026.11") == ()


# -- turning a release into a moment ------------------------------------------


class TestTheMoment:
    def test_it_is_the_latest_acceptance_among_the_release_s_versions(
        self, workspace
    ):
        Releases(workspace).declare("2026.11", "A Reviewer")
        _accept(workspace, "daily-limit", release="2026.11")
        second = _accept(workspace, "sign-in-locks", release="2026.11")

        history = CatalogueHistory(workspace)
        moment = history.moment_of("2026.11")

        latest = workspace.execute(
            "SELECT created_at FROM rule_version WHERE id = ?",
            (second.rule_version_id,),
        ).fetchone()["created_at"]
        assert moment == latest

    def test_a_release_with_nothing_agreed_has_no_moment(self, workspace):
        """And the caller must not substitute one. Falling back to "now" would
        answer a different question with the confidence of this one."""
        Releases(workspace).declare("2026.11", "A Reviewer")

        assert CatalogueHistory(workspace).moment_of("2026.11") is None

    def test_an_unknown_release_has_no_moment_either(self, workspace):
        assert CatalogueHistory(workspace).moment_of("never-declared") is None


# -- the reconstruction -------------------------------------------------------


class TestAsItStood:
    def test_it_shows_the_version_that_stood_not_the_newest(self, workspace):
        """The mistake CON-61 was written to prevent, in a new place. Reading
        the live `rule` table would show today's substance under a past
        heading — and it would look right."""
        releases = Releases(workspace)
        releases.declare("2026.11", "A Reviewer")
        releases.declare("2026.12", "A Reviewer")
        first = _accept(workspace, "daily-limit", release="2026.11")
        _accept(
            workspace,
            "daily-limit",
            release="2026.12",
            revises=first.rule_id,
            statement="A transfer above the daily limit is refused, and the "
            "customer is told why.",
        )

        history = CatalogueHistory(workspace)
        stood = history.as_at(history.moment_of("2026.11"))

        assert [(v.name, v.version_no) for v in stood] == [("daily-limit", 1)]
        assert "told why" not in stood[0].statement

    def test_a_rule_accepted_after_the_moment_is_absent(self, workspace):
        """Absent, not present at version 1. A rule that did not exist yet
        cannot have stood."""
        releases = Releases(workspace)
        releases.declare("2026.11", "A Reviewer")
        releases.declare("2026.12", "A Reviewer")
        _accept(workspace, "daily-limit", release="2026.11")
        _accept(workspace, "sign-in-locks", release="2026.12")

        history = CatalogueHistory(workspace)
        stood = history.as_at(history.moment_of("2026.11"))

        assert [v.name for v in stood] == ["daily-limit"]

    def test_a_rule_retired_after_the_moment_still_stood(self, workspace):
        """Retirement is a dated decision (D-084), so it belongs in a
        point-in-time read like any other. A rule retired today was part of the
        product last month."""
        Releases(workspace).declare("2026.11", "A Reviewer")
        accepted = _accept(workspace, "daily-limit", release="2026.11")
        history = CatalogueHistory(workspace)
        moment = history.moment_of("2026.11")

        Review(workspace).retire(
            accepted.rule_id, reason="replaced by a new policy", decided_by="A Reviewer"
        )

        assert [v.name for v in history.as_at(moment)] == ["daily-limit"]

    def test_a_rule_retired_before_the_moment_is_absent(self, workspace):
        """The other direction, and the one that makes the first meaningful."""
        releases = Releases(workspace)
        releases.declare("2026.11", "A Reviewer")
        releases.declare("2026.12", "A Reviewer")
        retired = _accept(workspace, "old-policy", release="2026.11")
        Review(workspace).retire(
            retired.rule_id, reason="no longer true", decided_by="A Reviewer"
        )
        _accept(workspace, "daily-limit", release="2026.12")

        history = CatalogueHistory(workspace)
        stood = history.as_at(history.moment_of("2026.12"))

        assert [v.name for v in stood] == ["daily-limit"]

    def test_a_version_carries_the_release_it_was_agreed_for(self, workspace):
        """So a rule untouched since an earlier release is not read as part of
        this one. Without it, "as it stood" and "what was agreed" would be
        indistinguishable in the output."""
        releases = Releases(workspace)
        releases.declare("2026.11", "A Reviewer")
        releases.declare("2026.12", "A Reviewer")
        _accept(workspace, "daily-limit", release="2026.11")
        _accept(workspace, "sign-in-locks", release="2026.12")

        history = CatalogueHistory(workspace)
        stood = history.as_at(history.moment_of("2026.12"))

        assert {v.name: v.agreed_for for v in stood} == {
            "daily-limit": "2026.11",
            "sign-in-locks": "2026.12",
        }

    def test_a_version_accepted_with_no_release_still_stood(self, workspace):
        """Nullable is the ordinary case (D-102), so a reconstruction that only
        saw released versions would show almost nothing in a real workspace."""
        Releases(workspace).declare("2026.11", "A Reviewer")
        _accept(workspace, "unreleased-rule")
        _accept(workspace, "daily-limit", release="2026.11")

        history = CatalogueHistory(workspace)
        stood = history.as_at(history.moment_of("2026.11"))

        assert {v.name for v in stood} == {"unreleased-rule", "daily-limit"}
        assert [v.agreed_for for v in stood if v.name == "unreleased-rule"] == [None]


# -- the reading, assembled ---------------------------------------------------


class TestTheReading:
    def test_an_unknown_release_refuses_rather_than_reading_as_empty(
        self, workspace
    ):
        """An empty reading for a typo would say "that release had no rules",
        which is a false answer rather than a refusal."""
        Releases(workspace).declare("2026.11", "A Reviewer")

        with pytest.raises(NotRegistered, match="'2026.11'"):
            read_release(workspace, "2026.12")

    def test_it_separates_what_was_agreed_from_what_stood(self, workspace):
        releases = Releases(workspace)
        releases.declare("2026.11", "A Reviewer")
        releases.declare("2026.12", "A Reviewer")
        _accept(workspace, "daily-limit", release="2026.11")
        _accept(workspace, "sign-in-locks", release="2026.12")

        reading = read_release(workspace, "2026.12")

        assert [v.name for v in reading.agreed] == ["sign-in-locks"]
        assert {v.name for v in reading.stood} == {"daily-limit", "sign-in-locks"}

    def test_a_release_with_nothing_agreed_is_not_reconstructable(self, workspace):
        """**With other rules in the catalogue**, which is the whole point. A
        fallback to "now" is invisible in an empty workspace — a mutation
        survived against the first version of this test, which had nothing
        accepted. The real danger is a release declared last week rendering
        every rule agreed since as though it had contained them."""
        releases = Releases(workspace)
        releases.declare("2026.11", "A Reviewer")
        releases.declare("2026.12", "A Reviewer")
        _accept(workspace, "daily-limit", release="2026.11")
        _accept(workspace, "sign-in-locks")

        reading = read_release(workspace, "2026.12")

        assert reading.is_reconstructable is False
        assert reading.stood == ()

    def test_the_basis_is_stated_with_the_answer(self, workspace):
        """A reader who thinks they are seeing a stored snapshot would be wrong
        twice: nothing was stored, and there is no release boundary."""
        Releases(workspace).declare("2026.11", "A Reviewer")
        _accept(workspace, "daily-limit", release="2026.11")

        said = " ".join(describe_release_basis(read_release(workspace, "2026.11")))

        assert "Nothing was snapshotted at the time" in said
        assert "no release precedes another" in said

    def test_it_never_claims_the_release_shipped(self, workspace):
        """The line this must not cross. Whether a release shipped is not
        recorded (CON-86), and `constat state` is what verifies behaviour."""
        Releases(workspace).declare("2026.11", "A Reviewer")
        _accept(workspace, "daily-limit", release="2026.11")

        said = " ".join(describe_release_basis(read_release(workspace, "2026.11")))

        assert "does not say the release shipped" in said
        assert "constat state" in said

    def test_an_empty_release_says_what_it_does_not_mean(self, workspace):
        Releases(workspace).declare("2026.11", "A Reviewer")

        said = " ".join(describe_release_basis(read_release(workspace, "2026.11")))

        assert "ordinary state rather than a problem" in said
        assert "not a statement that the release contained nothing" in said


# -- the command line ---------------------------------------------------------


class TestTheCommandLine:
    def _home(self, workspace) -> str:
        return str(Path(workspace.path).parent)

    def test_show_renders_both_views(self, workspace, capsys):
        from constat.cli import main

        releases = Releases(workspace)
        releases.declare("2026.11", "A Reviewer")
        releases.declare("2026.12", "A Reviewer")
        _accept(workspace, "daily-limit", release="2026.11")
        _accept(workspace, "sign-in-locks", release="2026.12")
        capsys.readouterr()

        code = main(
            ["--workspace", self._home(workspace), "release", "show", "2026.12"]
        )

        out = capsys.readouterr().out
        assert code == 0
        assert "Agreed for it (1):" in out
        assert "The catalogue as it then stood (2):" in out

    def test_each_reconstructed_version_names_its_own_release(
        self, workspace, capsys
    ):
        from constat.cli import main

        releases = Releases(workspace)
        releases.declare("2026.11", "A Reviewer")
        releases.declare("2026.12", "A Reviewer")
        _accept(workspace, "daily-limit", release="2026.11")
        _accept(workspace, "sign-in-locks", release="2026.12")
        capsys.readouterr()

        main(["--workspace", self._home(workspace), "release", "show", "2026.12"])

        out = capsys.readouterr().out
        assert "[agreed for 2026.11]" in out

    def test_agreed_only_omits_the_reconstruction(self, workspace, capsys):
        from constat.cli import main

        Releases(workspace).declare("2026.11", "A Reviewer")
        _accept(workspace, "daily-limit", release="2026.11")
        capsys.readouterr()

        main(
            [
                "--workspace",
                self._home(workspace),
                "release",
                "show",
                "2026.11",
                "--agreed-only",
            ]
        )

        out = capsys.readouterr().out
        assert "as it then stood" not in out
        assert "does not say the release" in out

    def test_an_unknown_release_exits_non_zero(self, workspace, capsys):
        from constat.cli import main

        code = main(
            ["--workspace", self._home(workspace), "release", "show", "nope"]
        )

        assert code != 0
        assert "no release named 'nope'" in capsys.readouterr().err
