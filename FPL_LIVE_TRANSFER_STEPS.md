# Actioning a transfer live on fantasy.premierleague.com — process notes

Captured 28 Aug 2026, first real run: `Sarr -> Schade`, GW2. Written so this
becomes a repeatable skill rather than re-discovered each time. Uses the
Claude-in-Chrome browser tools against the user's real, already-logged-in
session — never enter credentials.

## Prerequisites

- The decision must already be recorded in `squad.json` / `TEAM_CHANGE_LOG.md`
  **before** touching the live site (see `fpl-weekly-brief` SKILL.md Step 4) —
  the repo is the record; the site submission is a separate, later step.
- Confirm the user has explicitly asked for the live submission. This is an
  irreversible-once-confirmed action.

## Steps that worked

1. **Navigate to `https://fantasy.premierleague.com/my-team`.** If already
   logged in (check for the team name / manager name in the left panel, e.g.
   "River Leaf FC" / "aSyd Reigns"), proceed. If not logged in, stop and ask
   the user to log in themselves — never enter a password.
2. **Click the "Transfers" sub-nav tab** (`Pick Team | Points | Transfers |
   Leagues | ...`) to reach `/transfers`. Confirms gameweek, deadline, budget,
   free transfers and points cost at the top of the page.
3. **Scroll to the pitch view.** Each player card has a small "✕" icon
   top-left — click it to remove that player. The page auto-refilters the
   left "Player Selection" panel to the vacated position and shows the
   proceeds in "Budget".
4. **Search the incoming player by name** in the left panel's search box,
   then click the "+" button on their row to add them. Confirms "15 / 15"
   players and updates "Budget" (this is your remaining bank, not the cost).
5. **Scroll down and click "Make Transfers".** This opens a "Confirm
   Transfers" side panel — **it renders partially off-screen/cut off at the
   viewport width used here (1503px)**. Scroll the page to the top first; the
   panel repositions to a readable, non-cut-off state. Check the cost
   breakdown table (Out / In / Cost / Total cost) matches intent, then click
   **"Confirm"**.
6. **You land back on the Pick Team page** (`/my-team`), transfer applied.

## Setting captain/vice — the part that silently fails if you skip step 4

7. **Click a player's shirt on the pitch** to open their profile panel. At
   the bottom is a `contentinfo` region with **two separate checkboxes**,
   `"Captain"` and `"Vice Captain"` (both real accessibility labels — use
   `find` to get exact refs rather than guessing coordinates, since this
   panel can also render cut off at the right edge of the viewport depending
   on scroll position).
8. **Click the checkbox for the role you want.** The pitch updates
   immediately (badge appears on the shirt) — **this LOOKS saved but is not**.
9. **THE ACTUAL SAVE STEP: scroll down past the Substitutes row and click
   the "Save Your Team" button.** Confirmed via `read_network_requests` that
   clicking a Captain/Vice checkbox alone fires **no API call** — it's pure
   client-side state. Only clicking "Save Your Team" persists it; a banner
   reading "Your team has been saved." confirms success.
10. **Verify with a hard reload**, not just a screenshot of the current DOM
    state — navigate to `/my-team` again fresh and re-check the badges. This
    caught the bug twice in this session: captain/vice changes that looked
    right on-screen reverted to the pre-change armband after a real reload,
    because step 9 hadn't happened yet.

## Other things worth knowing for next time

- **Live prices can differ from what `squad.json` has recorded.** In this
  run, Sarr's tracked price (£6.5m) was stale — he actually sold for £6.4m
  live, a real market move this repo doesn't yet forecast (roadmap B1). Read
  the actual price off the player card (zoom on it — the price is shown
  top-left of the shirt) rather than assuming the repo's number is current,
  and flag any mismatch in the change log rather than silently reconciling
  it into the repo's internal ledger.
- **A red warning-triangle icon on a player's shirt card** is the site's own
  injury/doubt flag — useful as an independent visual confirmation of
  whatever `injury_report` already said.
- **`browser_batch` speeds this up a lot** — batch a click + wait + screenshot
  together rather than one call per action, except right after a click whose
  result you need to inspect before deciding the next click (e.g. checking
  which checkbox a panel actually exposes).
- **Prefer `ref`-based clicks (from `find`/`read_page`) over raw pixel
  coordinates** once a panel is open — panel layout shifts depending on page
  scroll position when it renders cut-off, and a stale coordinate from a
  previous screenshot can land on the wrong element.
- **Close a player panel by clicking elsewhere or the explicit "✕" close
  button, not by pressing Escape** — Escape appeared to leave a pending
  checkbox click in an inconsistent state in this session (unconfirmed
  whether Escape itself caused it, but avoid it until re-tested).

## Suggested next refinement

Fold this into `fpl-weekly-brief` SKILL.md's Step 4 "If transfers are
actioned live" section directly, so the skill itself carries the exact
click sequence rather than relying on this being rediscovered. Not done here
since skill files need `save_skill` to update, not a repo edit.
