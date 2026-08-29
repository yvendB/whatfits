"""The search itself: which combinations of portions to consider, and how to
avoid considering the overwhelming majority of them.

Because every product contributes only amounts from its own portion grid, the
search space is discrete and small enough to enumerate exhaustively with
pruning -- no heuristics, no approximation. The result is the genuine optimum
under the score function, which matters: if a suggestion looks wrong, then the
score function is wrong, and that is a far easier thing to debug.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Mapping, Sequence

from .model import Budget, Meal, Nutrition, Portion, Product, Suggestion
from .scoring import DEFAULT_WEIGHTS, Weights, fit_cost, portion_cost, score


@dataclass(frozen=True)
class SolveResult:
    suggestions: list[Suggestion]
    combinations_evaluated: int
    nodes_visited: int
    elapsed_s: float
    truncated: bool = False
    """True if the node limit was hit and the search is no longer exhaustive."""


def solve(
    pantry: Sequence[Product],
    budget: Budget,
    meal: Meal | None = None,
    *,
    weights: Weights = DEFAULT_WEIGHTS,
    max_components: int = 3,
    top_k: int = 5,
    history: Mapping[str, int] | None = None,
    node_limit: int = 5_000_000,
) -> SolveResult:
    started = time.perf_counter()

    # --- prepare candidates -------------------------------------------------
    # A portion that busts the budget on its own can never be part of an
    # acceptable combination, so it is dropped before the search begins. Its
    # nutrition and its portion-only cost are unpacked into plain floats here,
    # once, so the inner loop never walks an attribute chain or re-derives a
    # value that cannot change.
    ceiling = budget.kcal + budget.max_over_kcal
    floor = budget.kcal - budget.max_under_kcal

    Candidate = tuple[Portion, float, float, float, float, float]
    candidates: list[list[Candidate]] = []

    for product in pantry:
        if meal is not None and meal not in product.meals:
            continue
        viable: list[Candidate] = []
        for portion in product.portions():
            nutrition = portion.nutrition
            if nutrition.kcal > ceiling:
                continue
            viable.append(
                (
                    portion,
                    nutrition.kcal,
                    nutrition.carbs_g,
                    nutrition.protein_g,
                    nutrition.fat_g,
                    portion_cost(portion, weights, history),
                )
            )
        if viable:
            candidates.append(viable)

    # Sorting by the largest portion each product can contribute, descending,
    # makes the bound below exact rather than merely valid: the k best
    # remaining products are simply the next k in the list.
    candidates.sort(key=lambda entries: max(e[1] for e in entries), reverse=True)
    max_kcal = [max(e[1] for e in entries) for entries in candidates]

    # suffix_bound[i][k] = most kcal obtainable from candidates[i:] with k slots
    n = len(candidates)
    suffix_bound: list[list[float]] = []
    for i in range(n + 1):
        row = [0.0]
        running = 0.0
        for k in range(1, max_components + 1):
            if i + k - 1 < n:
                running += max_kcal[i + k - 1]
            row.append(running)
        suffix_bound.append(row)

    # --- search -------------------------------------------------------------
    # One entry per distinct set of products, so the results are genuinely
    # different meals rather than the same meal at five nearby gram counts.
    # The chosen list is always built in increasing product order, so the
    # tuple of indices is already canonical and cheap to use as the key.
    best: dict[tuple[int, ...], tuple[float, tuple[Portion, ...], tuple[float, ...]]] = {}
    nodes = 0
    evaluated = 0
    truncated = False

    def descend(
        start: int,
        chosen: list[Portion],
        indices: list[int],
        kcal: float,
        carbs: float,
        protein: float,
        fat: float,
        fixed: float,
    ) -> None:
        nonlocal nodes, evaluated, truncated

        if nodes >= node_limit:
            truncated = True
            return
        nodes += 1

        if chosen and floor <= kcal <= ceiling:
            evaluated += 1
            value = fixed + fit_cost(kcal, carbs, protein, fat, budget, weights)
            key = tuple(indices)
            previous = best.get(key)
            if previous is None or value < previous[0]:
                best[key] = (value, tuple(chosen), (kcal, carbs, protein, fat))

        remaining = max_components - len(chosen)
        if remaining == 0:
            return

        for index in range(start, n):
            # Products are sorted by descending contribution, so once the best
            # possible remainder from here cannot reach the floor, no later
            # product can either.
            if kcal + suffix_bound[index][remaining] < floor:
                break

            for portion, p_kcal, p_carbs, p_protein, p_fat, p_cost in candidates[index]:
                if kcal + p_kcal > ceiling:
                    continue
                chosen.append(portion)
                indices.append(index)
                descend(
                    index + 1,
                    chosen,
                    indices,
                    kcal + p_kcal,
                    carbs + p_carbs,
                    protein + p_protein,
                    fat + p_fat,
                    fixed + p_cost,
                )
                indices.pop()
                chosen.pop()

    descend(0, [], [], 0.0, 0.0, 0.0, 0.0, 0.0)

    # The per-term breakdown is only wanted for what is actually returned, so
    # the full score function runs a handful of times rather than thousands.
    winners = sorted(best.values(), key=lambda entry: entry[0])[:top_k]
    suggestions = [
        Suggestion(
            portions=portions,
            score=value,
            breakdown=score(
                portions, budget, weights, history, Nutrition(*totals)
            )[1],
            totals=Nutrition(*totals),
        )
        for value, portions, totals in winners
    ]

    return SolveResult(
        suggestions=suggestions,
        combinations_evaluated=evaluated,
        nodes_visited=nodes,
        elapsed_s=time.perf_counter() - started,
        truncated=truncated,
    )
