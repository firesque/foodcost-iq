"""Theoretical usage engine: POS sales x exploded recipes."""
from __future__ import annotations

import pandas as pd

from foodcost.utils.units import parse_measure


def theoretical_usage(pos: pd.DataFrame, pos_map: pd.DataFrame,
                      exploded: pd.DataFrame) -> pd.DataFrame:
    """Compute theoretical ingredient usage for the sold mix.

    Parameters
    ----------
    pos : [location, item, qty_sold, revenue]
    pos_map : [item, recipe, confidence]
    exploded : per-portion ingredient rows [recipe, ingredient, qty, measure, book_cost]

    Returns
    -------
    DataFrame [ingredient, ingredient_clean, category, base_unit,
               theo_qty, theo_cost, locations...]
    """
    sold = pos.merge(pos_map[["item", "recipe"]], on="item", how="inner")
    sold = sold[sold["recipe"].notna()]
    merged = sold.merge(exploded, on="recipe", how="inner")
    if merged.empty:
        return pd.DataFrame()

    # resolve to base units for physical aggregation
    base = merged.apply(
        lambda r: parse_measure(float(r["qty"]) * float(r["qty_sold"]),
                                str(r["measure"] or "Each")), axis=1)
    merged["theo_qty_base"] = [q.value for q in base]
    merged["base_unit"] = [q.base_unit for q in base]
    merged["theo_cost"] = merged["book_cost"] * merged["qty_sold"]

    agg = (merged.groupby(
        ["ingredient", "ingredient_clean", "category", "base_unit"],
        as_index=False)
        .agg(theo_qty=("theo_qty_base", "sum"),
             theo_cost=("theo_cost", "sum")))
    return agg


def usage_by_menu_item(pos: pd.DataFrame, pos_map: pd.DataFrame,
                       exploded: pd.DataFrame) -> pd.DataFrame:
    """Ingredient demand broken down by menu item (dollar-weighted)."""
    sold = pos.merge(pos_map[["item", "recipe"]], on="item", how="inner")
    sold = sold[sold["recipe"].notna()]
    agg_sold = sold.groupby("recipe", as_index=False)["qty_sold"].sum()
    merged = agg_sold.merge(exploded, on="recipe", how="inner")
    merged["theo_cost"] = merged["book_cost"] * merged["qty_sold"]
    return merged[["recipe", "ingredient", "ingredient_clean", "category",
                   "qty", "measure", "qty_sold", "theo_cost"]]


def daily_theoretical_cost(daily_sales: pd.DataFrame, pos_map: pd.DataFrame,
                           menu_costs: pd.DataFrame) -> pd.DataFrame:
    """Daily theoretical food cost from the transaction-level export."""
    if daily_sales.empty:
        return pd.DataFrame()
    df = daily_sales.merge(pos_map[["item", "recipe"]], on="item", how="left")
    df = df.merge(menu_costs, on="recipe", how="left")
    df["theo_cost"] = df["recipe_cost"].fillna(0) * df["qty_sold"]
    return (df.groupby("date", as_index=False)
              .agg(revenue=("revenue", "sum"),
                   theo_cost=("theo_cost", "sum"),
                   items_sold=("qty_sold", "sum")))
