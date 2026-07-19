"""Recipe costing: explode sub-recipes and roll costs up to menu items.

Two cost bases are computed:
* ``book_cost``   — the cost embedded in the recipe workbook (source system)
* ``invoice_cost``— derived from the latest matched vendor prices when a
                    reliable per-unit conversion exists (falls back to book)
"""
from __future__ import annotations

import pandas as pd

from foodcost.utils.units import parse_measure

MAX_DEPTH = 6  # guard against recursive prep references


def explode_recipes(recipes: pd.DataFrame, ingredients: pd.DataFrame) -> pd.DataFrame:
    """Explode PREP/BATCH/YIELD references into base ingredients.

    Returns one row per (menu recipe, base ingredient) with the effective
    quantity per one portion of the menu recipe and its book cost.
    """
    sub_types = {"prep", "batch", "yield"}
    recipe_meta = recipes.set_index("recipe")
    sub_recipes = set(recipes.loc[recipes["recipe_type"].isin(sub_types), "recipe"])
    by_recipe: dict[str, pd.DataFrame] = {
        r: g for r, g in ingredients.groupby("recipe")
    }

    def resolve(recipe: str, factor: float, depth: int) -> list[dict]:
        """Return base-ingredient rows for one unit of ``recipe`` x factor."""
        if depth > MAX_DEPTH or recipe not in by_recipe:
            return []
        rows: list[dict] = []
        for _, ing in by_recipe[recipe].iterrows():
            name = ing["ingredient"]
            qty = float(ing["qty"]) if pd.notna(ing["qty"]) else 0.0
            yld = float(ing["yield_pct"]) if pd.notna(ing["yield_pct"]) else 100.0
            eff_qty = qty / (yld / 100.0) if yld else qty
            cost = float(ing["book_cost"]) if pd.notna(ing["book_cost"]) else 0.0

            # A sub-recipe reference (e.g. "PREP Home Fries")?
            sub_name = _find_sub_sheet(name, sub_recipes)
            if sub_name:
                sub_factor = _sub_recipe_fraction(
                    eff_qty, str(ing["measure"] or ""), sub_name, recipe_meta)
                rows.extend(resolve(sub_name, factor * sub_factor, depth + 1))
                # keep the book cost attribution at the prep level too? No —
                # the exploded base ingredients carry their own book costs
                # scaled by sub_factor, which reconciles with the prep total.
            else:
                rows.append({
                    "ingredient": name,
                    "ingredient_clean": ing["ingredient_clean"],
                    "category": ing["category"],
                    "qty": eff_qty * factor,
                    "measure": ing["measure"],
                    "book_cost": cost * factor,
                })
        return rows

    out = []
    menu = recipes[recipes["recipe_type"] == "menu_item"]
    for _, r in menu.iterrows():
        for row in resolve(r["recipe"], 1.0, 0):
            out.append({"recipe": r["recipe"], **row})
    df = pd.DataFrame(out)
    if df.empty:
        return df
    # aggregate duplicated ingredients within a recipe
    return (df.groupby(["recipe", "ingredient", "ingredient_clean",
                        "category", "measure"], as_index=False)
              .agg(qty=("qty", "sum"), book_cost=("book_cost", "sum")))


def _find_sub_sheet(ingredient_name: str, sub_recipes: set[str]) -> str | None:
    """'PREP Home Fries' -> matching sheet name if one exists."""
    if ingredient_name in sub_recipes:
        return ingredient_name
    # sometimes referenced without exact case
    for s in sub_recipes:
        if s.upper() == ingredient_name.upper():
            return s
    return None


def _sub_recipe_fraction(qty: float, measure: str, sub_name: str,
                         recipe_meta: pd.DataFrame) -> float:
    """Fraction of one batch of ``sub_name`` used by ``qty measure``.

    Example: recipe uses 8 OZ-wt of PREP Home Fries whose yield is 10 Lb
    -> fraction = 8 / 160 = 0.05 of a batch.
    """
    try:
        meta = recipe_meta.loc[sub_name]
    except KeyError:
        return 0.0
    y_qty = float(meta["yield_qty"]) if pd.notna(meta["yield_qty"]) else 1.0
    y_unit = str(meta["yield_unit"] or "Each")

    used = parse_measure(qty, measure)
    total = parse_measure(y_qty, y_unit)
    if used.dimension == total.dimension and used.dimension != "unknown" and total.value:
        return used.value / total.value
    # dimensions disagree (e.g. portions vs weight) -> use portions if known
    n_port = meta.get("n_portions")
    if pd.notna(n_port) and n_port:
        return qty / float(n_port)
    return qty / y_qty if y_qty else 0.0


def cost_menu_items(recipes: pd.DataFrame, exploded: pd.DataFrame) -> pd.DataFrame:
    """Roll exploded ingredient costs up to per-portion menu-item cost."""
    if exploded.empty:
        return pd.DataFrame()
    cost = (exploded.groupby("recipe", as_index=False)
                    .agg(recipe_cost=("book_cost", "sum")))
    meta = recipes[recipes["recipe_type"] == "menu_item"][
        ["recipe", "book_cost", "n_portions"]]
    out = cost.merge(meta, on="recipe", how="left")
    # Prefer the workbook's own total when explosion diverges wildly
    # (indicates unit-conversion trouble in a prep chain).
    out["recipe_cost"] = out.apply(
        lambda r: r["book_cost"]
        if pd.notna(r["book_cost"]) and r["book_cost"] > 0
        and (r["recipe_cost"] <= 0 or
             not (0.5 <= r["recipe_cost"] / r["book_cost"] <= 2.0))
        else r["recipe_cost"],
        axis=1,
    )
    return out[["recipe", "recipe_cost"]]
