"""Where documentation is published is a workspace setting (CON-108).

Before this the target came from one place: the `.wiki.git` convention applied
to the current repository's remote, or `--target` typed on every command that
writes. That is fine for a workspace over one repository and awkward for the
case Constat is built for — a catalogue spanning several, where no single
remote is the obvious home and `review`, `publish` and `--record-decisions`
would each need the flag.

The same argument D-060 made for `reader`: a workspace has one answer and it
does not change between runs, so ask once.

Four properties carry these tests:

1. **Three sources, in order.** `--target` beats the setting, the setting
   beats the remote.
2. **The remote stays the fallback**, so a workspace that configured nothing
   still works on its first run. A configured target widens where you can
   publish; it never makes Constat willing to guess.
3. **Unset is a distinct act**, not an empty string — "" would read as a
   configured target that happens to be blank, and every later refusal would
   have to disambiguate it.
4. **Setting it publishes nothing.** It is configuration, and configuration
   that wrote to a remote would be the surprise D-058 exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from constat.cli import EXIT_OK, EXIT_USAGE, main
from constat.errors import InvalidInput
from constat.operations import detect_target, gather, publish_state
from constat.publish import STATE_REFERENCE
from constat.store import Registry, Settings, TicketStore, Workspace

from helpers import git
from test_runs import distinct_subject


@pytest.fixture
def workspace(tmp_path: Path):
    with Workspace.create(tmp_path / "ws") as ws:
        Registry(ws).add(
            str(distinct_subject(tmp_path, "billing", "LIMIT = 250\n")), alias="billing"
        )
        TicketStore(ws).add("622")
        gather(ws, "622")
        yield ws


@pytest.fixture
def wiki(tmp_path: Path) -> str:
    bare = tmp_path / "wiki.git"
    git(tmp_path, "init", "--quiet", "--bare", str(bare))
    return f"file://{bare}"


# -- the setting --------------------------------------------------------------


class TestTheSetting:
    def test_it_is_unset_by_default(self, workspace) -> None:
        assert Settings(workspace).target is None

    def test_it_round_trips(self, workspace, wiki) -> None:
        Settings(workspace).set_target(wiki)

        assert Settings(workspace).target == wiki

    def test_whitespace_is_not_a_target(self, workspace) -> None:
        with pytest.raises(InvalidInput):
            Settings(workspace).set_target("   ")

    def test_unsetting_restores_the_unset_state(self, workspace, wiki) -> None:
        """Distinct from setting an empty string, which would read as a
        configured target that happens to be blank."""
        settings = Settings(workspace)
        settings.set_target(wiki)

        settings.unset_target()

        assert settings.target is None


# -- precedence ----------------------------------------------------------------


class TestWhichTargetWins:
    def test_the_setting_is_used_when_there_is_one(self, workspace, wiki) -> None:
        Settings(workspace).set_target(wiki)

        resolved = detect_target(repository=None, workspace=workspace)

        assert resolved.url == wiki

    def test_the_remote_is_the_fallback(self, workspace, tmp_path) -> None:
        """A workspace that configured nothing still works on its first run.

        Asserted by the refusal rather than by a URL: this subject has no
        remote, so detection has nothing to derive from — which proves the
        setting was not consulted and the remote path was taken.
        """
        from constat.errors import TargetUnknown

        subject = distinct_subject(tmp_path, "nowhere", "x = 1\n")

        with pytest.raises(TargetUnknown):
            detect_target(repository=str(subject), workspace=workspace)

    def test_an_unknown_host_still_refuses_with_a_setting_present(
        self, workspace, tmp_path
    ) -> None:
        """A configured target widens where you can publish. It does not make
        Constat willing to guess about a repository that names another host.
        """
        from constat.errors import TargetUnknown

        Settings(workspace).set_target("file:///tmp/configured.git")
        subject = distinct_subject(tmp_path, "nowhere", "x = 1\n")

        # The setting wins, so this resolves rather than refusing …
        assert detect_target(str(subject), workspace).url == "file:///tmp/configured.git"

        # … and with the setting gone, the remote decides again and refuses.
        Settings(workspace).unset_target()
        with pytest.raises(TargetUnknown):
            detect_target(str(subject), workspace)


# -- through the command line --------------------------------------------------


class TestTheCommandLine:
    def _ws(self, workspace) -> str:
        return str(Path(workspace.path).parent)

    def test_publish_uses_the_configured_target(
        self, workspace, wiki, tmp_path
    ) -> None:
        main(["--workspace", self._ws(workspace), "config", "target", wiki])

        code = main(["--workspace", self._ws(workspace), "publish"])

        assert code == EXIT_OK
        clone = tmp_path / "check"
        git(tmp_path, "clone", "--quiet", wiki, str(clone))
        assert (clone / f"{STATE_REFERENCE}.md").exists()

    def test_setting_it_publishes_nothing(self, workspace, wiki, tmp_path) -> None:
        """Configuration that wrote to a remote would be the surprise D-058
        exists to prevent."""
        main(["--workspace", self._ws(workspace), "config", "target", wiki])

        clone = tmp_path / "check"
        git(tmp_path, "clone", "--quiet", wiki, str(clone))
        assert list(clone.glob("*.md")) == []

    def test_showing_it_when_unset_says_where_it_comes_from(
        self, workspace, capsys
    ) -> None:
        main(["--workspace", self._ws(workspace), "config", "target"])

        out = capsys.readouterr().out
        assert "not set" in out
        assert "remote" in out

    def test_a_url_and_unset_together_refuse(self, workspace, wiki, capsys) -> None:
        code = main(
            ["--workspace", self._ws(workspace), "config", "target", wiki, "--unset"]
        )

        assert code == EXIT_USAGE
        assert "Pick one" in capsys.readouterr().err

    def test_the_flag_overrides_the_setting(
        self, workspace, wiki, tmp_path, capsys
    ) -> None:
        other = tmp_path / "other.git"
        git(tmp_path, "init", "--quiet", "--bare", str(other))
        main(["--workspace", self._ws(workspace), "config", "target", wiki])
        capsys.readouterr()

        main(
            [
                "--workspace", self._ws(workspace),
                "publish", "--target", f"file://{other}",
            ]
        )

        assert str(other) in capsys.readouterr().out
        clone = tmp_path / "unconfigured"
        git(tmp_path, "clone", "--quiet", wiki, str(clone))
        assert list(clone.glob("*.md")) == []
