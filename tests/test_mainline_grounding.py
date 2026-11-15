"""An anchor may be grounded in mainline, not only in a ticket's diff (CON-71, D-072).

Two failures made this necessary, both found by running the loop:

* On 615 a real rule went unproposed. The evidence *described* it — the install
  pages deliberately carry no advertising — but their home, `src/pages/`, was
  not in that commit's diff, so the only groundable anchor would have been a
  false claim about where the rule lives.
* On 628, after the ticket landed, **no** rule could be proposed at all. A
  landed ticket contributes no evidence (D-031), so there were no paths to
  anchor to.

Both have the same cause: grounding looked only at the ticket's delta. The
product's mainline is the second ground, and which of the two supports an
anchor is recorded rather than flattened — "the evidence shows this changed"
and "this file exists" are different claims (product rule 3).

**Mainline is not in the payload.** It is grounding data for the parse, not
context for the model: the live workspace holds 922 files across three
repositories, and sending that to a provider on every gather would cost real
money to say what one sentence of guidance says. The tests therefore pass it to
`parse` directly, which is also how `submit_reply` and the provider path do it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from constat.ai.parsing import parse
from constat.ai.redaction import (
    CommitContext,
    FileChange,
    ProviderPayload,
    RepositoryContext,
)
from constat.operations import collect, mainline_files, submit_reply
from constat.store import Catalogue, Registry, Review, RuleProposals, TicketStore, Workspace
from helpers import commit_file, git


REFERENCE = "615"

# The evidence names one changed file. `src/pages/install.ts` is mentioned in
# the commit body but not changed — the 615 shape exactly.
CHANGED = "functions/_lib/render.ts"
ELSEWHERE = "src/pages/install.ts"


def _payload() -> ProviderPayload:
    return ProviderPayload(
        reference=REFERENCE,
        repositories=(
            RepositoryContext(
                alias="web",
                default_branch="main",
                status="pending",
                commits=(
                    CommitContext(
                        sha="a" * 40,
                        subject="Stop loading ads on content pages",
                        body=(
                            "The install pages are rendered separately "
                            "(src/pages/) and deliberately stay ad-free."
                        ),
                        files=(
                            FileChange(
                                path=CHANGED, change_type="modified", diff="d"
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def _reply(path: str, alias: str | None = "web") -> str:
    anchor: dict = {"path_glob": path}
    if alias is not None:
        anchor["repository_alias"] = alias
    return json.dumps(
        {
            "rules": [
                {
                    "name": "install-pages-carry-no-advertising",
                    "statement": "The install pages carry no advertising.",
                    "behaviours": ["An install page shows no ad"],
                    "anchors": [anchor],
                }
            ]
        }
    )


# -- the two grounds ----------------------------------------------------------


class TestTheTwoGrounds:
    def test_an_evidence_path_is_grounded_in_evidence(self) -> None:
        result = parse(_reply(CHANGED), _payload(), {"web": frozenset({CHANGED})})

        assert result.rejections == ()
        assert result.proposals[0].anchors[0].grounded_in == "evidence"

    def test_the_evidence_wins_when_both_would_match(self) -> None:
        """The stronger claim is preferred, not whichever is checked first."""
        mainline = frozenset({CHANGED, ELSEWHERE})

        result = parse(_reply(CHANGED), _payload(), {"web": mainline})

        assert result.proposals[0].anchors[0].grounded_in == "evidence"

    def test_a_path_only_in_mainline_is_grounded_in_mainline(self) -> None:
        """The 615 rule that could not be proposed before."""
        result = parse(_reply(ELSEWHERE), _payload(), {"web": frozenset({ELSEWHERE})})

        assert result.rejections == ()
        anchor = result.proposals[0].anchors[0]
        assert anchor.path_glob == ELSEWHERE
        assert anchor.grounded_in == "mainline"

    def test_a_path_in_neither_is_still_refused(self) -> None:
        """D-049 is not relaxed: an invented path is invented either way."""
        result = parse(_reply("src/pages/nope.ts"), _payload(), {"web": frozenset()})

        assert result.proposals == ()
        reason = result.rejections[0].reason
        assert "no anchor grounded in the evidence supplied" in reason
        assert "mainline" in reason

    def test_mainline_grounding_is_off_by_default(self) -> None:
        """`parse` with no mainline behaves exactly as it did before CON-71, so
        a caller that cannot supply it is not silently weakened."""
        result = parse(_reply(ELSEWHERE), _payload())

        assert result.proposals == ()

    def test_an_unscoped_anchor_may_match_any_repository(self) -> None:
        """Matching how an unscoped anchor already matches everywhere."""
        result = parse(
            _reply(ELSEWHERE, alias=None), _payload(), {"web": frozenset({ELSEWHERE})}
        )

        assert result.proposals[0].anchors[0].grounded_in == "mainline"

    def test_a_scoped_anchor_is_checked_against_that_repository(self) -> None:
        """Scoped to `web`, present only in `api` — not grounded."""
        result = parse(
            _reply(ELSEWHERE),
            _payload(),
            {"web": frozenset(), "api": frozenset({ELSEWHERE})},
        )

        assert result.proposals == ()


# -- it survives storage and acceptance ---------------------------------------


@pytest.fixture
def workspace(tmp_path: Path):
    """A clone with a mainline containing a file no ticket touched."""
    bare = tmp_path / "web.git"
    bare.mkdir()
    git(bare, "init", "--bare", "--quiet", "--initial-branch=main")
    clone = tmp_path / "web"
    git(tmp_path, "clone", "--quiet", str(bare), "web")
    git(clone, "config", "user.name", "Test Fixture")
    git(clone, "config", "user.email", "fixture@example.invalid")
    (clone / "functions" / "_lib").mkdir(parents=True)
    (clone / "src" / "pages").mkdir(parents=True)
    commit_file(clone, CHANGED, "render\n", "Initial render")
    commit_file(clone, ELSEWHERE, "install\n", "Initial install page")
    git(clone, "push", "--quiet", "origin", "main")

    git(clone, "checkout", "--quiet", "-b", "feat/615-no-ads")
    commit_file(clone, CHANGED, "no ads\n", "Stop loading ads (615)")
    git(clone, "push", "--quiet", "origin", "feat/615-no-ads")
    git(clone, "checkout", "--quiet", "main")

    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(str(clone), alias="web", default_branch="main")
        TicketStore(ws).add(REFERENCE)
        yield ws, clone


class TestThroughTheRealPath:
    def test_mainline_files_are_read_from_the_shared_ref(self, workspace) -> None:
        ws, _clone = workspace

        files = mainline_files(ws)

        assert files["web"] == frozenset({CHANGED, ELSEWHERE})

    def test_submit_accepts_a_mainline_anchor(self, workspace) -> None:
        """End to end: the 615 rule now reaches the queue."""
        ws, _clone = workspace

        result = submit_reply(ws, REFERENCE, _reply(ELSEWHERE), provider="mcp")

        assert result.rejections == ()
        assert result.stored_count == 1

    def test_the_ground_is_stored_with_the_reading(self, workspace) -> None:
        ws, _clone = workspace
        result = submit_reply(ws, REFERENCE, _reply(ELSEWHERE), provider="mcp")

        stored = RuleProposals(ws).find(result.stored[0])

        assert stored.proposal.anchors[0].grounded_in == "mainline"

    def test_acceptance_carries_the_ground_to_the_catalogue(self, workspace) -> None:
        ws, _clone = workspace
        result = submit_reply(ws, REFERENCE, _reply(ELSEWHERE), provider="mcp")
        accepted = Review(ws).accept(result.stored[0], decided_by="emmanuel")

        rule = Catalogue(ws).find("install-pages-carry-no-advertising")
        assert rule.anchors[0].grounded_in == "mainline"

        frozen = ws.execute(
            "SELECT grounded_in FROM rule_version_anchor WHERE rule_version_id = ?",
            (accepted.rule_version_id,),
        ).fetchone()
        assert frozen["grounded_in"] == "mainline"

    def test_the_reviewer_is_told_the_anchor_is_weaker(self, workspace, capsys) -> None:
        """An anchor grounded only in mainline means this ticket is not the
        evidence that the rule's home changed. A reviewer deciding has to see
        that (product rule 3)."""
        from constat.cli import _report_proposals

        ws, _clone = workspace
        submit_reply(ws, REFERENCE, _reply(ELSEWHERE), provider="mcp")
        _report_proposals(RuleProposals(ws), REFERENCE, False)

        out = capsys.readouterr().out
        assert "anchored in mainline, not in this ticket's changes" in out
        assert ELSEWHERE in out


# -- the failure that reopened the ticket -------------------------------------


class TestALandedTicketCanStillBeRead:
    def test_a_rule_can_be_proposed_after_the_ticket_lands(self, workspace) -> None:
        """628's failure. A landed ticket contributes no evidence (D-031), so
        before CON-71 every rule for it was refused as ungrounded — the product
        could document a ticket only in the window between merge and release.
        """
        ws, clone = workspace
        git(clone, "merge", "--quiet", "--no-ff", "-m", "Merge 615", "feat/615-no-ads")
        git(clone, "push", "--quiet", "origin", "main")
        git(clone, "fetch", "--quiet", "origin")

        # Nothing is pending any more: the work is in mainline, so there is
        # no evidence to ground against. That is the precondition of the bug.
        assert all(not f.commits for f in collect(ws, REFERENCE))

        result = submit_reply(ws, REFERENCE, _reply(CHANGED), provider="mcp")

        assert result.rejections == ()
        assert result.stored_count == 1
        assert (
            RuleProposals(ws).find(result.stored[0]).proposal.anchors[0].grounded_in
            == "mainline"
        )


# -- what the reader is told --------------------------------------------------


class TestGuidance:
    def test_it_names_both_grounds(self) -> None:
        from constat.ai.guidance import ANCHORS

        assert "a path in the evidence you were given" in ANCHORS
        assert "exists in the product's mainline today" in ANCHORS

    def test_it_says_evidence_is_the_stronger_claim(self) -> None:
        from constat.ai.guidance import ANCHORS

        assert "stronger claim" in ANCHORS

    def test_it_warns_the_file_list_is_not_supplied(self) -> None:
        """A reader that thinks it has been given mainline will guess paths."""
        from constat.ai.guidance import ANCHORS

        assert "not shown mainline's file list" in ANCHORS
