"""Publishing to a git-backed documentation repository (CON-57, D-058).

The default target, because a team's documentation usually lives next to its
code and because it needs no credential Constat has to hold: git already knows
how to authenticate, through whatever SSH agent or credential helper the user
configured. Constat inherits the environment and stays out of it.

**What it writes.** One Markdown file per ticket — `<reference>.md` — committed
and pushed. Overwriting an existing page is the normal case: the page is a view
of a living document, and the durable record is the workspace (D-004).

**Where it writes.** A clone Constat makes itself, in a temporary directory it
removes afterwards. Never the user's working tree: a failed publish must not be
able to leave a dirty checkout or a half-applied commit in a repository someone
is working in.

**How the default is derived.** From the subject repository's remote, by host.
A recognised host maps to its wiki; anything else **refuses** and asks for
`--target`. `resolve_default_branch` set that posture for D-028 and the reason
is sharper here: a wrong guess publishes a team's business rules somewhere
nobody expected to look.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from ...errors import DecisionsNotReadable, PublishFailed, TargetUnknown
from ...git.adapter import Repository, remote_url, run_git
from ..decisions import (
    TEMPLATE,
    folder_for,
    DecisionLine,
    DecisionsRead,
    DECISIONS_DIRECTORY,
    GENERATED_MARKER,
    file_for,
    parse,
)
from ..port import (
    AREA_PREFIX,
    Awaiting,
    AREAS_DIRECTORY,
    EVIDENCE_DIRECTORY,
    TICKETS_DIRECTORY,
    PublishedRef,
    is_generated,
)

NAME = "git-pages"

COMMIT_SUBJECT = "Constat: document for {reference}"

WIKI_HOSTS = ("github.com", "gitlab.com", "bitbucket.org")
"""Hosts whose wiki convention is `<repository>.wiki.git`.

A short, explicit list. The alternative — treat every unknown host as if it
followed GitHub's convention — would push to a URL derived from a guess, and
`git push` to a URL that happens to exist is not recoverable by apologising."""

_SCP_LIKE = re.compile(r"^(?P<user>[^@/]+)@(?P<host>[^:/]+):(?P<path>.+)$")


def _host_of(url: str) -> str | None:
    """The host in a git remote URL, in either syntax git accepts.

    `git@github.com:owner/repo.git` is not a URL any parser handles, and
    `urllib.parse` reports no host for it — so it is matched explicitly rather
    than silently treated as hostless, which would make every SSH remote
    unrecognised.
    """
    scp = _SCP_LIKE.match(url)
    if scp is not None:
        return scp.group("host").lower()

    match = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://(?:[^@/]+@)?(?P<host>[^:/]+)", url)
    return match.group("host").lower() if match is not None else None


def wiki_url(url: str) -> str:
    """The wiki repository URL for a remote, by the `.wiki.git` convention."""
    return (url[: -len(".git")] if url.endswith(".git") else url) + ".wiki.git"


def detect(repo: Repository, remote: str = "origin") -> GitPages:
    """Derive the publication target from a repository's remote, or refuse.

    Never falls back to a guess. A repository with no remote, or one on a host
    whose documentation convention Constat does not know, is a case for the
    user to answer with `--target`.
    """
    url = remote_url(repo, remote)
    if url is None:
        raise TargetUnknown(
            f"{repo.root} has no `{remote}` remote, so no publication target "
            "can be derived from it. Pass --target with the URL of the "
            "documentation repository to publish to."
        )

    host = _host_of(url)
    if host is None:
        raise TargetUnknown(
            f"could not read a host from the `{remote}` remote ({url}). "
            "Pass --target explicitly rather than having Constat guess where "
            "your documentation lives."
        )
    if host not in WIKI_HOSTS:
        known = ", ".join(WIKI_HOSTS)
        raise TargetUnknown(
            f"`{remote}` points at {host}, whose documentation convention "
            f"Constat does not know (it knows: {known}). Pass --target with "
            "the URL of the documentation repository. Refusing rather than "
            "assuming GitHub's `.wiki.git` convention: a push to a guessed "
            "URL is not undone by noticing afterwards."
        )
    return GitPages(wiki_url(url), derived_from=f"{remote} ({host})")


def _attribute(clone: Path, path: str, lines: tuple[DecisionLine, ...]):
    """Ask git who wrote each decision line, and whether it was signed.

    `git blame --line-porcelain` because a single file can carry decisions from
    several people, and attributing all of them to the file's last committer
    would credit the wrong reviewer — the kind of confident wrong answer this
    product exists to avoid.

    A blame that fails attributes nothing rather than guessing. The decisions
    are still returned, with `decided_by` unset, because a line nobody can be
    attributed to is a real state and losing the line would be worse.
    """
    blamed = run_git(
        ["blame", "--line-porcelain", "--", path], cwd=clone
    )
    if blamed.returncode != 0:
        return lines

    # line number -> (sha, author, author-time)
    by_line: dict[int, tuple[str, str, str]] = {}
    sha = author = when = None
    for row in blamed.stdout.split("\n"):
        if re.match(r"^[0-9a-f]{40} \d+ (\d+)", row):
            sha = row.split(" ", 1)[0]
            # Third field is the line number in the *final* file, which is
            # what `parse` counted.
            final_line = int(row.split(" ")[2])
            by_line[final_line] = ("", "", "")
            current = final_line
        elif row.startswith("author "):
            author = row[len("author ") :]
        elif row.startswith("author-time "):
            when = row[len("author-time ") :]
        elif row.startswith("\t") and sha is not None:
            by_line[current] = (sha, author or "", when or "")

    verdicts: dict[str, str] = {}
    attributed = []
    for line in lines:
        found = by_line.get(line.line_no)
        if found is None or not found[0]:
            attributed.append(line)
            continue
        sha, author, when = found
        if sha not in verdicts:
            verdicts[sha] = _signature_of(clone, sha)
        code, verification = verdicts[sha]
        attributed.append(
            replace(
                line,
                decided_by=author or None,
                decided_at=_iso(when),
                commit=sha,
                verification=verification,
                signature=code,
            )
        )
    return tuple(attributed)


def _signature_of(clone: Path, sha: str) -> tuple[str, str]:
    """`(raw %G? code, verification)` for one commit.

    **Three states, and the middle one is the finding that produced it.** A
    signature verified locally reads as `N` through a clone Constat made,
    because `git` needs `gpg.ssh.allowedSignersFile` or a keyring to check one
    — configuration that lives on the signer's machine and will never be on
    the machine reading the decisions back. Mapping that to "unsigned" would
    discard a real signature; mapping it to "signed and verified" would claim
    a check nobody performed.

    So presence is read from the commit object, where `gpgsig` sits regardless
    of trust configuration, and verification is reported separately:

    - `signed_commit` — git checked the signature and was satisfied (`G`, `U`).
    - `signed_unverified` — a signature is there and this machine cannot check
      it. Stronger evidence than an unsigned commit, weaker than a verified
      one, and it must not be rounded to either.
    - `git_commit` — no signature. The author is attested by history alone,
      which is still more than the CLI's unchecked `--by` string (D-061).
    """
    shown = run_git(["show", "--no-patch", "--format=%G?", sha], cwd=clone)
    code = shown.stdout.strip()[:1] if shown.returncode == 0 else "E"
    if code in ("G", "U"):
        return code, "signed_commit"

    body = run_git(["cat-file", "commit", sha], cwd=clone)
    header = body.stdout.split("\n\n", 1)[0] if body.returncode == 0 else ""
    if "gpgsig" in header:
        return code, "signed_unverified"
    return code, "git_commit"


def _iso(epoch: str) -> str | None:
    """A git author-time as an ISO timestamp, or nothing if it is unreadable."""
    if not epoch.isdigit():
        return None
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat(
        timespec="seconds"
    )


def _context(item: Awaiting) -> str:
    """One proposal's prompt: what is being decided, then the line to write on.

    The context is **indented**, which `parse` already skips — the same
    mechanism that keeps the template's worked examples from arriving as
    decisions nobody made. So a reviewer reads and writes in one place, and
    nothing Constat wrote here is ever read back as a verdict.

    A revision shows both statements. "Is this a change, and is the change
    right" is the reviewer's whole question, and it cannot be answered from
    the new statement alone (CON-120).
    """
    if item.previous is None:
        return f"**NEW** — {item.statement}\n"
    # Both statements, because "is this a change, and is the change right" is
    # the reviewer's whole question and the new one alone cannot answer it.
    return f"**WAS** — {item.previous}\n\n**NOW** — {item.statement}\n"


class GitPages:
    """A git repository used as a documentation target."""

    name = NAME

    def __init__(self, url: str, *, derived_from: str | None = None) -> None:
        self.url = url
        self.derived_from = derived_from

    def describe(self) -> str:
        if self.derived_from is None:
            return self.url
        return f"{self.url} (derived from {self.derived_from})"

    @staticmethod
    def safe_name(reference: str) -> str:
        """The filename stem for a reference.

        Sanitised because a reference reaches here from a commit message and a
        reference like `../../etc/x` must not become a path. Everything outside
        a conservative set becomes `-`.
        """
        return re.sub(r"[^A-Za-z0-9._-]", "-", reference).strip("-.") or "document"

    def page_for(self, reference: str) -> str:
        """Where a page goes: the root for the whole-product pages, `areas/`
        for an area, `decisions/` for a ticket (CON-113, CON-123).

        The directory is the separation. Both audiences share one target, so a
        reader can tell from the path which of the two they are reading, and
        the business pages carry no path of their own (D-115).

        A ticket page sits at `decisions/630.md`, directly above the
        `decisions/630/` pages it links to: one folder for the whole act of
        deciding, nesting the way a wiki already nests it.
        """
        if reference.startswith(AREA_PREFIX):
            safe = self.safe_name(reference[len(AREA_PREFIX):])
            return f"{AREAS_DIRECTORY}/{safe}.md"
        safe = self.safe_name(reference)
        if is_generated(reference):
            return f"{safe}.md"
        return f"{TICKETS_DIRECTORY}/{safe}.md"

    def references_published(self, prefix: str) -> tuple[str, ...]:
        """Every reference already published under `prefix` (CON-111).

        Read from a fresh clone rather than remembered: the target is the only
        thing that knows what is on it, and a workspace that published from
        another machine would otherwise rewrite nothing.

        The inverse of `page_for`, so it only reports pages this naming scheme
        could have produced — a file somebody added by hand that happens to
        start with the prefix is reported too, and that is the honest answer:
        Constat cannot tell them apart and must not assume it can.
        """
        workdir = Path(tempfile.mkdtemp(prefix="constat-list-"))
        try:
            clone = workdir / "pages"
            result = run_git(
                ["clone", "--quiet", "--depth", "1", self.url, str(clone)]
            )
            if result.returncode != 0:
                # Nothing published yet is indistinguishable from unreachable
                # here, and both mean the same thing to the caller: there is
                # no page to tombstone. A real failure surfaces on the write.
                return ()
            # An area page lives in `areas/` and is named without its
            # prefix, so the reference is rebuilt from the stem. It
            # round-trips to the same file even though the area's exact
            # name cannot be recovered — sanitising is one-way.
            if prefix == AREA_PREFIX:
                found = sorted(
                    f"{AREA_PREFIX}{path.name[: -len('.md')]}"
                    for path in (clone / AREAS_DIRECTORY).glob("*.md")
                ) if (clone / AREAS_DIRECTORY).is_dir() else []
            else:
                found = sorted(
                    path.name[: -len(".md")]
                    for path in clone.glob(f"{prefix}*.md")
                )
            return tuple(found)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def read_decisions(self, reference: str) -> DecisionsRead:
        """Read the decisions a reviewer wrote in the target (CON-58).

        Clones afresh every time rather than caching. A decision file read from
        a stale copy would report an approval as absent, and "nobody has
        decided" is the one answer that must never be wrong by omission
        (D-041). The clone is shallow and removed afterwards, like `publish`.

        **Returns a reading, never applies one.** Nothing here touches the
        catalogue: D-089 intends an off-CLI approval to count and says the
        amendment to D-055 lands with the mechanism that enforces it, so this
        half reads and reports.
        """
        workdir = Path(tempfile.mkdtemp(prefix="constat-decisions-"))
        try:
            clone = workdir / "pages"
            result = run_git(
                ["clone", "--quiet", self.url, str(clone)]
            )
            if result.returncode != 0:
                raise DecisionsNotReadable(
                    f"could not clone the documentation repository {self.url}: "
                    f"{result.stderr.strip() or 'git clone failed'}. Refusing "
                    "rather than reporting no decisions: an empty answer would "
                    "read as 'nobody has decided'."
                )

            folder = folder_for(self.safe_name(reference))
            location = f"{self.url} :: {folder}/"
            # Numerically where the name is a proposal id, so 9 comes before
            # 10 — a reader of the report sees the queue in the order the
            # proposals were raised rather than in dictionary order.
            def _order(path: Path) -> tuple[int, int, str]:
                stem = path.stem
                if stem.isdigit():
                    return (0, int(stem), "")
                return (1, 0, stem)

            files = sorted((clone / folder).glob("*.md"), key=_order)

            # The file CON-122 replaced is still read if a target has one.
            # Not rewritten and not deleted: it may already hold verdicts
            # nobody has recorded yet, and a reader who stopped looking there
            # would drop a decision somebody believes they made — the
            # substitution D-041 exists to prevent.
            legacy = clone / f"{folder}.md"
            if legacy.exists() and GENERATED_MARKER not in legacy.read_text():
                files.append(legacy)
            if not files:
                # Absent, not empty. The page has never been published, so the
                # reviewer has had nowhere to write — a different situation
                # from having written nothing, and a reader must be able to
                # tell them apart.
                return DecisionsRead(
                    reference=reference, location=location, present=False
                )

            # One file per proposal (CON-122), so every file is parsed and
            # attributed on its own: the commit that carries a verdict is the
            # one that touched that proposal's page, not the ticket's last
            # edit anywhere.
            decisions: list = []
            unreadable: list = []
            for file in files:
                found, bad = parse(file.read_text())
                path = (
                    f"{folder}.md" if file.parent == clone / DECISIONS_DIRECTORY
                    else f"{folder}/{file.name}"
                )
                decisions.extend(_attribute(clone, path, found))
                unreadable.extend(bad)
            return DecisionsRead(
                reference=reference,
                location=location,
                decisions=tuple(decisions),
                unreadable=tuple(unreadable),
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def publish(
        self, reference: str, body: str, awaiting: tuple[Awaiting, ...] = ()
    ) -> PublishedRef:
        """Clone, write the page, commit and push. Returns where it landed."""
        workdir = Path(tempfile.mkdtemp(prefix="constat-publish-"))
        try:
            clone = workdir / "pages"
            result = run_git(["clone", "--quiet", "--depth", "1", self.url, str(clone)])
            if result.returncode != 0:
                raise PublishFailed(
                    f"could not clone the documentation repository {self.url}: "
                    f"{result.stderr.strip() or 'git clone failed'}. Nothing "
                    "has been published. An existing-but-empty repository is "
                    "fine — Constat makes the first commit — so this means the "
                    "repository is unreachable or does not exist. On GitHub "
                    "and GitLab a wiki is not created until it is opened once "
                    "in the browser."
                )

            page = clone / self.page_for(reference)
            # A ticket page lives under `decisions/` (CON-113, CON-123), which
            # a fresh clone does not have until something is written there.
            page.parent.mkdir(parents=True, exist_ok=True)

            # The one path where a page Constat writes can collide with a page
            # a person wrote. Before CON-123 the ticket page was at
            # `reviews/630.md` and `decisions/630.md` was the reviewer's own
            # file; now the ticket page *is* `decisions/630.md`. Writing over
            # a target published before the move would destroy verdicts
            # nobody had recorded — so a file at that path that is not
            # Constat's own refuses, loudly, and nothing is published.
            if (
                not is_generated(reference)
                and page.exists()
                and GENERATED_MARKER not in page.read_text()
                and page.read_text().strip()
            ):
                raise PublishFailed(
                    f"{self.page_for(reference)} in {self.url} was written by "
                    "a person, not by Constat, and publishing would overwrite "
                    "it. It is the decisions file as it was before one page "
                    "per rule proposal (D-126), and it may hold verdicts "
                    "nobody has recorded yet. Record them with `constat "
                    f"review {reference} --record-decisions`, then delete the "
                    "file in the target and publish again. Nothing has been "
                    "published."
                )
            unchanged = page.exists() and page.read_text() == body
            page.write_text(body)

            # Seeded once, if absent, and never written again (CON-58). The
            # reviewer needs somewhere to write that Constat does not own —
            # the page above is a living view rewritten on every run, so a
            # decision put there would be destroyed on the next publish.
            #
            # **Only for a ticket page.** A generated page carries no rule
            # proposal and says so in terms, and `--record-decisions` reads a
            # ticket's file and no other — so seeding one beside the
            # catalogue or an area invited a verdict that nothing would ever
            # read. A decision somebody believes was recorded is the failure
            # D-041 exists to prevent.
            # One file per proposal (CON-122), each seeded when its
            # proposal first appears and never written again — D-105's
            # promise, which a ticket-wide file could not keep while the
            # queue grew. On a wiki the file is also the unit the Edit button
            # acts on, so a page per proposal is what makes a decision per
            # rule possible at all.
            #
            # Nothing is seeded beside a generated page: it carries no
            # proposal and says so, and `--record-decisions` would never read
            # a verdict written there (D-041, D-117).
            seeded: list[str] = []
            if not is_generated(reference):
                stem = self.safe_name(reference)
                for item in awaiting:
                    path = file_for(stem, item.id)
                    decisions = clone / path
                    if decisions.exists():
                        continue
                    decisions.parent.mkdir(parents=True, exist_ok=True)
                    decisions.write_text(
                        TEMPLATE.format(
                            proposal=item.id,
                            name=item.name,
                            context=_context(item),
                            reference=reference,
                        )
                    )
                    seeded.append(path)
                    unchanged = False

            if unchanged:
                # Nothing to commit, and `git commit` would fail. Reporting it
                # as published is correct: the page holds this document.
                head = run_git(["rev-parse", "HEAD"], cwd=clone)
                return PublishedRef(
                    target=self.name,
                    location=f"{self.url} :: {self.page_for(reference)}",
                    reference=reference,
                    revision=head.stdout.strip() or None,
                )

            run_git(["add", "--", self.page_for(reference)], cwd=clone)
            for path in seeded:
                run_git(["add", "--", path], cwd=clone)
            committed = run_git(
                ["commit", "--quiet", "-m", COMMIT_SUBJECT.format(reference=reference)],
                cwd=clone,
            )
            if committed.returncode != 0:
                raise PublishFailed(
                    "could not commit the document: "
                    f"{committed.stderr.strip() or 'git commit failed'}. "
                    "Nothing has been published. If git reports an unknown "
                    "author, set user.name and user.email — Constat uses your "
                    "git identity rather than one of its own."
                )

            pushed = run_git(["push", "--quiet", "origin", "HEAD"], cwd=clone)
            if pushed.returncode != 0:
                raise PublishFailed(
                    f"could not push to {self.url}: "
                    f"{pushed.stderr.strip() or 'git push failed'}. Nothing "
                    "has been published; the commit exists only in a temporary "
                    "clone and is discarded."
                )

            head = run_git(["rev-parse", "HEAD"], cwd=clone)
            return PublishedRef(
                target=self.name,
                location=f"{self.url} :: {self.page_for(reference)}",
                reference=reference,
                revision=head.stdout.strip() or None,
            )
        finally:
            # Always, including after a failure: the clone may hold the
            # document, and a document is the thing being protected.
            shutil.rmtree(workdir, ignore_errors=True)
