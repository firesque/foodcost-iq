"""FoodCost IQ — restaurant food cost, recipe costing & waste intelligence.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from foodcost.config import (  # noqa: E402
    APP_DIR, DATA_STORE, DEFAULT_INVOICE_ROOT, DEFAULT_POS_DIR_CANDIDATES,
    DEFAULT_RECIPE_CANDIDATES, SAMPLE_DATA)
from foodcost.pipeline import build_bundle, load_bundle, save_bundle  # noqa: E402
from ui import theme  # noqa: E402

st.set_page_config(
    page_title="FoodCost IQ",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.inject()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _load_cached_bundle():
    return load_bundle(DATA_STORE)


def _default_paths() -> dict:
    d = {"recipe_path": "", "sysco_dir": "", "freshpoint_dir": "", "pos_dir": ""}
    sysco = DEFAULT_INVOICE_ROOT / "Sysco"
    fp = DEFAULT_INVOICE_ROOT / "FreshPoint"
    if sysco.exists():
        d["sysco_dir"] = str(sysco)
    if fp.exists():
        d["freshpoint_dir"] = str(fp)
    for cand in DEFAULT_POS_DIR_CANDIDATES:
        if cand.exists():
            d["pos_dir"] = str(cand)
            break
    for cand in DEFAULT_RECIPE_CANDIDATES:
        if cand.exists():
            d["recipe_path"] = str(cand)
            break
    return d


def _build_sample_bundle():
    """First-run fallback: build from bundled sample data."""
    bundle = build_bundle(
        recipe_path=SAMPLE_DATA / "recipes_sample.csv",
        sysco_dir=None, freshpoint_dir=None,
        pos_dir=None,
        generic_files={
            "invoices": SAMPLE_DATA / "invoices_sample.csv",
            "pos": SAMPLE_DATA / "pos_sales_sample.csv",
        },
        app_dir=APP_DIR)
    save_bundle(bundle, DATA_STORE)
    return bundle


bundle = _load_cached_bundle()
if bundle is None:
    with st.spinner("First run — building demo dataset from sample data…"):
        try:
            bundle = _build_sample_bundle()
            _load_cached_bundle.clear()
        except Exception as exc:  # pragma: no cover
            st.error(f"Could not build initial dataset: {exc}")
            bundle = None

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div style="padding:6px 0 14px 0">'
        '<span style="font-size:1.35rem;font-weight:800;color:#fff">🍳 FoodCost IQ</span><br>'
        '<span style="font-size:0.75rem;color:#93A4BE;letter-spacing:0.08em">'
        'WASTE & MARGIN INTELLIGENCE</span></div>',
        unsafe_allow_html=True)

    page = st.radio("Navigate", [
        "🏠  Executive Dashboard",
        "🧠  AI Insights",
        "🍽️  Menu Profitability",
        "🥚  Ingredient Intelligence",
        "🗑️  Waste & Variance",
        "🚚  Vendors & Invoices",
        "🎛️  Scenario Studio",
        "🧪  Data Quality",
        "📂  Data Manager",
    ], label_visibility="collapsed")

    st.divider()
    if bundle is not None:
        n_inv = bundle.purchases["invoice_no"].nunique()
        n_loc = bundle.pos["location"].nunique()
        st.caption(f"Loaded: {len(bundle.recipes)} recipes · {n_inv} invoices · "
                   f"{n_loc} locations")
    st.caption("Built for Keke's Breakfast Cafe · Period 5")

# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
if bundle is None and "Data Manager" not in page:
    st.warning("No dataset loaded yet — open the **Data Manager** page.")
    st.stop()

if "Executive" in page:
    from ui.views import dashboard
    dashboard.render(bundle)
elif "AI Insights" in page:
    from ui.views import insights_page
    insights_page.render(bundle)
elif "Menu" in page:
    from ui.views import menu
    menu.render(bundle)
elif "Ingredient" in page:
    from ui.views import ingredients
    ingredients.render(bundle)
elif "Waste" in page:
    from ui.views import waste
    waste.render(bundle)
elif "Vendors" in page:
    from ui.views import vendors_page
    vendors_page.render(bundle)
elif "Scenario" in page:
    from ui.views import scenarios_page
    scenarios_page.render(bundle)
elif "Quality" in page:
    from ui.views import quality_page
    quality_page.render(bundle)
else:
    from ui.views import data_page
    data_page.render(bundle, _default_paths())
