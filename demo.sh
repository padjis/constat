#!/usr/bin/env bash
#
# A self-contained tour of Constat, for somebody who has just cloned it.
#
# Needs: python, git, and this repository installed (`pip install -e .`).
# Needs NOT: an API key, a network connection, or any repository of your own.
#
# It builds a throwaway subject repository in a temporary directory, runs the
# whole loop against it, and prints what each step is demonstrating. Your own
# workspace at ~/.constat is never touched — CONSTAT_HOME is pointed at the
# temporary directory on the first line of work below, which is also why this
# can be run twice in a row without cleaning anything up.
#
# Every reading here is supplied by hand, because the evidence pipeline runs
# with no provider configured (D-003) and a demo that needed an API key would
# be a demo of somebody's billing relationship.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLAYGROUND="$(mktemp -d)"
export CONSTAT_HOME="$PLAYGROUND/workspace"

CONSTAT="constat"
if [ -x "$HERE/.venv/bin/constat" ]; then
  CONSTAT="$HERE/.venv/bin/constat"
fi

if ! "$CONSTAT" --version >/dev/null 2>&1; then
  echo "constat is not runnable. Install it first:" >&2
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -e ." >&2
  exit 1
fi

step() {
  printf '\n\033[1m── %s\033[0m\n' "$1"
}
note() {
  printf '   %s\n' "$1"
}

trap 'printf "\nThe playground is at %s — delete it when you are done.\n" "$PLAYGROUND"' EXIT

printf '\033[1mConstat demo\033[0m — %s\n' "$("$CONSTAT" --version)"
note "playground: $PLAYGROUND"
note "workspace:  $CONSTAT_HOME   (your own ~/.constat is untouched)"

# ---------------------------------------------------------------- the subject

step "A throwaway product to read"
mkdir -p "$PLAYGROUND/remote.git"
git -C "$PLAYGROUND/remote.git" init --bare --quiet --initial-branch=main
git -C "$PLAYGROUND" clone --quiet "$PLAYGROUND/remote.git" billing
BILLING="$PLAYGROUND/billing"
git -C "$BILLING" config user.name "Demo"
git -C "$BILLING" config user.email "demo@example.invalid"

cat > "$BILLING/limits.py" <<'PY'
DAILY_LIMIT_EUROS = 100
REFUSED = "Transfer declined — daily limit reached"
PY
git -C "$BILLING" add -A
git -C "$BILLING" commit --quiet -m "A transfer limit"
git -C "$BILLING" push --quiet origin main

git -C "$BILLING" checkout --quiet -b feat/402-raise-the-limit
cat > "$BILLING/limits.py" <<'PY'
DAILY_LIMIT_EUROS = 250
REFUSED = "Transfer declined — daily limit reached"
PY
git -C "$BILLING" commit --quiet -am "402: raise the daily limit to 250"
git -C "$BILLING" push --quiet origin feat/402-raise-the-limit
git -C "$BILLING" checkout --quiet main
note "a repository whose mainline says 100, with ticket 402 raising it to 250 on a branch"

# ------------------------------------------------------------- the workspace

step "A workspace, and a repository to read"
"$CONSTAT" init --reader mcp
"$CONSTAT" repo add "$BILLING" --name billing --default-branch main

step "Gather what ticket 402 changed"
note "read-only: nothing is written to the subject repository, ever"
"$CONSTAT" ticket add 402 --no-provider

step "The evidence, as it would leave the machine"
note "identity never crosses the boundary (D-040); the payload is scanned for"
note "credentials before it can be printed (D-047)"
"$CONSTAT" document 402 --no-provider --payload | head -24
note "… truncated here; the full payload is what a model would read"

# ------------------------------------------------------------- the reading

step "A reading, supplied by hand"
note "normally an agent writes this over MCP. The shape is the same either way,"
note "which is the point of D-045: one door, whoever is at it."
cat > "$PLAYGROUND/reading.json" <<'JSON'
{"rules": [{
  "name": "a-transfer-above-the-daily-limit-is-refused",
  "statement": "A transfer above the customer's daily limit is refused, and the customer is told why.",
  "behaviours": ["Refuse the transfer", "Name the limit in the refusal"],
  "examples": [
    {"situation": "A transfer of 240 euros against a 250 limit", "outcome": "Accepted"},
    {"situation": "A transfer of 260 euros against a 250 limit", "outcome": "Refused, and the limit is shown"},
    {"situation": "Two transfers of 200 euros on the same day", "outcome": "The second is refused"}],
  "messages": ["Transfer declined — daily limit reached"],
  "anchors": [{"path_glob": "limits.py", "repository_alias": "billing"}],
  "area": "payments"
}]}
JSON
"$CONSTAT" rule submit 402 --from "$PLAYGROUND/reading.json"

step "What is waiting, across the whole workspace"
"$CONSTAT" rule proposals

step "The reading in full, before deciding on it"
"$CONSTAT" rule proposals 402

# ------------------------------------------------------------- the decision

step "A person decides — the only door to the catalogue"
note "no tool, flag or setting can do this (D-048, D-055)"
"$CONSTAT" rule accept 1 --by "A Reviewer"

step "The rule, as the catalogue now holds it"
"$CONSTAT" rule show R-1

step "Its message, checked against the code"
note "the most verifiable thing a rule carries: either the text is in the"
note "code or it is not (D-083)"
"$CONSTAT" message verify

# ------------------------------------------------------- the current picture

step "The product as it stands"
note "watch where the rule appears: its evidence is on an unmerged branch, so"
note "it is agreed and not yet shipped (D-087)"
"$CONSTAT" state

step "Now the work lands"
git -C "$BILLING" merge --quiet --no-ff -m "Merge 402" origin/feat/402-raise-the-limit
git -C "$BILLING" push --quiet origin main
note "nothing is re-accepted and nothing re-read — the same rule moves"
"$CONSTAT" state | sed -n '/Business rules/,/What this does not/p'

# ------------------------------------------------------------- the history

step "A checkpoint, so later changes can be measured against it"
"$CONSTAT" checkpoint take --label "the demo state" --by "A Reviewer"

step "A second reading, revising the rule"
cat > "$PLAYGROUND/revision.json" <<'JSON'
{"rules": [{
  "name": "a-transfer-above-the-daily-limit-is-refused",
  "statement": "A transfer above the customer's daily limit is refused, and the customer is told the limit and when it resets.",
  "behaviours": ["Refuse the transfer", "Name the limit in the refusal", "Say when the limit resets"],
  "examples": [
    {"situation": "A transfer of 240 euros against a 250 limit", "outcome": "Accepted"},
    {"situation": "A transfer of 260 euros against a 250 limit", "outcome": "Refused, with the limit and its reset time"}],
  "messages": ["Transfer declined — daily limit reached"],
  "anchors": [{"path_glob": "limits.py", "repository_alias": "billing"}],
  "area": "payments",
  "relation": "revises",
  "revises": 1
}]}
JSON
"$CONSTAT" rule submit 402 --from "$PLAYGROUND/revision.json"
"$CONSTAT" rule accept 2 --by "A Reviewer"

step "What changed between the two versions"
note "compared by the identity of each detail, never by position (D-078)"
"$CONSTAT" rule history 1

step "And what the catalogue has done since the checkpoint"
"$CONSTAT" checkpoint changes

# ------------------------------------------------------------ the refusals

step "Refusals are the product working"
note "a rule whose anchor names a path nobody supplied is discarded (D-046)"
cat > "$PLAYGROUND/ungrounded.json" <<'JSON'
{"rules": [{"name": "invented", "statement": "Something happens somewhere.",
  "anchors": [{"path_glob": "no/such/file.py", "repository_alias": "billing"}]}]}
JSON
"$CONSTAT" rule submit 402 --from "$PLAYGROUND/ungrounded.json" || true

note ""
note "and a statement that leaks code is refused with the token named (D-066)"
cat > "$PLAYGROUND/leaky.json" <<'JSON'
{"rules": [{"name": "leaky", "statement": "A transfer is refused by limits.py.",
  "anchors": [{"path_glob": "limits.py", "repository_alias": "billing"}]}]}
JSON
"$CONSTAT" rule submit 402 --from "$PLAYGROUND/leaky.json" || true

step "Done"
note "Everything above ran with no API key and no network."
note "Read LIMITS.md next: what Constat does not do, and what it has not verified."
