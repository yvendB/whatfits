# WhatFits?

**The leftover-budget planner for the last meal of the day.**

It's 9 pm and you have 950 kcal left. What fits — from what is actually in your cupboard, without spending five minutes nudging gram counts around in a tracker?

---

## 1. The Problem

Calorie trackers (Yazio, MyFitnessPal, …) tell you *how much* you are still allowed to eat. None of them tell you *what*. In practice the evening goes like this:

- X kcal and Y g of protein are still open.
- You mentally walk through your cupboard, type in 80 g of rice, correct it to 120 g, add corn, recalculate, drop the chicken again.
- It takes far too long — and you routinely forget food you actually have.
- Worst of all, the result is unusable in real life: nobody opens a tin for 37 grams of sweetcorn.

## 2. The Idea in One Sentence

You enter your remaining budget (or it arrives automatically), and the app proposes combinations from **your own** food that hit that budget — in **amounts you can actually measure**: whole tins, half packs, one chicken breast.

## 3. Core Features

### 3.1 Capturing the Remaining Budget

- **Manual** (the baseline, must always work): remaining kcal, plus optionally the remaining macros (carbs / protein / fat).
- **Automatic** (later): sync with the tracker the user already runs. Plenty of people deliberately do *not* want their apps connected, so the manual path stays fully equivalent and must never become second class.

### 3.2 My Pantry

The user registers the food they eat regularly once — e.g. chicken breast, rice, sweetcorn, kidney beans, peas & carrots, peanuts.

Per entry:

| Field | Example | Purpose |
|---|---|---|
| Product (from DB) | "Bonduelle sweetcorn, tinned" | exact nutrition values |
| Pack size | tin, 285 g / 150 g drained | basis for whole units |
| **Portion grid** | 1 tin · ½ tin | permitted step size in a suggestion |
| Partial pack allowed? | corn: no · peanuts: yes | prevents "37 g of sweetcorn" |
| Suitable for | dinner, lunch | filters out breakfast nonsense |
| Already open in the fridge? | yes, ½ tin | bonus for using it up |

The **portion grid** is the one idea that separates this app from a plain calculator.

### 3.3 The Suggestion Algorithm (the core)

**Input:** remaining budget (kcal + macros with tolerances), the pantry with its portion grids, the meal type, user preferences.
**Output:** several combinations, ranked by how well they fit.

The search space is deliberately **discrete**: every product may only contribute amounts from its own grid (corn: 0 / ½ / 1 / 1½ tins — rice: 0 / 50 / 60 / … / 150 g). That makes the result practical by construction, instead of rounding it into shape afterwards.

Each combination is ranked by a weighted score, roughly:

```
score =  w_kcal  · deviation(kcal)          // asymmetric: over ≠ under
       + w_macro · deviation(P, C, F)
       + w_pack  · partial_pack_penalty     // odd leftovers are expensive, whole packs are free
       - w_open  · use_up_bonus             // clearing an already-open pack pays off
       + w_rep   · repetition_penalty       // not the same thing five days running
       + w_n     · component_count          // three ingredients beat six
```

In practice: pre-filter by meal and category, then depth-first search with branch and bound over at most three to five components. With a pantry of 20–40 products this resolves in milliseconds on the device — **no server required**, the core feature works offline.

> **Architecture note:** the solver belongs in a standalone, platform-independent module covered by unit tests, independent of the UI framework. It is the app's one genuine differentiator, and the part that is easiest to test — and to show in a portfolio.

### 3.4 Getting Products In, and Keeping Them Clean

Three ways in, in ascending order of how much work they cost the user:

1. **Barcode scan.** The least work possible, and how people already add products in trackers they know. The barcode is not merely a convenience: it is the *primary key* of [Open Food Facts](https://world.openfoodfacts.org), so scanning and the cold-start fix are the same mechanism rather than two features.
2. **Search by name or brand.** For the packet that is already open, or whose barcode the database does not carry. Typing "Rinderhack Purland" has to find the Kaufland own brand.
3. **By hand.** The fallback — and needed more often than one would hope (see below). It must never feel like a punishment.

**Barcodes get validated before they are trusted.** Every retail barcode is a GTIN carrying a mod-10 check digit, so a mistyped one is detectable with no network call at all. Worth doing: a wrong barcode does not fail, it silently points at a different food.

Users may add their own products — as in Yazio — because otherwise the one store brand you actually buy is always missing. Two stages keep the database from rotting:

**Automatic plausibility check on entry:**

- Calculated calories: `kcal ≈ 4·carbs + 4·protein + 9·fat`. If the entered kcal value deviates by more than roughly 20 %, warn.
- Hard bounds: macros sum to ≤ 100 g per 100 g; no single value above that; ≤ ~900 kcal per 100 g, which would be pure fat.
- Order-of-magnitude check against the category: 500 g of rice is ~600 kcal, not 6,000 — this catches decimal-place typos reliably.

**Community review** for entries that look suspicious or are used frequently.

> **Cold start — measured.** An empty product database makes the app unusable, and [Open Food Facts](https://world.openfoodfacts.org) is the base layer: open, barcode-indexed, ~2.8 M products across 150+ countries, ODbL. Coverage, counting only what the solver needs — kcal, carbohydrates, protein and fat:
>
> | Slice | Size | Has all four |
> |---|---|---|
> | German products, most scanned | 100 | 97 % |
> | German products, newest entries | 100 | 97 % |
> | German products, least scanned | 100 | 95 % |
> | Landjunker (Lidl, fresh meat) | 87 — full census | 77 % |
> | **Purland (Kaufland, fresh meat)** | **157 — full census** | **53 %** |
>
> So the database is in good shape for packaged goods and has a **specific hole in fresh meat and produce**. A scan of "Rinder-Hackfleisch Purland, 500 g" returns a real product with not one nutrition value attached. So **"scanned, but incomplete" has to be a designed-for path rather than an error state** — rare for a tin of sweetcorn, routine for mince — and it has to lead straight into filling the gaps by hand. Which feeds the community database, closing the same loop as 3.7.
>
> *Method, because an earlier version of this table was wrong:* first-page samples are not random samples — Open Food Facts orders by popularity by default, which flattered the big brands and misrepresented the small ones. The figures above come from comparing several different sort orders, and from enumerating the two small brands completely. Separately, only 58 % of German products carry Open Food Facts' own `nutrition-facts-completed` flag, but that demands the full table including salt, sugars and saturated fat. We need four numbers, so that stricter measure is not our constraint.

> **Why this database and not another one.** The question is worth asking once, properly:
>
> - **USDA FoodData Central** — free, open, ~450 k branded foods. Tested with three European barcodes (Nutella EAN-13, Purland mince, K-Classic sweetcorn): **zero hits for all three.** It is a US database keyed on UPC. Not usable here.
> - **FatSecret, Nutritionix, Edamam, Spike** — 3 M+ products and good coverage, but commercial APIs. You may query them; you may not hold the data. For a product whose roadmap ends in a paid app, that means a per-request cost, a hard dependency, and a supplier who can change the terms.
> - **Open Food Facts** — the only one in its class you can actually keep a copy of.
>
> It is not a compromise for lack of a better option; it is the only open barcode-to-nutrition database at this scale. The fresh-produce gap gets closed by users, which is the community mechanism the concept already calls for.

> **The portion grid can never come from a database.** Open Food Facts knows the net weight. It does not know the drained weight of a tin, how many pieces are in a pack, or whether you would use half of one. That knowledge is the user's, and it is precisely what makes this more than a lookup table.

> **Licence, still open:** ODbL requires attribution and imposes conditions on derived databases. That has to be settled *before* commercial use, not after.

### 3.5 Meal Context

Split into **breakfast / lunch / dinner / snack**. This matters to the solver because different food makes sense per meal — suggestion sets for different meals should overlap as little as possible.

### 3.6 Suggestions From History

From the usage data of recent weeks the app learns which products fit which budget situations — and reminds the user of food they keep forgetting despite having it in the cupboard. That is exactly the mistake people make when doing this in their head.

### 3.7 Community

- Users can publish their own **dishes** (finished combinations), which can then be offered to others as ready-made suggestions.
- **Community points** on the profile as an incentive to contribute data.

## 4. User-Facing Settings

- **Target accuracy:** how precisely does the budget have to be hit?
- **May I go over?** Overshoot allowed yes/no, and if yes, by how much.
- **Partial-pack rules** per product or category: tins only whole or half, nuts to the gram.
- **Maximum number of components** per suggestion.

These settings are the weights of the score function, translated into plain language.

## 5. Business Model

- The app is **free** by default, funded by ads.
- A **Pro subscription** removes the ads. Price range in line with Yazio — deliberately cheap; this is not a premium product.

## 6. Platforms & Roadmap

**iOS first, Android after. One thing at a time.**

| Phase | Content | Goal |
|---|---|---|
| **0** | [Solver prototype](solver/) — plain script, real pantry data | **Done.** The portion grid costs almost nothing in accuracy |
| **1** | iOS app, local only, manual entry, own pantry, solver | Usable daily by myself |
| **2** | Product database + barcode scan + search, Health integration | Usable by strangers |
| **3** | Accounts, community dishes, points | Network effect |
| **4** | Ads + Pro subscription | Monetisation |
| **5** | Android | Reach |

Phases 0 and 1 are the only ones strictly needed to find out whether the idea holds up.

### Phase 0 result

The [solver prototype](solver/) answers the question phase 0 was for. Restricted
to whole tins, whole pieces and sensible gram steps, it hits the calorie target
within a median of 3 kcal across 300 random evening budgets, leaves nothing
standing open in the fridge, and runs in about 5 ms with no dependencies and no
server. The search is exhaustive rather than heuristic, and is pinned to a
brute-force enumeration by a test.

Two things phase 0 changed: the default plate is three components rather than
four (same accuracy, seven times faster), and the scoring weights are now known
to be plausible but uncalibrated — `use_up_bonus` is the first one phase 1
should tune against real use. Details and caveats in [solver/README.md](solver/README.md).

## 7. Technical Notes

**On tracker integration:** a direct Yazio integration is unrealistic — there is no public API, and it would require a partnership. The practical route is the platform's own health store: **Apple Health (HealthKit)**, and **Health Connect** on Android. Trackers write their nutrition data there; WhatFits reads today's consumed kcal and macros and derives the remainder itself. This works without any cooperation from Yazio, and with every other tracker at the same time.
*To verify:* whether Yazio actually writes nutrition data to Apple Health in the version in use, and at what granularity.

**Proposed stack:** the solver as a standalone, tested module. Above it a cross-platform UI (Flutter or React Native), so that phase 5 does not mean building everything twice, with native bridges for HealthKit and Health Connect. A backend is only needed from phase 2/3 onwards; for a solo developer a backend-as-a-service beats self-hosted infrastructure, and relational Postgres fits product data well. Pantry and solver stay **offline-first**.

## 8. Scope

WhatFits is **not** a calorie tracker and does not aim to become one. It is a companion for the last decision of the day. That keeps the product small and sharp — but it also means a permanent dependency on the app the user already runs. That is the central strategic risk, and it should be carried deliberately rather than defined away.

## 9. Open Questions

- Open Food Facts licensing (ODbL) under commercial use.
- Does Yazio reliably write to Apple Health? What about the other major trackers?
- How much of the gap in fresh-produce coverage can community contributions realistically close, and how fast?
- Trademark clearance for "WhatFits" (DPMA, EUIPO, USPTO) — the obvious collisions are ruled out, but a web search is not a legal clearance.
- Community features need moderation. At what point is that worth the effort?

## 10. Licence

Copyright (c) 2026 Yven de Buhr. All rights reserved. See [LICENSE](LICENSE).

This repository is public so the work can be read and evaluated. It is not
open source: no permission is granted to reuse the code or the concept
material in another project.

---

*Idea dump of 2026-08-29, structured. Changes and additions belong directly in this file.*
