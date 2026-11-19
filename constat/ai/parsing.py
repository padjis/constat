"""Turning a provider's reply into proposals — or refusing it.

This is the trust boundary on AI output, and it exists before any real
provider does, because every property worth enforcing here is enforceable
without spending anything.

Three rules shape it.

**A reply that cannot be parsed is an error, never an empty result.** The
tempting implementation returns no proposals when the JSON is broken, and the
document then reads "no rules were identified" — a parse failure wearing the
costume of a finding. That is the same mistake D-041 refused for a
misconfigured provider, and it is refused again here.

**An anchor must be grounded in the evidence.** A model will cheerfully
propose a rule anchored to `src/billing/limits.py` whether or not that file
was in the payload. An anchor pointing at a path nobody sent is a fabrication,
and a governance tool that stores it has invented its own evidence. Anchors
are checked against the paths actually present, and ungrounded proposals are
dropped with a reason.

**Rejections are reported, not swallowed.** If a model returns eight rules and
six are discarded, a document showing two and saying nothing has misrepresented
what happened. Every rejection carries a reason and reaches the document.

A reply may also claim to **revise** an existing rule by naming its id
(D-050). That claim is checked the same way an anchor is: the rule has to have
been in the payload. A reading cannot have read a rule it was never shown, so
claiming a relationship to one is inventing it.
"""

from __future__ import annotations

from typing import Mapping

import json
import re
from dataclasses import dataclass

from ..errors import MalformedResponse
from ..globs import matches_path
from ..models import Anchor, Behaviour, Example, Message, RuleProposal
from .redaction import ProviderPayload
from .statements import code_leakage, restates

FENCE = re.compile(r"^\s*```(?:json)?\s*(?P<body>.*?)\s*```\s*$", re.DOTALL)
"""Models wrap JSON in a code fence more often than not. Unwrapping it is
pragmatism, not laxity: the content inside still has to parse, and anything
that is not JSON is still refused."""

MAX_AREA = 60
"""An area is a heading, not a sentence. A long one is a statement that has
wandered into the wrong field."""

RELATIONS = ("establishes", "revises", "repairs")
"""How a reading may stand to the catalogue (D-065). Kept here beside the
parse that enforces it: SQLite cannot add a CHECK to an existing column, so a
migrated workspace relies on this gate exactly as a fresh one does."""

MAX_MESSAGE = 500
"""A user-facing message. Longer than an example half, because real messages
run to several sentences of instruction — and still bounded, because an
unbounded one is prose that wandered out of the statement."""

MAX_EXAMPLE = 200
"""Each half of an example. A case is a sentence, not a scenario document; past
this length it is prose that belongs in the statement or nowhere."""

MAX_NAME = 120
MAX_STATEMENT = 600
"""Bounds on generated text. An unbounded statement would let a model write a
page of prose into a field a reviewer has to read in a list."""


@dataclass(frozen=True)
class Rejection:
    """A proposal that was discarded, and why.

    Carries the proposed name only. The rest of a rejected proposal is not
    kept: it is unvalidated model output, and storing it would put
    unattributable text into a governance record.
    """

    name: str
    reason: str

    def describe(self) -> str:
        return f"`{self.name}` — {self.reason}"


@dataclass(frozen=True)
class ParseResult:
    proposals: tuple[RuleProposal, ...] = ()
    rejections: tuple[Rejection, ...] = ()

    @property
    def note(self) -> str:
        """What the document says about this pass.

        Never silent. Both halves matter: what was proposed, and what was
        thrown away.
        """
        if not self.proposals and not self.rejections:
            return (
                "The provider returned no rules. That is the provider finding "
                "none in this evidence, not a statement that none exist."
            )
        parts = []
        if self.rejections:
            parts.append(
                f"{len(self.rejections)} proposal(s) were discarded as "
                "ungrounded or malformed, listed below."
            )
        return " ".join(parts)


def _known_rules(payload: ProviderPayload) -> set[int]:
    """Rule ids the provider was actually shown.

    A `revises` claim naming a rule that was not in the payload is as
    ungrounded as an anchor naming a path nobody sent: the reading cannot have
    read it, so it is inventing a relationship rather than observing one.
    """
    return {rule.rule_id for rule in payload.catalogue}


def _known(payload: ProviderPayload) -> tuple[set[str], set[str]]:
    """The paths and repository aliases the provider was actually given."""
    aliases = {r.alias for r in payload.repositories}
    paths = {
        changed.path
        for r in payload.repositories
        for c in r.commits
        for changed in c.files
    }
    return paths, aliases


def _unwrap(text: str) -> str:
    match = FENCE.match(text)
    return match.group("body") if match else text


def _load(text: str) -> list[dict]:
    """Parse the reply, or raise. Never returns an empty list for bad input."""
    if not text.strip():
        raise MalformedResponse(
            "the provider returned an empty reply. Treated as an error rather "
            "than as 'no rules were identified', which would present a "
            "provider failure as a finding."
        )

    try:
        document = json.loads(_unwrap(text))
    except json.JSONDecodeError as exc:
        raise MalformedResponse(
            f"the provider's reply is not valid JSON ({exc.msg} at line "
            f"{exc.lineno}). Refused rather than reported as no rules found."
        ) from None

    if not isinstance(document, dict) or "rules" not in document:
        raise MalformedResponse(
            "the provider's reply is JSON but has no top-level 'rules' key, so "
            "it cannot be distinguished from a reply that found nothing."
        )

    rules = document["rules"]
    if not isinstance(rules, list):
        raise MalformedResponse("the 'rules' key is not a list.")
    return rules


def _behaviours(raw: object) -> tuple[Behaviour, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(
        Behaviour(description=item.strip())
        for item in raw
        if isinstance(item, str) and item.strip()
    )


def _messages(raw: object) -> tuple[Message, ...] | str:
    """Parsed messages, or a reason to reject the whole proposal (CON-82).

    **No code-leakage check, deliberately.** A message is a quotation of what
    the product shows a user, and real messages carry file names, error codes
    and product names. D-066's gate exists to keep *Constat's own sentences*
    business-readable; applying it to a verbatim quotation would refuse the
    true text and leave a reader with a sanitised approximation — which is
    worse than nothing, because it looks like evidence.

    What is checked is that the text is non-empty, bounded, and not repeated
    within one reading.
    """
    if raw is None:
        return ()
    if not isinstance(raw, list):
        return "'messages' is not a list"

    messages: list[Message] = []
    seen: set[str] = set()
    for position, item in enumerate(raw, start=1):
        if not isinstance(item, str):
            return f"message {position} is not a string"
        text = item.strip()
        if not text:
            return f"message {position} is empty"
        if len(text) > MAX_MESSAGE:
            return (
                f"message {position} is longer than {MAX_MESSAGE} characters; "
                "a message is what the product shows, not a description of it"
            )
        if text in seen:
            return f"message {position} repeats an earlier one"
        seen.add(text)
        messages.append(Message(text=text))
    return tuple(messages)


def _examples(raw: object, statement: str) -> tuple[Example, ...] | str:
    """Parsed examples, or a reason to reject the whole proposal (CON-80).

    Returns a string rather than dropping a bad example, because a silently
    dropped one is the "eight rules in, two out, nothing said" failure this
    module exists to prevent — applied one level down. A reading that offered
    three cases and had one quietly removed has been edited, not parsed.

    Absent or empty is fine and returns `()`: examples are optional, and a
    rule without them is weaker rather than invalid.
    """
    if raw is None:
        return ()
    if not isinstance(raw, list):
        return "'examples' is not a list"

    examples: list[Example] = []
    seen: set[str] = set()
    for position, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            return f"example {position} is not an object with a situation and an outcome"

        situation = item.get("situation")
        outcome = item.get("outcome")
        situation = situation.strip() if isinstance(situation, str) else ""
        outcome = outcome.strip() if isinstance(outcome, str) else ""

        # Both halves, always. A situation with no outcome is a case nobody
        # answered, and an outcome with no situation is an assertion with
        # nothing to check it against. Either one alone would render as a table
        # row with a blank cell, which reads as an omission by Constat rather
        # than by the reading.
        if not situation:
            return f"example {position} has no situation"
        if not outcome:
            return f"example {position} has no outcome"
        if len(situation) > MAX_EXAMPLE or len(outcome) > MAX_EXAMPLE:
            return (
                f"example {position} is longer than {MAX_EXAMPLE} characters; "
                "an example is a case, not a scenario"
            )

        # The same test as the statement and the behaviours (D-066). An example
        # is read by the same person, in the same table, and a rule whose
        # statement is clean and whose examples name files is still technical.
        for half, text in (("situation", situation), ("outcome", outcome)):
            leak = code_leakage(text)
            if leak is not None:
                return (
                    f"the {half} of example {position} is not business "
                    f"language — it contains {leak} (D-066)"
                )

        if restates(f"{situation} {outcome}", statement):
            return (
                f"example {position} restates the statement instead of giving "
                "a case of it; an example has to be specific enough to "
                "disagree with"
            )

        key = situation.lower()
        if key in seen:
            return f"example {position} repeats an earlier situation"
        seen.add(key)

        examples.append(Example(situation=situation, outcome=outcome))

    return tuple(examples)


def _anchors(
    raw: object,
    paths: set[str],
    aliases: set[str],
    mainline: Mapping[str, frozenset[str]] | None = None,
) -> tuple[Anchor, ...]:
    """Grounded anchors only. An ungrounded one leaves the tuple empty, which
    the caller treats as a rejection.

    Two grounds, tried in that order (D-072). The ticket's changed paths come
    first because they are the stronger claim; the product's mainline files
    come second, so a rule can be anchored where it actually lives even when
    this ticket did not touch it. Which ground was used is recorded on the
    anchor, never flattened — "the evidence shows this changed" and "this file
    exists" are different claims.

    `mainline` is **not** part of the payload. The reader is told the rule in
    the guidance and is not handed a thousand file paths it did not ask for:
    sending the whole tree to a provider on every gather would cost real money
    to say something a sentence covers.
    """
    if not isinstance(raw, list):
        return ()

    mainline = mainline or {}
    anchors = []
    for item in raw:
        if isinstance(item, str):
            item = {"path_glob": item}
        if not isinstance(item, dict):
            return ()

        glob = item.get("path_glob")
        if not isinstance(glob, str) or not glob.strip():
            return ()
        glob = glob.strip()

        alias = item.get("repository_alias")
        if alias is not None:
            # Known from the payload, or from the mainline map — whose keys are
            # the registered repositories. A baseline's payload carries no
            # repositories at all (there is no ticket evidence), so without the
            # second source every repository-scoped anchor in a baseline would
            # be refused as naming a repository nobody showed the reader.
            known_alias = alias in aliases or alias in (mainline or {})
            if not isinstance(alias, str) or not known_alias:
                return ()

        if any(matches_path(path, glob) for path in paths):
            ground = "evidence"
        elif _in_mainline(glob, alias, mainline):
            ground = "mainline"
        else:
            return ()

        anchors.append(
            Anchor(path_glob=glob, repository_alias=alias, grounded_in=ground)
        )
    return tuple(anchors)


def _in_mainline(
    glob: str, alias: str | None, mainline: Mapping[str, frozenset[str]]
) -> bool:
    """Whether the glob matches a file in mainline.

    An anchor with no repository is checked against every repository, matching
    how an unscoped anchor already matches everywhere when a document asks
    which rules a change touches.
    """
    scopes = [mainline[alias]] if alias in mainline else list(mainline.values())
    return any(
        matches_path(path, glob) for paths in scopes for path in paths
    )


def parse(
    text: str,
    payload: ProviderPayload,
    mainline: Mapping[str, frozenset[str]] | None = None,
) -> ParseResult:
    """Parse a provider reply into grounded proposals.

    Raises `MalformedResponse` if the reply as a whole is unusable. Individual
    proposals that are malformed or ungrounded are rejected with a reason
    rather than failing the run: one bad rule in eight should not discard the
    other seven, but it must not vanish silently either.
    """
    paths, aliases = _known(payload)
    known_rules = _known_rules(payload)
    proposals: list[RuleProposal] = []
    rejections: list[Rejection] = []
    seen: set[str] = set()

    for index, raw in enumerate(_load(text), start=1):
        if not isinstance(raw, dict):
            rejections.append(Rejection(f"#{index}", "not an object"))
            continue

        name = raw.get("name")
        name = name.strip() if isinstance(name, str) else ""
        label = name or f"#{index}"

        statement = raw.get("statement")
        statement = statement.strip() if isinstance(statement, str) else ""

        if not name:
            rejections.append(Rejection(label, "no name"))
            continue
        if len(name) > MAX_NAME:
            rejections.append(Rejection(label[:MAX_NAME], "name is too long"))
            continue
        if not statement:
            rejections.append(Rejection(label, "no statement"))
            continue
        if len(statement) > MAX_STATEMENT:
            rejections.append(Rejection(label, "statement is too long"))
            continue

        # A rule is a business statement, always (D-066). Leakage is refused
        # here and named, so the reading is told what to remove; whether the
        # sentence is *business-oriented* is a judgement this cannot make and
        # does not pretend to — see `statements.py`.
        leak = code_leakage(statement)
        if leak is not None:
            rejections.append(
                Rejection(
                    label,
                    f"the statement is not a business statement — it contains "
                    f"{leak}. A rule has to read aloud to a product owner "
                    "(D-066).",
                )
            )
            continue
        if name in seen:
            rejections.append(Rejection(label, "duplicate name in one reply"))
            continue

        area = raw.get("area")
        area = area.strip() if isinstance(area, str) else ""
        if area:
            if len(area) > MAX_AREA:
                rejections.append(
                    Rejection(label, f"'area' is longer than {MAX_AREA} characters")
                )
                continue
            # D-066 unchanged: "advertising" is an area, a package name is not.
            # The same gate, because an area is a business statement too — the
            # heading a business reader navigates by (D-070).
            leak = code_leakage(area)
            if leak is not None:
                rejections.append(
                    Rejection(
                        label,
                        f"'area' is not a business area — it contains {leak}. "
                        "An area is what a business reader would call this part "
                        "of the product (D-066, D-070).",
                    )
                )
                continue

        relation = raw.get("relation")
        relation = relation.strip().lower() if isinstance(relation, str) else None
        if relation is not None and relation not in RELATIONS:
            rejections.append(
                Rejection(
                    label,
                    f"'relation' is {relation!r}, not one of "
                    f"{', '.join(RELATIONS)} (D-065)",
                )
            )
            continue

        revises = raw.get("revises")
        if revises is not None:
            if not isinstance(revises, int) or isinstance(revises, bool):
                rejections.append(Rejection(label, "'revises' is not a rule id"))
                continue
            if revises not in known_rules:
                # Symmetric with an ungrounded anchor: the reading is claiming
                # a relationship to something it was never shown.
                rejections.append(
                    Rejection(
                        label,
                        f"claims to revise rule {revises}, which was not in "
                        "the evidence supplied",
                    )
                )
                continue

        # Behaviours are part of the rule, so the same test applies. A rule
        # whose statement is clean and whose behaviours name classes is still
        # a technical record of a rule.
        behaviours = _behaviours(raw.get("behaviours"))
        leaking = next(
            ((b, code_leakage(b.description)) for b in behaviours if code_leakage(b.description)),
            None,
        )
        if leaking is not None:
            rejections.append(
                Rejection(
                    label,
                    f"a behaviour is not a business statement — it contains "
                    f"{leaking[1]} (D-066).",
                )
            )
            continue

        # A relation and an id have to agree. `revises` without an id names
        # nothing; `repairs` with one claims a relationship this ticket cannot
        # express yet (CON-73's boundary), and silently dropping either half
        # would store a reading that says something the reader did not.
        if relation == "revises" and revises is None:
            rejections.append(
                Rejection(label, "'relation' is 'revises' but no rule id was named")
            )
            continue
        if relation == "repairs" and revises is not None:
            rejections.append(
                Rejection(
                    label,
                    "a repair states the rule it repairs rather than naming an "
                    "id: drop 'revises', or use 'revises' if the rule's "
                    "statement is changing (D-065)",
                )
            )
            continue
        if relation is None:
            # Inferred from the id, which is what the two relations meant
            # before there was a field for them. Not a default: it is the same
            # fact the reply already stated, read a second way.
            relation = "revises" if revises is not None else "establishes"

        examples = _examples(raw.get("examples"), statement)
        if isinstance(examples, str):
            rejections.append(Rejection(label, examples))
            continue

        messages = _messages(raw.get("messages"))
        if isinstance(messages, str):
            rejections.append(Rejection(label, messages))
            continue

        anchors = _anchors(raw.get("anchors"), paths, aliases, mainline)
        if not anchors:
            # Deliberately fatal for the proposal. An unanchored rule can
            # never be matched to a future change (CON-40), and an anchor
            # naming a path nobody sent is the model inventing evidence.
            rejections.append(
                Rejection(
                    label,
                    "no anchor grounded in the evidence supplied, or in any "
                    "registered repository's mainline",
                )
            )
            continue

        seen.add(name)
        proposals.append(
            RuleProposal(
                name=name,
                statement=statement,
                behaviours=behaviours,
                messages=messages,
                examples=examples,
                anchors=anchors,
                revises_rule_id=revises,
                relation=relation,
                area=area or None,
            )
        )

    return ParseResult(proposals=tuple(proposals), rejections=tuple(rejections))
