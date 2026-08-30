"""Reading a pantry from JSON, and checking it before the solver trusts it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .barcode import normalise as normalise_barcode
from .barcode import problems as barcode_problems
from .model import (
    Grid,
    MassGrid,
    Meal,
    Nutrition,
    PackGrid,
    Product,
    plausibility_problems,
)


class PantryError(ValueError):
    """The pantry file is malformed. Distinct from a merely implausible entry."""


def _build_grid(raw: dict[str, Any], product_id: str) -> Grid:
    kind = raw.get("kind")
    try:
        if kind == "pack":
            return PackGrid(
                pack_g=float(raw["pack_g"]),
                unit=str(raw.get("unit", "pack")),
                fraction=float(raw.get("fraction", 1.0)),
                max_packs=float(raw.get("max_packs", 2.0)),
            )
        if kind == "mass":
            return MassGrid(
                step_g=float(raw["step_g"]),
                min_g=float(raw["min_g"]),
                max_g=float(raw["max_g"]),
            )
    except KeyError as missing:
        raise PantryError(f"{product_id}: grid is missing {missing}") from missing

    raise PantryError(f"{product_id}: grid kind must be 'pack' or 'mass', got {kind!r}")


def _build_product(raw: dict[str, Any]) -> Product:
    try:
        product_id = str(raw["id"])
        nutrition_raw = raw["per_100g"]
        return Product(
            id=product_id,
            name=str(raw["name"]),
            per_100g=Nutrition(
                kcal=float(nutrition_raw["kcal"]),
                carbs_g=float(nutrition_raw["carbs_g"]),
                protein_g=float(nutrition_raw["protein_g"]),
                fat_g=float(nutrition_raw["fat_g"]),
            ),
            grid=_build_grid(raw["grid"], product_id),
            meals=frozenset(Meal(m) for m in raw["meals"]),
            category=str(raw.get("category", "other")),
            open_g=float(raw.get("open_g", 0.0)),
            barcode=(
                normalise_barcode(raw["barcode"]) if raw.get("barcode") else None
            ),
        )
    except KeyError as missing:
        raise PantryError(f"product entry is missing {missing}") from missing
    except ValueError as bad:
        raise PantryError(f"product entry is invalid: {bad}") from bad


def load_pantry(path: str | Path) -> list[Product]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = data.get("products")
    if not isinstance(entries, list):
        raise PantryError("pantry file must contain a 'products' list")

    products = [_build_product(entry) for entry in entries]

    seen: set[str] = set()
    for product in products:
        if product.id in seen:
            raise PantryError(f"duplicate product id: {product.id}")
        seen.add(product.id)

    return products


def check_pantry(products: Iterable[Product]) -> dict[str, list[str]]:
    """Run the plausibility check over a pantry.

    Returns only the products that have something wrong with them, so an empty
    result means the data is fit to plan meals from.
    """
    problems = {}
    for product in products:
        found = plausibility_problems(product.per_100g)
        if product.barcode:
            found += [f"barcode: {issue}" for issue in barcode_problems(product.barcode)]
        if found:
            problems[product.id] = found
    return problems
