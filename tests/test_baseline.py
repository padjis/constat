"""Documenting an area as it already behaves (CON-89, D-080).

A new workspace has an empty catalogue and, before this, no route into it but
one ticket at a time. A baseline is the way in: it describes an area of the
product as it stands, with no change to read.

Four properties carry these tests:

1. **Constat supplies no evidence.** There is no delta, so there is no payload
   worth building — the reader has the repository. What Constat does is what
   only it can: ground the anchors, record which revision was described, store
   the result as proposals nobody has accepted.
2. **Every anchor rests on mainline**, which D-072 already allows. A baseline's
   anchors are the weaker of the two grounds *by construction*, and that is
   correct: nothing here is evidence that anything changed, because nothing
   did.
3. **The revision is recorded.** A claim about the present that cannot name
   the revision it described is not inspectable (product rule 2), and unlike a
   ticket there is no commit set to point at.
4. **Scope is the command's argument.** A reading naming another area is
   refused rather than re-filed, or `baseline advertising` would mean nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constat.ai.guidance import BASELINE, for_baseline
from constat.operations import baseline_area, evidence_for_run
from constat.store import (
    Catalogue,
    Registry,
    Review,
    RuleProposals,
    TicketStore,
    Workspace,
)

from helpers import commit_file, git


AREA = "advertising"


def _shipped_repository(tmp_path: Path, alias: str, files: dict[str, str]) -> Path:
    """A clone whose files are on `origin/main`.

    A bare remote and a push, following `test_mainline_grounding`: mainline is
    the remote-tracking ref (CON-76), so a locally committed file is **not**
    mainline and a baseline would correctly refuse to anchor to it. The first
    version of this fixture committed without pushing and every grounding test
    failed — the code being right about what "shipped" means.
    """
    bare = tmp_path / f"{alias}.git"
    bare.mkdir()
    git(bare, "init", "--bare", "--quiet", "--initial-branch=main")
    clone = tmp_path / alias
    git(tmp_path, "clone", "--quiet", str(bare), alias)
    git(clone, "config", "user.name", "Test Fixture")
    git(clone, "config", "user.email", "fixture@example.invalid")
    for name, content in files.items():
        commit_file(clone, name, content, f"Add {name} ({alias})")
    git(clone, "push", "--quiet", "origin", "main")
    return clone


@pytest.fixture
def workspace(tmp_path: Path):
    """A workspace whose subject has everything on mainline.

    Deliberately not a pending branch: a baseline describes what is shipped,
    so the fixture has to be a product rather than a change in flight.
    """
    with Workspace.create(tmp_path / "ws") as ws:
        subject = _shipped_repository(
            tmp_path,
            "ui",
            {"render.ts": "const ADS = false;\n", "pages.ts": "export const install = 1;\n"},
        )
        Registry(ws).add(str(subject), alias="ui", default_branch="main")
        yield ws


def _reading(area: str | None = AREA, path: str = "pages.ts", **overrides) -> str:
    rule = {
        "name": "install-pages-carry-no-advertising",
        "statement": "The install pages carry no third-party advertising.",
        "examples": [
            {"situation": "A visitor opens an install page", "outcome": "No advert is shown"}
        ],
        "anchors": [{"path_glob": path, "repository_alias": "ui"}],
    }
    if area is not None:
        rule["area"] = area
    rule.update(overrides)
    return json.dumps({"rules": [rule]})


# -- the way in ---------------------------------------------------------------


class TestABaselineNeedsNoTicket:
    def test_a_cold_start_opens_its_own_reference(self, workspace) -> None:
        """The property that makes this the route into an empty workspace.
        Refusing an unknown reference here would make the first baseline in a
        workspace impossible — D-063's posture, for the same reason."""
        result = baseline_area(workspace, AREA, "baseline-advertising", _reading())

        assert result.opened_ticket
        assert TicketStore(workspace).find("baseline-advertising") is not None
        assert result.submitted.stored_count == 1

    def test_an_existing_reference_is_reused(self, workspace) -> None:
        """How a baseline normally arises: an undocumented area is found while
        documenting a change, so the occasioning ticket is the reference."""
        TicketStore(workspace).add("615")

        result = baseline_area(workspace, AREA, "615", _reading())

        assert not result.opened_ticket
        assert result.submitted.stored_count == 1

    def test_the_stored_reading_says_it_came_from_a_baseline(
        self, workspace
    ) -> None:
        baseline_area(workspace, AREA, "615", _reading())

        stored = RuleProposals(workspace).for_ticket("615")[0]
        assert stored.from_baseline
        assert stored.run_kind == "baseline"

    def test_a_submitted_reply_does_not_read_as_a_baseline(
        self, workspace
    ) -> None:
        """The distinction has to cut both ways, or it says nothing."""
        from constat.operations import gather, submit_reply

        TicketStore(workspace).add("615")
        gather(workspace, "615")
        submit_reply(workspace, "615", _reading())

        stored = [
            p for p in RuleProposals(workspace).for_ticket("615") if not p.is_decided
        ]
        assert not any(p.from_baseline for p in stored)


class TestGroundingRestsOnMainline:
    def test_an_anchor_in_mainline_is_accepted(self, workspace) -> None:
        result = baseline_area(workspace, AREA, "615", _reading(path="pages.ts"))

        assert result.submitted.stored_count == 1
        anchor = RuleProposals(workspace).for_ticket("615")[0].proposal.anchors[0]
        assert anchor.grounded_in == "mainline"

    def test_an_anchor_nowhere_in_mainline_is_refused(self, workspace) -> None:
        """The gate still holds with no evidence to check against: a path
        nobody can see is a fabrication whether or not a ticket is involved
        (D-046)."""
        result = baseline_area(workspace, AREA, "615", _reading(path="invented.ts"))

        assert result.submitted.stored_count == 0
        assert "no anchor grounded" in result.submitted.rejections[0].reason

    def test_no_anchor_is_ever_grounded_in_evidence(self, workspace) -> None:
        """By construction, and it matters: a baseline must not claim that the
        reference it is filed under is evidence that anything changed."""
        baseline_area(workspace, AREA, "615", _reading())

        anchors = RuleProposals(workspace).for_ticket("615")[0].proposal.anchors
        assert {a.grounded_in for a in anchors} == {"mainline"}


class TestTheRevisionIsRecorded:
    def test_the_mainline_revision_of_each_repository_is_reported(
        self, workspace
    ) -> None:
        result = baseline_area(workspace, AREA, "615", _reading())

        assert len(result.read_from) == 1
        alias, revision = result.read_from[0]
        assert alias == "ui"
        assert len(revision) == 40

    def test_the_revision_is_stored_as_the_run_s_evidence_pointer(
        self, workspace
    ) -> None:
        """A baseline is a claim about the present; one that cannot say which
        present is not inspectable (product rule 2, D-073)."""
        result = baseline_area(workspace, AREA, "615", _reading())

        commits = evidence_for_run(workspace, result.submitted.run_id)
        assert len(commits) == 1
        assert commits[0].repository_alias == "ui"
        assert commits[0].sha == result.read_from[0][1]

    def test_an_unreadable_repository_is_reported_not_skipped(
        self, workspace, tmp_path
    ) -> None:
        """Silence would make a rule that lives there look wrong rather than
        unreadable: its files are absent from the grounding map, so the rule
        would be refused as ungrounded (D-070)."""
        gone = _shipped_repository(tmp_path, "gone", {"other.ts": "x\n"})
        Registry(workspace).add(str(gone), alias="gone", default_branch="main")
        import shutil

        shutil.rmtree(gone)

        result = baseline_area(workspace, AREA, "615", _reading())

        reported = dict(result.read_from)
        assert reported["gone"].startswith("unreadable:")


class TestScopeIsTheArgument:
    def test_a_reading_naming_another_area_is_refused(self, workspace) -> None:
        result = baseline_area(workspace, AREA, "615", _reading(area="payouts"))

        assert result.submitted.stored_count == 0
        assert len(result.out_of_area) == 1
        assert "payouts" in result.out_of_area[0].reason
        # Not also in the parse's rejections: an out-of-scope reading is not
        # ungrounded or malformed, and reporting it as both would say it twice
        # and mislabel it the second time.
        assert result.submitted.rejections == ()

    def test_the_refusal_is_not_a_silent_refiling(self, workspace) -> None:
        """Re-filing it under the baselined area would store a rule the reading
        never claimed, and the reviewer would decide something nobody said."""
        baseline_area(workspace, AREA, "615", _reading(area="payouts"))

        assert RuleProposals(workspace).for_ticket("615") == ()

    def test_an_omitted_area_is_filled_in(self, workspace) -> None:
        """The command names the area, so a reading need not repeat it."""
        result = baseline_area(workspace, AREA, "615", _reading(area=None))

        assert result.submitted.stored_count == 1
        assert RuleProposals(workspace).for_ticket("615")[0].proposal.area == AREA

    def test_the_declared_area_is_matched_exactly(self, workspace) -> None:
        result = baseline_area(workspace, AREA, "615", _reading(area="Advertising"))

        assert result.submitted.stored_count == 0


class TestNothingIsAccepted:
    def test_a_baseline_writes_no_rule(self, workspace) -> None:
        """The invariant a baseline must not be allowed to bend. It documents
        existing behaviour, which makes it tempting to treat as uncontroversial
        — but a rule enters the catalogue only by a human decision (D-048)."""
        baseline_area(workspace, AREA, "615", _reading())

        assert Catalogue(workspace).list() == ()

    def test_accepting_a_baseline_reading_works_normally(self, workspace) -> None:
        """And when a human does accept it, it is a rule like any other: the
        catalogue must not record which command proposed it."""
        result = baseline_area(workspace, AREA, "615", _reading())
        proposal_id = result.submitted.stored[0]

        Review(workspace).accept(proposal_id, decided_by="a person")

        rule = Catalogue(workspace).find("install-pages-carry-no-advertising")
        assert rule.area == AREA
        assert Catalogue(workspace).areas() == (AREA,)


class TestTheQueueReadsCorrectly:
    def test_the_mainline_ground_is_shown_without_implying_a_deficiency(
        self, workspace, capsys
    ) -> None:
        """On a ticket, "anchored in mainline, not in this ticket's changes" is
        a warning worth making. On a baseline there are no ticket changes, so
        the same wording would imply something was missing: the ground stays
        visible, the clause goes."""
        from constat.cli import main

        baseline_area(workspace, AREA, "615", _reading())
        capsys.readouterr()

        main(["--workspace", str(Path(workspace.path).parent), "rule", "proposals", "615"])

        out = capsys.readouterr().out
        assert "anchored in mainline: pages.ts" in out
        assert "not in this ticket's changes" not in out
        assert "from a baseline" in out


class TestGuidance:
    def test_the_baseline_guidance_names_the_area(self) -> None:
        prompt = for_baseline("advertising")

        assert "advertising" in prompt
        assert BASELINE in prompt

    def test_it_shares_the_rule_writing_guidance(self) -> None:
        """A rule from a baseline and a rule from a ticket go in the same
        catalogue and must mean the same thing (D-045, CON-66). If these
        diverge, the catalogue becomes a record of which command was used."""
        from constat.ai.guidance import ANCHORS, EXAMPLES, WHAT_A_RULE_IS

        prompt = for_baseline("advertising")

        assert WHAT_A_RULE_IS in prompt
        assert EXAMPLES in prompt
        assert ANCHORS in prompt

    def test_it_never_instructs_acceptance(self) -> None:
        prompt = for_baseline("advertising").lower()

        assert "nothing you propose is accepted" in prompt

    def test_it_says_returning_no_rules_is_correct(self) -> None:
        """An area whose code carries no business rule has none to document,
        and inventing some to fill a heading is the failure this exists to
        avoid."""
        assert "no rules is still a correct answer" in for_baseline("x").lower()
