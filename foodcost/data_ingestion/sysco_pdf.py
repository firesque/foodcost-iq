"""Sysco delivery-invoice PDF parser.

Sysco invoices are column-aligned. We use word x-coordinates from
pdfplumber to slot each word into its column, which is far more robust
than regexing the flattened text (pack/size tokens are often fused).

Column map (x0 ranges, empirically stable across Sysco Tampa Bay docs):
    loc flag      < 60
    qty           60-100
    unit (CS/EA)  84-100   (qty and unit are separate words)
    pack/size     100-155
    description   155-392
    mfr number    392-428
    item number   428-478  (7 digits)
    unit price    478-540
    extended      540-620
"""
from __future__ import annotations

import re
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd

from foodcost.config import normalize_location

warnings.filterwarnings("ignore")

_ITEM_RE = re.compile(r"^\d{7}$")
_PRICE_RE = re.compile(r"^-?\d{1,4}\.\d{2}$")
_DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2})\b")

# Category group headers that appear between line-item blocks.
# Values align with the recipe workbook's category prefixes.
_CATEGORY_HEADERS = {
    "DAIRY PRODUCTS": "DAIRY", "DAIRY": "DAIRY",
    "POULTRY": "MEAT PLTRY", "MEATS": "MEAT", "MEAT": "MEAT",
    "BEEF": "MEAT BEEF", "PORK": "MEAT PORK", "SEAFOOD": "MEAT",
    "FROZEN": "FZN", "FROZEN FOODS": "FZN",
    "CANNED AND DRY": "DRY", "CANNED & DRY": "DRY",
    "DRY GROCERY": "DRY", "GROCERY": "DRY",
    "PRODUCE": "PROD", "FRESH PRODUCE": "PROD",
    "BAKERY": "DRY", "BREAD AND ROLLS": "DRY",
    "PAPER AND DISPOSABLES": "PAPER", "PAPER & DISPOSABLES": "PAPER",
    "PAPER & DISP": "PAPER",
    "CHEMICALS": "MISC", "CHEMICAL/JANITORIAL": "MISC",
    "SUPPLIES AND EQUIPMENT": "MISC", "SUPPLIES & EQUIPMENT": "MISC",
    "DROP-SHIP": "MISC", "SUBSTITUTE": "MISC",
    "BEVERAGE": "NA BEV", "BEVERAGES": "NA BEV", "BEVEAGE": "NA BEV",
    "DISPENSER/ BEVERAGE": "NA BEV", "DISPENSER/BEVERAGE": "NA BEV",
}


def _group_lines(words: list[dict], tol: float = 3.0) -> list[list[dict]]:
    """Group pdfplumber words into visual lines by their top coordinate."""
    lines: dict[int, list[dict]] = {}
    for w in words:
        key = round(w["top"] / tol)
        lines.setdefault(key, []).append(w)
    return [sorted(v, key=lambda w: w["x0"]) for _, v in sorted(lines.items())]


def parse_sysco_pdf(path: str | Path) -> pd.DataFrame:
    """Parse one Sysco invoice PDF into a line-item DataFrame."""
    import pdfplumber

    path = Path(path)
    rows: list[dict] = []
    invoice_no, delv_date, location = None, None, None
    category = "MISC"

    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            lines = _group_lines(words)
            for line in lines:
                texts = [w["text"] for w in line]
                joined = " ".join(texts)

                # --- header metadata ------------------------------------
                if location is None and "KEKE" in joined.upper():
                    location = normalize_location(joined)
                if delv_date is None:
                    m = _DATE_RE.search(joined)
                    if m and "DELV" not in joined:
                        try:
                            delv_date = datetime.strptime(m.group(1), "%m/%d/%y")
                        except ValueError:
                            pass
                if invoice_no is None:
                    m = re.search(r"\b(1033\d{5})\b", joined)
                    if m:
                        invoice_no = m.group(1)

                # --- category headers -----------------------------------
                bare = joined.strip().upper()
                if bare in _CATEGORY_HEADERS:
                    category = _CATEGORY_HEADERS[bare]
                    continue

                # --- line items -----------------------------------------
                item_words = [w for w in line
                              if 420 <= w["x0"] <= 478 and _ITEM_RE.match(w["text"])]
                if not item_words:
                    continue
                prices = [w for w in line
                          if w["x0"] > 478 and _PRICE_RE.match(w["text"])]
                if not prices:
                    continue

                qty_words = [w["text"] for w in line if 58 <= w["x0"] < 84]
                unit_words = [w["text"] for w in line if 84 <= w["x0"] < 100]
                pack_words = [w["text"] for w in line if 100 <= w["x0"] < 155]
                desc_words = [w["text"] for w in line if 155 <= w["x0"] < 392]
                unit_price = float(prices[0]["text"])
                extended = float(prices[-1]["text"]) if len(prices) > 1 else unit_price

                qty_txt = "".join(qty_words)
                try:
                    qty = float(re.sub(r"[^\d.-]", "", qty_txt) or 1)
                except ValueError:
                    qty = 1.0
                # 'S' marker next to qty indicates a split case
                is_split = "S" in qty_txt.upper() or "SP" in "".join(unit_words).upper()

                desc = " ".join(desc_words).strip()
                if not desc:
                    continue
                rows.append({
                    "vendor": "Sysco",
                    "invoice_no": invoice_no or path.stem.split("_")[0],
                    "date": delv_date,
                    "location": location or "Unknown",
                    "item_no": item_words[0]["text"],
                    "description": desc,
                    "category": category,
                    "qty": qty,
                    "uom": ("SPLIT" if is_split else ("".join(unit_words) or "CS")),
                    "pack_size": " ".join(pack_words),
                    "unit_price": unit_price,
                    "extended_price": extended,
                })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = df["date"].fillna(_date_from_filename(path))
        df["location"] = df["location"].replace("Unknown", None).ffill().bfill()
    return df


def _date_from_filename(path: Path) -> datetime | None:
    """Filenames embed the export date: 103303323_20260429_195255293.pdf."""
    m = re.search(r"_(\d{8})_", path.name)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d")
        except ValueError:
            return None
    return None


def parse_sysco_folder(folder: str | Path) -> pd.DataFrame:
    """Parse every Sysco PDF in a folder; skips unreadable files."""
    frames = []
    for f in sorted(Path(folder).glob("*.pdf")):
        try:
            df = parse_sysco_pdf(f)
            if not df.empty:
                frames.append(df)
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
