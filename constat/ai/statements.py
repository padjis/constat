"""Refusing a rule statement that leaks code (CON-74, D-066).

A rule is a business statement. D-066 made that absolute: no mechanism, no
identifier, no endpoint, no file, no technology, no condition only a developer
could evaluate. A sentence that cannot be read aloud to a product owner is not
a rule, whatever evidence it is attached to.

**What this module can and cannot do.** It cannot decide whether a sentence is
*business-oriented* — that is a judgement, and guessing at judgements is what
this product refuses to do everywhere else. What it can do is catch **code
leaking into prose**, syntactically and without interpretation: an identifier,
a path, an annotation, a call, an HTTP verb or status. The same posture as the
credential scan — a signal, not an opinion.

So the honest division of labour is:

* **leakage** is refused here, mechanically and with the offending token named;
* **business-ness** is the guidance's job (`WHAT_A_RULE_IS`) and the
  reviewer's.

The statement that caused D-066 — *"a first launch succeeds even when the
app's launch sends several requests at once"* — contains no code token at all
and passes every check below. It is still not a business rule. Nothing here
pretends otherwise, and a reader who expects this to guarantee quality will be
disappointed in exactly that case.

**Deliberately forgiving in one direction.** Every pattern needs two signals
or an unambiguous one, because a false refusal is worse than a miss: it
discards a reading a person might have accepted, and the reader is given no
way to argue. `AdSense`, `GitHub`, `JavaScript` and `iPhone` carry one internal
capital and pass; `findOrCreateDevice`, `DeviceProvisioningService` and
`PostgreSQL` carry two or more and do not. A technology name is out by D-066
anyway, so refusing the third is not an accident.
"""

from __future__ import annotations

import re

LEAKS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "an identifier",
        # Two or more internal capitals: findOrCreate, DeviceService,
        # PostgreSQL. One is left alone so AdSense and GitHub survive.
        #
        # The first segment must contain a lowercase letter, or every
        # all-caps business word matches: VAT, SMS, PDF and KYC each look
        # like three "internal capitals" to a pattern that does not insist
        # on a lowercase run first.
        re.compile(r"\b[A-Za-z][a-z0-9]+(?:[A-Z][a-z0-9]*){2,}\b"),
    ),
    (
        "a qualified name",
        # Service.method, module.attr. Both sides must contain a letter, so
        # "1.1%" and a sentence's full stop are not names.
        re.compile(r"\b[A-Za-z][A-Za-z0-9]*\.[A-Za-z][A-Za-z0-9]{2,}\b"),
    ),
    (
        "a file path",
        re.compile(r"\b[\w.-]+/[\w.-]+|\b\w+\.(?:py|ts|js|java|kt|go|rb|sql|yaml|yml|json)\b"),
    ),
    ("a snake_case identifier", re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")),
    ("an annotation or decorator", re.compile(r"[@#]\w+")),
    ("a function call", re.compile(r"\b\w+\(\s*\)|\b\w+\([^)]*\)")),
    (
        "an HTTP method or status",
        # Status codes are matched only through the word HTTP. A bare `[45]\d\d`
        # would refuse "a transfer above 500 euros is refused" — which is the
        # canonical example of a business rule, not a leak.
        re.compile(r"\bHTTP\b|\b(?:GET|POST|PUT|PATCH|DELETE)\b"),
    ),
    # No semicolon. It was here until 2026-11-19 and was a false positive: a
    # semicolon is ordinary English punctuation, and refusing it discarded a
    # real rule on the first real use of the baseline path. **The accepted
    # rule R-2 in the author's own catalogue contains one** — "Losing an
    # analytics beacon is acceptable; failing a request a user is waiting on is
    # not" — so the gate had come to refuse a rule a human had already agreed
    # to. That is the failure this module's own docstring warns about: a false
    # refusal discards a reading a person might have accepted, and the reader
    # cannot argue back.
    ("a code fence or inline code", re.compile(r"[`{}<>]|::")),
)

ALLOWED = ("i.e.", "e.g.", "etc.", "vs.")
"""Prose abbreviations that look like qualified names. Removed before the
patterns run rather than exempted inside them, which would make every pattern
carry a clause about English."""


def restates(example_text: str, statement: str) -> bool:
    """Whether an example is the statement said again rather than a case of it.

    An example earns its place by being **specific**: a situation concrete
    enough that a business reader can say "no, that's not what happens". A
    model asked for examples will sometimes return the statement with the
    words shuffled, which costs a reviewer a line to read and tells them
    nothing new.

    Mechanical and deliberately blunt: compare the two as word sets, ignoring
    order and the commonest function words. Near-identity is a restatement;
    anything else is left alone.

    **Errs toward allowing**, like `code_leakage` and for the same reason — a
    false refusal discards a case a person might have wanted, and the reader
    cannot argue back. An example that shares most of the statement's words
    while adding a real quantity, name or condition keeps those extra words and
    so falls under the threshold.
    """
    def shape(text: str) -> frozenset[str]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        return frozenset(w for w in words if w not in _FILLER)

    left, right = shape(example_text), shape(statement)
    if not left or not right:
        return False
    overlap = len(left & right) / len(left | right)
    return overlap >= 0.85


_FILLER = frozenset(
    "a an the is are was were be been being do does did not no of to in on at "
    "for with by from and or but if then than that this these those it its as "
    "when while which who whom whose into over under".split()
)
"""Function words, removed before comparing. Left in, they inflate the overlap
of any two English sentences and a real example starts looking like a
restatement."""


def code_leakage(text: str) -> str | None:
    """What kind of code `text` leaks, or None if it reads as prose.

    Returns a description rather than a bool so the refusal can say what to
    remove. A reading told "not business-oriented" has nothing to act on; one
    told "contains an identifier: `findOrCreateDevice`" does.
    """
    cleaned = text
    for abbreviation in ALLOWED:
        cleaned = cleaned.replace(abbreviation, "")

    for description, pattern in LEAKS:
        found = pattern.search(cleaned)
        if found is not None:
            return f"{description}: {found.group(0).strip()!r}"
    return None
