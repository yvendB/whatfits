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

