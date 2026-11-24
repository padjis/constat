"""A declared release is published as a page (CON-112).

`release show` has reported what was agreed for a release since D-103, and it
reached only a terminal. This is the same reading as a page, for the audience
the documentation is for.

**It needs no release lifecycle.** CON-86 — closing a release putting its
versions into effect — is still open and undecided, and this does not wait on
it: the page says *agreed*, which is a fact Constat holds, rather than *in
effect*, which it does not.

The three kinds of claim D-103 separated are kept apart on the page, because a
page is read by people who were not in the conversation:

1. **`agreed` is a fact.** Somebody accepted each version for this release.
2. **`stood` is a reconstruction**, derived from `agreed` — nothing was
   snapshotted at the time, and the page says so rather than letting a reader
   assume it was.
3. **Nothing says the release shipped.** No ship is recorded anywhere (CON-86)
   and a release name is never parsed for ordering (D-102).

A fourth property is about naming: `release-` is reserved, because every page
is named from a reference and a ticket called `release-2026.11` would
otherwise overwrite one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.operations import (
    gather,
    publish_releases,
    read_release,
    release_page,
    render_index,
    render_release,
)
from constat.publish import GitPages
from constat.store import Registry, Releases, Review, TicketStore, Workspace

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


def _accept_for(workspace, release: str | None = None) -> None:
    proposal = record(workspace, a_reading())
    Review(workspace).accept(proposal, decided_by="a person", release=release)


def _pages(tmp_path: Path, wiki: str, name: str = "check") -> Path:
    clone = tmp_path / name
    git(tmp_path, "clone", "--quiet", wiki, str(clone))
    return clone


# -- what the page says --------------------------------------------------------


class TestTheReleasePage:
    def test_an_empty_release_says_how_to_fill_it(self, subject) -> None:
        """Rather than rendering as though the release were empty of meaning."""
        Releases(subject).declare("2026.11", declared_by="a person")

        body = render_release(read_release(subject, "2026.11"))

        assert "Nothing has been agreed for it yet" in body
        assert "rule accept <ID> --release 2026.11" in body

    def test_an_agreed_version_is_called_a_fact(self, subject) -> None:
        Releases(subject).declare("2026.11", declared_by="a person")
        _accept_for(subject, release="2026.11")

        body = render_release(read_release(subject, "2026.11"))

        assert "daily-limit" in body
        assert "**fact**" in body

    def test_the_reconstruction_is_named_as_one(self, subject) -> None:
        """The reader must not read an assembled view as a stored snapshot."""
        Releases(subject).declare("2026.11", declared_by="a person")
        _accept_for(subject, release="2026.11")

        body = render_release(read_release(subject, "2026.11"))

        assert "**reconstructed** rather than recorded" in body

    def test_it_refuses_to_claim_the_release_shipped(self, subject) -> None:
        """CON-86 is unbuilt, so the page must not imply otherwise."""
        Releases(subject).declare("2026.11", declared_by="a person")
        _accept_for(subject, release="2026.11")

        body = render_release(read_release(subject, "2026.11"))

        assert "does not say this release shipped" in body

    def test_it_links_to_the_catalogue_and_the_index(self, subject) -> None:
        Releases(subject).declare("2026.11", declared_by="a person")

        body = render_release(read_release(subject, "2026.11"))

        assert "(the-product-as-it-stands.md)" in body
        assert "(index.md)" in body


# -- publishing ----------------------------------------------------------------


class TestPublishingReleases:
    def test_each_declared_release_gets_a_page(
        self, subject, wiki, tmp_path
    ) -> None:
        Releases(subject).declare("2026.11", declared_by="a person")
        Releases(subject).declare("2026.12", declared_by="a person")

        publish_releases(subject, GitPages(wiki))

        pages = sorted(p.name for p in _pages(tmp_path, wiki).glob("*.md"))
        assert pages == ["release-2026.11.md", "release-2026.12.md"]

    def test_a_workspace_with_no_releases_publishes_nothing(
        self, subject, wiki
    ) -> None:
        """Not a failure. `release list` says in terms that no declared
        release is not a statement that nothing shipped."""
        assert publish_releases(subject, GitPages(wiki)) == ()

    def test_it_records_no_operation(self, subject, wiki) -> None:
        Releases(subject).declare("2026.11", declared_by="a person")

        results = publish_releases(subject, GitPages(wiki))

        assert results[0].run_id is None


# -- the index -----------------------------------------------------------------


class TestTheIndexListsReleases:
    def test_a_declared_release_appears(self, subject) -> None:
        Releases(subject).declare("2026.11", declared_by="a person")

        body = render_index((), Releases(subject).list())

        assert "[2026.11](release-2026.11.md)" in body

    def test_no_release_section_without_releases(self, subject) -> None:
        body = render_index((), ())

        assert "By release" not in body


# -- the reserved prefix -------------------------------------------------------


class TestTheReleasePrefixIsReserved:
    def test_a_ticket_cannot_take_it(self, subject, wiki) -> None:
        """Every page is named from a reference, so without this a ticket
        called `release-2026.11` would overwrite a release page."""
        from constat.cli import main

        code = main(
            [
                "--workspace", str(Path(subject.path).parent),
                "review", "release-2026.11", "--target", wiki,
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
                "review", "release-2026.11", "--target", wiki,
            ]
        )

        assert list(_pages(tmp_path, wiki).glob("*.md")) == []

    def test_the_page_name_matches_the_prefix(self) -> None:
        assert release_page("2026.11") == "release-2026.11"
