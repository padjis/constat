"""The catalogue itself can be published (CON-106).

Found by trying to publish and having nothing worth publishing. `publish` was
ticket-scoped, and a ticket document is an *impact* view: it answers which
rules have anchors in what that ticket changed (D-035, D-038). A landed ticket
or one opened for a baseline contributes no evidence in that window, so it
honestly reports "none" — which meant a workspace could hold an accepted
catalogue that `publish` could not reach, and the audience the documentation
is *for* had nowhere to read it.

The document was never wrong. The catalogue had no publication at all.

Five properties carry these tests:

1. **`publish` with no reference publishes the catalogue**, as `constat state`
   renders it.
2. **Publishing a ticket refreshes the catalogue too**, so publishing always
   leaves it current — without losing the ticket's evidence page, which is the
   other half of product rule 8.
3. **A rule with no ticket of its own reaches the page.** The case that
   started this: rules accepted from a baseline.
4. **The page says nothing on it can be decided**, because it shows accepted
   rules and a reviewer writing a verdict there would write into a page that
   is rewritten in full on the next publish.
5. **The page name is reserved**, so a ticket cannot be published over the
   catalogue.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.operations import gather, publish_document, publish_state
from constat.publish import STATE_REFERENCE, GitPages
from constat.store import Registry, Review, TicketStore, Workspace

from helpers import git
from test_acceptance import a_reading, record
from test_runs import distinct_subject


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        yield ws


@pytest.fixture
def wiki(tmp_path: Path) -> str:
    bare = tmp_path / "wiki.git"
    git(tmp_path, "init", "--quiet", "--bare", str(bare))
    seed = tmp_path / "seed"
    seed.mkdir()
    git(seed, "init", "--quiet", "--initial-branch=main")
    git(seed, "commit", "--quiet", "--allow-empty", "-m", "init")
    git(seed, "push", "--quiet", str(bare), "HEAD:refs/heads/main")
    return f"file://{bare}"


@pytest.fixture
def subject(workspace, tmp_path: Path):
    Registry(workspace).add(
        str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
    )
    TicketStore(workspace).add("622")
    gather(workspace, "622")
    return workspace


def _accept_a_rule(workspace) -> None:
    proposal = record(workspace, a_reading())
    Review(workspace).accept(proposal, decided_by="a person")


def _pages(tmp_path: Path, wiki: str, name: str = "check") -> Path:
    clone = tmp_path / name
    git(tmp_path, "clone", "--quiet", wiki, str(clone))
    return clone


# -- the catalogue reaches a page ---------------------------------------------


class TestPublishingTheCatalogue:
    def test_it_lands_on_its_own_page(self, subject, wiki, tmp_path) -> None:
        _accept_a_rule(subject)

        publish_state(subject, GitPages(wiki))

        page = _pages(tmp_path, wiki) / f"{STATE_REFERENCE}.md"
        assert page.exists()
        assert "The product as it stands" in page.read_text()

    def test_it_carries_the_accepted_rules(self, subject, wiki, tmp_path) -> None:
        _accept_a_rule(subject)

        publish_state(subject, GitPages(wiki))

        body = (_pages(tmp_path, wiki) / f"{STATE_REFERENCE}.md").read_text()
        assert "daily-limit" in body

    def test_it_says_nothing_on_it_can_be_decided(
        self, subject, wiki, tmp_path
    ) -> None:
        """It looks like the authoritative document, so it has to disclaim the
        one thing a reader would otherwise try to do on it."""
        _accept_a_rule(subject)

        publish_state(subject, GitPages(wiki))

        body = (_pages(tmp_path, wiki) / f"{STATE_REFERENCE}.md").read_text()
        assert "Nothing on this page can be\ndecided" in body
        assert "rewritten in full" in body

    def test_it_records_no_operation(self, subject, wiki) -> None:
        """Stated rather than hidden: the page belongs to no ticket, and an
        operation row requires a document."""
        _accept_a_rule(subject)

        result = publish_state(subject, GitPages(wiki))

        assert result.run_id is None

    def test_republishing_overwrites_rather_than_accumulating(
        self, subject, wiki, tmp_path
    ) -> None:
        _accept_a_rule(subject)
        publish_state(subject, GitPages(wiki))

        publish_state(subject, GitPages(wiki))

        pages = sorted(p.name for p in _pages(tmp_path, wiki).glob("*.md"))
        assert pages == [f"{STATE_REFERENCE}.md"]


# -- the case that started it -------------------------------------------------


class TestARuleWithNoTicketOfItsOwn:
    def test_it_still_reaches_the_catalogue_page(
        self, subject, wiki, tmp_path
    ) -> None:
        """The gap CON-106 was opened for.

        A rule accepted from a baseline has no ticket whose *changes* it
        anchors in, so no ticket document shows it. Before this, that rule was
        unpublishable.
        """
        _accept_a_rule(subject)
        ticket_body = TicketStore(subject).document("622").body
        assert "daily-limit" not in ticket_body  # the impact view shows none

        publish_state(subject, GitPages(wiki))

        body = (_pages(tmp_path, wiki) / f"{STATE_REFERENCE}.md").read_text()
        assert "daily-limit" in body


# -- publishing a ticket refreshes the catalogue ------------------------------


class TestPublishingATicket:
    def test_both_pages_exist_after_the_cli_publishes_a_ticket(
        self, subject, wiki, tmp_path
    ) -> None:
        from constat.cli import main

        _accept_a_rule(subject)

        code = main(
            [
                "--workspace", str(Path(subject.path).parent),
                "review", "622", "--target", wiki,
            ]
        )

        assert code == 0
        clone = _pages(tmp_path, wiki)
        # The index joined them in CON-110 and CON-113 moved the ticket page
        # into a folder — the whole-product pages stay at the root.
        assert sorted(p.name for p in clone.glob("*.md")) == [
            "index.md", f"{STATE_REFERENCE}.md"
        ]
        assert (clone / "decisions" / "reviewed" / "622.md").exists()

    def test_the_page_is_what_review_show_prints(
        self, subject, wiki, tmp_path
    ) -> None:
        """D-056's property, restated by CON-114.

        It used to be "what lands is the stored document". The page is no
        longer the document — the document is the technical view and stays at
        the terminal — so the property it was protecting moves with it: a
        reviewer can see exactly what will be published before anything leaves
        the machine, and the page cannot differ from what they were shown.
        """
        from constat.operations import render_review
        from constat.cli import main

        _accept_a_rule(subject)
        expected = render_review(subject, "622")

        main(
            [
                "--workspace", str(Path(subject.path).parent),
                "review", "622", "--target", wiki,
            ]
        )

        assert (_pages(tmp_path, wiki) / "decisions" / "reviewed" / "622.md").read_text() == expected

    def test_the_page_carries_no_evidence(self, subject, wiki, tmp_path) -> None:
        """The whole point of CON-114: the stored document names files, the
        published page does not."""
        from constat.cli import main

        _accept_a_rule(subject)
        assert "rules.py" in TicketStore(subject).document("622").body

        main(
            [
                "--workspace", str(Path(subject.path).parent),
                "review", "622", "--target", wiki,
            ]
        )

        page = (_pages(tmp_path, wiki) / "decisions" / "reviewed" / "622.md").read_text()
        assert "rules.py" not in page


# -- the reserved name --------------------------------------------------------


class TestTheCataloguePageNameIsReserved:
    def test_a_ticket_cannot_be_published_over_it(self, subject, wiki) -> None:
        """Both page kinds are named from a reference, so without this a
        ticket could overwrite the catalogue and nobody would notice until the
        page was already wrong."""
        from constat.cli import main

        code = main(
            [
                "--workspace", str(Path(subject.path).parent),
                "review", STATE_REFERENCE, "--target", wiki,
            ]
        )

        assert code == 2

    def test_the_refusal_leaves_the_target_untouched(
        self, subject, wiki, tmp_path
    ) -> None:
        from constat.cli import main

        main(
            [
                "--workspace", str(Path(subject.path).parent),
                "review", STATE_REFERENCE, "--target", wiki,
            ]
        )

        assert list(_pages(tmp_path, wiki).glob("*.md")) == []

    def test_reading_decisions_needs_a_ticket(self, subject, wiki) -> None:
        """A verdict is written against a rule proposal, and the catalogue
        page carries none.

        Enforced by the parser since CON-107 rather than by a runtime check:
        the decision flags live on `review`, which requires a reference, so
        there is no form of the command that asks the catalogue page for
        decisions.
        """
        from constat.cli import main

        with pytest.raises(SystemExit) as raised:
            main(
                [
                    "--workspace", str(Path(subject.path).parent),
                    "review", "--read-decisions", "--target", wiki,
                ]
            )

        assert raised.value.code == 2

    def test_the_catalogue_command_takes_no_reference(
        self, subject, wiki, capsys
    ) -> None:
        """`publish` is the catalogue and nothing else now (CON-107).

        It refuses with a message naming `review` rather than with argparse's
        "unrecognized arguments", which tells someone who learned the old
        form nothing about where it went. A refusal that does not say what to
        do instead is a dead end.
        """
        from constat.cli import main

        code = main(
            [
                "--workspace", str(Path(subject.path).parent),
                "publish", "622", "--target", wiki,
            ]
        )

        assert code == 2
        assert "constat review 622" in capsys.readouterr().err

    def test_asking_the_catalogue_for_decisions_names_review(
        self, subject, capsys
    ) -> None:
        from constat.cli import main

        code = main(
            ["--workspace", str(Path(subject.path).parent), "publish",
             "--read-decisions"]
        )

        assert code == 2
        assert "review <REF> --read-decisions" in capsys.readouterr().err


# -- which of the two moments the page is at ---------------------------------


class TestThePageSaysWhichMomentItIsAt:
    """Read from the queue rather than asserted by a flag (CON-107).

    The same command does two things depending on when it is run: before any
    decision the ticket page is a thing to circulate, after it is a record.
    Saying which costs nothing and answers the question a reviewer actually
    has — is there anything here for me to do.
    """

    def test_an_undecided_page_says_it_is_circulated_for_review(
        self, subject, wiki, capsys
    ) -> None:
        from constat.cli import main

        record(subject, a_reading())  # stored, not accepted
        capsys.readouterr()

        main(
            [
                "--workspace", str(Path(subject.path).parent),
                "review", "622", "--target", wiki,
            ]
        )

        out = capsys.readouterr().out
        assert "circulated for review" in out
        assert "1 proposal(s) on this page await a decision" in out

    def test_a_decided_page_says_it_is_a_record(
        self, subject, wiki, capsys
    ) -> None:
        from constat.cli import main

        _accept_a_rule(subject)
        capsys.readouterr()

        main(
            [
                "--workspace", str(Path(subject.path).parent),
                "review", "622", "--target", wiki,
            ]
        )

        assert "published as a record" in capsys.readouterr().out
