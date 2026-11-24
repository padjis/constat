"""A page per area, and a tombstone when one empties (CON-111).

The catalogue was one page for the whole product, with areas as headings. That
reads fine at seventeen rules and becomes a wall nobody scrolls, and it gives
a team no link to send anybody: there was no URL for *their* rules.

**The hard part was never the page, it was what happens when an area stops
existing.** An area is free text frozen on each accepted version (D-079,
CON-88) — there is no `area` identity and no rename — so an area empties when
the last rule filed under it is re-accepted elsewhere. Nothing in the
workspace remembers that a page was written for it, and Constat's own
publication record covers ticket pages only (D-110).

So the target is asked what it holds, and a page with no content behind it any
more is **rewritten as a tombstone**: the URL keeps resolving and the page
stops claiming to be current. Deleting it would break a link; leaving it would
serve rules that are no longer filed there, with nothing saying so.

Four properties carry these tests:

1. **One page per area**, carrying the business half only — no paths, for
   D-115's reason.
2. **An emptied area is tombstoned**, not deleted and not left alone.
3. **Page names are compared as page names.** An area is free text, so
   `app install` is the reference `area-app install` and the file
   `area-app-install.md`; comparing the two forms tombstoned every area with a
   space in it the instant after writing it.
4. **`area-` is reserved**, because every page is named from a reference.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.operations import (
    area_page,
    gather,
    product_state,
    publish_areas,
    render_area,
    render_emptied_area,
    render_index,
    _page_link,
)
from constat.publish import AREA_PREFIX, GitPages
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


def _accept_in(workspace, area: str | None) -> None:
    proposal = record(workspace, a_reading())
    Review(workspace).accept(proposal, decided_by="a person")
    if area is not None:
        workspace.execute(
            "UPDATE rule SET area = ? WHERE name = 'daily-limit'", (area,)
        )


def _pages(tmp_path: Path, wiki: str, name: str = "check") -> list[str]:
    """The area pages on the target. They live in `areas/`, one folder per
    page kind, so the business pages stay at the root."""
    clone = tmp_path / name
    git(tmp_path, "clone", "--quiet", wiki, str(clone))
    return sorted(p.name for p in (clone / "areas").glob("*.md"))


def _read(tmp_path: Path, wiki: str, page: str, name: str = "r") -> str:
    clone = tmp_path / name
    git(tmp_path, "clone", "--quiet", wiki, str(clone))
    return (clone / "areas" / page).read_text()


# -- one page per area ---------------------------------------------------------


class TestAnAreaPage:
    def test_it_carries_the_rules_of_that_area(self, subject) -> None:
        _accept_in(subject, "payments")
        grouped = product_state(subject).by_area()

        body = render_area("payments", grouped["payments"])

        assert body.startswith("# payments")
        assert "daily-limit" in body

    def test_it_names_no_file(self, subject) -> None:
        """D-115's rule, applied to the page that inherits its content."""
        _accept_in(subject, "payments")
        grouped = product_state(subject).by_area()

        body = render_area("payments", grouped["payments"])

        assert "rules.py" not in body

    def test_it_links_out(self, subject) -> None:
        _accept_in(subject, "payments")
        grouped = product_state(subject).by_area()

        body = render_area("payments", grouped["payments"])

        # `../`, because an area page lives under `areas/`.
        assert "(../the-product-as-it-stands.md)" in body
        assert "(../index.md)" in body

    def test_the_read_from_link_climbs_out_of_the_folder(self, subject) -> None:
        """Found by comparing an area page with the catalogue: the link was
        written as `reviews/...`, which from inside `areas/` resolves to
        `areas/reviews/...` — so every "read from" on every area page was
        broken. The catalogue's copy of the same line was correct, which is
        what two renderers of one thing cost."""
        _accept_in(subject, "payments")
        grouped = product_state(subject).by_area()

        body = render_area("payments", grouped["payments"])

        assert "(../reviews/" in body
        assert "](reviews/" not in body

    def test_it_says_nothing_on_it_can_be_decided(self, subject) -> None:
        _accept_in(subject, "payments")
        grouped = product_state(subject).by_area()

        body = render_area("payments", grouped["payments"])

        assert "Nothing on this page can be decided" in body

    def test_each_area_reaches_the_target(self, subject, wiki, tmp_path) -> None:
        _accept_in(subject, "payments")

        publish_areas(subject, GitPages(wiki))

        assert "payments.md" in _pages(tmp_path, wiki)


# -- an area that empties ------------------------------------------------------


class TestAnEmptiedArea:
    def test_its_page_is_rewritten_rather_than_left(
        self, subject, wiki, tmp_path
    ) -> None:
        """The case the whole design turns on. Re-filing the only rule leaves
        a page for an area the catalogue no longer holds."""
        _accept_in(subject, "payments")
        publish_areas(subject, GitPages(wiki))
        subject.execute("UPDATE rule SET area = 'billing' WHERE name = 'daily-limit'")

        publish_areas(subject, GitPages(wiki))

        body = _read(tmp_path, wiki, "payments.md")
        assert "No rule is filed under this area any more" in body
        assert "daily-limit" not in body

    def test_the_page_is_not_deleted(self, subject, wiki, tmp_path) -> None:
        """Deleting it would break a link somebody may hold."""
        _accept_in(subject, "payments")
        publish_areas(subject, GitPages(wiki))
        subject.execute("UPDATE rule SET area = 'billing' WHERE name = 'daily-limit'")

        publish_areas(subject, GitPages(wiki))

        assert "payments.md" in _pages(tmp_path, wiki)

    def test_the_tombstone_points_at_what_is_current(self) -> None:
        body = render_emptied_area("payments")

        assert "(../the-product-as-it-stands.md)" in body
        assert "(../index.md)" in body

    def test_it_does_not_claim_to_record_what_was_there(self) -> None:
        """A tombstone that implied it held the old content would be a claim
        nothing backs: the page is rewritten, not archived."""
        body = render_emptied_area("payments")

        assert "not a record of what the area used to contain" in body


# -- names are compared as names -----------------------------------------------


class TestNamesAreComparedAsPageNames:
    def test_an_area_with_a_space_is_not_tombstoned(
        self, subject, wiki, tmp_path
    ) -> None:
        """The bug this found, caught by running it.

        `app install` is the reference `area-app install` and the file
        `area-app-install.md`. Comparing the reference against the filename
        tombstoned the page immediately after writing it — the catalogue page
        said one thing and the area page said the area was empty.
        """
        _accept_in(subject, "app install")

        publish_areas(subject, GitPages(wiki))
        publish_areas(subject, GitPages(wiki))

        body = _read(tmp_path, wiki, "app-install.md")
        assert "No rule is filed" not in body
        assert "daily-limit" in body

    def test_publishing_twice_writes_the_same_set(
        self, subject, wiki, tmp_path
    ) -> None:
        _accept_in(subject, "app install")
        publish_areas(subject, GitPages(wiki))

        first = _pages(tmp_path, wiki, "one")
        publish_areas(subject, GitPages(wiki))

        assert _pages(tmp_path, wiki, "two") == first


# -- the index and the reserved prefix -----------------------------------------


class TestTheIndexAndTheName:
    def test_the_index_lists_areas(self, subject) -> None:
        _accept_in(subject, "payments")

        body = render_index((), (), tuple(product_state(subject).by_area()))

        assert f"[payments]({_page_link(area_page('payments'))})" in body

    def test_a_ticket_cannot_take_the_prefix(self, subject, wiki) -> None:
        from constat.cli import main

        code = main(
            [
                "--workspace", str(Path(subject.path).parent),
                "review", f"{AREA_PREFIX}payments", "--target", wiki,
            ]
        )

        assert code == 2

    def test_an_unpublished_target_lists_nothing(self, wiki) -> None:
        """Nothing published and unreachable are the same answer here: there
        is no page to tombstone, and a real failure surfaces on the write."""
        assert GitPages(wiki).references_published(AREA_PREFIX) == ()
