"""
Google Sheets-backed product repository.
Uses jp_row3 layout: headers in row 3 (商品No, 商品名, 店舗名, etc.).
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

import gspread
from google.auth import default
from google.oauth2.service_account import Credentials

from src.models.product import Product

# 各フィールドに対応するスプレッドシートのヘッダー名（複数可・先頭が優先）
JP_HEADERS: dict[str, list[str]] = {
    "product_no": ["商品No"],
    "name": ["商品名"],
    "store_name": ["店舗名"],
    "purchase_date": ["仕入れ日付", "仕入日付"],
    "purchase_price": ["仕入額", "仕入れ額"],
    "listed_date": ["出品日"],
    "sale_date": ["売却日"],
    "sale_price": ["売上金"],
    "sales_channel": ["販売先"],
    "shipping_cost": ["送料"],
    "handling_fee": ["手数料"],
    "listed_flag": ["出品済"],
}


class ExternalUpdateDetectedError(RuntimeError):
    """Raised when an update conflicts with external changes (revision mismatch)."""
    pass


class SheetsProductRepository:
    def __init__(
        self,
        spreadsheet_id: str,
        worksheet_name: str,
        *,
        credentials: Credentials | None = None,
    ) -> None:
        self._spreadsheet_id = spreadsheet_id
        self._worksheet_name = worksheet_name
        self._credentials = credentials
        self._worksheet: gspread.Worksheet | None = None
        self._jp_col_map: dict[str, int] | None = None

    def _open_worksheet(self) -> gspread.Worksheet:
        if self._worksheet is not None:
            return self._worksheet
        if self._credentials is not None:
            creds = self._credentials
        else:
            creds, _ = default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(self._spreadsheet_id)
        self._worksheet = spreadsheet.worksheet(self._worksheet_name)
        self._configure_sheet_layout()
        return self._worksheet

    def _configure_sheet_layout(self) -> None:
        """Configure jp_row3 layout: headers in row 3."""
        ws = self._worksheet
        if ws is None:
            return
        row3 = ws.row_values(3)
        self._jp_col_map = {}
        for idx, raw_header in enumerate(row3):
            h = (raw_header or "").replace("\n", "").strip()
            for en_key, headers in JP_HEADERS.items():
                if en_key in self._jp_col_map:
                    continue  # 既に設定済みはスキップ
                if h in headers:
                    self._jp_col_map[en_key] = idx + 1
                    break

    def _jp_col(self, key: str) -> int | None:
        """Return 1-based column index for given field key, or None if not found."""
        if self._jp_col_map is None:
            self._open_worksheet()
        return self._jp_col_map.get(key) if self._jp_col_map else None

    def _row_revision(self, row_values: list[Any]) -> str:
        """Return a hash of the row for revision tracking."""
        content = "|".join(str(v) for v in (row_values or []))
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _to_iso_date(self, value: Any) -> str | None:
        """Convert various date formats to YYYY-MM-DD. Returns None for empty."""
        if value in (None, ""):
            return None
        s = str(value).strip()
        if not s:
            return None
        # Already YYYY-MM-DD
        m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        # M/D or M/D/YY
        m = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$", s)
        if m:
            y = int(m.group(3)) if m.group(3) else date.today().year
            if y < 100:
                y += 2000 if y < 50 else 1900
            return f"{y}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
        # 2月26日（木） style
        m = re.match(r"^(\d{1,2})月(\d{1,2})日", s)
        if m:
            y = date.today().year
            return f"{y}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
        return None

    def _to_int_str(self, value: Any) -> str:
        """Convert to string representation of int, or empty string."""
        if value in (None, ""):
            return ""
        try:
            return str(int(float(str(value).replace(",", ""))))
        except (ValueError, TypeError):
            return ""

    def _record_from_jp_row(self, row_num: int, row_values: list[Any]) -> dict[str, Any]:
        """Build a record dict from a JP row. Derives sale_status from sale_date/sale_price/listed_flag."""
        if self._jp_col_map is None:
            self._open_worksheet()
        col = self._jp_col_map or {}
        n = len(row_values)

        def _cell(key: str) -> str:
            idx = col.get(key)
            if idx is None or idx > n:
                return ""
            v = row_values[idx - 1]
            return str(v).strip() if v is not None else ""

        purchase_date = self._to_iso_date(_cell("purchase_date"))
        listed_date = self._to_iso_date(_cell("listed_date"))
        sale_date = self._to_iso_date(_cell("sale_date"))
        sale_price_str = self._to_int_str(_cell("sale_price"))
        sale_price = int(sale_price_str) if sale_price_str else None
        shipping_cost_str = self._to_int_str(_cell("shipping_cost"))
        shipping_cost = int(shipping_cost_str) if shipping_cost_str else None
        handling_fee_str = self._to_int_str(_cell("handling_fee"))
        handling_fee = int(handling_fee_str) if handling_fee_str else None
        listed_flag = _cell("listed_flag").strip()

        # Derive sale_status
        if sale_date or (sale_price is not None and sale_price > 0):
            sale_status = "売却済"
        elif listed_flag.lower() in ("true", "1", "yes", "○", "〇", "はい", "出品済", "済"):
            sale_status = "出品済"
        else:
            sale_status = "未出品"

        return {
            "product_no": _cell("product_no"),
            "name": _cell("name"),
            "store_name": _cell("store_name"),
            "purchase_date": purchase_date or "",
            "purchase_price": self._to_int_str(_cell("purchase_price")) or "0",
            "sale_status": sale_status,
            "listed_date": listed_date or "",
            "sale_date": sale_date or "",
            "sale_price": sale_price if sale_price is not None else "",
            "sales_channel": _cell("sales_channel") or None,
            "shipping_cost": shipping_cost if shipping_cost is not None else "",
            "handling_fee": handling_fee if handling_fee is not None else "",
            "revision": self._row_revision(row_values),
        }

    def _apply_updates_to_jp_row(self, product: Product, listed_date: date | None) -> dict[str, Any]:
        """Build cell updates for a JP row from product and listed_date."""
        col = self._jp_col_map or {}
        updates: dict[str, Any] = {}
        if col.get("name"):
            updates[col["name"]] = product.name
        if col.get("store_name"):
            updates[col["store_name"]] = product.store_name
        if col.get("purchase_date"):
            updates[col["purchase_date"]] = (
                product.purchase_date.isoformat() if product.purchase_date else ""
            )
        if col.get("purchase_price"):
            updates[col["purchase_price"]] = product.purchase_price
        if col.get("listed_date"):
            d = listed_date or product.listed_date
            updates[col["listed_date"]] = d.isoformat() if d else ""
        if col.get("sale_date"):
            updates[col["sale_date"]] = (
                product.sale_date.isoformat() if product.sale_date else ""
            )
        if col.get("sale_price"):
            updates[col["sale_price"]] = product.sale_price if product.sale_price is not None else ""
        if col.get("sales_channel"):
            updates[col["sales_channel"]] = product.sales_channel or ""
        if col.get("shipping_cost"):
            updates[col["shipping_cost"]] = product.shipping_cost if product.shipping_cost is not None else ""
        if col.get("handling_fee"):
            updates[col["handling_fee"]] = product.handling_fee if product.handling_fee is not None else ""
        if col.get("listed_flag"):
            updates[col["listed_flag"]] = "TRUE" if product.sale_status in ("出品済", "売却済") else "FALSE"
        return updates

    def _find_first_insertable_jp_row(self) -> tuple[int, str] | None:
        """Find first row (>=5) where product_no exists but other fields are empty. Returns (row_index, product_no)."""
        ws = self._open_worksheet()
        all_values = ws.get_all_values()
        if len(all_values) < 5:
            return None
        col = self._jp_col_map or {}
        product_no_col = col.get("product_no")
        name_col = col.get("name")
        if product_no_col is None or name_col is None:
            return None
        for i in range(4, len(all_values)):
            row = all_values[i]
            n = len(row)
            pno = (row[product_no_col - 1] if product_no_col <= n else "").strip()
            name_val = (row[name_col - 1] if name_col <= n else "").strip()
            if pno and not name_val:
                return (i + 1, pno)
        return None

    def list_products(self, include_archived: bool = False) -> list[Product]:
        """List products from sheet. Skips rows that fail Product.from_row (ValueError)."""
        ws = self._open_worksheet()
        all_values = ws.get_all_values()
        if len(all_values) < 5:
            return []
        products: list[Product] = []
        for i in range(4, len(all_values)):
            row = all_values[i]
            try:
                rec = self._record_from_jp_row(i + 1, row)
                if not rec.get("product_no"):
                    continue
                product = Product.from_row(rec)
                if not include_archived and product.is_archived:
                    continue
                products.append(product)
            except ValueError:
                continue
        return products

    def _next_product_no(self) -> str:
        """Compute next product number (P00001, P00002, ...)."""
        products = self.list_products(include_archived=True)
        max_seq = 0
        for p in products:
            if p.product_no.startswith("P") and p.product_no[1:].isdigit():
                max_seq = max(max_seq, int(p.product_no[1:]))
        return f"P{max_seq + 1:05d}"

    def create_product(self, payload: dict[str, Any]) -> Product:
        """Create product. Tries slot insertion first, then append."""
        slot = self._find_first_insertable_jp_row()
        product_no = payload.get("product_no") or (slot[1] if slot else self._next_product_no())
        data = dict(payload)
        data["product_no"] = product_no
        data.setdefault("sale_status", "未出品")
        data.setdefault("listed_date", None)
        data.setdefault("sale_date", None)
        data.setdefault("sale_price", None)
        data.setdefault("sales_channel", None)
        data.setdefault("shipping_cost", None)
        data.setdefault("handling_fee", None)
        product = Product.from_row(data)

        ws = self._open_worksheet()
        slot = self._find_first_insertable_jp_row()

        if slot is not None:
            insert_row, _ = slot
            # Slot insertion: write into empty slot
            col = self._jp_col_map or {}
            product_no_col = col.get("product_no")
            if product_no_col:
                ws.update_cell(insert_row, product_no_col, product_no)
            listed_date = product.listed_date if product.sale_status == "出品済" else None
            updates = self._apply_updates_to_jp_row(product, listed_date)
            for col_idx, val in updates.items():
                ws.update_cell(insert_row, col_idx, val)
        else:
            # Append
            row_data: list[Any] = [""] * max((self._jp_col_map or {}).values(), default=10)
            col = self._jp_col_map or {}
            for k, c in col.items():
                if k == "product_no":
                    row_data[c - 1] = product_no
                elif k == "name":
                    row_data[c - 1] = product.name
                elif k == "store_name":
                    row_data[c - 1] = product.store_name
                elif k == "purchase_date":
                    row_data[c - 1] = product.purchase_date.isoformat() if product.purchase_date else ""
                elif k == "purchase_price":
                    row_data[c - 1] = product.purchase_price
                elif k == "listed_date":
                    d = product.listed_date if product.sale_status == "出品済" else None
                    row_data[c - 1] = d.isoformat() if d else ""
                elif k == "sale_date":
                    row_data[c - 1] = product.sale_date.isoformat() if product.sale_date else ""
                elif k == "sale_price":
                    row_data[c - 1] = product.sale_price if product.sale_price is not None else ""
                elif k == "sales_channel":
                    row_data[c - 1] = product.sales_channel or ""
                elif k == "shipping_cost":
                    row_data[c - 1] = product.shipping_cost if product.shipping_cost is not None else ""
                elif k == "handling_fee":
                    row_data[c - 1] = product.handling_fee if product.handling_fee is not None else ""
                elif k == "listed_flag":
                    row_data[c - 1] = "TRUE" if product.sale_status in ("出品済", "売却済") else "FALSE"
            ws.append_row(row_data)

        # Re-fetch to get revision
        all_values = ws.get_all_values()
        target_row = slot[0] if slot is not None else len(all_values)
        if target_row <= len(all_values):
            row_vals = all_values[target_row - 1]
            product.revision = self._row_revision(row_vals)
        return product

    def update_product(
        self,
        product_no: str,
        updates: dict[str, Any],
        expected_revision: str,
    ) -> Product:
        """Update product by product_no. Raises ExternalUpdateDetectedError on revision mismatch."""
        ws = self._open_worksheet()
        all_values = ws.get_all_values()
        if len(all_values) < 5:
            raise KeyError(f"product_no not found: {product_no}")

        product_no_col = (self._jp_col_map or {}).get("product_no")
        if product_no_col is None:
            raise KeyError(f"product_no not found: {product_no}")

        target_row: int | None = None
        for i in range(4, len(all_values)):
            row = all_values[i]
            n = len(row)
            pno = (row[product_no_col - 1] if product_no_col <= n else "").strip()
            if pno == product_no:
                target_row = i + 1
                break

        if target_row is None:
            raise KeyError(f"product_no not found: {product_no}")

        row_vals = all_values[target_row - 1]
        current_revision = self._row_revision(row_vals)
        if current_revision != expected_revision:
            raise ExternalUpdateDetectedError("external update detected")

        rec = self._record_from_jp_row(target_row, row_vals)
        current = Product.from_row(rec)
        merged = current.to_row()
        merged.update(updates)
        merged["product_no"] = product_no
        updated = Product.from_row(merged)

        listed_date = updated.listed_date
        cell_updates = self._apply_updates_to_jp_row(updated, listed_date)
        for col_idx, val in cell_updates.items():
            ws.update_cell(target_row, col_idx, val)

        updated.revision = self._row_revision(
            ws.row_values(target_row)
        )
        return updated

    def _update_product_legacy(
        self,
        product_no: str,
        updates: dict[str, Any],
        expected_revision: str,
    ) -> Product:
        """Legacy update path (alias for update_product)."""
        return self.update_product(product_no, updates, expected_revision)

    def _update_product_jp(
        self,
        product_no: str,
        updates: dict[str, Any],
        expected_revision: str,
    ) -> Product:
        """JP layout update path (alias for update_product)."""
        return self.update_product(product_no, updates, expected_revision)

    def list_sales_channels(self) -> list[str]:
        """List sales channels from 手数料リスト worksheet, column 1."""
        if self._credentials is not None:
            creds = self._credentials
        else:
            creds, _ = default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(self._spreadsheet_id)
        try:
            fee_sheet = spreadsheet.worksheet("手数料リスト")
        except gspread.WorksheetNotFound:
            return []
        col1 = fee_sheet.col_values(1)
        channels: list[str] = []
        seen: set[str] = set()
        for v in col1[1:]:
            ch = str(v).strip()
            if ch and ch not in seen:
                seen.add(ch)
                channels.append(ch)
        return channels
