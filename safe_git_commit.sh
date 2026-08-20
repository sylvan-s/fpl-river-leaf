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
# files that differ between THIS working tree and origin/main, commits and
# pushes from the clone, then discards it. This repo's actual `.git/` is
# only ever read (to get the origin URL and identity, and to fetch), never
# written to for the commit itself.
#
# WHY COMPARE AGAINST origin/main, NOT LOCAL git status. Every commit this
# script makes goes straight to origin without ever advancing this working
# tree's own local HEAD (doing that would need the same blocked rename-
# over-existing this script exists to avoid, applied to .git/HEAD/.git/
# index instead of .git/objects). That means local HEAD falls further
# behind origin every time this script runs, and a plain `git status` in
# this repo would keep reporting already-pushed files as "changed" forever.
# Diffing against `origin/main` after a fresh `git fetch` gives the real
# answer regardless of how stale local HEAD is.
#
# LIMITATIONS. Renames and filenames containing spaces are not specially
# handled (a rename shows as a delete + an add, which is still correct, just
# not space-efficient in the resulting commit). Fine for this repo, which
# only ever adds/edits plainly-named markdown, JSON and HTML files here.
set -euo pipefail
cd "$(dirname "$0")"

MSG="${1:?usage: safe_git_commit.sh \"commit message\"}"

git fetch --quiet origin

CANDIDATES=$(
  { git diff --name-only origin/main --
    git ls-files --others --exclude-standard
  } | sort -u
)

if [ -z "$CANDIDATES" ]; then
  echo "Nothing to commit (working tree already matches origin/main)."
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
done <<< "$CANDIDATES"

cd "$CLONE"
git add -A
if git diff --cached --quiet; then
  echo "Nothing to commit (candidates matched origin/main byte-for-byte after all)."
  exit 0
fi
git commit -q -m "$MSG"
git push --quiet
echo "Pushed: $(git log --oneline -1)"
echo "Done — committed and pushed via scratch clone, this working tree's own .git was untouched."
