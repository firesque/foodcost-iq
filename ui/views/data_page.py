"""Data manager: sources, uploads, rebuild."""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from foodcost.config import APP_DIR, DATA_STORE
from foodcost.pipeline import build_bundle, save_bundle
from ui import theme


def render(bundle_or_none, defaults: dict) -> None:
    theme.hero("Data Manager",
               "Point the engine at your recipe workbook, invoice folders and "
               "POS exports — or upload files directly.", "SOURCES")

    st.markdown("#### Source folders")
    with st.container(border=True):
        recipe_path = st.text_input(
            "Recipe workbook (.xlsx, one sheet per recipe) or flat CSV",
            value=defaults.get("recipe_path", ""))
        c1, c2 = st.columns(2)
        sysco_dir = c1.text_input("Sysco invoice folder (PDFs)",
                                  value=defaults.get("sysco_dir", ""))
        fp_dir = c2.text_input("FreshPoint invoice folder (PDFs)",
                               value=defaults.get("freshpoint_dir", ""))
        pos_dir = st.text_input(
            "POS exports folder (slsmix*.xls + optional Item Sales Detail.xlsx)",
            value=defaults.get("pos_dir", ""))

    st.markdown("#### Or upload files (CSV / Excel)")
    with st.container(border=True):
        up_recipes = st.file_uploader(
            "Recipes (flat: recipe, ingredient, qty, measure[, category, book_cost])",
            type=["csv", "xlsx"], key="up_r")
        up_inv = st.file_uploader(
            "Invoices (flat: vendor, invoice_no, date, item_no, description, "
            "category, qty, unit_price, extended_price)",
            type=["csv"], key="up_i")
        up_pos = st.file_uploader(
            "POS sales (flat: item, qty_sold[, revenue, location, date])",
            type=["csv", "xlsx"], key="up_p")

    generic = {}
    tmp = Path(tempfile.gettempdir())
    for key, up in [("recipes", up_recipes), ("invoices", up_inv), ("pos", up_pos)]:
        if up is not None:
            dest = tmp / up.name
            dest.write_bytes(up.getvalue())
            generic[key] = dest

    c1, c2 = st.columns([1, 3])
    if c1.button("⚙️ Build / Rebuild dataset", type="primary",
                 use_container_width=True):
        status = st.status("Building analytics dataset…", expanded=True)

        def tick(msg: str) -> None:
            status.write(msg)

        try:
            bundle = build_bundle(
                recipe_path=recipe_path or None,
                sysco_dir=sysco_dir or None,
                freshpoint_dir=fp_dir or None,
                pos_dir=pos_dir or None,
                generic_files=generic or None,
                app_dir=APP_DIR, progress=tick)
            save_bundle(bundle, DATA_STORE)
            st.session_state.pop("insights", None)
            status.update(label="Dataset built ✓", state="complete")
            st.success("Done — all pages now reflect the new data.")
            st.rerun()
        except Exception as exc:
            status.update(label="Build failed", state="error")
            st.error(f"{exc}")
    c2.caption("PDF parsing of a full period (100+ invoices) takes a few "
               "minutes the first time. Results are cached in `data_store/` — "
               "the app opens instantly afterwards.")

    if bundle_or_none is not None:
        b = bundle_or_none
        theme.section("Currently loaded")
        theme.metric_row([
            ("Recipes", f"{len(b.recipes):,}"),
            ("Invoice Lines", f"{len(b.purchases):,}",
             f"{b.purchases['invoice_no'].nunique()} invoices"),
            ("POS Items", f"{len(b.pos):,}",
             f"{b.pos['location'].nunique()} locations"),
            ("Sample Data?", "No" if len(b.purchases) > 500 else "Possibly"),
        ])
