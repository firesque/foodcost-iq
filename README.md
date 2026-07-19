# 🍳 FoodCost IQ

**Restaurant food cost, recipe costing & waste intelligence engine** — built for
multi-unit operators. Turns recipe books, Sysco/FreshPoint invoices and POS
sales exports into an executive-grade margin and waste command center.

---

## What it does

| Engine | What you get |
|---|---|
| **Recipe costing** | Plate cost for every menu item (sub-recipes/preps exploded), food-cost % and gross margin by item |
| **Theoretical usage** | POS sales × recipes = what you *should* have used, by ingredient, in dollars and physical units |
| **Waste & variance** | Purchases vs theoretical usage, waste-risk scores, estimated waste dollars, likely causes |
| **Vendor analysis** | Sysco vs FreshPoint spend, case-price trends, biggest increases, invoice drilldown |
| **AI insights** | Prioritized plain-English findings with recommended actions and dollar impact (deterministic engine; optional Claude LLM narrative) |
| **Scenario studio** | Model ingredient price shocks, menu repricing, portion changes, volume shifts |
| **Data quality** | Unmatched POS items, unmapped vendor SKUs, suspicious prices, unit problems |

## Quick start

```bash
cd FoodCostApp
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`.

* **First run with real data already cached:** if `data_store/` exists the app
  opens instantly on the real Period 5 dataset.
* **First run from scratch:** the app builds a demo dataset from
  `sample_data/` so every page works immediately. Point it at real data on the
  **📂 Data Manager** page and click **Build / Rebuild dataset**.

## Feeding it your data

The Data Manager accepts either **source folders** (the formats you already
export) or **flat CSV uploads**:

1. **Recipe workbook** (`.xlsx`) — one sheet per recipe (`MI …`, `PREP …`,
   `BATCH …`, `YIELD …` prefixes), or a flat CSV with columns
   `recipe, ingredient, qty, measure[, category, book_cost]`.
2. **Sysco invoice folder** — the delivery-copy PDFs exactly as downloaded.
3. **FreshPoint invoice folder** — customer invoice + credit memo PDFs.
4. **POS folder** — `slsmix*.xls` sales-mix exports (one per location) and
   optionally `Item Sales Detail.xlsx` for daily trends.

PDF parsing runs once and is cached to `data_store/` (parquet).

### Fixing ingredient matches

Vendor SKUs are mapped to recipe ingredients automatically (keyword rules +
abbreviation expansion + fuzzy matching). To correct any mapping, add a row to
`ingredient_map_overrides.csv`:

```csv
item_no,ingredient
4537134,MEAT PLTRY Eggs
```

then rebuild. The Data Quality page lists everything unmapped, sorted by spend.

### Optional LLM narrative

The insight engine is fully deterministic and works offline. To upgrade the
narrative with Claude:

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-…
```

## Project structure

```
FoodCostApp/
├── app.py                      # Streamlit entry point + navigation
├── foodcost/
│   ├── config.py               # paths, location aliases, thresholds
│   ├── pipeline.py             # end-to-end build + parquet cache
│   ├── data_ingestion/
│   │   ├── recipes.py          # recipe workbook / CSV parser
│   │   ├── sysco_pdf.py        # column-aware Sysco PDF parser
│   │   ├── freshpoint_pdf.py   # FreshPoint invoice/credit-memo parser
│   │   └── pos.py              # sales mix, item sales detail, generic CSV
│   ├── processing/
│   │   ├── matching.py         # vendor SKU ↔ ingredient, POS ↔ recipe
│   │   └── data_quality.py     # cross-source integrity checks
│   ├── costing/
│   │   ├── recipe_costing.py   # sub-recipe explosion, plate costs
│   │   ├── usage.py            # theoretical usage engine
│   │   ├── variance.py         # waste-risk model
│   │   ├── vendors.py          # price trends, vendor comparisons
│   │   └── scenarios.py        # what-if modeling
│   ├── ai_engine/
│   │   ├── insights.py         # deterministic consultant-grade insights
│   │   └── llm.py              # optional Claude narrative layer
│   └── utils/                  # units, text normalization
├── ui/
│   ├── theme.py                # design system (CSS, plotly template, cards)
│   └── views/                  # one module per page
├── sample_data/                # demo dataset (regenerate: scripts/make_sample_data.py)
├── scripts/
└── data_store/                 # parquet cache (safe to delete)
```

## Method notes (why you can trust the numbers)

* **Variance is computed in dollars first.** Vendor pack sizes are often
  ambiguous (`115 DZ`, `25LB`), so purchased-vs-theoretical comparisons anchor
  on exact invoice dollars and recipe book costs; physical units are shown
  where conversions are unambiguous.
* **Waste-risk score** (0–100) blends variance ratio (45%), excess dollars
  (30%) and category perishability (25%) — produce over-buying outranks paper
  goods at the same ratio.
* **Sub-recipes** (PREP/BATCH/YIELD) are exploded through their batch yields so
  menu-item costs include prep components correctly.
* **Credit memos** post as negative purchases; split cases are flagged.

## Known limitations

* Pack-size → physical unit conversion is best-effort (dollar math is exact).
* Invoice locations without POS exports (e.g. a store whose sales mix wasn't
  exported) inflate chain-level variance; filter by location when needed.
* POS modifiers with $0 price ("NO BEVERAGE") don't map to recipes — they're
  surfaced on the Data Quality page rather than silently dropped.
