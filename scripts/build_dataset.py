"""CLI: build the analytics dataset without the UI.

Usage:
    python scripts/build_dataset.py \
        --recipes "/path/Recipe.xlsx" \
        --sysco   "/path/Sysco" \
        --freshpoint "/path/FreshPoint" \
        --pos     "/path/POS exports"

Writes the parquet cache to data_store/ — the app then opens instantly.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from foodcost.config import APP_DIR, DATA_STORE  # noqa: E402
from foodcost.pipeline import build_bundle, save_bundle  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Build FoodCost IQ dataset")
    ap.add_argument("--recipes", help="Recipe workbook (.xlsx) or flat CSV")
    ap.add_argument("--sysco", help="Folder of Sysco invoice PDFs")
    ap.add_argument("--freshpoint", help="Folder of FreshPoint invoice PDFs")
    ap.add_argument("--pos", help="Folder with slsmix*.xls / Item Sales Detail.xlsx")
    ap.add_argument("--invoices-csv", help="Flat invoice CSV (alternative to PDFs)")
    ap.add_argument("--pos-csv", help="Flat POS CSV (alternative to --pos)")
    args = ap.parse_args()

    generic = {}
    if args.invoices_csv:
        generic["invoices"] = args.invoices_csv
    if args.pos_csv:
        generic["pos"] = args.pos_csv

    t0 = time.time()
    bundle = build_bundle(
        recipe_path=args.recipes, sysco_dir=args.sysco,
        freshpoint_dir=args.freshpoint, pos_dir=args.pos,
        generic_files=generic or None, app_dir=APP_DIR,
        progress=lambda m: print(f"[{time.time() - t0:6.1f}s] {m}", flush=True))
    save_bundle(bundle, DATA_STORE)
    print(f"Done in {time.time() - t0:,.0f}s — dataset written to {DATA_STORE}")


if __name__ == "__main__":
    main()
