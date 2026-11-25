"""The state of a ticket is in its path, and a rule's page is named (CON-125).

Asked for in these words: *two sub folders under decisions, one for tickets
reviewed and one for tickets to review*, and *add a title to every decision
page in the navigation panel, the format expected is number-the-title-here.md*.

Both are about one surface: a wiki's own page tree. The index could say which
tickets were waiting and a reader navigating the tree never saw it, and a tree
of `26.md`, `27.md`, `28.md` says nothing about what any of them is.

**The cost is real and stated.** A ticket whose last rule is decided *moves*,
so a URL somebody pasted into a chat stops resolving — and what moves includes
the pages a reviewer wrote. It is a `git mv`, so content and history survive;
the link does not. The alternative, leaving the state out of the path, is what
was there before and is what the division was invisible in.

Five properties carry these tests:

1. **A ticket with rules waiting is under `to-review/`**, with its rules in a
   folder directly beneath its page.
2. **A ticket with nothing waiting is under `reviewed/`.**
3. **Deciding the last rule moves the pair**, reviewer's pages included, and
   leaves nothing behind at the old path.
4. **A rule's page is named `<id>-<name>.md`**, and is found by its id
   whatever it is called — so a page seeded under an older scheme is never
   duplicated.
5. **A verdict is read from either folder**, because a reader must not have to
   know which side a ticket is on.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from constat.operations import gather, publish_document, render_review
from constat.publish import GitPages
from constat.publish.decisions import file_for, folder_for, ticket_page_for
from constat.store import Registry, Review, RuleProposals, TicketStore, Workspace

from helpers import git
from test_acceptance import a_reading, record, register


REFERENCE = "622"


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    bare = tmp_path / "wiki.git"
    bare.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "--quiet", "--initial-branch=main", str(bare)],
        check=True,
        capture_output=True,
    )
    return bare


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        register(ws, tmp_path)
        yield ws


def _clone(tmp_path: Path, wiki: Path, name: str) -> Path:
    clone = tmp_path / name
    git(tmp_path, "clone", "--quiet", str(wiki), str(clone))
    return clone


def _decide_everything(workspace) -> None:
    review = Review(workspace)
    for item in RuleProposals(workspace).undecided(REFERENCE):
        review.accept(item.id, decided_by="a person")


# -- which folder a ticket is in ----------------------------------------------


class TestTheFolderSaysTheState:
    def test_a_ticket_with_rules_waiting_is_to_review(
        self, workspace, wiki, tmp_path
    ):
        record(workspace, a_reading(name="daily-limit"))

        publish_document(workspace, REFERENCE, GitPages(str(wiki)))

        clone = _clone(tmp_path, wiki, "waiting")
        assert (clone / "decisions" / "to-review" / f"{REFERENCE}.md").exists()
        assert not (clone / "decisions" / "reviewed").exists()

    def test_its_rules_sit_directly_beneath_its_page(
        self, workspace, wiki, tmp_path
    ):
        record(workspace, a_reading(name="daily-limit"))

        publish_document(workspace, REFERENCE, GitPages(str(wiki)))

        clone = _clone(tmp_path, wiki, "beneath")
        folder = clone / folder_for(REFERENCE)
        assert [p.name for p in folder.glob("*.md")] == ["1-daily-limit.md"]

    def test_a_ticket_with_nothing_waiting_is_reviewed(
        self, workspace, wiki, tmp_path
    ):
        proposal = record(workspace, a_reading(name="daily-limit"))
        Review(workspace).accept(proposal, decided_by="a person")

        publish_document(workspace, REFERENCE, GitPages(str(wiki)))

        clone = _clone(tmp_path, wiki, "decided")
        assert (clone / "decisions" / "reviewed" / f"{REFERENCE}.md").exists()
        assert not (clone / "decisions" / "to-review").exists()

    def test_a_ticket_that_raised_no_rule_is_reviewed(
        self, workspace, wiki, tmp_path
    ):
        """Nothing is awaiting it, which is the question the folder answers.
        It is not a claim that the ticket was examined and found empty."""
        publish_document(workspace, REFERENCE, GitPages(str(wiki)))

        clone = _clone(tmp_path, wiki, "no-rules")
        assert (clone / "decisions" / "reviewed" / f"{REFERENCE}.md").exists()


# -- the move ------------------------------------------------------------------


class TestDecidingTheLastRuleMovesIt:
    def test_the_page_and_the_folder_both_move(self, workspace, wiki, tmp_path):
        record(workspace, a_reading(name="daily-limit"))
        target = GitPages(str(wiki))
        publish_document(workspace, REFERENCE, target)

        _decide_everything(workspace)
        publish_document(workspace, REFERENCE, target)

        clone = _clone(tmp_path, wiki, "moved")
        assert (clone / ticket_page_for(REFERENCE, decided=True)).exists()
        assert (
            clone / file_for(REFERENCE, "1", "daily-limit", decided=True)
        ).exists()

    def test_nothing_is_left_behind_at_the_old_path(
        self, workspace, wiki, tmp_path
    ):
        """A page at both paths would be a page saying two things at once, and
        the wiki's tree would show the ticket on both sides of the
        division."""
        record(workspace, a_reading(name="daily-limit"))
        target = GitPages(str(wiki))
        publish_document(workspace, REFERENCE, target)

        _decide_everything(workspace)
        publish_document(workspace, REFERENCE, target)

        clone = _clone(tmp_path, wiki, "nothing-behind")
        assert not (clone / ticket_page_for(REFERENCE)).exists()
        assert not (clone / folder_for(REFERENCE)).exists()

    def test_a_reviewers_verdict_moves_with_it_unaltered(
        self, workspace, wiki, tmp_path
    ):
        """The cost of this design, kept as small as it can be: Constat moves
        a file a person wrote. A `git mv` carries the content and the history;
        nothing here reads, rewrites or reformats what they wrote."""
        record(workspace, a_reading(name="daily-limit"))
        target = GitPages(str(wiki))
        publish_document(workspace, REFERENCE, target)

        editor = _clone(tmp_path, wiki, "editor")
        git(editor, "config", "user.name", "A Business Reviewer")
        git(editor, "config", "user.email", "biz@example.invalid")
        page = editor / file_for(REFERENCE, "1", "daily-limit")
        page.write_text(page.read_text() + "1: approved — mine\n")
        git(editor, "add", "-A")
        git(editor, "commit", "--quiet", "-m", "decide")
        git(editor, "push", "--quiet", "origin", "HEAD")
        written = page.read_text()

        _decide_everything(workspace)
        publish_document(workspace, REFERENCE, target)

        clone = _clone(tmp_path, wiki, "carried")
        moved = clone / file_for(REFERENCE, "1", "daily-limit", decided=True)
        assert moved.read_text() == written

    def test_the_move_alone_is_committed(self, workspace, wiki, tmp_path):
        """`git commit` fails with nothing staged, and a republish whose only
        change is the move would otherwise look like a failure."""
        record(workspace, a_reading(name="daily-limit"))
        target = GitPages(str(wiki))
        publish_document(workspace, REFERENCE, target)

        _decide_everything(workspace)
        result = publish_document(workspace, REFERENCE, target)

        assert result.ref.revision is not None
        assert "reviewed" in result.ref.location


# -- the filename --------------------------------------------------------------


class TestTheRulesNameIsInTheFilename:
    def test_it_is_number_then_name(self, workspace, wiki, tmp_path):
        record(workspace, a_reading(name="a-transfer-above-500-is-refused"))

        publish_document(workspace, REFERENCE, GitPages(str(wiki)))

        clone = _clone(tmp_path, wiki, "named")
        assert (
            clone / folder_for(REFERENCE) / "1-a-transfer-above-500-is-refused.md"
        ).exists()

    def test_a_page_seeded_under_the_older_scheme_is_not_duplicated(
        self, workspace, wiki, tmp_path
    ):
        """Found by asking what happens to a target published before the name
        went into the filename. Seeding a second page for the same proposal
        would split a reviewer's verdict from the page Constat reads."""
        record(workspace, a_reading(name="daily-limit"))
        target = GitPages(str(wiki))
        publish_document(workspace, REFERENCE, target)

        editor = _clone(tmp_path, wiki, "rename")
        git(editor, "config", "user.name", "Somebody")
        git(editor, "config", "user.email", "biz@example.invalid")
        git(
            editor, "mv", "--",
            file_for(REFERENCE, "1", "daily-limit"),
            f"{folder_for(REFERENCE)}/1.md",
        )
        git(editor, "commit", "--quiet", "-m", "the older name")
        git(editor, "push", "--quiet", "origin", "HEAD")

        publish_document(workspace, REFERENCE, target)

        clone = _clone(tmp_path, wiki, "not-duplicated")
        assert [p.name for p in (clone / folder_for(REFERENCE)).glob("*.md")] == [
            "1.md"
        ]

    def test_the_ticket_page_links_to_the_named_file(self, workspace):
        record(workspace, a_reading(name="daily-limit"))

        body = render_review(workspace, REFERENCE)

        assert f"({REFERENCE}/1-daily-limit.md)" in body


# -- reading a verdict ---------------------------------------------------------


class TestAVerdictIsReadFromEitherFolder:
    def _write(self, tmp_path: Path, wiki: Path, path: str, name: str) -> None:
        editor = _clone(tmp_path, wiki, name)
        git(editor, "config", "user.name", "A Business Reviewer")
        git(editor, "config", "user.email", "biz@example.invalid")
        page = editor / path
        page.write_text(page.read_text() + "1: approved\n")
        git(editor, "add", "-A")
        git(editor, "commit", "--quiet", "-m", "decide")
        git(editor, "push", "--quiet", "origin", "HEAD")

    def test_from_to_review(self, workspace, wiki, tmp_path):
        record(workspace, a_reading(name="daily-limit"))
        target = GitPages(str(wiki))
        publish_document(workspace, REFERENCE, target)

        self._write(
            tmp_path, wiki, file_for(REFERENCE, "1", "daily-limit"), "w1"
        )

        read = target.read_decisions(REFERENCE)
        assert [d.verdict for d in read.decisions] == ["approved"]

    def test_from_reviewed(self, workspace, wiki, tmp_path):
        """A reviewer can write on a page after the ticket moved — a second
        rule decided later, or a mind changed — and a reader that only looked
        in `to-review/` would report their verdict as absent."""
        proposal = record(workspace, a_reading(name="daily-limit"))
        Review(workspace).accept(proposal, decided_by="a person")
        target = GitPages(str(wiki))
        publish_document(workspace, REFERENCE, target)

        clone = _clone(tmp_path, wiki, "seeded-reviewed")
        folder = clone / folder_for(REFERENCE, decided=True)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "1-daily-limit.md").write_text("## Decisions\n\n")
        git(clone, "config", "user.name", "A Business Reviewer")
        git(clone, "config", "user.email", "biz@example.invalid")
        git(clone, "add", "-A")
        git(clone, "commit", "--quiet", "-m", "seed")
        git(clone, "push", "--quiet", "origin", "HEAD")

        self._write(
            tmp_path,
            wiki,
            file_for(REFERENCE, "1", "daily-limit", decided=True),
            "w2",
        )

        read = target.read_decisions(REFERENCE)
        assert [d.verdict for d in read.decisions] == ["approved"]
