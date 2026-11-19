"""Workspace schema.

Versioned from the first release (D-008). A stored governance record is
useless if the schema that produced it cannot be identified.

Two integrity rules from ARCHITECTURE.md section 5 are enforced **by the
database**, not by application code: approved versions cannot be updated or
deleted. Application-level immutability is a convention a future bug can break
silently; a trigger cannot be bypassed by forgetting to call the right helper.
"""

from __future__ import annotations

SCHEMA_VERSION = 19

SCHEMA = """
-- Workspace settings: answers that belong to a setup rather than to a run.
--
-- `reader` is who reads the evidence — `mcp` (an agent, through the MCP
-- server) or `provider` (Constat itself). D-059 refuses a rule-generating
-- command when nothing can read, and the only way to tell "an agent will read
-- this next" from "you forgot the key" is to be told. Being told once, here,
-- beats being asked on every ticket (D-060).
CREATE TABLE setting (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE schema_meta (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    schema_version  INTEGER NOT NULL,
    constat_version TEXT    NOT NULL,
    created_at      TEXT    NOT NULL
);

-- A registered repository (D-027). `identity` is the root commit (D-025):
-- it survives the repository being moved, renamed or re-cloned, which
-- `source` and `cache_path` do not.
CREATE TABLE repository (
    id              INTEGER PRIMARY KEY,
    alias           TEXT    NOT NULL UNIQUE,
    source          TEXT    NOT NULL,
    source_kind     TEXT    NOT NULL CHECK (source_kind IN ('local', 'remote')),
    cache_path      TEXT,
    identity        TEXT,
    default_branch  TEXT,
    added_at        TEXT    NOT NULL,
    last_fetched_at TEXT
);

-- No title column. A title is unverified free text, and the provenance
-- taxonomy has no slot for "unverified label" (D-032). A reference is what
-- Constat matches on; anything descriptive must come from evidence.
CREATE TABLE ticket (
    id          INTEGER PRIMARY KEY,
    reference   TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL
);

-- Exactly one living document per ticket (D-029). The UNIQUE constraint on
-- ticket_id is the model, not an optimisation.
CREATE TABLE document (
    id          INTEGER PRIMARY KEY,
    ticket_id   INTEGER NOT NULL UNIQUE REFERENCES ticket(id) ON DELETE CASCADE,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    body        TEXT    NOT NULL DEFAULT ''
);

-- An immutable snapshot, frozen at approval (D-029). Append-only: see the
-- triggers below.
CREATE TABLE document_version (
    id                  INTEGER PRIMARY KEY,
    document_id         INTEGER NOT NULL REFERENCES document(id),
    version_no          INTEGER NOT NULL,
    content             TEXT    NOT NULL,
    content_hash        TEXT    NOT NULL,
    previous_version_id INTEGER REFERENCES document_version(id),
    decision            TEXT    NOT NULL CHECK (decision IN ('approved', 'rejected')),
    decided_by          TEXT    NOT NULL,
    decided_at          TEXT    NOT NULL,
    rationale           TEXT,
    UNIQUE (document_id, version_no)
);

-- One invocation that touched a document. A gather writes one `operation` row
-- per repository, so an operation row cannot answer "which run produced this";
-- a rule proposal is a reading of the evidence one run gathered (D-046,
-- D-048), and it needs something to point at. This is that something.
CREATE TABLE run (
    id          INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    kind        TEXT    NOT NULL,
    started_at  TEXT    NOT NULL
);

-- The commits whose evidence a run read (D-073, CON-79). Without this a rule
-- is accepted on evidence the workspace cannot afterwards produce: the chain
-- rule_version -> rule_proposal -> run -> operation ended at a summary line
-- reading "pending: 1 commit(s)", and once the ticket landed the document
-- regenerated with no diffs at all. Product rule 2 requires an important claim
-- to point at a source commit; this is the pointer.
--
-- **A pointer, not a copy.** The payload is deliberately not stored: a copy in
-- the governance store becomes a second source of truth that can disagree with
-- git, which is the failure D-002 avoids by shelling out to git rather than
-- reimplementing it, and it would grow without bound.
--
-- `repository_identity` is the root commit (D-025) rather than a path or an
-- alias, so the pointer survives the repository being moved, renamed or
-- re-cloned. `repository_id` is a convenience for joins and may be nulled by a
-- repository being unregistered; the identity is what endures.
--
-- `subject` is stored because a SHA can dangle. A squash-merge or a force-push
-- destroys the commit a rule points at, and a pointer that can still say
-- *what* it pointed at leaves a visible gap rather than a blank one. It is
-- already identity-scrubbed on the way in.
CREATE TABLE run_commit (
    id                  INTEGER PRIMARY KEY,
    run_id              INTEGER NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    repository_id       INTEGER REFERENCES repository(id),
    repository_identity TEXT,
    repository_alias    TEXT,
    sha                 TEXT    NOT NULL,
    subject             TEXT    NOT NULL DEFAULT '',
    UNIQUE (run_id, sha)
);

CREATE INDEX idx_run_commit_run ON run_commit(run_id);

-- What ran, against which repository, and what it contributed. Without this a
-- document becomes unattributable prose, which is the failure this product
-- exists to prevent (D-029).
--
-- `run_id` is nullable only because rows written before schema 4 have no run
-- to belong to. Inventing one for them would be fabricating provenance, so
-- they keep NULL and say so.
CREATE TABLE operation (
    id            INTEGER PRIMARY KEY,
    document_id   INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    run_id        INTEGER REFERENCES run(id) ON DELETE CASCADE,
    repository_id INTEGER REFERENCES repository(id),
    kind          TEXT    NOT NULL,
    ran_at        TEXT    NOT NULL,
    summary       TEXT    NOT NULL DEFAULT '',
    payload       TEXT
);

-- A message a user can see, stored once with its own citation (CON-82).
--
-- **Global, not owned by a rule.** One message routinely belongs to several
-- rules — the same refusal text covers a size limit and a format check — and
-- copying it per rule is how two copies come to disagree. `text` is UNIQUE, so
-- proposing the same wording twice links to one entry rather than minting a
-- second.
--
-- **Stored verbatim.** This is the exact string a user reads, which is what
-- makes it the most checkable thing a rule can carry: a business reader may be
-- unsure whether a limit is really enforced, and is never unsure whether the
-- screen says what the catalogue claims it says.
CREATE TABLE message (
    id         INTEGER PRIMARY KEY,
    ref        TEXT,
    text       TEXT    NOT NULL UNIQUE,
    created_at TEXT    NOT NULL
);

-- A business area declared ahead of its first rule (CON-88).
--
-- Most declared areas are not here. An area is declared by a human accepting a
-- rule that carries it — acceptance freezes the area on the version (D-070) —
-- so the declared set is derived from the catalogue, and this table holds only
-- the areas named *before* they have a rule. A baseline needs that: it opens an
-- area, then files rules under it (CON-89).
--
-- No CHECK and no vocabulary. This records what a person called a part of their
-- product, and refusing a heading because it is not in a list would be Constat
-- deciding how someone's business is organised.
CREATE TABLE area (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    declared_by TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

-- A business rule. Under D-035 a rule is a business statement, and no code
-- signal produces one; under D-048 it enters the catalogue only as an accepted
-- rule proposal, and can never be removed — see the trigger below.
--
-- `name` is not UNIQUE (D-050). A name is a label that may change between
-- versions; identity is this surrogate id, which survives renames,
-- restatements and anchor drift. Anchors only *match* a rule.
--
-- `ref` is the citable identifier a person writes down — `R-14` (CON-81).
-- Flat, not area-prefixed: an area is mutable by design (D-079 left it free
-- text), and an identifier that encodes a mutable fact becomes a false claim
-- the moment that fact changes. CON-67 taught that about positions; the same
-- applies here.
--
-- Stored rather than derived from `id`. `R-{id}` would be free and is a trap:
-- a public citation would then depend on rowids surviving every future table
-- rebuild, and `rule` has already been rebuilt once (migration 4 -> 5). A
-- citation that can shift is not a citation.
CREATE TABLE rule (
    id          INTEGER PRIMARY KEY,
    ref         TEXT,
    name        TEXT    NOT NULL,
    statement   TEXT    NOT NULL,
    area        TEXT,
    created_at  TEXT    NOT NULL
);

-- A rule proposal: a dated, attributed reading of the evidence one run
-- gathered (D-046, D-048). Not a rule yet, and never edited — a later run
-- makes a new reading rather than mutating this one, so "current" is derived.
--
-- `revises_rule_id` is the reading's own claim about which rule it revises,
-- found by anchor overlap and decided by the interpretation pass (D-050). NULL
-- means it claims to be new. It is a claim, not a key: a wrong one is a
-- rejectable interpretation rather than a corrupted identity.
--
-- `model` is self-reported unless `model_attested` says otherwise (D-045,
-- D-057). Submitted from outside it is a string the caller typed, nearer
-- `assumption` than `observed_fact`; on the provider path Constat issued the
-- request and read the id off the response, and only then may it be shown
-- without the caveat. One column, because the difference is not a matter of
-- degree: either Constat established it or it was told.
CREATE TABLE rule_proposal (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,
    statement       TEXT    NOT NULL,
    revises_rule_id INTEGER REFERENCES rule(id),
    relation        TEXT    CHECK (relation IN ('establishes', 'revises', 'repairs')),
    area            TEXT,
    provider        TEXT    NOT NULL,
    model           TEXT,
    model_attested  INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL
);
-- `relation` says how a reading stands to the catalogue (D-065): it
-- `establishes` a rule, `revises` one, or `repairs` one that was already true
-- and which the code was violating. A bug fix is the third case and had no way
-- to be said before schema 10 — so readings manufactured new rules out of
-- repairs, which is what CON-73 fixes.
--
-- Nullable, and NULL means "written before relations existed". Rows from
-- schema 9 and earlier are left exactly as they were: the relation they would
-- have carried is derivable (`revises_rule_id` set means a revision, unset
-- means an establishment), and that derivation happens on read rather than by
-- an UPDATE here. `rule_proposal` is append-only by trigger, and a migration
-- that dropped the trigger to write a column into historical readings would be
-- editing what a reviewer was shown — the exact loss the trigger exists to
-- prevent, performed by the code that enforces it.

CREATE TABLE rule_proposal_behaviour (
    id               INTEGER PRIMARY KEY,
    rule_proposal_id INTEGER NOT NULL REFERENCES rule_proposal(id) ON DELETE CASCADE,
    description      TEXT    NOT NULL
);

-- The messages a reading says a rule shows (CON-82). Text rather than a
-- message id: a reading predates the message existing, and minting one at
-- submission would put an entry in the catalogue that no human had accepted.
CREATE TABLE rule_proposal_message (
    id               INTEGER PRIMARY KEY,
    rule_proposal_id INTEGER NOT NULL REFERENCES rule_proposal(id) ON DELETE CASCADE,
    text             TEXT    NOT NULL
);

-- A worked example: one situation and what the product does with it (CON-80).
--
-- Two columns, not a per-rule table of input columns. A reading is re-run, and
-- a per-rule column schema would come back different each time, leaving one
-- rule with three shapes of table and nobody able to diff them.
--
-- Nothing here says the outcome is *right*. That is the reviewer's whole job,
-- and the examples exist to give them something to be right or wrong about.
CREATE TABLE rule_proposal_example (
    id               INTEGER PRIMARY KEY,
    rule_proposal_id INTEGER NOT NULL REFERENCES rule_proposal(id) ON DELETE CASCADE,
    situation        TEXT    NOT NULL,
    outcome          TEXT    NOT NULL
);

-- `grounded_in` says which ground supports the anchor (D-072): `evidence` if
-- the ticket changed the path, `mainline` if the path exists in the product but
-- this ticket did not touch it. Both are verifiable; they are different claims,
-- and product rule 3 keeps them apart.
CREATE TABLE rule_proposal_anchor (
    id               INTEGER PRIMARY KEY,
    rule_proposal_id INTEGER NOT NULL REFERENCES rule_proposal(id) ON DELETE CASCADE,
    repository_id    INTEGER REFERENCES repository(id),
    path_glob        TEXT    NOT NULL,
    grounded_in      TEXT    CHECK (grounded_in IN ('evidence', 'mainline'))
);

-- A human's answer to one rule proposal. Separate from the reading so that
-- accepting or rejecting does not mutate it — the same shape `document_version`
-- uses for documents (CON-31). `rejected` means inconclusive, not wrong
-- (D-036), so a later reading of better evidence is expected.
-- `attribution` says how `decided_by` was obtained: `stated` if a person
-- typed it with --by, `inferred` if it came from git's configured identity.
-- Neither is verified — nothing here proves who ran the command — so this is
-- not a trust level. It is the difference between a name someone asserted and
-- a name a machine supplied, and a reviewer weighing a decision is entitled to
-- know which (product rule 3, D-061).
--
-- CON-58 adds `channel` and `verification` beside this. They answer different
-- questions: `channel` is *where* the decision was made and `verification` is
-- whether anything attested to it. `attribution` is finer than both and sits
-- inside the CLI channel.
CREATE TABLE rule_proposal_decision (
    id               INTEGER PRIMARY KEY,
    rule_proposal_id INTEGER NOT NULL REFERENCES rule_proposal(id),
    decision         TEXT    NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    decided_by       TEXT    NOT NULL,
    attribution      TEXT    NOT NULL DEFAULT 'stated',
    decided_at       TEXT    NOT NULL,
    rationale        TEXT
);

-- A human's decision that a rule no longer describes the product (CON-83).
--
-- **A decision, not a deletion.** `rule` can never be removed — the trigger
-- aborts it — because a catalogue that can be emptied is protected by
-- convention only (D-048). Retirement is therefore a state recorded *about* a
-- rule, in its own append-only table, the shape `rule_proposal_decision` uses
-- for acceptance. The rule, its versions, its citation and its evidence all
-- stay readable forever.
--
-- **Append-only, so retirement is final.** There is no reinstatement row by
-- design: bringing behaviour back means a new reading accepted as a new rule,
-- which is a decision somebody makes rather than a flag somebody clears. The
-- citation is never reused either way.
--
-- This is also where a *lapsed condition* goes (D-071). A rule conditional on
-- a business state — "while the site is not approved by the ad network" —
-- becomes false when that state changes, and nothing in the statement can say
-- so. Retiring it with that reason is the answer, and it is why this table
-- carries a reason rather than only a decider.
CREATE TABLE rule_retirement (
    id          INTEGER PRIMARY KEY,
    rule_id     INTEGER NOT NULL REFERENCES rule(id),
    reason      TEXT    NOT NULL,
    decided_by  TEXT    NOT NULL,
    attribution TEXT    NOT NULL DEFAULT 'stated',
    decided_at  TEXT    NOT NULL
);

-- A frozen snapshot of a rule at the moment a human accepted a reading of it.
-- Same split as document/document_version (D-029): `rule` is the current
-- state, this is the durable history. Append-only — see the triggers below.
--
-- `from_rule_proposal_id` is what makes a rule traceable: every version points
-- at the reading a human accepted to produce it, and that reading points at
-- the run whose evidence it read.
-- `area` is frozen here beside the name and statement (D-070). Which business
-- area a rule was understood to belong to is part of what a human accepted,
-- and a later re-grouping must not rewrite what an earlier reviewer agreed to.
CREATE TABLE rule_version (
    id                    INTEGER PRIMARY KEY,
    rule_id               INTEGER NOT NULL REFERENCES rule(id),
    version_no            INTEGER NOT NULL,
    name                  TEXT    NOT NULL,
    statement             TEXT    NOT NULL,
    area                  TEXT,
    from_rule_proposal_id INTEGER NOT NULL REFERENCES rule_proposal(id),
    previous_version_id   INTEGER REFERENCES rule_version(id),
    created_at            TEXT    NOT NULL,
    UNIQUE (rule_id, version_no)
);

CREATE TABLE rule_version_behaviour (
    id              INTEGER PRIMARY KEY,
    rule_version_id INTEGER NOT NULL REFERENCES rule_version(id) ON DELETE CASCADE,
    behaviour_no    INTEGER,
    description     TEXT    NOT NULL
);

-- The frozen numbers are what makes a diff between two versions possible, and
-- they are the high-water mark too: this table is append-only, so the next free
-- number for a rule is max(example_no) + 1 across its whole history. No counter
-- to keep in step, and reuse is structurally impossible even though the live
-- `example` table is deleted and rewritten on every acceptance.
CREATE TABLE rule_version_message (
    id              INTEGER PRIMARY KEY,
    rule_version_id INTEGER NOT NULL REFERENCES rule_version(id) ON DELETE CASCADE,
    message_id      INTEGER NOT NULL REFERENCES message(id)
);

CREATE TABLE rule_version_example (
    id              INTEGER PRIMARY KEY,
    rule_version_id INTEGER NOT NULL REFERENCES rule_version(id) ON DELETE CASCADE,
    example_no      INTEGER,
    situation       TEXT    NOT NULL,
    outcome         TEXT    NOT NULL
);

CREATE TABLE rule_version_anchor (
    id              INTEGER PRIMARY KEY,
    rule_version_id INTEGER NOT NULL REFERENCES rule_version(id) ON DELETE CASCADE,
    repository_id   INTEGER REFERENCES repository(id),
    path_glob       TEXT    NOT NULL,
    grounded_in     TEXT    CHECK (grounded_in IN ('evidence', 'mainline'))
);

-- A distinct way the application handles a business case under its rule.
-- `behaviour_no` is this detail's durable identity within its rule (CON-67).
-- Assigned on acceptance by matching `description`, and never reused: the next
-- number comes from the high-water mark across every version the rule ever had,
-- so a removed detail's number cannot come back attached to something else.
-- Positions cannot serve as identity — D-043 requires durable identities rather
-- than positions in text, and "the second example" changes meaning the moment
-- the first one is removed.
CREATE TABLE behaviour (
    id           INTEGER PRIMARY KEY,
    rule_id      INTEGER NOT NULL REFERENCES rule(id) ON DELETE CASCADE,
    behaviour_no INTEGER,
    description  TEXT    NOT NULL,
    created_at   TEXT    NOT NULL,
    UNIQUE (rule_id, description)
);

-- Which messages a rule shows, now. Rewritten on each acceptance like the
-- other current-state tables; the frozen copy is `rule_version_message`.
CREATE TABLE rule_message (
    id         INTEGER PRIMARY KEY,
    rule_id    INTEGER NOT NULL REFERENCES rule(id) ON DELETE CASCADE,
    message_id INTEGER NOT NULL REFERENCES message(id),
    UNIQUE (rule_id, message_id)
);

-- The worked examples of a rule in the catalogue (CON-80). Rewritten on each
-- acceptance, like `behaviour`: the frozen copy is `rule_version_example`.
CREATE TABLE example (
    id          INTEGER PRIMARY KEY,
    rule_id     INTEGER NOT NULL REFERENCES rule(id) ON DELETE CASCADE,
    example_no  INTEGER,
    situation   TEXT    NOT NULL,
    outcome     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    UNIQUE (rule_id, situation)
);

-- Where a rule is believed to be implemented. A ticket's evidence touching an
-- anchor makes the rule impacted. `repository_id` is nullable so a rule can
-- span repositories by path pattern alone.
CREATE TABLE anchor (
    id            INTEGER PRIMARY KEY,
    rule_id       INTEGER NOT NULL REFERENCES rule(id) ON DELETE CASCADE,
    repository_id INTEGER REFERENCES repository(id) ON DELETE CASCADE,
    path_glob     TEXT    NOT NULL,
    grounded_in   TEXT    CHECK (grounded_in IN ('evidence', 'mainline')),
    created_at    TEXT    NOT NULL,
    UNIQUE (rule_id, repository_id, path_glob)
);

-- Uniqueness as an explicit index rather than an inline constraint, so a
-- freshly created workspace is structurally identical to a migrated one:
-- ALTER TABLE cannot add an inline UNIQUE, so the migration has to use an
-- index, and two shapes of the same table is a difference waiting to surprise
-- somebody.
CREATE UNIQUE INDEX idx_rule_ref ON rule(ref);
CREATE UNIQUE INDEX idx_message_ref ON message(ref);
CREATE INDEX idx_rule_retirement_rule ON rule_retirement(rule_id);
CREATE INDEX idx_rule_message_rule ON rule_message(rule_id);
CREATE INDEX idx_rule_proposal_message ON rule_proposal_message(rule_proposal_id);
CREATE INDEX idx_rule_version_message ON rule_version_message(rule_version_id);
CREATE INDEX idx_behaviour_rule ON behaviour(rule_id);
CREATE INDEX idx_example_rule ON example(rule_id);
CREATE INDEX idx_anchor_rule ON anchor(rule_id);
CREATE INDEX idx_document_version_document ON document_version(document_id);
CREATE INDEX idx_operation_document ON operation(document_id);
CREATE INDEX idx_operation_run ON operation(run_id);
CREATE INDEX idx_run_document ON run(document_id);
CREATE INDEX idx_rule_proposal_run ON rule_proposal(run_id);
CREATE INDEX idx_rule_proposal_revises ON rule_proposal(revises_rule_id);
CREATE INDEX idx_rule_proposal_behaviour ON rule_proposal_behaviour(rule_proposal_id);
CREATE INDEX idx_rule_proposal_example ON rule_proposal_example(rule_proposal_id);
CREATE INDEX idx_rule_proposal_anchor ON rule_proposal_anchor(rule_proposal_id);
CREATE INDEX idx_rule_proposal_decision ON rule_proposal_decision(rule_proposal_id);
CREATE INDEX idx_rule_version_rule ON rule_version(rule_id);
CREATE INDEX idx_rule_version_behaviour ON rule_version_behaviour(rule_version_id);
CREATE INDEX idx_rule_version_example ON rule_version_example(rule_version_id);
CREATE INDEX idx_rule_version_anchor ON rule_version_anchor(rule_version_id);

-- History is durable (product rule 5), enforced here rather than trusted to
-- callers. A later approval must create a new row; it must never rewrite or
-- remove an earlier one.
CREATE TRIGGER document_version_is_append_only_update
BEFORE UPDATE ON document_version
BEGIN
    SELECT RAISE(ABORT,
        'document_version is append-only: approved versions cannot be modified');
END;

CREATE TRIGGER document_version_is_append_only_delete
BEFORE DELETE ON document_version
BEGIN
    SELECT RAISE(ABORT,
        'document_version is append-only: approved versions cannot be deleted');
END;

-- A rule cannot be removed (D-048). Enforced here because a catalogue that can
-- be emptied by a DELETE is protected by convention only, and the convention
-- is what a future bug forgets.
CREATE TRIGGER rule_cannot_be_deleted
BEFORE DELETE ON rule
BEGIN
    SELECT RAISE(ABORT,
        'a rule cannot be removed: supersede it with a new accepted rule proposal');
END;

-- A rule proposal is a reading, fixed at the moment it was made. Editing one
-- would rewrite what a reviewer was shown; deleting one would erase that it was
-- ever offered, which is the same loss D-046 refuses for discarded readings.
CREATE TRIGGER rule_proposal_is_append_only_update
BEFORE UPDATE ON rule_proposal
BEGIN
    SELECT RAISE(ABORT, 'rule_proposal is append-only: a reading cannot be edited');
END;

CREATE TRIGGER rule_proposal_is_append_only_delete
BEFORE DELETE ON rule_proposal
BEGIN
    SELECT RAISE(ABORT, 'rule_proposal is append-only: a reading cannot be deleted');
END;

CREATE TRIGGER rule_retirement_is_append_only_update
BEFORE UPDATE ON rule_retirement
BEGIN
    SELECT RAISE(ABORT,
        'rule_retirement is append-only: a retirement cannot be modified');
END;

CREATE TRIGGER rule_retirement_is_append_only_delete
BEFORE DELETE ON rule_retirement
BEGIN
    SELECT RAISE(ABORT,
        'rule_retirement is append-only: a retirement cannot be undone — accept a new rule');
END;

CREATE TRIGGER rule_proposal_decision_is_append_only_update
BEFORE UPDATE ON rule_proposal_decision
BEGIN
    SELECT RAISE(ABORT,
        'rule_proposal_decision is append-only: a recorded decision cannot be modified');
END;

CREATE TRIGGER rule_proposal_decision_is_append_only_delete
BEFORE DELETE ON rule_proposal_decision
BEGIN
    SELECT RAISE(ABORT,
        'rule_proposal_decision is append-only: a recorded decision cannot be deleted');
END;

-- A baselined rule version is the approved record (product rule 5). A later
-- acceptance must add a version, never rewrite or remove one.
CREATE TRIGGER rule_version_is_append_only_update
BEFORE UPDATE ON rule_version
BEGIN
    SELECT RAISE(ABORT,
        'rule_version is append-only: an accepted version cannot be modified');
END;

CREATE TRIGGER rule_version_is_append_only_delete
BEFORE DELETE ON rule_version
BEGIN
    SELECT RAISE(ABORT,
        'rule_version is append-only: an accepted version cannot be deleted');
END;
"""


# Ordered migrations from one schema version to the next. A governance tool
# that discarded stored decisions on every schema change would contradict its
# own promise (product rule 5), so a version bump carries a migration rather
# than a refusal.
# Statements are listed individually rather than as a script: sqlite3's
# executescript() implicitly commits, which would silently defeat the
# surrounding transaction and could leave a workspace half-migrated.
MIGRATIONS: dict[int, tuple[str, ...]] = {
    # 1 -> 2: drop ticket.title (D-032).
    1: ("ALTER TABLE ticket DROP COLUMN title",),
    # 2 -> 3: the rule catalogue (D-038).
    2: (
        "CREATE TABLE rule ("
        " id INTEGER PRIMARY KEY,"
        " name TEXT NOT NULL UNIQUE,"
        " statement TEXT NOT NULL,"
        " created_at TEXT NOT NULL)",
        "CREATE TABLE behaviour ("
        " id INTEGER PRIMARY KEY,"
        " rule_id INTEGER NOT NULL REFERENCES rule(id) ON DELETE CASCADE,"
        " description TEXT NOT NULL,"
        " created_at TEXT NOT NULL,"
        " UNIQUE (rule_id, description))",
        "CREATE TABLE anchor ("
        " id INTEGER PRIMARY KEY,"
        " rule_id INTEGER NOT NULL REFERENCES rule(id) ON DELETE CASCADE,"
        " repository_id INTEGER REFERENCES repository(id) ON DELETE CASCADE,"
        " path_glob TEXT NOT NULL,"
        " created_at TEXT NOT NULL,"
        " UNIQUE (rule_id, repository_id, path_glob))",
        "CREATE INDEX idx_behaviour_rule ON behaviour(rule_id)",
        "CREATE INDEX idx_anchor_rule ON anchor(rule_id)",
    ),
    # 3 -> 4: a run has an identity, and operations belong to one (D-046).
    # Existing operation rows keep run_id NULL: they were written before runs
    # existed, and back-filling a run for them would fabricate provenance.
    3: (
        "CREATE TABLE run ("
        " id INTEGER PRIMARY KEY,"
        " document_id INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,"
        " kind TEXT NOT NULL,"
        " started_at TEXT NOT NULL)",
        "ALTER TABLE operation ADD COLUMN run_id INTEGER REFERENCES run(id)",
        "CREATE INDEX idx_operation_run ON operation(run_id)",
        "CREATE INDEX idx_run_document ON run(document_id)",
    ),
    # 4 -> 5: rule proposals (D-046, D-048), and rule.name loses UNIQUE
    # (D-050).
    #
    # Dropping a constraint needs a table rebuild, and `rule` is the parent of
    # `behaviour` and `anchor` with ON DELETE CASCADE — so dropping it alone
    # would cascade the catalogue away. All three are rebuilt instead, children
    # first on the way out. Renaming `rule_new` to `rule` rewrites the new
    # children's foreign keys to match, which is why the renames come last.
    4: (
        "CREATE TABLE rule_new ("
        " id INTEGER PRIMARY KEY,"
        " name TEXT NOT NULL,"
        " statement TEXT NOT NULL,"
        " created_at TEXT NOT NULL)",
        "INSERT INTO rule_new (id, name, statement, created_at)"
        " SELECT id, name, statement, created_at FROM rule",
        "CREATE TABLE behaviour_new ("
        " id INTEGER PRIMARY KEY,"
        " rule_id INTEGER NOT NULL REFERENCES rule_new(id) ON DELETE CASCADE,"
        " description TEXT NOT NULL,"
        " created_at TEXT NOT NULL,"
        " UNIQUE (rule_id, description))",
        "INSERT INTO behaviour_new (id, rule_id, description, created_at)"
        " SELECT id, rule_id, description, created_at FROM behaviour",
        "CREATE TABLE anchor_new ("
        " id INTEGER PRIMARY KEY,"
        " rule_id INTEGER NOT NULL REFERENCES rule_new(id) ON DELETE CASCADE,"
        " repository_id INTEGER REFERENCES repository(id) ON DELETE CASCADE,"
        " path_glob TEXT NOT NULL,"
        " created_at TEXT NOT NULL,"
        " UNIQUE (rule_id, repository_id, path_glob))",
        "INSERT INTO anchor_new (id, rule_id, repository_id, path_glob, created_at)"
        " SELECT id, rule_id, repository_id, path_glob, created_at FROM anchor",
        "DROP TABLE anchor",
        "DROP TABLE behaviour",
        "DROP TABLE rule",
        "ALTER TABLE rule_new RENAME TO rule",
        "ALTER TABLE behaviour_new RENAME TO behaviour",
        "ALTER TABLE anchor_new RENAME TO anchor",
        "CREATE INDEX idx_behaviour_rule ON behaviour(rule_id)",
        "CREATE INDEX idx_anchor_rule ON anchor(rule_id)",
        "CREATE TRIGGER rule_cannot_be_deleted"
        " BEFORE DELETE ON rule BEGIN"
        " SELECT RAISE(ABORT,"
        " 'a rule cannot be removed: supersede it with a new accepted rule proposal');"
        " END",
        "CREATE TABLE rule_proposal ("
        " id INTEGER PRIMARY KEY,"
        " run_id INTEGER NOT NULL REFERENCES run(id) ON DELETE CASCADE,"
        " name TEXT NOT NULL,"
        " statement TEXT NOT NULL,"
        " revises_rule_id INTEGER REFERENCES rule(id),"
        " provider TEXT NOT NULL,"
        " model TEXT,"
        " created_at TEXT NOT NULL)",
        "CREATE TABLE rule_proposal_behaviour ("
        " id INTEGER PRIMARY KEY,"
        " rule_proposal_id INTEGER NOT NULL"
        " REFERENCES rule_proposal(id) ON DELETE CASCADE,"
        " description TEXT NOT NULL)",
        "CREATE TABLE rule_proposal_anchor ("
        " id INTEGER PRIMARY KEY,"
        " rule_proposal_id INTEGER NOT NULL"
        " REFERENCES rule_proposal(id) ON DELETE CASCADE,"
        " repository_id INTEGER REFERENCES repository(id),"
        " path_glob TEXT NOT NULL)",
        "CREATE TABLE rule_proposal_decision ("
        " id INTEGER PRIMARY KEY,"
        " rule_proposal_id INTEGER NOT NULL REFERENCES rule_proposal(id),"
        " decision TEXT NOT NULL CHECK (decision IN ('accepted', 'rejected')),"
        " decided_by TEXT NOT NULL,"
        " decided_at TEXT NOT NULL,"
        " rationale TEXT)",
        "CREATE INDEX idx_rule_proposal_run ON rule_proposal(run_id)",
        "CREATE INDEX idx_rule_proposal_revises ON rule_proposal(revises_rule_id)",
        "CREATE INDEX idx_rule_proposal_behaviour"
        " ON rule_proposal_behaviour(rule_proposal_id)",
        "CREATE INDEX idx_rule_proposal_anchor"
        " ON rule_proposal_anchor(rule_proposal_id)",
        "CREATE INDEX idx_rule_proposal_decision"
        " ON rule_proposal_decision(rule_proposal_id)",
        "CREATE TRIGGER rule_proposal_is_append_only_update"
        " BEFORE UPDATE ON rule_proposal BEGIN"
        " SELECT RAISE(ABORT,"
        " 'rule_proposal is append-only: a reading cannot be edited'); END",
        "CREATE TRIGGER rule_proposal_is_append_only_delete"
        " BEFORE DELETE ON rule_proposal BEGIN"
        " SELECT RAISE(ABORT,"
        " 'rule_proposal is append-only: a reading cannot be deleted'); END",
        "CREATE TRIGGER rule_proposal_decision_is_append_only_update"
        " BEFORE UPDATE ON rule_proposal_decision BEGIN"
        " SELECT RAISE(ABORT,"
        " 'rule_proposal_decision is append-only:"
        " a recorded decision cannot be modified'); END",
        "CREATE TRIGGER rule_proposal_decision_is_append_only_delete"
        " BEFORE DELETE ON rule_proposal_decision BEGIN"
        " SELECT RAISE(ABORT,"
        " 'rule_proposal_decision is append-only:"
        " a recorded decision cannot be deleted'); END",
    ),
    # 5 -> 6: accepted rule versions (D-053). Rules that predate acceptance
    # keep no version: they were never accepted, and inventing a version for
    # them would fabricate an approval.
    5: (
        "CREATE TABLE rule_version ("
        " id INTEGER PRIMARY KEY,"
        " rule_id INTEGER NOT NULL REFERENCES rule(id),"
        " version_no INTEGER NOT NULL,"
        " name TEXT NOT NULL,"
        " statement TEXT NOT NULL,"
        " from_rule_proposal_id INTEGER NOT NULL REFERENCES rule_proposal(id),"
        " previous_version_id INTEGER REFERENCES rule_version(id),"
        " created_at TEXT NOT NULL,"
        " UNIQUE (rule_id, version_no))",
        "CREATE TABLE rule_version_behaviour ("
        " id INTEGER PRIMARY KEY,"
        " rule_version_id INTEGER NOT NULL"
        " REFERENCES rule_version(id) ON DELETE CASCADE,"
        " description TEXT NOT NULL)",
        "CREATE TABLE rule_version_anchor ("
        " id INTEGER PRIMARY KEY,"
        " rule_version_id INTEGER NOT NULL"
        " REFERENCES rule_version(id) ON DELETE CASCADE,"
        " repository_id INTEGER REFERENCES repository(id),"
        " path_glob TEXT NOT NULL)",
        "CREATE INDEX idx_rule_version_rule ON rule_version(rule_id)",
        "CREATE INDEX idx_rule_version_behaviour"
        " ON rule_version_behaviour(rule_version_id)",
        "CREATE INDEX idx_rule_version_anchor"
        " ON rule_version_anchor(rule_version_id)",
        "CREATE TRIGGER rule_version_is_append_only_update"
        " BEFORE UPDATE ON rule_version BEGIN"
        " SELECT RAISE(ABORT,"
        " 'rule_version is append-only:"
        " an accepted version cannot be modified'); END",
        "CREATE TRIGGER rule_version_is_append_only_delete"
        " BEFORE DELETE ON rule_version BEGIN"
        " SELECT RAISE(ABORT,"
        " 'rule_version is append-only:"
        " an accepted version cannot be deleted'); END",
    ),
    # 6 -> 7: whether Constat established the model id itself (D-057).
    #
    # Existing rows keep the default of 0. Not backfilled, and not backfillable:
    # every reading recorded before this column existed arrived from outside,
    # and nothing now can establish what read evidence months ago. The same
    # honest gap as `operation.run_id` at D-049 — a NULL-equivalent that says
    # "unknown" rather than a value that says "no" by assertion.
    6: (
        "ALTER TABLE rule_proposal"
        " ADD COLUMN model_attested INTEGER NOT NULL DEFAULT 0",
    ),
    # 7 -> 8: workspace settings, and `reader` (D-060).
    #
    # Existing workspaces are set to `provider`, which is exactly how they
    # behave today: a rule-generating command refuses without one. Defaulting
    # them to `mcp` would silently switch off a refusal someone is relying on.
    8: (
        "ALTER TABLE rule_proposal_decision"
        " ADD COLUMN attribution TEXT NOT NULL DEFAULT 'stated'",
    ),
    7: (
        "CREATE TABLE setting ("
        " key TEXT PRIMARY KEY,"
        " value TEXT NOT NULL,"
        " updated_at TEXT NOT NULL)",
        "INSERT INTO setting (key, value, updated_at)"
        " VALUES ('reader', 'provider', '1970-01-01T00:00:00+00:00')",
    ),
    # 9 -> 10: a reading says how it stands to the catalogue (D-065, CON-73).
    #
    # One ALTER and nothing else. No back-fill: existing readings keep NULL
    # and their relation is derived on read, because `rule_proposal` is
    # append-only by trigger and writing a column into a historical reading
    # would edit what a reviewer was shown. SQLite's ADD COLUMN cannot carry a
    # CHECK, so the constraint lives in the schema for new workspaces and in
    # `parse` for every reading that arrives; a migrated workspace is validated
    # by the same parse as a fresh one.
    9: (
        "ALTER TABLE rule_proposal ADD COLUMN relation TEXT",
    ),
    # 10 -> 11: a rule belongs to a business area (D-070, CON-77).
    #
    # Nullable everywhere, and no back-fill. A rule accepted before areas
    # existed was accepted without one, and inventing an area for it would put
    # a claim nobody made into a frozen version — the same reason schema 10
    # left `relation` NULL on historical readings. An unplaced rule renders
    # under "unplaced", which is accurate.
    10: (
        "ALTER TABLE rule_proposal ADD COLUMN area TEXT",
        "ALTER TABLE rule ADD COLUMN area TEXT",
        "ALTER TABLE rule_version ADD COLUMN area TEXT",
    ),
    # 11 -> 12: an anchor records which ground supports it (D-072, CON-71).
    #
    # Nullable, no back-fill, for the reason every other migration here gives:
    # an anchor written before this existed was grounded in the evidence by
    # construction — that was the only ground — but writing `evidence` into it
    # now would be asserting something nobody recorded. NULL reads as "not
    # recorded", which is the truth.
    11: (
        "ALTER TABLE rule_proposal_anchor ADD COLUMN grounded_in TEXT",
        "ALTER TABLE anchor ADD COLUMN grounded_in TEXT",
        "ALTER TABLE rule_version_anchor ADD COLUMN grounded_in TEXT",
    ),
    # 12 -> 13: a run records the commits it read (D-073, CON-79).
    #
    # Nothing is back-filled, and for once that is not only a matter of
    # principle: the evidence those runs read is **gone**. A landed ticket
    # contributes no evidence, the documents were regenerated, and no SHA was
    # ever written down — so there is nothing to recover and inventing one
    # would be the worst possible lie to tell in a governance record. Rules
    # accepted before schema 13 have no evidence pointer and say so.
    12: (
        "CREATE TABLE run_commit ("
        " id INTEGER PRIMARY KEY,"
        " run_id INTEGER NOT NULL REFERENCES run(id) ON DELETE CASCADE,"
        " repository_id INTEGER REFERENCES repository(id),"
        " repository_identity TEXT,"
        " repository_alias TEXT,"
        " sha TEXT NOT NULL,"
        " subject TEXT NOT NULL DEFAULT '',"
        " UNIQUE (run_id, sha))",
        "CREATE INDEX idx_run_commit_run ON run_commit(run_id)",
    ),
    # 13 -> 14: a rule carries worked examples (CON-80).
    #
    # Three new tables and no back-fill, which here is not even a choice: an
    # example is something a reading proposed and a human accepted, and no
    # reading before this could propose one. Deriving examples from a stored
    # statement would be Constat inventing the evidence a reviewer is meant to
    # check — the failure D-046 refuses at the trust boundary, committed
    # instead by the migration.
    #
    # Rules accepted before schema 14 therefore have no examples, and the
    # renderers say so rather than showing an empty table, because "nobody
    # proposed examples" and "this rule has no cases" are different claims.
    13: (
        "CREATE TABLE rule_proposal_example ("
        " id INTEGER PRIMARY KEY,"
        " rule_proposal_id INTEGER NOT NULL REFERENCES rule_proposal(id) ON DELETE CASCADE,"
        " situation TEXT NOT NULL,"
        " outcome TEXT NOT NULL)",
        "CREATE TABLE rule_version_example ("
        " id INTEGER PRIMARY KEY,"
        " rule_version_id INTEGER NOT NULL REFERENCES rule_version(id) ON DELETE CASCADE,"
        " situation TEXT NOT NULL,"
        " outcome TEXT NOT NULL)",
        "CREATE TABLE example ("
        " id INTEGER PRIMARY KEY,"
        " rule_id INTEGER NOT NULL REFERENCES rule(id) ON DELETE CASCADE,"
        " situation TEXT NOT NULL,"
        " outcome TEXT NOT NULL,"
        " created_at TEXT NOT NULL,"
        " UNIQUE (rule_id, situation))",
        "CREATE INDEX idx_rule_proposal_example"
        " ON rule_proposal_example(rule_proposal_id)",
        "CREATE INDEX idx_rule_version_example"
        " ON rule_version_example(rule_version_id)",
        "CREATE INDEX idx_example_rule ON example(rule_id)",
    ),
    # 14 -> 15: a detail has a durable number within its rule (CON-67).
    #
    # Nullable, no back-fill. A rule accepted before this has details that were
    # never numbered, and assigning numbers now would let `rule history` report
    # a diff between two versions as though the numbers had been recorded at the
    # time. They were not: the match would be made today, by this code, and
    # presented as what a reviewer saw. NULL reads as "not numbered", and the
    # diff says so rather than comparing.
    # 18 -> 19: a rule can be retired (CON-83).
    #
    # One table and two triggers. Nothing is retired by the migration, which
    # needs no argument: retirement is a human decision, and inventing one
    # would be the thing D-048 exists to prevent, performed by a migration.
    18: (
        "CREATE TABLE rule_retirement ("
        " id INTEGER PRIMARY KEY,"
        " rule_id INTEGER NOT NULL REFERENCES rule(id),"
        " reason TEXT NOT NULL,"
        " decided_by TEXT NOT NULL,"
        " attribution TEXT NOT NULL DEFAULT 'stated',"
        " decided_at TEXT NOT NULL)",
        "CREATE TRIGGER rule_retirement_is_append_only_update"
        " BEFORE UPDATE ON rule_retirement BEGIN"
        " SELECT RAISE(ABORT,"
        " 'rule_retirement is append-only: a retirement cannot be modified');"
        " END",
        "CREATE TRIGGER rule_retirement_is_append_only_delete"
        " BEFORE DELETE ON rule_retirement BEGIN"
        " SELECT RAISE(ABORT,"
        " 'rule_retirement is append-only: a retirement cannot be undone');"
        " END",
        "CREATE INDEX idx_rule_retirement_rule ON rule_retirement(rule_id)",
    ),
    # 17 -> 18: a user-facing message is a catalogue entry (CON-82).
    #
    # Four tables and no back-fill. Nothing to back-fill from: no reading
    # before this could propose a message, and mining existing statements for
    # quoted strings would be Constat inventing the evidence a reviewer is
    # meant to check — D-046's failure, performed by a migration.
    17: (
        "CREATE TABLE message ("
        " id INTEGER PRIMARY KEY,"
        " ref TEXT,"
        " text TEXT NOT NULL UNIQUE,"
        " created_at TEXT NOT NULL)",
        "CREATE TABLE rule_proposal_message ("
        " id INTEGER PRIMARY KEY,"
        " rule_proposal_id INTEGER NOT NULL REFERENCES rule_proposal(id) ON DELETE CASCADE,"
        " text TEXT NOT NULL)",
        "CREATE TABLE rule_version_message ("
        " id INTEGER PRIMARY KEY,"
        " rule_version_id INTEGER NOT NULL REFERENCES rule_version(id) ON DELETE CASCADE,"
        " message_id INTEGER NOT NULL REFERENCES message(id))",
        "CREATE TABLE rule_message ("
        " id INTEGER PRIMARY KEY,"
        " rule_id INTEGER NOT NULL REFERENCES rule(id) ON DELETE CASCADE,"
        " message_id INTEGER NOT NULL REFERENCES message(id),"
        " UNIQUE (rule_id, message_id))",
        "CREATE UNIQUE INDEX idx_message_ref ON message(ref)",
        "CREATE INDEX idx_rule_message_rule ON rule_message(rule_id)",
        "CREATE INDEX idx_rule_proposal_message"
        " ON rule_proposal_message(rule_proposal_id)",
        "CREATE INDEX idx_rule_version_message"
        " ON rule_version_message(rule_version_id)",
    ),
    # 16 -> 17: a rule has a citable identifier (CON-81).
    #
    # **Back-filled, unlike every migration before it, and the difference is
    # the point.** The others refused to back-fill because they would have been
    # inventing a claim nobody made — an area, a number, an example. A citation
    # invents nothing: the rules exist, and naming them is not asserting
    # anything about them. Refusing here would leave the catalogue with rules
    # nobody can cite, which is the defect this closes.
    #
    # Assigned in id order so the result is stable and reproducible.
    16: (
        "ALTER TABLE rule ADD COLUMN ref TEXT",
        "UPDATE rule SET ref = 'R-' || id WHERE ref IS NULL",
        "CREATE UNIQUE INDEX idx_rule_ref ON rule(ref)",
    ),
    # 15 -> 16: an area can be declared before its first rule (CON-88).
    #
    # Nothing is migrated into it, and nothing needs to be: every area already
    # in use is on an accepted rule, and `Catalogue.areas` reads those. Copying
    # them in would create a second source of truth for the same fact, which
    # could then disagree with the catalogue.
    15: (
        "CREATE TABLE area ("
        " id INTEGER PRIMARY KEY,"
        " name TEXT NOT NULL UNIQUE,"
        " declared_by TEXT NOT NULL,"
        " created_at TEXT NOT NULL)",
    ),
    14: (
        "ALTER TABLE behaviour ADD COLUMN behaviour_no INTEGER",
        "ALTER TABLE example ADD COLUMN example_no INTEGER",
        "ALTER TABLE rule_version_behaviour ADD COLUMN behaviour_no INTEGER",
        "ALTER TABLE rule_version_example ADD COLUMN example_no INTEGER",
    ),
}
