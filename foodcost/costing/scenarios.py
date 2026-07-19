"""What-if scenario modeling.

All scenarios operate on the menu-item profitability table
[recipe, qty_sold, revenue, recipe_cost] and return a before/after
comparison of food-cost %, gross margin and profit dollars.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Scenario:
    """Parameters of a what-if scenario (all in percent, +/-)."""

    ingredient_price_pct: float = 0.0      # applied to selected ingredients
    ingredients: list[str] = field(default_factory=list)
    menu_price_pct: float = 0.0            # applied to selected menu items
    portion_pct: float = 0.0               # portion size change on selected items
    volume_pct: float = 0.0                # sales volume change (all items)
    menu_items: list[str] = field(default_factory=list)


def run_scenario(profit: pd.DataFrame, exploded: pd.DataFrame,
                 sc: Scenario) -> dict:
    """Apply a scenario and return before/after aggregates + per-item detail.

    profit : [recipe, qty_sold, revenue, recipe_cost]
    exploded : per-portion ingredient rows [recipe, ingredient_clean, book_cost]
    """
    df = profit.copy()
    df["unit_price"] = df["revenue"] / df["qty_sold"].replace(0, pd.NA)
    df["unit_price"] = df["unit_price"].fillna(0.0)

    # --- ingredient price shock ------------------------------------------
    new_cost = df.set_index("recipe")["recipe_cost"].copy()
    if sc.ingredient_price_pct and sc.ingredients:
        affected = exploded[exploded["ingredient_clean"].isin(sc.ingredients)]
        delta = (affected.groupby("recipe")["book_cost"].sum()
                 * sc.ingredient_price_pct / 100.0)
        new_cost = new_cost.add(delta, fill_value=0.0)

    df["new_recipe_cost"] = df["recipe"].map(new_cost)

    # --- portion change on selected items --------------------------------
    targets = set(sc.menu_items) if sc.menu_items else set(df["recipe"])
    if sc.portion_pct:
        mask = df["recipe"].isin(targets)
        df.loc[mask, "new_recipe_cost"] *= (1 + sc.portion_pct / 100.0)

    # --- menu price change ------------------------------------------------
    df["new_unit_price"] = df["unit_price"]
    if sc.menu_price_pct:
        mask = df["recipe"].isin(targets)
        df.loc[mask, "new_unit_price"] *= (1 + sc.menu_price_pct / 100.0)

    # --- volume change ----------------------------------------------------
    vol = 1 + sc.volume_pct / 100.0
    df["new_qty"] = df["qty_sold"] * vol

    # --- aggregates -------------------------------------------------------
    def _agg(rev_col: str, cost_col: str, qty_col: str) -> dict:
        revenue = float((df[rev_col] * df[qty_col]).sum())
        cost = float((df[cost_col] * df[qty_col]).sum())
        return {
            "revenue": revenue,
            "food_cost": cost,
            "gross_profit": revenue - cost,
            "food_cost_pct": (cost / revenue * 100) if revenue else 0.0,
        }

    before = _agg("unit_price", "recipe_cost", "qty_sold")
    after = _agg("new_unit_price", "new_recipe_cost", "new_qty")

    detail = df[["recipe", "qty_sold", "unit_price", "new_unit_price",
                 "recipe_cost", "new_recipe_cost"]].copy()
    detail["profit_delta"] = (
        (detail["new_unit_price"] - detail["new_recipe_cost"]) * df["new_qty"]
        - (detail["unit_price"] - detail["recipe_cost"]) * df["qty_sold"]
    )
    detail = detail.sort_values("profit_delta")

    return {"before": before, "after": after, "detail": detail,
            "profit_delta": after["gross_profit"] - before["gross_profit"]}
