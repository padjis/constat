"""Decisions a reviewer wrote in the published target (CON-58, D-105).

`read_decisions` has raised `DecisionsNotReadable` on every target since the
port was declared. This implements it, for the half that reads: nothing here
records a decision, because D-089 says the amendment to D-055 lands with the
mechanism that enforces it.

**The design is plain git, and that is the point.** No forge API, no token, no
per-platform backend — clone, read a file, `git blame` it. Every test below runs
against a bare repository on disk, which is the proof: if it works there it
works on any host, because nothing in the path knows what a host is.

The properties:

1. **Identity comes from the commit, never from the text.** A typed name is no
   better than the CLI's unchecked `--by` (D-061).
2. **Three verification states, and the middle one is real.** A signature
   verified on the signer's machine reads as unverified through a clone Constat
   made, because the allowed-signers file lives with the signer. Rounding that
   either way would be a false claim.
3. **An unreadable line is reported, never guessed at.**
4. **Absent is not empty.** No file means nobody had anywhere to write.
5. **Constat seeds the file once and never writes it again**, because the page
   beside it is regenerated on every publish.
"""

from __future__ import annotations

import re

import subprocess
from pathlib import Path

import pytest

from constat.errors import DecisionsNotReadable
from constat.publish.decisions import TEMPLATE, file_for, parse
from constat.publish.targets.git_pages import GitPages


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    """A bare repository standing in for any git documentation target."""
    bare = tmp_path / "wiki.git"
    bare.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "--quiet", "--initial-branch=main", str(bare)],
        check=True,
        capture_output=True,
    )
    return bare


@pytest.fixture
def published(wiki: Path) -> GitPages:
    target = GitPages(str(wiki))
    target.publish("402", "# Document for 402\n\nproposal 1: a transfer rule.\n")
    return target


def review(tmp_path: Path, wiki: Path, lines: str, *, sign: bool = False) -> Path:
    """A reviewer clones, appends decisions and pushes — a browser edit on a
    forge produces the same commit, which is why nothing here needs a forge."""
    clone = tmp_path / f"review-{abs(hash(lines)) % 10000}"
    subprocess.run(
        ["git", "clone", "--quiet", str(wiki), str(clone)],
        check=True,
        capture_output=True,
    )
    git(clone, "config", "user.name", "A Business Reviewer")
    git(clone, "config", "user.email", "biz@example.invalid")

    if sign:
        key = tmp_path / "signer"
        if not key.exists():
            subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-N", "", "-q", "-f", str(key)],
                check=True,
                capture_output=True,
            )
        git(clone, "config", "gpg.format", "ssh")
        git(clone, "config", "user.signingkey", str(key) + ".pub")

    page = clone / file_for("402.md")
    page.write_text(page.read_text() + lines)
    git(clone, "add", "-A")
    git(clone, "commit", "--quiet", *(["-S"] if sign else []), "-m", "decide")
    git(clone, "push", "--quiet", "origin", "HEAD")
    return clone


# -- the format, with no git involved -----------------------------------------


class TestTheFormat:
    def test_an_approval_and_a_rejection_are_read(self):
        found, _ = parse("## Decisions\n1: approved\n2: rejected\n")

        assert [(d.reference, d.verdict) for d in found] == [
            ("1", "approved"),
            ("2", "rejected"),
        ]

    def test_a_reason_is_optional_and_kept(self):
        found, _ = parse("## Decisions\n2: rejected — the limit is per account\n")

        assert found[0].reason == "the limit is per account"

    def test_a_hyphen_works_as_well_as_an_em_dash(self):
        """A browser editor produces either, and refusing one would make the
        format depend on which keyboard the reviewer had."""
        found, _ = parse("## Decisions\n2: rejected - not per customer\n")

        assert found[0].reason == "not per customer"

    def test_a_rule_citation_is_accepted_as_well_as_a_proposal_id(self):
        found, _ = parse("## Decisions\nR-7: approved\n")

        assert found[0].reference == "R-7"

    def test_the_empty_template_yields_nothing_at_all(self):
        """The finding that produced the `## Decisions` marker. A first version
        reported all ten lines of the template's instructions as unreadable,
        which would bury the two lines that mattered under the explanation of
        how to write them."""
        found, unreadable = parse(TEMPLATE.format(reference="402"))

        assert found == ()
        assert unreadable == ()

    def test_the_template_s_own_examples_are_not_read_as_decisions(self):
        """They are indented, which is what keeps `1: approved` in the
        instructions from arriving as a decision nobody made."""
        assert "    1: approved" in TEMPLATE

        found, _ = parse(TEMPLATE.format(reference="402"))

        assert found == ()

    def test_a_typo_is_reported_with_its_line_and_text(self):
        _, unreadable = parse("## Decisions\n1: aproved\n")

        assert unreadable == ((2, "1: aproved"),)

    def test_prose_below_the_marker_is_reported(self):
        """"Looks fine to me" beside a rule is a decision Constat does not
        have, and silence would leave the reviewer believing it was
        recorded."""
        _, unreadable = parse("## Decisions\nlooks fine to me\n")

        assert unreadable == ((2, "looks fine to me"),)

    def test_prose_above_the_marker_is_not_reported(self):
        _, unreadable = parse("Some instructions.\n\n## Decisions\n1: approved\n")

        assert unreadable == ()

    def test_a_file_with_no_marker_is_scanned_whole(self):
        """A reviewer who deletes the heading gets a noisier report rather than
        a silent one. Noisy beats silent: an unread decision reported as prose
        is a decision somebody believes was recorded."""
        found, unreadable = parse("1: approved\nsomething else\n")

        assert [d.reference for d in found] == ["1"]
        assert unreadable == ((2, "something else"),)

    def test_a_capitalised_verdict_is_not_a_decision(self):
        """So "Approved?" in a sentence cannot read as one."""
        found, unreadable = parse("## Decisions\n1: Approved\n")

        assert found == ()
        assert len(unreadable) == 1

    def test_approved_and_rejected_are_separable(self):
        found, _ = parse("## Decisions\n1: approved\n2: rejected\n3: approved\n")
        from constat.publish.decisions import DecisionsRead

        read = DecisionsRead(reference="402", location="x", decisions=found)

        assert [d.reference for d in read.approved] == ["1", "3"]
        assert [d.reference for d in read.rejected] == ["2"]


# -- the git half --------------------------------------------------------------


class TestReadingFromAGitTarget:
    def test_it_works_on_a_bare_repository_with_no_forge_at_all(
        self, tmp_path, wiki, published
    ):
        """The whole generic claim, in one test. No host, no API, no token."""
        review(tmp_path, wiki, "1: approved\n")

        read = published.read_decisions("402")

        assert [d.reference for d in read.decisions] == ["1"]

    def test_the_decider_comes_from_the_commit_not_the_file(
        self, tmp_path, wiki, published
    ):
        """The reason this channel is worth having. The reviewer never types a
        name, and the one recorded is attested by the repository."""
        review(tmp_path, wiki, "1: approved\n")

        read = published.read_decisions("402")

        assert read.decisions[0].decided_by == "A Business Reviewer"
        assert read.decisions[0].commit is not None
        assert read.decisions[0].decided_at is not None

    def test_the_template_does_not_ask_for_a_name(self, published):
        assert "Do not write your name" in TEMPLATE

    def test_the_template_names_commands_that_exist(self, published):
        """This file is seeded once and **never rewritten** (D-105), so a
        command renamed under it leaves a permanently wrong instruction in
        someone else's repository — republishing cannot fix it.

        It happened: CON-107 renamed `publish <REF>` to `review <REF>` and
        this template kept telling reviewers to run the removed form. Found
        by reading a real published file, not by a test, which is why there
        is now a test.
        """
        from constat.cli import build_parser

        parser = build_parser()
        commands = set(parser._subparsers._group_actions[0].choices)

        named = set(re.findall(r"`constat ([a-z-]+)", TEMPLATE))

        assert named, "the template should tell a reviewer what to run"
        assert named <= commands, f"template names commands that do not exist: {named - commands}"

    def test_an_unsigned_commit_is_attested_not_verified(
        self, tmp_path, wiki, published
    ):
        review(tmp_path, wiki, "1: approved\n")

        read = published.read_decisions("402")

        assert read.decisions[0].verification == "git_commit"

    def test_a_signed_commit_is_reported_as_signed_but_unverified(
        self, tmp_path, wiki, published
    ):
        """**The finding.** The signature verifies on the signer's machine and
        reads as absent through a clone Constat made, because `git` needs
        `gpg.ssh.allowedSignersFile` to check one — configuration that lives
        with the signer and will never be on the machine reading decisions
        back. Presence is read from the commit object instead, where `gpgsig`
        sits regardless of trust, and the two facts are reported separately.
        Mapping this to "unsigned" would discard a real signature; mapping it
        to "verified" would claim a check nobody performed.
        """
        review(tmp_path, wiki, "9: approved\n", sign=True)

        read = published.read_decisions("402")

        signed = [d for d in read.decisions if d.reference == "9"]
        assert [d.verification for d in signed] == ["signed_unverified"]

    def test_decisions_from_two_people_are_attributed_separately(
        self, tmp_path, wiki, published
    ):
        """`git blame` per line, because attributing every line to the file's
        last committer would credit the wrong reviewer."""
        review(tmp_path, wiki, "1: approved\n")
        second = tmp_path / "other"
        subprocess.run(
            ["git", "clone", "--quiet", str(wiki), str(second)],
            check=True,
            capture_output=True,
        )
        git(second, "config", "user.name", "Another Reviewer")
        git(second, "config", "user.email", "other@example.invalid")
        page = second / file_for("402.md")
        page.write_text(page.read_text() + "2: rejected\n")
        git(second, "add", "-A")
        git(second, "commit", "--quiet", "-m", "also decide")
        git(second, "push", "--quiet", "origin", "HEAD")

        read = published.read_decisions("402")

        assert {d.reference: d.decided_by for d in read.decisions} == {
            "1": "A Business Reviewer",
            "2": "Another Reviewer",
        }

    def test_an_unreadable_line_survives_the_round_trip(
        self, tmp_path, wiki, published
    ):
        review(tmp_path, wiki, "1: aproved\n")

        read = published.read_decisions("402")

        assert read.decisions == ()
        assert [text for _, text in read.unreadable] == ["1: aproved"]

    def test_an_absent_file_is_not_an_empty_one(self, wiki):
        """Nothing published means nobody had anywhere to write, which is a
        different situation from having written nothing — and reporting them
        alike would read as "nobody has decided" (D-041)."""
        read = GitPages(str(wiki)).read_decisions("999")

        assert read.present is False
        assert read.decisions == ()

    def test_a_seeded_file_with_nothing_in_it_is_present_and_empty(
        self, published
    ):
        read = published.read_decisions("402")

        assert read.present is True
        assert read.decisions == ()

    def test_an_unreachable_target_refuses_rather_than_reporting_none(
        self, tmp_path
    ):
        """The posture `NotYetReadable` set and this inherits: an empty answer
        would read as nobody having decided."""
        with pytest.raises(DecisionsNotReadable, match="nobody has decided"):
            GitPages(str(tmp_path / "absent.git")).read_decisions("402")

    def test_reading_leaves_no_temporary_clone_behind(self, published):
        import tempfile

        before = set(Path(tempfile.gettempdir()).glob("constat-decisions-*"))
        published.read_decisions("402")
        after = set(Path(tempfile.gettempdir()).glob("constat-decisions-*"))

        assert after == before


class TestTheFileConstatDoesNotOwn:
    def test_publishing_seeds_the_decision_file(self, wiki, published):
        clone = wiki.parent / "check"
        subprocess.run(
            ["git", "clone", "--quiet", str(wiki), str(clone)],
            check=True,
            capture_output=True,
        )

        assert (clone / file_for("402.md")).exists()

    def test_republishing_does_not_overwrite_a_reviewer_s_decisions(
        self, tmp_path, wiki, published
    ):
        """The reason decisions are not written on the page itself. The page is
        a living view regenerated on every run (D-029), so a decision put there
        would be destroyed — CON-39's problem, avoided rather than solved."""
        review(tmp_path, wiki, "1: approved\n")

        published.publish("402", "# Document for 402\n\nquite different now.\n")

        read = published.read_decisions("402")
        assert [d.reference for d in read.decisions] == ["1"]

    def test_the_page_itself_is_still_replaced(self, tmp_path, wiki, published):
        """The other half of the same property: Constat owns the page."""
        published.publish("402", "# Replaced\n")

        clone = tmp_path / "after"
        subprocess.run(
            ["git", "clone", "--quiet", str(wiki), str(clone)],
            check=True,
            capture_output=True,
        )

        # Under `evidence/` since CON-113; the decisions file beside it is
        # still keyed on the reference alone, so moving the page did not move
        # a reviewer's verdicts.
        assert (clone / "evidence" / "402.md").read_text() == "# Replaced\n"


# -- the command line ----------------------------------------------------------


class TestTheCommandLine:
    def _home(self, tmp_path: Path) -> str:
        from constat.cli import main

        ws = str(tmp_path / "ws")
        main(["--workspace", ws, "init"])
        return ws

    def test_it_reports_what_was_read(self, tmp_path, wiki, published, capsys):
        from constat.cli import main

        review(tmp_path, wiki, "1: approved\n")
        home = self._home(tmp_path)
        capsys.readouterr()

        code = main(
            ["--workspace", home, "review", "402", "--target", str(wiki),
             "--read-decisions"]
        )

        out = capsys.readouterr().out
        assert code == 0
        assert "1 decision(s) read" in out
        assert "A Business Reviewer" in out

    def test_it_says_nothing_is_recorded_and_names_the_command(
        self, tmp_path, wiki, published, capsys
    ):
        """D-089's constraint, in the output. A reader must not be able to
        mistake "Constat has seen your approval" for "your approval is
        recorded"."""
        from constat.cli import main

        review(tmp_path, wiki, "1: approved\n")
        home = self._home(tmp_path)
        capsys.readouterr()

        main(["--workspace", home, "review", "402", "--target", str(wiki),
              "--read-decisions"])

        out = capsys.readouterr().out
        assert "Nothing here is recorded" in out
        assert "constat rule accept" in out

    def test_it_explains_the_verification_gradient(
        self, tmp_path, wiki, published, capsys
    ):
        from constat.cli import main

        review(tmp_path, wiki, "1: approved\n")
        home = self._home(tmp_path)
        capsys.readouterr()

        main(["--workspace", home, "review", "402", "--target", str(wiki),
              "--read-decisions"])

        out = capsys.readouterr().out
        assert "signed_unverified" in out
        assert "lives with the signer" in out

    def test_an_absent_file_does_not_read_as_nobody_deciding(
        self, tmp_path, wiki, capsys
    ):
        from constat.cli import main

        home = self._home(tmp_path)
        capsys.readouterr()

        main(["--workspace", home, "review", "999", "--target", str(wiki),
              "--read-decisions"])

        out = capsys.readouterr().out
        assert "no decision file" in out
        assert "nobody has decided" in out
        assert "never been published" in out

    def test_unreadable_lines_are_shown_to_the_reviewer(
        self, tmp_path, wiki, published, capsys
    ):
        from constat.cli import main

        review(tmp_path, wiki, "1: aproved\n")
        home = self._home(tmp_path)
        capsys.readouterr()

        main(["--workspace", home, "review", "402", "--target", str(wiki),
              "--read-decisions"])

        out = capsys.readouterr().out
        assert "could not be read" in out
        assert "1: aproved" in out

    def test_reading_does_not_publish(self, tmp_path, wiki, published, capsys):
        """`--read-decisions` must not write the page. Publishing is the only
        command that writes outside the workspace, and a read that also wrote
        would make that sentence false."""
        from constat.cli import main

        home = self._home(tmp_path)
        before = git(wiki, "rev-parse", "HEAD")
        capsys.readouterr()

        main(["--workspace", home, "review", "402", "--target", str(wiki),
              "--read-decisions"])

        assert git(wiki, "rev-parse", "HEAD") == before
