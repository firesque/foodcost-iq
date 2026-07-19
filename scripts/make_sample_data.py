"""Generate realistic sample data so the app runs with zero real files.

Creates in sample_data/:
    recipes_sample.csv    — flat recipe table
    invoices_sample.csv   — flat invoice line items (Sysco + FreshPoint)
    pos_sales_sample.csv  — POS sales export
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)
OUT = Path(__file__).resolve().parent.parent / "sample_data"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- recipes
RECIPES = {
    "MI Cheese Omelet": [("MEAT PLTRY Eggs", 3, "Each", 0.49),
                         ("DAIRY Cheese American Sliced", 3, "Each", 0.33),
                         ("DAIRY Butter Salted", 0.5, "OZ-wt", 0.09),
                         ("PRODUCE Potatoes", 8, "OZ-wt", 0.55)],
    "MI Western Omelet": [("MEAT PLTRY Eggs", 3, "Each", 0.49),
                          ("MEAT PLTRY Ham", 2, "OZ-wt", 0.62),
                          ("PRODUCE Green Peppers", 1, "OZ-wt", 0.11),
                          ("PRODUCE Onion", 1, "OZ-wt", 0.06),
                          ("DAIRY Cheese Cheddar Shredded", 1.5, "OZ-wt", 0.28),
                          ("PRODUCE Potatoes", 8, "OZ-wt", 0.55)],
    "MI Bacon & Eggs": [("MEAT PLTRY Eggs", 2, "Each", 0.33),
                        ("MEAT PLTRY Bacon", 4, "Each", 0.88),
                        ("PRODUCE Potatoes", 8, "OZ-wt", 0.55),
                        ("BREAD Texas Toast", 2, "Each", 0.24)],
    "MI Pancake Stack": [("GROCERY Pancake Mix", 6, "OZ-wt", 0.42),
                         ("DAIRY Butter Salted", 1, "OZ-wt", 0.18),
                         ("GROCERY Maple Syrup", 2, "OZ-fl", 0.35)],
    "MI French Toast": [("BREAD Texas Toast", 3, "Each", 0.36),
                        ("MEAT PLTRY Eggs", 1, "Each", 0.16),
                        ("DAIRY Milk", 2, "OZ-fl", 0.06),
                        ("GROCERY Maple Syrup", 2, "OZ-fl", 0.35)],
    "MI Fresh Fruit Bowl": [("PRODUCE Strawberries", 3, "OZ-wt", 0.66),
                            ("PRODUCE Banana", 1, "Each", 0.22),
                            ("PRODUCE Grapes", 2, "OZ-wt", 0.38),
                            ("PRODUCE Cantaloupe", 3, "OZ-wt", 0.30)],
    "MI Chicken & Waffles": [("MEAT PLTRY Chicken Tenders", 3, "Each", 1.41),
                             ("GROCERY Waffle Mix", 5, "OZ-wt", 0.44),
                             ("GROCERY Maple Syrup", 2, "OZ-fl", 0.35)],
    "MI Breakfast BLT": [("MEAT PLTRY Bacon", 4, "Each", 0.88),
                         ("PRODUCE Lettuce", 1, "OZ-wt", 0.08),
                         ("PRODUCE Tomatoes", 2, "Each", 0.24),
                         ("BREAD Sourdough Bread", 2, "Each", 0.30),
                         ("GROCERY Mayonnaise", 0.5, "OZ-fl", 0.05)],
    "MI Veggie Skillet": [("PRODUCE Potatoes", 10, "OZ-wt", 0.69),
                          ("PRODUCE Mushrooms", 2, "OZ-wt", 0.31),
                          ("PRODUCE Spinach", 1, "OZ-wt", 0.19),
                          ("PRODUCE Green Peppers", 1, "OZ-wt", 0.11),
                          ("DAIRY Cheese Cheddar Shredded", 2, "OZ-wt", 0.37),
                          ("MEAT PLTRY Eggs", 2, "Each", 0.33)],
    "MI Orange Juice Lg": [("NA BEV Orange Juice", 16, "OZ-fl", 0.72)],
}

rows = []
for recipe, ings in RECIPES.items():
    for name, qty, measure, cost in ings:
        rows.append({"recipe": recipe, "recipe_type": "menu_item",
                     "ingredient": name, "qty": qty, "measure": measure,
                     "book_cost": cost})
pd.DataFrame(rows).to_csv(OUT / "recipes_sample.csv", index=False)

# ---------------------------------------------------------------- invoices
VENDOR_ITEMS = [
    ("Sysco", "4537134", "KEKE'S EGG SHELL XL WHT GR AA", "DAIRY", 29.21, 0.18),
    ("Sysco", "7008537", "BTRBALL BACON TURKEY LAYFLT", "MEAT PLTRY", 45.24, 0.02),
    ("Sysco", "1948559", "HORMEL BACON APPLEWOOD SMKD", "MEAT PLTRY", 52.10, 0.09),
    ("Sysco", "3029461", "WHLFIMP BUTTER SALTED WHIP TUB", "DAIRY", 32.11, 0.04),
    ("Sysco", "6414544", "CHEESE CHEDDAR SHRD FCY", "DAIRY", 58.90, 0.06),
    ("Sysco", "2210351", "CHEESE AMER SLCD 160CT", "DAIRY", 47.35, 0.05),
    ("Sysco", "6946152", "PIERCE CHICKEN TNDR FRTR RAW", "MEAT PLTRY", 29.78, 0.11),
    ("Sysco", "5583321", "SYS PANCAKE & WAFFLE MIX", "GROCERY", 24.60, 0.01),
    ("Sysco", "8812234", "SYRUP MAPLE FLVR JUG", "GROCERY", 31.55, 0.03),
    ("Sysco", "7141200", "HAM PIT SMKD B/I SLCD", "MEAT PLTRY", 61.20, 0.05),
    ("Sysco", "4676280", "WHLFCLS MILK 2% GALLON", "DAIRY", 22.92, 0.02),
    ("Sysco", "9077122", "BREAD TEXAS TOAST THICK", "BREAD", 18.75, 0.02),
    ("Sysco", "9077123", "BREAD SOURDOUGH SLCD", "BREAD", 21.40, 0.02),
    ("Sysco", "3390871", "JUICE ORANGE 100% FRZN CONC", "NA BEV", 38.20, 0.07),
    ("FreshPoint", "480010", "BANANA GREEN TIP", "PRODUCE", 19.20, 0.03),
    ("FreshPoint", "250056", "BERRY STRAWBERRY DRISCOLL", "PRODUCE", 26.70, 0.21),
    ("FreshPoint", "260305", "GRAPE RED SEEDLESS", "PRODUCE", 35.69, 0.05),
    ("FreshPoint", "270112", "MELON CANTALOUPE CT", "PRODUCE", 28.40, 0.06),
    ("FreshPoint", "407810", "TOMATO 5X6 2LAY", "PRODUCE", 68.60, 0.08),
    ("FreshPoint", "403647", "LETTUCE CELLO ICEBERG", "PRODUCE", 33.83, 0.04),
    ("FreshPoint", "405035", "MUSHROOM SLICED", "PRODUCE", 14.25, 0.05),
    ("FreshPoint", "512300", "SPINACH BABY CELLO", "PRODUCE", 21.10, 0.06),
    ("FreshPoint", "514021", "ONION SWEET DICED", "PRODUCE", 34.00, 0.02),
    ("FreshPoint", "407030", "PEPPER GREEN BELL BUSHEL", "PRODUCE", 27.28, 0.05),
    ("FreshPoint", "561200", "POTATO IDAHO #2 50LB", "PRODUCE", 24.90, 0.04),
]

start = datetime(2026, 4, 30)
inv_rows, inv_no = [], 90000
for week in range(4):
    for vendor in ("Sysco", "FreshPoint"):
        for loc in ("Lake Nona", "Windermere", "Cape Coral"):
            inv_no += 1
            date = start + timedelta(days=week * 7 + random.randint(0, 5))
            for v, item, desc, cat, base, drift in VENDOR_ITEMS:
                if v != vendor or random.random() < 0.25:
                    continue
                price = round(base * (1 + drift * week) *
                              random.uniform(0.99, 1.01), 2)
                qty = random.randint(1, 6)
                # produce over-ordering baked in for the waste story
                if cat == "PRODUCE" and random.random() < 0.5:
                    qty += random.randint(1, 3)
                inv_rows.append({
                    "vendor": vendor, "invoice_no": str(inv_no),
                    "date": date.date(), "location": loc, "item_no": item,
                    "description": desc, "category": cat, "qty": qty,
                    "uom": "CS", "pack_size": "CS",
                    "unit_price": price,
                    "extended_price": round(price * qty, 2)})
pd.DataFrame(inv_rows).to_csv(OUT / "invoices_sample.csv", index=False)

# ---------------------------------------------------------------- POS
PRICES = {"MI Cheese Omelet": 11.49, "MI Western Omelet": 13.79,
          "MI Bacon & Eggs": 12.29, "MI Pancake Stack": 10.99,
          "MI French Toast": 11.49, "MI Fresh Fruit Bowl": 8.99,
          "MI Chicken & Waffles": 15.49, "MI Breakfast BLT": 12.99,
          "MI Veggie Skillet": 13.29, "MI Orange Juice Lg": 4.99}
pos_rows = []
for loc in ("Lake Nona", "Windermere", "Cape Coral"):
    for recipe, price in PRICES.items():
        qty = random.randint(120, 700)
        pos_rows.append({
            "item": recipe.replace("MI ", "").upper(),
            "qty_sold": qty,
            "revenue": round(qty * price * random.uniform(0.97, 1.0), 2),
            "location": loc})
pd.DataFrame(pos_rows).to_csv(OUT / "pos_sales_sample.csv", index=False)

print("sample data written to", OUT)
