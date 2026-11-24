"""Pages name each other, and something lists them (CON-110).

Before this there were **no links at all** between published pages, and
nothing enumerated them. A reader on the catalogue had no path to the evidence
behind a rule; a reader on a ticket page had no path to what the product does;
and ticket pages accumulated in the target with nothing listing what was
there.

None of that was decided. The renderers simply never emitted a link.

The index is built from the **publication record** rather than from the ticket
list, which is the first thing in Constat to read one back: `publish_document`
has written an `operation` row since D-058 and nothing had ever looked at it,
so "where has this document been published" was unanswerable.

Four properties carry these tests:

1. **A rule names the ticket it was read from**, resolved through the chain
   `rule -> rule_version -> rule_proposal -> run -> document -> ticket`.
2. **A ticket page names the catalogue and the index**, so every page is two
   clicks from every other.
3. **The index lists what was published**, not what might be — a ticket whose
   page nobody published is absent, because there is no page to link to.
4. **The link and the filename agree.** A renderer that derived a page name
   differently from the target would emit links resolving nowhere.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.operations import (
    gather,
    product_state,
    published_pages,
    publish_document,
    publish_index,
    render_index,
    render_area,
    render_state,
    _page_link,
)
from constat.publish import INDEX_REFERENCE, STATE_REFERENCE, GitPages
from constat.publish.targets.git_pages import GitPages as Target
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
    return f"file://{bare}"


@pytest.fixture
def subject(workspace, tmp_path: Path):
    Registry(workspace).add(
        str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
    )
    TicketStore(workspace).add("622")
    gather(workspace, "622")
    return workspace


def _accept_a_rule(workspace) -> int:
    proposal = record(workspace, a_reading())
    return Review(workspace).accept(proposal, decided_by="a person").rule_id


def _pages(tmp_path: Path, wiki: str, name: str = "check") -> Path:
    clone = tmp_path / name
    git(tmp_path, "clone", "--quiet", wiki, str(clone))
    return clone


# -- a rule points at its evidence --------------------------------------------


class TestARuleNamesTheTicketItCameFrom:
    def test_the_chain_resolves(self, subject) -> None:
        rule_id = _accept_a_rule(subject)

        assert Review(subject).references_for(rule_id) == ("622",)

    def test_an_unknown_rule_resolves_to_nothing(self, subject) -> None:
        """Empty is an answer, not a fault: a rule accepted before Constat
        kept the link has no page to point at."""
        assert Review(subject).references_for(9999) == ()

    def test_an_area_page_links_to_the_ticket_page(self, subject) -> None:
        """Moved from the state page by CON-116: a rule is listed on its area
        page, and the state page indexes the areas. The link is the same one,
        emitted once now rather than twice."""
        _accept_a_rule(subject)
        grouped = product_state(subject).by_area()
        area, states = next(iter(grouped.items()))

        body = render_area(area, states)

        assert "read from [622](../reviews/622.md)" in body

    def test_a_rule_with_no_ticket_says_nothing(self, subject) -> None:
        """Rather than inventing a page that may not exist."""
        _accept_a_rule(subject)
        state = product_state(subject)
        stripped = type(state.rules[0])(rule=state.rules[0].rule, matched={})

        body = render_state(type(state)(repositories=state.repositories, rules=(stripped,)))

        assert "read from" not in body


# -- the way back out ----------------------------------------------------------


class TestATicketPageNamesTheRest:
    def test_it_links_up_to_the_catalogue(self, subject) -> None:
        """`../`, because the page lives under `evidence/` (CON-113). A link
        that forgot the directory would resolve nowhere."""
        body = TicketStore(subject).document("622").body

        assert "(../status.md)" in body

    def test_it_links_up_to_the_index(self, subject) -> None:
        body = TicketStore(subject).document("622").body

        assert "(../index.md)" in body


# -- the index -----------------------------------------------------------------


class TestTheIndex:
    def test_an_unpublished_workspace_says_so(self, subject) -> None:
        """Honest rather than empty: there is nothing to link to yet."""
        body = render_index(published_pages(subject))

        assert "No ticket pages have been published" in body
        assert f"({_page_link(STATE_REFERENCE)})" in body

    def test_it_lists_a_published_page(self, subject, wiki) -> None:
        publish_document(subject, "622", GitPages(wiki))

        body = render_index(published_pages(subject))

        assert "[622](reviews/622.md)" in body

    def test_it_lists_what_was_published_not_what_exists(
        self, subject, wiki
    ) -> None:
        """The reason it reads the publication record rather than the ticket
        list: an unpublished ticket has no page, so linking to one would be a
        link into nothing."""
        TicketStore(subject).add("700")
        gather(subject, "700")
        publish_document(subject, "622", GitPages(wiki))

        body = render_index(published_pages(subject))

        assert "[622](reviews/622.md)" in body
        assert "700" not in body

    def test_republishing_lists_a_page_once(self, subject, wiki) -> None:
        publish_document(subject, "622", GitPages(wiki))
        publish_document(subject, "622", GitPages(wiki))

        assert len(published_pages(subject)) == 1

    def test_it_reaches_the_target(self, subject, wiki, tmp_path) -> None:
        publish_index(subject, GitPages(wiki))

        assert (_pages(tmp_path, wiki) / f"{INDEX_REFERENCE}.md").exists()

    def test_it_records_no_operation(self, subject, wiki) -> None:
        """Same narrowing as the catalogue page (D-110): it belongs to no
        ticket, and an operation row requires a document."""
        result = publish_index(subject, GitPages(wiki))

        assert result.run_id is None


# -- the link and the filename agree ------------------------------------------


class TestLinksResolve:
    @pytest.mark.parametrize(
        "reference", ["622", "ABC-123", "baseline-app-install", "../../etc/x"]
    )
    def test_the_renderer_agrees_with_the_target(self, reference) -> None:
        """Two places derive a page name from a reference. A renderer that
        sanitised differently would emit links that resolve nowhere, and the
        sanitising exists so a reference from a commit message cannot become
        a path.
        """
        assert _page_link(reference) == Target("file:///x.git").page_for(reference)


# -- the reserved name ---------------------------------------------------------


class TestTheIndexNameIsReserved:
    def test_a_ticket_cannot_be_published_over_it(self, subject, wiki) -> None:
        from constat.cli import main

        code = main(
            [
                "--workspace", str(Path(subject.path).parent),
                "review", INDEX_REFERENCE, "--target", wiki,
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
                "review", INDEX_REFERENCE, "--target", wiki,
            ]
        )

        assert list(_pages(tmp_path, wiki).glob("*.md")) == []
