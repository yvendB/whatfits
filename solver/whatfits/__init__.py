"""WhatFits solver -- phase 0 prototype.

Given what is left of today's calorie budget and what is actually in the
cupboard, propose meals in amounts a person can serve: whole tins, whole
pieces, sensible gram steps.
"""

from . import barcode, openfoodfacts
from .model import (
    Budget,
    MassGrid,
    Meal,
    Nutrition,
    PackGrid,
    Portion,
    Product,
    Suggestion,
    plausibility_problems,
)
from .pantry import PantryError, check_pantry, load_pantry
from .scoring import DEFAULT_WEIGHTS, Weights, score
from .search import SolveResult, solve

__all__ = [
    "Budget",
    "barcode",
    "openfoodfacts",
    "DEFAULT_WEIGHTS",
    "MassGrid",
    "Meal",
    "Nutrition",
    "PackGrid",
    "PantryError",
    "Portion",
    "Product",
    "SolveResult",
    "Suggestion",
    "Weights",
    "check_pantry",
    "load_pantry",
    "plausibility_problems",
    "score",
    "solve",
]
