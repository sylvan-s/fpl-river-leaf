# Repo sync: why `git status` lies here, and what to trust instead

**Run `bash preflight.sh` before touching anything. Every session, local or
Cowork, before reading a file or forming a view of repo state.**

## The one rule

`git status` is not a truthful answer in this repo, and that is by design.
The only meaningful question is:

> How do I differ from `origin/main`, after a fresh `git fetch`?

Everything below is why.

## Why local HEAD goes stale

Two environments write to this repo and they do not have the same
capabilities:

| | filesystem | git | effect on local HEAD |
|---|---|---|---|
| **Cowork** | permission-mediated bridge to the folder on Sylvan's Mac | must use `safe_git_commit.sh` | **never advances** |
| **Claude Code** | real disk at `~/Projects/FPL` | plain git works | advances normally |

Cowork's mount cannot do the `rename()`-over-existing that git's commit
machinery depends on (`index.lock` → `index`, `HEAD.lock` → `HEAD`, loose
object temp files). So `safe_git_commit.sh` commits from a scratch clone of
`origin` under `/tmp` and deliberately never touches this working tree's own
`.git/`. Its header explains the consequence:

> local HEAD falls further behind origin every time this script runs, and a
> plain `git status` in this repo would keep reporting already-pushed files
> as "changed" forever.

That is correct behaviour, not a fault. But it means a session that trusts
`git status` sees a large "uncommitted" working tree that is in fact already
on GitHub, sitting on a HEAD that may be many commits stale.

## What this actually looked like (12 Sep 2026)

A zero-byte `.git/index.lock`, **eight days old**, with no git process
holding it, had blocked every local commit since 4 Sep. Work continued
normally — through Cowork, via the scratch clone — so nothing appeared
broken. By the time anyone looked:

- local HEAD was **12 commits behind** origin
- ~60 files showed as modified, **every one already pushed**
- **zero** files existed locally that origin did not have

The obvious reading — "there's uncommitted work, commit it" — would have
overwritten origin's GW1–3 prediction record with a local GW1–2 copy.
`prediction_tracker.json` was **older** locally; `fixture_window.json` was
**newer** locally. Same tree, opposite directions.

**So: never resolve this wholesale. Direction is a per-file judgement.**

## What `preflight.sh` checks

1. **Stale lock files** and their *age*, plus whether a git process is
   actually running. An 8-day-old lock is not contention, it is debris.
2. **HEAD vs `origin/main`**, naming the incoming commits.
3. **Working tree vs `origin/main`** — separating files that exist *only*
   here (real unpushed work) from untracked files already on origin (noise).
   Untracked files need listing separately because `git diff origin/main`
   reports them as deletions: they are not in the index, so git cannot see
   them as present.
4. **Append-only logs** — `docs/data/intel_sweep_log.jsonl` and
   `fpl_calibration_log.jsonl` must never shrink. If the local copy has
   fewer lines than origin's, local is stale and committing it would delete
   history nothing downstream can reconstruct: a missing entry is
   indistinguishable from one that was never written.

It then **fast-forwards only when the tree already matches `origin/main`
byte for byte** — the case where there is provably nothing to lose. Anything
genuinely different and it stops and shows you what.

It never pushes, never commits, never discards.

### The `reset --hard` inside it is deliberate

`git merge --ff-only` refuses whenever a file differs from **HEAD**, even
when that file's content is byte-identical to the merge target — it compares
against HEAD, not against where it is going. That is the *normal* state here
(new content in the tree, old HEAD), so the merge path fails in the common
case and `preflight.sh` falls back to `git reset --hard origin/main`.

That is safe **only** because it sits behind the proof that the tree already
matches origin. Do not move it out from behind that check.

## Committing

- **Cowork:** `bash safe_git_commit.sh "message"` — always. Never raw
  `git commit`.
- **Claude Code (local):** plain git is fine, once `preflight.sh` is clean.

## Known gap, not yet fixed

`safe_git_commit.sh` copies its candidate files over a fresh clone and
pushes: **whole-file, last-writer-wins, no merge.** If a routine pushes
while another session is mid-run, the second overwrites the first's version
of any file on both lists. For most files that is recoverable churn. For the
append-only `.jsonl` logs it is silent, unrecoverable data loss.

`preflight.sh`'s append-only check catches this *after the fact*, at the
start of the next session. It does not prevent it. Hardening the commit
script — re-check that `origin/main` has not moved before pushing, retry on
rejection, append-and-dedupe rather than copy-over for `*.jsonl` — is the
outstanding fix.
