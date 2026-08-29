# WhatToEat?

**The leftover-budget planner for the last meal of the day.**

It's 9 pm and you have 950 kcal left. What do you eat — from what is actually in your cupboard, without spending five minutes nudging gram counts around in a tracker?

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

### 3.4 Product Database & Data Quality

Users may add their own products — as in Yazio — because otherwise the one store brand you actually buy is always missing. Two stages keep the database from rotting:

**Automatic plausibility check on entry:**

- Calculated calories: `kcal ≈ 4·carbs + 4·protein + 9·fat`. If the entered kcal value deviates by more than roughly 20 %, warn.
- Hard bounds: macros sum to ≤ 100 g per 100 g; no single value above that; ≤ ~900 kcal per 100 g, which would be pure fat.
- Order-of-magnitude check against the category: 500 g of rice is ~600 kcal, not 6,000 — this catches decimal-place typos reliably.

**Community review** for entries that look suspicious or are used frequently.

> **Cold-start problem:** an empty product database makes the app unusable. The obvious base layer is [Open Food Facts](https://world.openfoodfacts.org) — open, barcode-indexed, millions of products. **To check:** its licence (ODbL) requires attribution and imposes conditions on derived databases. That has to be settled *before* commercial use, not after.

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

