#!/usr/bin/env python3
"""Squad-shape constants — the £100m / 2-5-5-3 / 3-per-club rules.

EXTRACTED 14 Aug 2026 (architecture review candidate #4). Before this,
build_squad.py and optimise_squad.py each hand-wrote the same constraint,
keyed differently:

  build_squad.py:    SQUAD_SHAPE = {1: 2, 2: 5, 3: 5, 4: 3}   (int position codes)
  optimise_squad.py: SQUAD       = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}

(build_squad.py's copy was dead code — nothing in that file actually read
SQUAD_SHAPE; the squad shape was hardcoded again inline in build()/main()
via literal 5-, 5-, 3- arithmetic. Replacing it with this import removes the
unused duplicate rather than changing behaviour.)

One representation, string-keyed to match POS = {1:"GKP", 2:"DEF", ...} used
everywhere else in the pipeline.
"""

BUDGET = 100.0
MAX_PER_CLUB = 3
XI_SIZE = 11
SQUAD_SHAPE = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
FORMATION = {"GKP": (1, 1), "DEF": (3, 5), "MID": (2, 5), "FWD": (1, 3)}
