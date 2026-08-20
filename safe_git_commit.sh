#!/usr/bin/env bash
# Commit and push through a scratch-space clone, bypassing this environment's
# connected-folder mount for the actual git bookkeeping.
#
#   bash safe_git_commit.sh "commit message"
#
# WHY THIS EXISTS. Cowork's connected-folder mount is a permission-mediated
# bridge to the real folder on Sylvan's Mac, built for safe reading, writing,
# and creating files. It does not support the unlink()/rename-over-existing
# semantics git's own commit machinery depends on for its lock and loose-
# object temp files (index.lock -> index, HEAD.lock -> HEAD, .git/objects/*/
# tmp_obj_*). Symptom without this script: `git commit` intermittently
# leaves one of those behind, and `rm -f` on it either silently no-ops
# (reports success, file persists) or returns "Operation not permitted" -
# first hit and documented 20 Aug 2026, see INTEL_SWEEP.md's "Known issue".
#
# WHAT THIS DOES INSTEAD. Clones this repo's own origin into a fresh
# directory under /tmp - ordinary ephemeral sandbox disk, not the bridged
# mount, so unlink/rename work exactly as normal. Copies over exactly the
# files `git status --porcelain` reports as changed in THIS working tree,
# commits and pushes from the clone, then discards it. This repo's actual
# `.git/` is never written to for the commit itself - only read, to find
# the origin URL and the list of changed files.
#
# LIMITATIONS. Parses `git status --porcelain` with a simple awk - fine for
# adds/modifies/deletes of plainly-named files (everything this repo's
# scheduled tasks touch: ROLE_INTEL.md, docs/data/intel_sweep_log.jsonl,
# docs/news.html and similar). Renames and filenames containing spaces are
# NOT handled correctly - if you hit either, stage and commit by hand from
# a real terminal instead of trusting this script.
set -euo pipefail
cd "$(dirname "$0")"

MSG="${1:?usage: safe_git_commit.sh \"commit message\"}"

CHANGED=$(git status --porcelain | awk '{ $1=""; sub(/^ /,""); print }')
if [ -z "$CHANGED" ]; then
  echo "Nothing to commit."
  exit 0
fi

CLONE="/tmp/safe-git-commit-$$"
trap 'rm -rf "$CLONE"' EXIT

REMOTE_URL=$(git remote get-url origin)
git clone --quiet "$REMOTE_URL" "$CLONE"

# A fresh clone has no local [user] section, and this sandbox has no global
# git config either - first hit 20 Aug 2026 ("Author identity unknown").
# Carry over this working tree's own identity (read-only - never writes back
# to this repo's own config) so commits are attributed correctly.
USER_NAME="$(git config user.name  2>/dev/null || echo 'Claude (Cowork)')"
USER_EMAIL="$(git config user.email 2>/dev/null || echo 'noreply@example.com')"
git -C "$CLONE" config user.name  "$USER_NAME"
git -C "$CLONE" config user.email "$USER_EMAIL"

while IFS= read -r f; do
  [ -z "$f" ] && continue
  if [ -e "$f" ]; then
    mkdir -p "$CLONE/$(dirname "$f")"
    cp "$f" "$CLONE/$f"
  else
    rm -f "$CLONE/$f"
  fi
done <<< "$CHANGED"

(
  cd "$CLONE"
  git add -A
  git commit -q -m "$MSG"
  git push --quiet
  echo "Pushed: $(git log --oneline -1)"
)

echo "Done — committed and pushed via scratch clone, this working tree's own .git was untouched."
