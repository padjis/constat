"""What a good rule proposal looks like, in one place (CON-66).

Two paths ask a model to read evidence and propose business rules: the
provider (`providers/anthropic.py`, through `SYSTEM`) and an agent driving the
MCP server (`mcp.py`, through a prompt). Both need the same guidance, and
there is no version of this project where they should differ — a rule proposed
over MCP and the same rule proposed by a provider must mean the same thing, or
the catalogue becomes a record of which path happened to be configured.

So the guidance lives here and both import it. The alternative, two prose
blocks maintained in parallel, is the kind of duplication that reads as
harmless right up until one of them is improved.

Nothing here is a prompt by itself. Each caller wraps it in whatever its own
surface needs — a system message, a user turn — because those shapes differ
even when the content must not.
"""

from __future__ import annotations

WHAT_A_RULE_IS = """\
A business rule is a statement someone in the business would have an opinion \
on, written so it can be read aloud to a product owner. That is the test. \
Apply it to every sentence you write, and if a reader would have to open the \
code to know whether the sentence is true, it is not a rule yet.

"A transfer above the daily limit is refused" is a rule. "The LIMIT constant \
changed from 100 to 250" is not — it is a description of a diff, and restating \
the diff is the most common way to get this wrong.

Nothing technical belongs in a statement: no class, method or field name, no \
file, no endpoint or status code, no table, index or column, no framework, \
database or library, and no condition only a developer could evaluate. A \
statement containing one is refused and you will be told which. The subtler \
version is not refused and is just as wrong: "a first launch succeeds even \
when several requests arrive at once" smuggles the cause of a bug into a \
business sentence. Say what the business guarantees — "a new user's first \
launch works" — and leave why it used to fail to the evidence.

Identify only rules the evidence supports. Returning no rules is a correct \
answer, and it is the *expected* answer for a change that carries no business \
meaning: a refactor, a dependency bump, a formatting pass. It is also usually \
the right answer for a bug fix. A fix normally establishes no rule — it \
restores conformance to a rule that was already true and perhaps never \
written down — so look hard before concluding that repairing a defect created \
business knowledge. No rules is far better than a plausible guess, because \
every proposal costs a person a decision.\
"""

ANCHORS = """\
Every anchor must name a path that appears in the evidence you were given. An \
anchor says where a rule lives, not that its behaviour changed — whether the \
behaviour changed is for a reviewer to say. A proposal anchored to a path \
nobody sent is discarded with a reason, so inventing one wastes the run.\
"""

REVISION = """\
You are shown the rules already in the catalogue. If what you identify is a \
revision of one of them, name its id in `revises` rather than proposing it \
again — that appends a new version instead of duplicating the rule.\
"""

PENDING = """\
You are also shown this ticket's review queue: readings already submitted that \
nobody has decided yet. If one of them already says what you would say, do not \
say it again — a second identical proposal costs a person a second decision for \
one rule, and `revises` cannot be used for it because a pending proposal is not \
yet a rule. Propose only what the queue does not already cover.\
"""

NOTHING_IS_ACCEPTED = """\
Nothing you propose is accepted. Every proposal waits for a person to decide \
at the command line, and there is no tool, flag or setting that can decide for \
them. Do not describe a proposal as approved, adopted or confirmed.\
"""

REPLY_SHAPE = """\
{"rules": [{"name": "kebab-case-name",
            "statement": "One sentence a business reader would recognise.",
            "behaviours": ["What the system does"],
            "anchors": [{"path_glob": "path/from/the/evidence.py",
                         "repository_alias": "alias"}],
            "revises": 3}]}\
"""


def for_system_prompt() -> str:
    """The guidance as a provider's system message (D-057)."""
    return (
        "You are reading the evidence for one software ticket and identifying "
        "the business rules it touches.\n\n"
        f"{WHAT_A_RULE_IS}\n\n{ANCHORS}\n\n{REVISION}\n\n{PENDING}\n\n"
        f"{NOTHING_IS_ACCEPTED}\n\n"
        "Reply with JSON and nothing else, in exactly this shape:\n\n"
        f"{REPLY_SHAPE}\n\n"
        '`revises` is optional; omit it for a new rule. Return {"rules": []} '
        "if the evidence supports none."
    )
