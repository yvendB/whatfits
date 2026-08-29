from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whatfits import MassGrid, Meal, Nutrition, PackGrid, Product  # noqa: E402

PANTRY_FILE = Path(__file__).resolve().parent.parent / "data" / "pantry.json"

ALL_MEALS = frozenset(Meal)


def make_product(
    product_id: str = "thing",
    *,
    kcal: float = 100.0,
    carbs: float = 10.0,
    protein: float = 10.0,
    fat: float = 2.0,
    grid=None,
    open_g: float = 0.0,
    meals=ALL_MEALS,
) -> Product:
    return Product(
        id=product_id,
        name=product_id.replace("-", " ").title(),
        per_100g=Nutrition(kcal=kcal, carbs_g=carbs, protein_g=protein, fat_g=fat),
        grid=grid or MassGrid(step_g=10, min_g=10, max_g=100),
        meals=meals,
        open_g=open_g,
    )


@pytest.fixture
def tin() -> Product:
    """A tinned product: 100 g per tin, whole or half tins only."""
    return make_product(
        "tin-thing",
        kcal=100.0,
        grid=PackGrid(pack_g=100, unit="tin", fraction=0.5, max_packs=2),
    )


@pytest.fixture
def pantry_file() -> Path:
    return PANTRY_FILE
