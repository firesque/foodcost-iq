"""Entity resolution: vendor invoice items -> recipe ingredients,
POS menu items -> recipe sheets.

Strategy (in priority order):
1. User override file ``ingredient_map_overrides.csv`` (exact item_no match).
2. Domain keyword rules with Sysco-style abbreviation expansion.
3. Token-set fuzzy matching (rapidfuzz) with a confidence cutoff.

Every mapping carries a ``confidence`` in [0, 100] and a ``method`` so the
data-quality page can surface weak links for human review.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

from foodcost.utils.text import normalize, normalize_pos_name

# ---------------------------------------------------------------------------
# Vendor-description token expansion (Sysco/FreshPoint abbreviations)
# ---------------------------------------------------------------------------
ABBREVIATIONS: dict[str, str] = {
    "BRST": "BREAST", "TNDR": "TENDER", "TNDRS": "TENDER", "FRTR": "FRITTER",
    "CHIX": "CHICKEN", "CHKN": "CHICKEN", "TRDTNL": "TRADITIONAL",
    "WHL": "WHOLE", "CHOC": "CHOCOLATE", "STRAWB": "STRAWBERRY",
    "BLUEB": "BLUEBERRY", "RASPB": "RASPBERRY", "VAN": "VANILLA",
    "AMER": "AMERICAN", "CHED": "CHEDDAR", "CHS": "CHEESE", "CHZ": "CHEESE",
    "SHRD": "SHREDDED", "SLCD": "SLICED", "SLC": "SLICED", "CRMBL": "CRUMBLED",
    "PORTN": "PORTION", "SSND": "SEASONED", "GRLL": "GRILLED",
    "APPLWD": "APPLEWOOD", "SMKD": "SMOKED", "HCKRY": "HICKORY",
    "SAUS": "SAUSAGE", "LNK": "LINK", "PTY": "PATTY", "TRKY": "TURKEY",
    "BCN": "BACON", "HSH": "HASH", "BRWN": "BROWN", "PNCK": "PANCAKE",
    "BTTR": "BATTER", "MRGRN": "MARGARINE", "SFLWR": "SAFFLOWER",
    "GRN": "GREEN", "PEPP": "PEPPER", "ONI": "ONION", "TOM": "TOMATO",
    "MUSH": "MUSHROOM", "SPIN": "SPINACH", "AVOC": "AVOCADO",
    "JAL": "JALAPENO", "CUKE": "CUCUMBER", "LTTC": "LETTUCE",
    "ORNG": "ORANGE", "GRPFRT": "GRAPEFRUIT", "WTRMLN": "WATERMELON",
    "CANTLP": "CANTALOUPE", "HNYDW": "HONEYDEW", "PNAPPL": "PINEAPPLE",
    "BAN": "BANANA", "BERRY": "BERRY",
}

# High-precision keyword rules: if the vendor description's TOKEN SET
# contains ALL the keywords, map to that recipe ingredient (clean name,
# i.e. category prefix stripped). Order matters: first hit wins.
# Targets are aligned with the Keke's recipe workbook's ingredient names;
# _closest_canonical() resolves them tolerantly for other recipe books.
KEYWORD_RULES: list[tuple[list[str], str]] = [
    # eggs & dairy
    (["EGG", "SHELL"], "Eggs"),
    (["EGG", "LIQUID"], "Eggs Liquid"),
    (["EGG", "WHITE"], "Eggs Liquid"),
    (["BUTTER", "SALTED"], "Butter Salted"),
    (["BUTTER", "ALTERNATE"], "Butter Alternative Liquid"),
    (["BUTTER", "ALTERNATIVE"], "Butter Alternative Liquid"),
    (["MARGARINE", "LIQUID"], "Butter Alternative Liquid"),
    (["CHEESE", "AMERICAN"], "Cheese American Sliced"),
    (["CHEESE", "CHEDDAR", "SHREDDED"], "Cheese Cheddar Shredded"),
    (["CHEESE", "CHEDDAR"], "Cheese Cheddar Sliced"),
    (["CHEESE", "PROVOLONE"], "Cheese Provolone Sliced"),
    (["CHEESE", "FETA"], "Cheese Feta Crumbles"),
    (["CHEESE", "JACK"], "Cheese Pepper Jack Sliced"),
    (["CHEESE", "PARMESAN"], "Cheese Parmesan Fresh"),
    (["CHEESE", "CREAM"], "Cream Cheese SS"),
    (["MILK"], "Milk Whole"),
    (["YOGURT"], "Yogurt Vanilla Low Fat"),
    # meats
    (["BACON", "TURKEY"], "Turkey Bacon"),
    (["SAUSAGE", "TURKEY"], "Turkey Sausage Links"),
    (["BACON", "CANADIAN"], "Bacon Canadian"),
    (["BACON", "TOPPING"], "Bacon Topping"),
    (["BACON", "BITS"], "Bacon Topping"),
    (["BACON"], "Bacon Applewood Smoked"),
    (["SAUSAGE"], "Sausage Links"),
    (["HAM", "STEAK"], "Ham Steak 4oz"),
    (["HAM", "DICED"], "Ham Diced"),
    (["HAM"], "Ham Canadian Sliced"),
    (["CHICKEN", "TENDER"], "Chicken Tenders Breaded"),
    (["CHICKEN", "BREAST"], "Chicken Breast Strips"),
    (["CHICKEN", "STRIP"], "Chicken Breast Strips"),
    (["TURKEY", "BREAST"], "Turkey Breast Sliced"),
    (["STEAK", "BEEF"], "Steak Philly 5oz"),
    (["STEAK", "PHILLY"], "Steak Philly 5oz"),
    (["BEEF", "PATTY"], "Patty 4oz"),
    (["TUNA"], "Tuna Albacore Chunk White"),
    # produce
    (["STRAWBERRY"], "Berry Strawberries"),
    (["BLUEBERRY", "IQF"], "Berry Blueberries FZN"),
    (["BLUEBERRY", "CULT"], "Berry Blueberries FZN"),
    (["BLUEBERRY", "PIE"], "Pie Filling Blueberry"),
    (["BLUEBERRY", "FILLING"], "Pie Filling Blueberry"),
    (["BLUEBERRY"], "Berry Blueberries Fresh"),
    (["BANANA"], "Banana"),
    (["GRAPE"], "Grape Red"),
    (["LEMON"], "Lemon"),
    (["ORANGE", "JUICE"], "Juice Orange"),
    (["ORANGE"], "Orange"),
    (["TOMATO"], "Tomato Bulk"),
    (["LETTUCE", "ROMAINE"], "Lettuce Romaine Heart"),
    (["LETTUCE"], "Lettuce Iceberg"),
    (["ONION", "RING"], "Onion Ring Battered"),
    (["ONION"], "Onion Sweet Diced"),
    (["PEPPER", "BELL"], "Pepper Bell Green"),
    (["PEPPER", "ROASTED"], "Pepper Red Roasted"),
    (["JALAPENO"], "Jalapeno Sliced"),
    (["MUSHROOM"], "Mushroom White Sliced"),
    (["SPINACH"], "Spinach Baby"),
    (["POTATO", "FRY"], "Fries Straight 3/8in"),
    (["POTATO", "CHIP"], "Chip Potato Kettle Bulk"),
    (["POTATO", "BUN"], "Bun Potato 4in"),
    (["POTATO", "RED"], "Potato Red"),
    (["POTATO", "SLICED"], "Potato Red"),
    (["POTATO", "HASH"], "Potato Red"),
    # dry goods
    (["GRITS"], "Grits Corn White"),
    (["MIX", "PANCAKE"], "Mix Pancake"),
    (["MIX", "WAFFLE"], "Mix Waffle Belgium"),
    (["FLOUR", "WAFFLE"], "Mix Waffle Belgium"),
    (["BATTER", "MIX"], "Batter Mix"),
    (["BREAD", "TEXAS"], "Bread Texas Toast Yellow"),
    (["BREAD", "WHEAT"], "Bread Wheat Berry"),
    (["BREAD", "SOURDOUGH"], "Bread Sourdough Oval Large"),
    (["BREAD", "RUSTIC"], "Bread Sourdough Oval Large"),
    (["BREAD", "WHITE"], "Bread White"),
    (["MUFFIN", "ENGLISH"], "Bread English Muffin Plain"),
    (["TORTILLA"], "Tortilla Wheat 12in"),
    (["CHOCOLATE", "CHIP"], "Chocolate Chip Milk Chocolate"),
    (["COCOA"], "Cocoa Mix SS"),
    (["PECAN"], "Nuts Pecan Pieces"),
    (["GRANOLA"], "Granola Low-fat No Raisin"),
    (["PEANUT", "BUTTER"], "Peanut Butter Creamy SS"),
    (["HONEY"], "Honey Bulk"),
    (["APPLE", "CINNAMON"], "Entree Apple Cinnamon"),
    (["GLAZE", "STRAWBERRY"], "Glaze Strawberry"),
    (["PRESERVE"], "Preserve Raspberry"),
    (["SAUCE", "RASPBERRY"], "Sauce Raspberry"),
    (["CROUTON"], "Croutons"),
    (["DRESSING", "CAESAR"], "Dressing Caesar"),
    (["DRESSING", "RANCH"], "Dressing Ranch"),
    (["DRESSING", "MUSTARD"], "Dressing Honey Mustard"),
    (["SALSA"], "Salsa Medium"),
    (["SAUCE", "BBQ"], "Sauce BBQ"),
    (["SAUCE", "CARAMEL"], "Sauce Caramel"),
    (["CARAMEL"], "Sauce Caramel"),
    (["HOLLANDAISE"], "Sauce Hollandaise"),
    (["SAUCE", "PESTO"], "Sauce Pesto Basil"),
    (["PETAL"], "Sauce Dip Texas Petal"),
    (["SAUCE", "HOT"], "Sauce Red Hot Bulk"),
    (["CINNAMON", "GROUND"], "Spice Cinnamon Ground"),
    (["PEPPER", "BLACK"], "Spice Pepper Black Ground"),
    (["SALT"], "Spice Salt Iodized"),
    (["VANILLA", "EXTRACT"], "Extract Vanilla Imitation"),
    (["MAYO"], "Mayo Bulk"),
    (["MAYONNAISE"], "Mayo Bulk"),
    (["SYRUP", "BERRY"], "Syrup Berry Wild"),
    # beverages
    (["COFFEE", "DECAF"], "Coffee Bean Decaf"),
    (["COFFEE"], "Coffee Beans"),
    (["TEA"], "Tea Brewed Pack"),
    (["JUICE", "APPLE"], "Juice Apple"),
    (["JUICE", "CRANBERRY"], "Juice Cranberry"),
    (["LEMONADE"], "Lemonade"),
    (["COKE", "DIET"], "Coke Diet"),
    (["COKE", "ZERO"], "Coke Zero"),
    (["COKE"], "Coke"),
    (["SPRITE"], "Sprite"),
    (["PUNCH"], "Fruit Punch"),
    (["WATER"], "Water Purified"),
    (["PEACH", "SYRUP"], "Syrup Peach White"),
    (["PROSECCO"], "La Marca Prosecco 187mL"),
    (["MERLOT"], "Copper Ridge Merlot 1.5L"),
]

FUZZY_CUTOFF = 82.0


def expand_abbreviations(desc: str) -> str:
    """Expand vendor shorthand tokens to full words."""
    tokens = normalize(desc).split()
    return " ".join(ABBREVIATIONS.get(t, t) for t in tokens)


def load_overrides(app_dir: Path) -> pd.DataFrame:
    """Load optional user mapping overrides (item_no -> ingredient)."""
    f = app_dir / "ingredient_map_overrides.csv"
    if f.exists():
        try:
            df = pd.read_csv(f, dtype=str)
            df.columns = [c.strip().lower() for c in df.columns]
            if {"item_no", "ingredient"} <= set(df.columns):
                return df
        except Exception:
            pass
    return pd.DataFrame(columns=["item_no", "ingredient"])


def match_invoice_items(
    invoice_items: pd.DataFrame,
    recipe_ingredients: pd.DataFrame,
    overrides: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Map unique invoice items to recipe ingredient names.

    Parameters
    ----------
    invoice_items : line-item DataFrame with [vendor, item_no, description]
    recipe_ingredients : ingredient DataFrame with [ingredient, ingredient_clean, category]

    Returns
    -------
    DataFrame [vendor, item_no, description, ingredient, ingredient_category,
               confidence, method]
    """
    # Canonical purchasable ingredients = everything that isn't a sub-recipe
    # or a cross-reference to another menu item.
    canon = (recipe_ingredients[~recipe_ingredients["category"]
             .isin(["PREP", "BATCH", "YIELD", "MI"])]
             [["ingredient", "ingredient_clean", "category"]]
             .drop_duplicates("ingredient"))
    canon_names = canon["ingredient_clean"].tolist()
    canon_lookup = canon.set_index("ingredient_clean")

    over = overrides if overrides is not None else pd.DataFrame(
        columns=["item_no", "ingredient"])
    over_map = dict(zip(over.get("item_no", []), over.get("ingredient", [])))

    uniq = (invoice_items[["vendor", "item_no", "description"]]
            .drop_duplicates(["vendor", "item_no"]))
    out_rows = []
    for _, row in uniq.iterrows():
        desc_expanded = expand_abbreviations(row["description"])
        desc_tokens = set(desc_expanded.split())
        ingredient, conf, method = None, 0.0, "unmatched"

        # 1. explicit override
        if str(row["item_no"]) in over_map:
            ingredient, conf, method = over_map[str(row["item_no"])], 100.0, "override"

        # 2. keyword rules (token-set membership, not substring)
        if ingredient is None:
            for keywords, target in KEYWORD_RULES:
                if all(k in desc_tokens for k in keywords):
                    hit = _closest_canonical(target, canon_names)
                    if hit:
                        ingredient, conf, method = hit, 95.0, "keyword"
                    break

        # 3. fuzzy fallback
        if ingredient is None and canon_names:
            scores = [(c, fuzz.token_set_ratio(desc_expanded, normalize(c)))
                      for c in canon_names]
            best, score = max(scores, key=lambda t: t[1])
            if score >= FUZZY_CUTOFF:
                ingredient, conf, method = best, float(score), "fuzzy"

        if ingredient is not None and ingredient in canon_lookup.index:
            full = canon_lookup.loc[ingredient]
            full = full.iloc[0] if isinstance(full, pd.DataFrame) else full
            out_rows.append({**row.to_dict(),
                             "ingredient": full["ingredient"],
                             "ingredient_clean": ingredient,
                             "ingredient_category": full["category"],
                             "confidence": conf, "method": method})
        else:
            out_rows.append({**row.to_dict(), "ingredient": None,
                             "ingredient_clean": None,
                             "ingredient_category": None,
                             "confidence": conf, "method": "unmatched"})
    return pd.DataFrame(out_rows)


def _closest_canonical(target: str, canon_names: list[str]) -> str | None:
    """Resolve a rule target to the closest actual recipe ingredient name."""
    t = normalize(target)
    # exact / substring first
    for c in canon_names:
        if normalize(c) == t:
            return c
    best, best_score = None, 0.0
    for c in canon_names:
        s = fuzz.token_set_ratio(t, normalize(c))
        if s > best_score:
            best, best_score = c, s
    return best if best_score >= 70 else None


# ---------------------------------------------------------------------------
# POS item -> recipe matching
# ---------------------------------------------------------------------------
# Explicit POS ticket-name -> recipe-sheet aliases for names fuzzy matching
# cannot bridge (verified against the Keke's recipe workbook).
POS_ALIASES: dict[str, str] = {
    "ICED TEA": "MI Brewed Tea - 20oz",
    "EGG&CHZ SAND W/HF": "MI Egg & Cheese Sandwich",
    "CHICKEN FAJITA OMELET": "MI Fajita Omelet",
    "WHITES&TURKBAC": "MI Whites and Turkey Bacon",
    "KID'S SILVER DOLLAR": "MI Silver Dollar Pancakes",
    "PAN-ITALIAN CHX": "MI Italian Chicken Panini",
    "BUFFALO CHIX WRAP": "MI Buffalo Chicken Wrap (Fried)",
    "CAROLINA CHIX WRAP": "MI Carolina Chicken Wrap Fried",
    "COKE": "MI Fountain Coke",
    "DIET COKE": "MI Fountain Diet Coke",
    "WILD BERRY SANGRIA": "MI Wildberry Sangria",
    "CHEESESTEAK OMELET": "MI Cheese Steak Omelet",
}


def match_pos_items(pos_items: list[str], recipe_names: list[str],
                    cutoff: float = 80.0) -> pd.DataFrame:
    """Map POS menu-item names to recipe sheet names.

    Recipe sheets are named like ``MI Cheese Omelet``; POS items like
    ``CHEESE OMELET`` or ``(1) Apple Cinnamon French Toast``.
    """
    cleaned = {r: normalize_pos_name(r) for r in recipe_names}
    name_set = set(recipe_names)
    rows = []
    for item in pos_items:
        alias = POS_ALIASES.get(str(item).strip().upper())
        if alias and alias in name_set:
            rows.append({"item": item, "recipe": alias, "confidence": 100.0})
            continue
        q = normalize_pos_name(item)
        best, best_score = None, 0.0
        for recipe, rclean in cleaned.items():
            s = fuzz.token_sort_ratio(q, rclean)
            # bonus for exact containment
            if q and (q == rclean):
                s = 100.0
            if s > best_score:
                best, best_score = recipe, s
        rows.append({
            "item": item,
            "recipe": best if best_score >= cutoff else None,
            "confidence": best_score,
        })
    return pd.DataFrame(rows)
