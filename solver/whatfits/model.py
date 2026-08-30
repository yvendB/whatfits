"""Core data model for the WhatFits solver.

The one idea that separates this from a plain calculator is the *portion
grid*: every food declares the amounts a person can realistically serve, and
the search only ever considers those. A suggestion is therefore practical by
construction, instead of being rounded into shape after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterator


class Meal(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


# --------------------------------------------------------------------------
# Nutrition
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Nutrition:
    """Nutrition values. Either per 100 g, or absolute for a portion."""

    kcal: float = 0.0
    carbs_g: float = 0.0
    protein_g: float = 0.0
    fat_g: float = 0.0

    def scaled(self, grams: float) -> Nutrition:
        """This nutrition (read as per-100 g) applied to `grams`."""
        factor = grams / 100.0
        return Nutrition(
            kcal=self.kcal * factor,
            carbs_g=self.carbs_g * factor,
            protein_g=self.protein_g * factor,
            fat_g=self.fat_g * factor,
        )

    def __add__(self, other: Nutrition) -> Nutrition:
        return Nutrition(
            kcal=self.kcal + other.kcal,
            carbs_g=self.carbs_g + other.carbs_g,
            protein_g=self.protein_g + other.protein_g,
            fat_g=self.fat_g + other.fat_g,
        )

    @property
    def atwater_kcal(self) -> float:
        """Energy implied by the macros: 4 kcal/g for carbs and protein, 9 for fat.

        Deliberately ignores fibre and alcohol. Both push the real value away
        from this estimate, which is why the plausibility check below tolerates
        a fairly wide band rather than demanding an exact match.
        """
        return 4.0 * self.carbs_g + 4.0 * self.protein_g + 9.0 * self.fat_g


# Tolerated gap between stated and calculated energy before we complain.
PLAUSIBILITY_TOLERANCE = 0.20

# Pure fat is ~900 kcal/100 g; nothing edible legitimately exceeds that.
MAX_KCAL_PER_100G = 900.0


def plausibility_problems(per_100g: Nutrition) -> list[str]:
    """Sanity-check a product entry, as described in the concept doc.

    Catches the two mistakes that actually happen when people type nutrition
    values by hand: a decimal place in the wrong position, and macros that do
    not add up to the stated energy.
    """
    problems: list[str] = []
    values = {
        "kcal": per_100g.kcal,
        "carbohydrates": per_100g.carbs_g,
        "protein": per_100g.protein_g,
        "fat": per_100g.fat_g,
    }

    for label, value in values.items():
        if value < 0:
            problems.append(f"{label} is negative ({value:g})")

    macro_sum = per_100g.carbs_g + per_100g.protein_g + per_100g.fat_g
    if macro_sum > 100.0:
        problems.append(
            f"macros add up to {macro_sum:.1f} g per 100 g, which is more than the food weighs"
        )

    if per_100g.kcal > MAX_KCAL_PER_100G:
        problems.append(
            f"{per_100g.kcal:.0f} kcal per 100 g exceeds pure fat ({MAX_KCAL_PER_100G:.0f})"
        )

    calculated = per_100g.atwater_kcal
    if per_100g.kcal > 0 and calculated > 0:
        gap = abs(per_100g.kcal - calculated) / per_100g.kcal
        if gap > PLAUSIBILITY_TOLERANCE:
            problems.append(
                f"stated {per_100g.kcal:.0f} kcal but the macros imply about "
                f"{calculated:.0f} kcal ({gap:.0%} apart)"
            )

    return problems


# --------------------------------------------------------------------------
# Portion grids
# --------------------------------------------------------------------------

_FRACTION_GLYPHS = {0.25: "1/4", 0.5: "1/2", 0.75: "3/4"}


def _format_packs(count: float, unit: str) -> str:
    """'1.5' and 'tin' -> '1 1/2 tins'. Keeps output readable in a kitchen."""
    whole = int(count)
    remainder = round(count - whole, 3)
    glyph = _FRACTION_GLYPHS.get(remainder, "")

    if whole == 0 and glyph:
        text = glyph
    elif glyph:
        text = f"{whole} {glyph}"
    elif count == int(count):
        text = str(whole)
    else:
        text = f"{count:g}"

    plural = "" if count <= 1 else "s"
    return f"{text} {unit}{plural}"


@dataclass(frozen=True)
class PackGrid:
    """Amounts are multiples of a fraction of a whole pack.

    `fraction=1.0` means whole packs only -- the rule that stops the solver
    from suggesting 37 g of sweetcorn and leaving the rest of the tin to spoil.
    """

    pack_g: float
    unit: str = "pack"
    fraction: float = 1.0
    max_packs: float = 2.0

    def portions(self) -> Iterator[tuple[float, str]]:
        count = self.fraction
        while count <= self.max_packs + 1e-9:
            grams = count * self.pack_g
            yield grams, f"{_format_packs(count, self.unit)} ({grams:.0f} g)"
            count = round(count + self.fraction, 6)

    def leftover_from_new_packs(self, grams: float) -> float:
        """Grams left open after breaking into fresh packs to serve `grams`."""
        if grams <= 0:
            return 0.0
        remainder = grams % self.pack_g
        return 0.0 if abs(remainder) < 1e-9 else self.pack_g - remainder


@dataclass(frozen=True)
class MassGrid:
    """Amounts in gram steps, for food where a part-portion is normal anyway."""

    step_g: float
    min_g: float
    max_g: float

    def portions(self) -> Iterator[tuple[float, str]]:
        grams = self.min_g
        while grams <= self.max_g + 1e-9:
            yield grams, f"{grams:.0f} g"
            grams = round(grams + self.step_g, 6)

    def leftover_from_new_packs(self, grams: float) -> float:
        return 0.0


Grid = PackGrid | MassGrid


# --------------------------------------------------------------------------
# Packaging consequences
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Packaging:
    """What serving a portion does to the packaging in the kitchen.

    Modelled explicitly because it is the whole point of the product. A
    suggestion is not better for being arithmetically closer if it leaves two
    tins standing open in the fridge.
    """

    finishes_open_pack: bool
    """True if an already-open pack gets used up entirely."""

    opens_new_pack: bool

    leftover_g: float
    """How much sits open in the fridge afterwards."""


def _packaging_for(grid: Grid, grams: float, open_g: float) -> Packaging:
    if open_g > 0 and grams <= open_g + 1e-9:
        # Served entirely from what is already open; nothing new is broken into.
        leftover = open_g - grams
        return Packaging(
            finishes_open_pack=leftover < 1e-9,
            opens_new_pack=False,
            leftover_g=max(0.0, leftover),
        )

    # Anything already open gets used up first, the rest comes from new packs.
    from_new = grams - open_g
    leftover = grid.leftover_from_new_packs(from_new)
    return Packaging(
        finishes_open_pack=open_g > 0,
        opens_new_pack=from_new > 0 and isinstance(grid, PackGrid),
        leftover_g=leftover,
    )


# --------------------------------------------------------------------------
# Products and portions
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    per_100g: Nutrition
    grid: Grid
    meals: frozenset[Meal]
    category: str = "other"
    open_g: float = 0.0
    """Amount already open in the fridge. Using it up earns a bonus."""

    barcode: str | None = None
    """GTIN from the packet. The join key to a product database, and the
    reason scanning can replace typing. See `barcode.py`."""

    def portions(self) -> list[Portion]:
        """Every amount of this product the solver is allowed to propose.

        Nutrition and packaging are resolved here, once, rather than on every
        access: the search touches the same portion objects hundreds of
        thousands of times.
        """
        return [
            Portion(
                product=self,
                grams=grams,
                label=label,
                nutrition=self.per_100g.scaled(grams),
                packaging=_packaging_for(self.grid, grams, self.open_g),
            )
            for grams, label in self.grid.portions()
        ]

    def with_open(self, grams: float) -> Product:
        return replace(self, open_g=grams)


@dataclass(frozen=True)
class Portion:
    product: Product
    grams: float
    label: str
    nutrition: Nutrition
    packaging: Packaging


# --------------------------------------------------------------------------
# Budget and results
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Budget:
    """What is left for the day, and how precisely it must be hit."""

    kcal: float
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    max_over_kcal: float = 50.0
    max_under_kcal: float = 150.0

    def accepts(self, kcal: float) -> bool:
        return self.kcal - self.max_under_kcal <= kcal <= self.kcal + self.max_over_kcal


@dataclass(frozen=True)
class Suggestion:
    portions: tuple[Portion, ...]
    score: float
    breakdown: dict[str, float]
    totals: Nutrition

    @property
    def product_ids(self) -> frozenset[str]:
        return frozenset(p.product.id for p in self.portions)
