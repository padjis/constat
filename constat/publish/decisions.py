"""Decisions a reviewer wrote in the published target (CON-58).

**Plain git, deliberately.** No forge API, no token, no per-platform backend:
Constat clones the target, reads one file, and asks `git` who wrote each line.
That works on github.com, on a self-hosted GitLab, on a bare repository over
SSH, on a path on disk — anywhere that is a git repository. A forge API would
have been the *less* generic choice, needing a backend and a credential per
platform, and product rule 7's "no stored credentials" survives precisely
because Constat is never the thing holding one.

**The reviewer's identity comes from the commit, never from the text.** A name
typed into a file is no better than the CLI's `--by` string, which nothing
checks (D-061). The commit author is attested by the repository's own history,
and a *signed* commit is verifiable by `git` itself — so this is the first
channel in Constat where an approval can be better evidenced than one made at
the command line. `git blame` attributes each line separately, because one file
can carry decisions from several people.

**One exact form, and everything else is reported.** A line Constat cannot read
is handed back verbatim with its number rather than guessed at: "looks fine to
me" beside a rule is not a decision, and inferring one from it would be the
unsupported certainty product rule 1 prohibits.

**Constat seeds this file once and never writes it again.** The published page
is a living view regenerated on every run, so a decision written there would be
destroyed — which is CON-39's problem, and the reason decisions live in their
own file instead. Constat owns the page; the reviewer owns this.

**Nothing in *this module* is applied.** Reading a decision is not recording
one, and the separation is deliberate: the format and the git plumbing live
here, and `operations.record_read_decisions` is the only thing that writes to
the catalogue (D-106). A reviewer can therefore be shown what Constat read
before anything acts on it, which is what `--read-decisions` is for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DECISIONS_DIRECTORY = "decisions"

#: `3: approved`, `R-7: rejected — the limit is per account, not per customer`.
#: Deliberately narrow. The separator may be an em dash or a hyphen because a
#: browser editor will produce either, and the verb is lower-case only so that
#: "Approved?" in a sentence cannot read as a decision.
DECISION_LINE = re.compile(
    r"^\s*(?P<ref>[A-Za-z]?-?\d+)\s*:\s*(?P<verdict>approved|rejected)\s*"
    r"(?:[—–-]\s*(?P<reason>.*?))?\s*$"
)

VERDICTS = ("approved", "rejected")

MARKER = "## decisions"
"""Where the reviewer's half of the file begins.

The template is mostly instructions, and a first implementation reported all
ten lines of them back as unreadable — which would bury the two lines that
mattered under the explanation of how to write them. So prose *above* this
heading is never reported, and anything unreadable *below* it is.

A reviewer who deletes the heading gets their whole file scanned instead, which
is noisier but loses nothing. Noisy beats silent: an unread decision reported as
prose is a decision somebody believes was recorded.
"""

#: Written once, if the file is absent, and never touched again.
TEMPLATE = """# Decisions for {reference}

Write one decision per line, in exactly this form:

    1: approved
    2: rejected — the limit is per account, not per customer

The number is the rule proposal's id, shown on the document page beside each
rule. The reason is optional. Only `approved` and `rejected` are read; any
other line is reported back to you unchanged rather than guessed at.

**Do not write your name.** Who decided is taken from the commit that added
the line, which the repository attests and a typed name does not. Sign the
commit if you want it verifiable rather than merely attributed.

A rejection means *inconclusive* — the evidence did not settle it — not that
the rule is wrong (D-036).

Nothing here takes effect on its own. Someone reads these back with
`constat review {reference} --read-decisions`, which reports what you wrote
and records nothing, and then records it against the catalogue with
`constat review {reference} --record-decisions`.
Reading twice is safe: the same line in the same commit is recorded once.

<!-- Constat wrote this file once and will never change it again. The document
     page beside it is regenerated on every run; this is yours. -->

## Decisions

"""


@dataclass(frozen=True)
class DecisionLine:
    """One decision, with who wrote it according to git."""

    reference: str
    """The rule proposal id or rule citation as written — `3`, `R-7`."""

    verdict: str
    reason: str | None
    line_no: int

    #: From `git blame`, not from the text. `None` only for a line that is not
    #: committed yet, which cannot happen through a clone but can in a test.
    decided_by: str | None = None
    decided_at: str | None = None
    commit: str | None = None

    #: How well the identity above is evidenced. Never `asserted` — that is
    #: what a CLI `--by` string is (D-061), and being better than it is the
    #: point of this channel.
    #:
    #: - `signed_commit` — git checked the signature and was satisfied.
    #: - `signed_unverified` — signed, and this machine cannot check it: the
    #:   allowed-signers file or keyring lives on the signer's machine. Not
    #:   rounded to either neighbour, because both would be a false claim.
    #: - `git_commit` — unsigned; the author is attested by history alone.
    verification: str = "git_commit"

    #: The raw `%G?` code, kept so nothing is lost in the mapping above: `G`
    #: good, `U` good but untrusted key, `B` bad, `N` none, `E` unverifiable.
    signature: str | None = None

    def describe(self) -> str:
        who = self.decided_by or "an uncommitted line"
        said = f"{self.reference}: {self.verdict}"
        if self.reason:
            said += f" — {self.reason}"
        return f"{said}  [{who}, {self.verification}]"


@dataclass(frozen=True)
class DecisionsRead:
    """What the target's decision file said, and what could not be read."""

    reference: str
    location: str
    decisions: tuple[DecisionLine, ...] = ()
    unreadable: tuple[tuple[int, str], ...] = field(default=())
    """Line number and text, verbatim, for every line that is not a decision.

    Reported rather than dropped. A reviewer who wrote `1: aproved` has made a
    decision Constat cannot read, and silence would leave them believing it had
    been recorded — the substitution D-041 refuses.
    """

    present: bool = True
    """False when the target has no decision file at all.

    Distinguished from an empty one, because "nobody has written anything" and
    "the file is not there" are different situations: the second means the page
    has never been published, and the reviewer has nowhere to write.
    """

    @property
    def approved(self) -> tuple[DecisionLine, ...]:
        return tuple(d for d in self.decisions if d.verdict == "approved")

    @property
    def rejected(self) -> tuple[DecisionLine, ...]:
        return tuple(d for d in self.decisions if d.verdict == "rejected")


def file_for(page: str) -> str:
    """The decision file beside a published page.

    Derived from the page filename rather than from the reference, so the two
    cannot disagree about what counts as a safe path — `page_for` already did
    that sanitising, and repeating the rule is how two rules drift apart.
    """
    return f"{DECISIONS_DIRECTORY}/{page}"


def parse(text: str) -> tuple[tuple[DecisionLine, ...], tuple[tuple[int, str], ...]]:
    """Read decisions out of a file's text. Knows nothing about git.

    Separated so the format is testable without a repository, and so a second
    git-backed target cannot invent a second format.

    A decision is read wherever it appears. An *unreadable* line is only
    reported from below the `## Decisions` heading, because everything above it
    is the template's own instructions — reporting those would bury the lines
    that matter under the explanation of how to write them.

    Indented lines are skipped entirely: the template's worked examples are
    indented, and `1: approved` in the instructions must not arrive as a
    decision nobody made.
    """
    decisions: list[DecisionLine] = []
    unreadable: list[tuple[int, str]] = []
    in_reviewer_region = MARKER not in text.lower()

    for number, raw in enumerate(text.split("\n"), start=1):
        line = raw.strip()
        if line.lower().startswith(MARKER):
            in_reviewer_region = True
            continue
        if not line:
            continue
        if raw.startswith(("    ", "\t")):
            continue
        if line.startswith("<!--") or line.startswith("-->"):
            continue

        matched = DECISION_LINE.match(line)
        if matched is None:
            if in_reviewer_region:
                unreadable.append((number, raw.rstrip()))
            continue

        reason = (matched.group("reason") or "").strip() or None
        decisions.append(
            DecisionLine(
                reference=matched.group("ref"),
                verdict=matched.group("verdict"),
                reason=reason,
                line_no=number,
            )
        )

    return tuple(decisions), tuple(unreadable)
