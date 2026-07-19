"""FreshPoint invoice / credit-memo PDF parser.

FreshPoint invoices are single-page, text-line based:

    480010 1 1 40# BANANA GREEN TIP 19.20 19.20
    item   ord shp pack description       unit  extended

Weighted items may include unit/extended weight columns between the pack
and the description or before the prices; the regex tolerates both.
Credit memos produce negative extended prices.
"""
from __future__ import annotations

import re
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd

from foodcost.config import normalize_location

warnings.filterwarnings("ignore")

# Header: item, ordered, shipped, pack, then description + numeric columns.
_HEAD_RE = re.compile(
    r"^(?P<item>\d{6})\s+"
    r"(?P<ordered>\d+)\s+"
    r"(?P<shipped>\d+)\s+"
    r"(?P<pack>\S+)\s+"
    r"(?P<rest>.+)$"
)
_NUM_RE = re.compile(r"^-?\d{1,5}\.\d{2}$")
_DATE_HEADER_RE = re.compile(
    r"(?P<inv>\d{10})\s+(?P<date>\d{1,2}/\d{2}/\d{2})\s+\d{6}"
)
_SHIPTO_RE = re.compile(r"Ship\s*To\s*:\s*(?P<loc>[^\n]+)", re.I)

# FreshPoint is a produce house; nearly everything is PRODUCE. A few
# common exceptions are classified by keyword.
_KEYWORD_CATEGORIES = [
    (re.compile(r"\b(JUICE|CIDER)\b"), "NA BEV"),
    (re.compile(r"\b(CHEESE|DAIRY|BUTTER|CREAM)\b"), "DAIRY"),
    (re.compile(r"\b(EGG)\b"), "MEAT PLTRY"),
]


def _categorize(desc: str) -> str:
    up = desc.upper()
    for pattern, cat in _KEYWORD_CATEGORIES:
        if pattern.search(up):
            return cat
    return "PROD"


def parse_freshpoint_pdf(path: str | Path) -> pd.DataFrame:
    """Parse one FreshPoint invoice or credit-memo PDF."""
    import pdfplumber

    path = Path(path)
    is_credit = "credit" in path.name.lower()
    with pdfplumber.open(str(path)) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)

    invoice_no, inv_date, location = None, None, None
    m = _DATE_HEADER_RE.search(text)
    if m:
        invoice_no = m.group("inv")
        try:
            inv_date = datetime.strptime(m.group("date"), "%m/%d/%y")
        except ValueError:
            inv_date = None
    ship = _SHIPTO_RE.search(text)
    if ship:
        location = normalize_location(ship.group("loc"))

    rows: list[dict] = []
    for line in text.splitlines():
        lm = _HEAD_RE.match(line.strip())
        if not lm:
            continue
        # Trailing numeric columns. Weighted items carry four
        # (unit wt, ext wt, unit price, extended); dry counts carry two.
        # The LAST TWO are always unit price and extended price.
        tokens = lm.group("rest").split()
        while tokens and not _NUM_RE.match(tokens[-1]) and tokens[-1].isalpha() \
                and len(tokens[-1]) <= 2:
            tokens.pop()            # trailing status code (e.g. "S", "P")
        nums: list[str] = []
        while tokens and _NUM_RE.match(tokens[-1]):
            nums.insert(0, tokens.pop())
        if len(nums) < 2:
            continue
        unit_price = float(nums[-2])
        extended = float(nums[-1])
        desc = " ".join(tokens).strip()
        qty = float(lm.group("shipped"))
        if is_credit:
            qty, extended = -abs(qty), -abs(extended)
        # Guard against footer noise that happens to match the pattern
        if len(desc) < 3 or "CUSTOMER SERVICE" in desc.upper():
            continue
        rows.append({
            "vendor": "FreshPoint",
            "invoice_no": invoice_no or path.stem,
            "date": inv_date,
            "location": location or "Unknown",
            "item_no": lm.group("item"),
            "description": desc,
            "category": _categorize(desc),
            "qty": qty,
            "uom": "CS",
            "pack_size": lm.group("pack"),
            "unit_price": unit_price,
            "extended_price": extended,
        })
    return pd.DataFrame(rows)


def parse_freshpoint_folder(folder: str | Path) -> pd.DataFrame:
    """Parse every FreshPoint PDF in a folder; skips unreadable files."""
    frames = []
    for f in sorted(Path(folder).glob("*.pdf")):
        try:
            df = parse_freshpoint_pdf(f)
            if not df.empty:
                frames.append(df)
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
