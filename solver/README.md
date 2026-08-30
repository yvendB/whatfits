# Phase 0 — the solver prototype

**The question this exists to answer:** insisting on whole tins and sensible
gram steps must cost accuracy. Does it cost so much that the idea does not
work?

**The answer: no.** Across 300 random evening budgets, the grid-constrained
solver hits the target within a median of 3 kcal, leaves nothing open in the
fridge, and runs in about 5 ms. See [Results](#results).

No dependencies beyond the standard library. Python 3.10+.

---

## Running it

### In VS Code, without touching a terminal

Open the **`WhatFits` folder itself** (File → Open Folder), not the folder above
it — otherwise the tasks below are not found.

Then `Ctrl+Shift+P` → **Tasks: Run Task**:

| Task | What it does |
|---|---|
| WhatFits: plan a meal | asks for calories and meal, then suggests |
| WhatFits: plan a meal (with macros) | same, plus protein / carb / fat targets |
| WhatFits: add a product by barcode | type the GTIN, it looks it up and adds it |
| WhatFits: search for a product | find one by name or brand |
| WhatFits: check the pantry | plausibility check over your data |
| WhatFits: benchmark the portion grid | what the grid costs in accuracy |
| WhatFits: run the tests | the full suite |

Planning is the default build task, so `Ctrl+Shift+B` runs it straight away.
With the Python extension installed, `F5` steps through it in the debugger.

### Filling the pantry from a barcode

```bash
python -m whatfits lookup 4250193181802 --add   # scan replacement: type the GTIN
python -m whatfits find "Rinderhack Purland"    # when there is no barcode to hand
```

`lookup` validates the check digit before spending a network call, reports every
value the database is missing rather than filling gaps with zeros, and refuses to
add a product it cannot plan with. Coverage is uneven — see
[Open Food Facts coverage](#open-food-facts-coverage) — so expect to type some
products in by hand.

### In a terminal

```bash
cd solver

# What can I eat with 950 kcal left, aiming for 65 g protein?
python -m whatfits plan 950 --protein 65 --carbs 130 --fat 25 --meal dinner

# Does my pantry data survive the plausibility check?
python -m whatfits check

# What does the portion grid actually cost in accuracy?
python -m whatfits benchmark --runs 300 --meal dinner

python -m pytest tests
```

> **On Windows `cmd`, plain `cd` will not move between drives.** If the prompt
> sits on `C:` and the repository is on `F:`, `cd F:\...` silently does nothing.
> Use `cd /d "F:\Users\prime\Claude Workspace\WhatFits\solver"`, or type `F:`
> on its own line first. PowerShell and the VS Code terminal do not have this
> problem.

Sample output:

```
Budget    950 kcal   130 g carbs   65 g protein   25 g fat
Pantry    9 products, 9 usable for dinner
Search    1,191 combinations from 2,299 nodes in 3 ms

 1.   954 kcal      (target 950, +4)      score 81
      150 g              Rice, dry  ~524 kcal
      2 breasts (300 g)  Chicken breast, raw  ~318 kcal
      1/2 tin (128 g)    Kidney beans, tinned, drained  ~112 kcal   <- uses up the pack already open
      carbs 134 g (+4)   protein 88 g (+23)   fat 7 g (-18)
```

Every amount is something a person can serve without a scale and without
opening a tin for a few grams. That is the whole point.

## Your own pantry

[`data/pantry.json`](data/pantry.json) is **seed data, not truth**. Replace the
nutrition values, pack sizes and grids with what is actually in your cupboard,
then run `python -m whatfits check`. Phase 0 only answers its question honestly
if the data is honest.

Two grid kinds:

| Kind | For | Example |
|---|---|---|
| `pack` | tins, packs, pieces | `fraction: 0.5` allows half tins, `1.0` whole only |
| `mass` | rice, nuts, oil | `step_g: 10` from `min_g` to `max_g` |

`open_g` records how much of an already-opened pack is in the fridge. Using it
up earns a bonus.

## How it works

**`model.py`** — the portion grid. Every product declares the amounts it may
contribute, and the search only ever sees those, so a suggestion is practical
by construction rather than rounded into shape afterwards. `Packaging` records
what serving a portion does to the packs in your kitchen: what gets used up,
what gets broken into, what is left standing open.

**`scoring.py`** — the score, in penalty points where one point is roughly one
kcal of badness. It splits in two, and the split is what makes the search fast:
`portion_cost` depends only on the portion (packaging waste, repetition, the
price of another item on the plate) and is computed once; `fit_cost` depends
only on the totals and is a handful of float operations.

**`search.py`** — depth-first enumeration with branch and bound. Products are
sorted by their largest possible contribution, descending, which makes the
upper bound exact rather than merely valid: the k best remaining products are
simply the next k in the list. The search is **exhaustive**, not heuristic —
`test_branch_and_bound_finds_the_same_optimum_as_brute_force` pins it to a
brute-force enumeration. That matters: if a suggestion looks wrong, the score
function is wrong, and that is a far easier thing to debug.

## Results

9-product pantry, dinner, 300 random budgets between 300 and 1200 kcal, macro
targets in conventional proportions, tolerance −150/+50 kcal.

| Max components | Solved | kcal error (median) | p90 | Left open | Runtime (median) |
|---|---|---|---|---|---|
| 2 | 80 % | 13 kcal | 116 kcal | 0 g | 1 ms |
| **3** (default) | **100 %** | **3 kcal** | **12 kcal** | **0 g** | **5 ms** |
| 4 | 100 % | 2 kcal | 8 kcal | 0 g | 35 ms |

### What this settles

- **The portion grid is not the constraint anyone feared.** Restricted to whole
  tins, whole pieces and 5–25 g steps, the solver still lands within a few kcal
  of target on essentially every evening.
- **Nothing is left open.** Median leftover is 0 g. The packaging rule does the
  job it was invented for.
- **It runs on a phone.** Milliseconds, single-threaded, no dependencies, no
  server. The concept doc's claim that the core feature works offline holds.
- **Three components is the right default.** Going from 3 to 4 buys 1 kcal of
  median accuracy for 7× the runtime and a busier plate. Two components fails
  to find anything 20 % of the time. This changed the default during phase 0.

### Open Food Facts coverage

Counting only what the solver needs: kcal, carbohydrates, protein and fat.

| Slice | Size | Has all four |
|---|---|---|
| German products, most scanned | 100 | 97 % |
| German products, newest entries | 100 | 97 % |
| German products, least scanned | 100 | 95 % |
| Landjunker (Lidl, fresh meat) | 87 — full census | 77 % |
| **Purland (Kaufland, fresh meat)** | **157 — full census** | **53 %** |

Good for packaged goods, with a specific hole in fresh meat and produce. So
"scanned but incomplete" is a designed-for path rather than an error — rare for
a tin of sweetcorn, routine for mince.

> **An earlier version of this table was wrong**, and the mistake is worth
> keeping visible: first-page results are not a random sample. Open Food Facts
> sorts by popularity by default, which flattered the big brands and
> misrepresented the small ones. These figures come from comparing several sort
> orders and from enumerating the small brands completely.
>
> Open Food Facts' own `nutrition-facts-completed` flag sits at 58 % for German
> products, but it demands the full table including salt, sugars and saturated
> fat. Four numbers is a much lower bar, so that stricter measure is not the
> constraint here.

**Why not a different database.** USDA FoodData Central is free and open but US
only — tested with three European barcodes, it returned zero hits for all three.
FatSecret, Nutritionix and Edamam have the coverage but are commercial APIs you
may query and not hold, which for a paid app means a per-request cost and a
supplier who can change the terms. Open Food Facts is the only open
barcode-to-nutrition database at this scale.

### What this does not settle

- **The weights are plausible, not calibrated.** They were reasoned about, not
  measured. The most influential single number is `use_up_bonus`: at 60 points
  it will accept a meaningfully worse macro split in order to finish an open
  pack. Whether that matches what a real person wants is a phase 1 question,
  and it is the first weight to tune.
- **Accuracy currently outranks packaging waste.** Going 25 kcal over budget
  costs more than leaving 50 g of a tin open. That is a judgement call encoded
  in the ratio between `kcal_over` and `offcut`, pinned by
  `test_accuracy_outranks_packaging_at_default_weights` so it cannot drift
  unnoticed.
- **A 9-product pantry is small.** Runtime grows with pantry size and component
  limit. At 40 products this needs re-measuring, and the `node_limit` and
  `truncated` flag exist for that eventuality.
- **Nothing here knows about taste.** The solver will happily propose rice with
  skyr and eggs. Meal-type filtering is the only palatability rule so far, and
  it is a crude one.

## Deliberately not here

No product database, no barcode scanning, no Health integration, no accounts,
no UI. Those are phases 2 and beyond. Phase 0 answers one question, and it is
finished when that question is answered.
