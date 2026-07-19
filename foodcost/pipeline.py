"""End-to-end pipeline: raw files -> analytics bundle.

``build_bundle`` runs everything (PDF parsing is the slow part) and
``save_bundle``/``load_bundle`` cache the result as parquet so the app
opens instantly after the first build.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import pandas as pd

from foodcost.config import DATA_STORE
from foodcost.costing.recipe_costing import cost_menu_items, explode_recipes
from foodcost.costing.usage import daily_theoretical_cost, theoretical_usage
from foodcost.costing.variance import ingredient_variance
from foodcost.costing.vendors import price_changes
from foodcost.data_ingestion.freshpoint_pdf import parse_freshpoint_folder
from foodcost.data_ingestion.pos import (
    parse_generic_pos, parse_item_sales_detail, parse_sales_mix_folder)
from foodcost.data_ingestion.recipes import parse_recipe_csv, parse_recipe_workbook
from foodcost.data_ingestion.sysco_pdf import parse_sysco_folder
from foodcost.processing.data_quality import run_checks
from foodcost.processing.matching import (
    load_overrides, match_invoice_items, match_pos_items)


@dataclass
class DataBundle:
    """Everything the UI needs, as flat DataFrames."""

    recipes: pd.DataFrame
    ingredients: pd.DataFrame
    exploded: pd.DataFrame
    menu_costs: pd.DataFrame
    purchases: pd.DataFrame
    invoice_map: pd.DataFrame
    pos: pd.DataFrame
    pos_map: pd.DataFrame
    profit: pd.DataFrame
    theo: pd.DataFrame
    variance: pd.DataFrame
    price_changes: pd.DataFrame
    daily: pd.DataFrame
    quality: pd.DataFrame


def build_bundle(recipe_path: str | Path | None,
                 sysco_dir: str | Path | None,
                 freshpoint_dir: str | Path | None,
                 pos_dir: str | Path | None,
                 generic_files: dict[str, str | Path] | None = None,
                 app_dir: Path | None = None,
                 progress=None) -> DataBundle:
    """Run the full pipeline.

    ``generic_files`` may provide CSV/Excel fallbacks with keys
    ``recipes``, ``invoices``, ``pos``.
    ``progress`` is an optional callable(str) used for status updates.
    """
    tick = progress or (lambda msg: None)
    generic = generic_files or {}

    # ------------------------------------------------------------- recipes
    tick("Parsing recipes…")
    recipes, ingredients = pd.DataFrame(), pd.DataFrame()
    if recipe_path and Path(recipe_path).exists():
        p = Path(recipe_path)
        if p.suffix.lower() == ".xlsx" and _is_workbook(p):
            recipes, ingredients = parse_recipe_workbook(p)
        else:
            recipes, ingredients = parse_recipe_csv(p)
    elif "recipes" in generic:
        recipes, ingredients = parse_recipe_csv(generic["recipes"])
    if recipes.empty:
        raise ValueError("No recipe data found — upload a recipe file first.")

    # ------------------------------------------------------------ invoices
    frames = []
    if sysco_dir and Path(sysco_dir).exists():
        tick("Parsing Sysco invoices (PDF)…")
        frames.append(parse_sysco_folder(sysco_dir))
    if freshpoint_dir and Path(freshpoint_dir).exists():
        tick("Parsing FreshPoint invoices (PDF)…")
        frames.append(parse_freshpoint_folder(freshpoint_dir))
    if "invoices" in generic:
        tick("Reading invoice CSV…")
        inv = pd.read_csv(generic["invoices"], parse_dates=["date"])
        frames.append(inv)
    frames = [f for f in frames if f is not None and not f.empty]
    purchases = (pd.concat(frames, ignore_index=True)
                 if frames else pd.DataFrame(columns=[
                     "vendor", "invoice_no", "date", "location", "item_no",
                     "description", "category", "qty", "uom", "pack_size",
                     "unit_price", "extended_price"]))
    purchases["date"] = pd.to_datetime(purchases["date"], errors="coerce")

    # ----------------------------------------------------------------- POS
    tick("Parsing POS sales…")
    pos, daily_raw = pd.DataFrame(), pd.DataFrame()
    if pos_dir and Path(pos_dir).exists():
        pos = parse_sales_mix_folder(pos_dir)
        detail = list(Path(pos_dir).glob("*Sales Detail*.xlsx"))
        if detail:
            tick("Parsing transaction-level sales (this can take a minute)…")
            daily_raw = parse_item_sales_detail(detail[0])
    if pos.empty and "pos" in generic:
        pos = parse_generic_pos(generic["pos"])
        pos["period_start"] = pos.get("date", pd.NaT)
        pos["period_end"] = pos.get("date", pd.NaT)
    if pos.empty:
        raise ValueError("No POS sales data found — upload a sales export.")

    # ------------------------------------------------------------ matching
    tick("Matching vendor items to ingredients…")
    overrides = load_overrides(app_dir or Path("."))
    invoice_map = (match_invoice_items(purchases, ingredients, overrides)
                   if not purchases.empty else pd.DataFrame(
                       columns=["vendor", "item_no", "description", "ingredient",
                                "ingredient_clean", "ingredient_category",
                                "confidence", "method"]))
    tick("Matching POS items to recipes…")
    menu_names = recipes.loc[recipes["recipe_type"] == "menu_item", "recipe"].tolist()
    pos_map = match_pos_items(sorted(pos["item"].unique()), menu_names)

    # ------------------------------------------------------------- costing
    tick("Exploding recipes and costing menu…")
    exploded = explode_recipes(recipes, ingredients)
    menu_costs = cost_menu_items(recipes, exploded)

    profit = _profitability(pos, pos_map, menu_costs)

    tick("Computing theoretical usage…")
    theo = theoretical_usage(pos, pos_map, exploded)

    tick("Computing waste variance…")
    period = _pos_period(pos)
    variance = ingredient_variance(purchases, invoice_map, theo, period)

    tick("Analyzing vendor price moves…")
    changes = price_changes(purchases)

    daily = daily_theoretical_cost(daily_raw, pos_map, menu_costs)

    tick("Running data-quality checks…")
    quality = run_checks(recipes, ingredients, purchases, invoice_map, pos, pos_map)

    return DataBundle(recipes=recipes, ingredients=ingredients,
                      exploded=exploded, menu_costs=menu_costs,
                      purchases=purchases, invoice_map=invoice_map,
                      pos=pos, pos_map=pos_map, profit=profit, theo=theo,
                      variance=variance, price_changes=changes,
                      daily=daily, quality=quality)


def _is_workbook(path: Path) -> bool:
    """Heuristic: multi-sheet workbook vs flat table."""
    try:
        import openpyxl

        wb = openpyxl.load_workbook(str(path), read_only=True)
        n = len(wb.sheetnames)
        wb.close()
        return n > 3
    except Exception:
        return False


def _profitability(pos: pd.DataFrame, pos_map: pd.DataFrame,
                   menu_costs: pd.DataFrame) -> pd.DataFrame:
    """Menu-item profitability table across all locations."""
    df = pos.merge(pos_map[["item", "recipe"]], on="item", how="left")
    agg = (df.groupby("recipe", dropna=True, as_index=False)
             .agg(qty_sold=("qty_sold", "sum"), revenue=("revenue", "sum")))
    agg = agg.merge(menu_costs, on="recipe", how="left")
    agg["recipe_cost"] = agg["recipe_cost"].fillna(0.0)
    agg["food_cost"] = agg["recipe_cost"] * agg["qty_sold"]
    agg["gross_profit"] = agg["revenue"] - agg["food_cost"]
    agg["food_cost_pct"] = (agg["food_cost"] / agg["revenue"] * 100).where(
        agg["revenue"] > 0)
    agg["avg_price"] = (agg["revenue"] / agg["qty_sold"]).where(agg["qty_sold"] > 0)
    return agg


def _pos_period(pos: pd.DataFrame) -> tuple | None:
    try:
        start = pd.to_datetime(pos["period_start"]).min()
        end = pd.to_datetime(pos["period_end"]).max()
        if pd.notna(start) and pd.notna(end):
            return (start, end)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
def save_bundle(bundle: DataBundle, store: Path = DATA_STORE) -> None:
    store.mkdir(parents=True, exist_ok=True)
    for f in fields(bundle):
        df = getattr(bundle, f.name)
        try:
            df.to_parquet(store / f"{f.name}.parquet", index=False)
        except Exception:
            df.to_pickle(store / f"{f.name}.pkl")


def load_bundle(store: Path = DATA_STORE) -> DataBundle | None:
    try:
        kwargs = {}
        for f in fields(DataBundle):
            pq = store / f"{f.name}.parquet"
            pk = store / f"{f.name}.pkl"
            if pq.exists():
                kwargs[f.name] = pd.read_parquet(pq)
            elif pk.exists():
                kwargs[f.name] = pd.read_pickle(pk)
            else:
                return None
        return DataBundle(**kwargs)
    except Exception:
        return None
