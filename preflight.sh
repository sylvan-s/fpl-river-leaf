#!/usr/bin/env bash
# Session preflight — run this FIRST, before reading or changing anything.
#
#   bash preflight.sh          diagnose, and fast-forward when provably safe
#   bash preflight.sh --report diagnose only, never touch .git
#
# WHY THIS EXISTS. In this repo `git status` is not a truthful answer, and
# that is by design, not a fault. Cowork's connected-folder mount cannot do
# the rename-over-existing that git's commit machinery needs, so Cowork
# sessions commit through `safe_git_commit.sh`, which pushes from a scratch
# clone and deliberately never advances this working tree's own HEAD (see
# that script's header). Every time it runs, local HEAD falls one commit
# further behind origin while the already-pushed files keep showing as
# "changed" forever.
#
# Consequence: a session that trusts `git status` sees dozens of "uncommitted
# changes" that are in fact already on GitHub, sitting on a HEAD that may be
# many commits stale. On 12 Sep 2026 that was 12 commits and ~60 files, and
# committing the local tree would have overwritten origin's GW1-3 prediction
# record with a local GW1-2 copy.
#
# THE ONE TRUE QUESTION is therefore never "what does git status say" but
# "how do I differ from origin/main after a fresh fetch". That is all this
# script asks.
#
# WHAT IT WILL AND WILL NOT DO. It fast-forwards only when the working tree
# already matches origin/main byte-for-byte — the case where there is nothing
# to lose. The moment anything genuinely differs it stops and shows you what,
# because direction cannot be inferred: on 12 Sep origin was newer for
# prediction_tracker.json and local was newer for fixture_window.json, in the
# same tree. Deciding that is a judgement call, not a merge.
#
# It never pushes, never commits, and never discards anything.

set -uo pipefail
cd "$(dirname "$0")"

REPORT_ONLY=0
[ "${1:-}" = "--report" ] && REPORT_ONLY=1

RED=$'\033[31m'; YEL=$'\033[33m'; GRN=$'\033[32m'; DIM=$'\033[2m'; OFF=$'\033[0m'
say()  { printf '%s\n' "$*"; }
warn() { printf '%s%s%s\n' "$YEL" "$*" "$OFF"; }
bad()  { printf '%s%s%s\n' "$RED" "$*" "$OFF"; }
good() { printf '%s%s%s\n' "$GRN" "$*" "$OFF"; }

ISSUES=0

say "=== preflight: $(pwd) ==="
say ""

# ---------------------------------------------------------------- stale locks
# A lock left by a crashed or bridge-blocked git is invisible until something
# fails. The one found on 12 Sep 2026 was zero bytes and eight days old, and
# had silently blocked every local commit for that whole period.
for lock in .git/index.lock .git/HEAD.lock .git/config.lock; do
  [ -e "$lock" ] || continue
  AGE_S=$(( $(date +%s) - $(stat -f %m "$lock" 2>/dev/null || stat -c %Y "$lock" 2>/dev/null || date +%s) ))
  AGE_H=$(( AGE_S / 3600 ))
  if pgrep -f '[g]it ' >/dev/null 2>&1; then
    warn "LOCK  $lock exists (${AGE_H}h old) AND a git process is running — leave it alone."
  else
    bad  "LOCK  $lock exists, ${AGE_H}h old, and NO git process is running — stale."
    say  "      This blocks every local commit until removed:  rm -f $lock"
  fi
  ISSUES=$((ISSUES+1))
done

# -------------------------------------------------------------------- fetch
if ! git fetch --quiet origin 2>/dev/null; then
  bad "FETCH failed — cannot reach origin. Everything below is unreliable."
  exit 1
fi

BRANCH=$(git branch --show-current)
[ "$BRANCH" = "main" ] || warn "BRANCH  on '$BRANCH', not main."

read -r BEHIND AHEAD < <(git rev-list --left-right --count origin/main...HEAD)
if [ "$BEHIND" -gt 0 ] || [ "$AHEAD" -gt 0 ]; then
  warn "HEAD    local is ${BEHIND} behind / ${AHEAD} ahead of origin/main"
  [ "$BEHIND" -gt 0 ] && git log --oneline HEAD..origin/main | sed 's/^/          incoming: /'
  [ "$AHEAD"  -gt 0 ] && git log --oneline origin/main..HEAD | sed 's/^/          local-only commit: /'
else
  good "HEAD    level with origin/main"
fi

# ------------------------------------------------- working tree vs origin/main
# Tracked files whose content differs, plus untracked files. Untracked files
# are listed separately because `git diff origin/main` reports them as
# deletions — they are not in the index, so git cannot see them as present.
TRACKED_DIFF=$(git diff --name-only origin/main -- 2>/dev/null)
UNTRACKED=$(git ls-files --others --exclude-standard)

UNIQUE=""; REDUNDANT=""
while IFS= read -r f; do
  [ -z "$f" ] && continue
  if git cat-file -e "origin/main:$f" 2>/dev/null; then
    REDUNDANT="$REDUNDANT$f"$'\n'
  else
    UNIQUE="$UNIQUE$f"$'\n'
  fi
done <<< "$UNTRACKED"

say ""
if [ -z "$TRACKED_DIFF" ] && [ -z "${UNIQUE//[$'\n']/}" ]; then
  good "TREE    matches origin/main — nothing of yours is unpushed"
else
  warn "TREE    differs from origin/main:"
  [ -n "$TRACKED_DIFF" ] && git diff --stat origin/main -- | sed 's/^/          /'
  if [ -n "${UNIQUE//[$'\n']/}" ]; then
    say ""
    bad "        files that exist ONLY here (not on origin) — real unpushed work:"
    printf '%s' "$UNIQUE" | sed '/^$/d;s/^/          + /'
  fi
  ISSUES=$((ISSUES+1))
fi

if [ -n "${REDUNDANT//[$'\n']/}" ]; then
  N=$(printf '%s' "$REDUNDANT" | sed '/^$/d' | wc -l | tr -d ' ')
  say "${DIM}        ($N untracked file(s) already present on origin — noise, not work)${OFF}"
fi

# ----------------------------------------------------- append-only log guard
# These never shrink. If the local copy has fewer lines than origin's, local
# is stale and pushing it would silently delete history that nothing
# downstream can reconstruct — a missing entry is indistinguishable from one
# that was never written.
say ""
for log in docs/data/intel_sweep_log.jsonl fpl_calibration_log.jsonl; do
  [ -f "$log" ] || continue
  L=$(wc -l < "$log" | tr -d ' ')
  R=$(git show "origin/main:$log" 2>/dev/null | wc -l | tr -d ' ')
  if [ "${R:-0}" -gt "${L:-0}" ]; then
    bad "APPEND  $log — local $L lines, origin $R. LOCAL IS STALE."
    say "        Do NOT commit this file. Take origin's copy."
    ISSUES=$((ISSUES+1))
  else
    good "APPEND  $log — local $L / origin ${R:-0}, not shrinking"
  fi
done

# ------------------------------------------------------------ act, or explain
say ""
if [ -z "$TRACKED_DIFF" ] && [ -z "${UNIQUE//[$'\n']/}" ] && [ "$BEHIND" -gt 0 ] && [ "$AHEAD" -eq 0 ]; then
  if [ "$REPORT_ONLY" = "1" ]; then
    say "Safe to fast-forward $BEHIND commit(s). Re-run without --report to do it."
  elif git merge --ff-only origin/main >/dev/null 2>&1; then
    good "FAST-FORWARDED $BEHIND commit(s) -> $(git log --oneline -1)"
    ISSUES=0
  elif git reset --hard origin/main >/dev/null 2>&1; then
    # `merge --ff-only` refuses whenever a file differs from HEAD, even when
    # its content is byte-identical to the merge target — it compares against
    # HEAD, not against where it is going. That is the NORMAL state here: a
    # Cowork commit leaves new content in the tree and an old HEAD, so every
    # such file looks "locally modified" and blocks the merge.
    #
    # `reset --hard` is safe at this point and ONLY at this point: this branch
    # is reached only after the tree was proven to match origin/main byte for
    # byte, so there is nothing for it to discard. Never move this call out
    # from behind that proof.
    good "FAST-FORWARDED $BEHIND commit(s) -> $(git log --oneline -1)"
    say  "${DIM}        (via reset --hard; tree already identical to origin, nothing discarded)${OFF}"
    ISSUES=0
  else
    bad  "FF FAILED — could not write .git. Expected under Cowork's mount;"
    say  "        unexpected locally, in which case see the lock report above."
    say  "        Work against origin/main and commit with:"
    say  "          bash safe_git_commit.sh \"message\""
    ISSUES=$((ISSUES+1))
  fi
elif [ "$ISSUES" -gt 0 ]; then
  say "NOT fast-forwarding — resolve the above first."
  say ""
  say "Whatever you do, decide direction PER FILE. Origin is not automatically"
  say "right and neither are you. To keep a full recovery point before anything"
  say "destructive:"
  say "  git checkout -b snapshot-\$(date +%F) && git add -A && git commit -m SNAPSHOT"
fi

say ""
[ "$ISSUES" -eq 0 ] && good "preflight clean." || warn "preflight found $ISSUES thing(s) to look at."
exit 0
