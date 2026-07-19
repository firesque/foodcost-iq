"""Central configuration: paths, location aliases, category rules, thresholds."""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent.parent
DATA_STORE = APP_DIR / "data_store"
SAMPLE_DATA = APP_DIR / "sample_data"

# Default locations of the raw source data (relative to the folder that
# contains FoodCostApp). Users can point the app anywhere from the UI.
DEFAULT_INVOICE_ROOT = APP_DIR.parent          # contains Sysco/ and FreshPoint/
DEFAULT_POS_DIR_CANDIDATES = [
    APP_DIR.parent.parent / "Item Details Period 5",
    APP_DIR / "sample_data",
]
DEFAULT_RECIPE_CANDIDATES = [
    APP_DIR.parent / "Recipe.xlsx",
    APP_DIR / "sample_data" / "recipes_sample.csv",
]

# ---------------------------------------------------------------------------
# Location normalization — invoice ship-to names -> POS location names
# ---------------------------------------------------------------------------
LOCATION_ALIASES: dict[str, str] = {
    "SIX MILE CYPRESS": "Ft. Myers - Six Mile Cypress",
    "DANIELS PARKWAY": "Daniels Parkway",
    "CHAMPIONS GATE": "Championsgate",
    "CHAMPIONSGATE": "Championsgate",
    "CAPE CORAL": "Cape Coral",
    "LAKE NONA": "Lake Nona",
    "WINDERMERE": "Windermere",
    "DELRAY": "Delray",
    "PARKLAND": "Parkland",
    "SARASOTA": "South Sarasota",
}

POS_LOCATION_ALIASES: dict[str, str] = {
    "Ft. Meyers - Six Mile Cypress": "Ft. Myers - Six Mile Cypress",
    "South Sarasota": "South Sarasota",
}


def normalize_location(raw: str) -> str:
    """Map a raw invoice/POS location string to a canonical location name."""
    up = (raw or "").upper()
    for key, canon in LOCATION_ALIASES.items():
        if key in up:
            return canon
    for key, canon in POS_LOCATION_ALIASES.items():
        if key.upper() in up:
            return canon
    return raw.strip() or "Unknown"


# ---------------------------------------------------------------------------
# Ingredient categories
# ---------------------------------------------------------------------------
# Recipe ingredient names are prefixed with a category token, e.g.
# "DAIRY Cheese American Sliced", "MEAT PLTRY Eggs", "PREP Home Fries".
RECIPE_CATEGORY_PREFIXES = [
    "MEAT PLTRY", "MEAT PORK", "MEAT BEEF", "NA BEV BIB", "NA BEV",
    "WINE SPARK", "WINE RED", "DAIRY", "PROD", "DRY", "FZN",
    "PREP", "BATCH", "YIELD", "MI",
]

# Perishability weighting used by the waste-risk model (0..1, higher = riskier)
CATEGORY_PERISHABILITY: dict[str, float] = {
    "PROD": 1.00,
    "DAIRY": 0.85,
    "MEAT PLTRY": 0.80,
    "MEAT PORK": 0.75,
    "MEAT BEEF": 0.75,
    "PREP": 0.70,
    "FZN": 0.35,
    "NA BEV": 0.30,
    "NA BEV BIB": 0.25,
    "DRY": 0.25,
    "WINE RED": 0.10,
    "WINE SPARK": 0.10,
    "MISC": 0.40,
    "PAPER": 0.05,
    "MEAT": 0.75,
}

# ---------------------------------------------------------------------------
# Analysis thresholds
# ---------------------------------------------------------------------------
FOOD_COST_TARGET_PCT = 30.0        # target food-cost % for menu items
HIGH_FOOD_COST_PCT = 38.0          # flag items above this
PRICE_SPIKE_PCT = 8.0              # flag vendor price moves above this
VARIANCE_ALERT_RATIO = 1.30        # purchased > 130% of theoretical -> alert
SUSPICIOUS_UNIT_PRICE = 500.0      # invoice unit price above this is suspect
MIN_SPEND_FOR_INSIGHT = 100.0      # ignore trivial-dollar findings
