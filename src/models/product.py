from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


ALLOWED_SALE_STATUS = {"未出品", "出品済", "売却済"}


def _to_date(value: Any, field_name: str, required: bool = True) -> date | None:
    if value in (None, ""):
        if required:
            raise ValueError(f"{field_name} is required")
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc
    raise ValueError(f"{field_name} has invalid type")


def _to_int(value: Any, field_name: str, required: bool = True) -> int | None:
    if value in (None, ""):
        if required:
            raise ValueError(f"{field_name} is required")
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be integer") from exc


@dataclass
class Product:
    product_no: str
    name: str
    store_name: str
    purchase_date: date
    purchase_price: int
    sale_status: str = "未出品"
    listed_date: date | None = None
    sale_date: date | None = None
    sale_price: int | None = None
    sales_channel: str | None = None
    shipping_cost: int | None = None  # 送料
    is_archived: bool = False
    revision: str = ""
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.product_no:
            raise ValueError("product_no is required")
        if not self.name:
            raise ValueError("name is required")
        if not self.store_name:
            raise ValueError("store_name is required")
        self.purchase_date = _to_date(self.purchase_date, "purchase_date", required=True)
        self.purchase_price = _to_int(self.purchase_price, "purchase_price", required=True)  # type: ignore[assignment]
        self.listed_date = _to_date(self.listed_date, "listed_date", required=False)
        self.sale_date = _to_date(self.sale_date, "sale_date", required=False)
        self.sale_price = _to_int(self.sale_price, "sale_price", required=False)
        self.shipping_cost = _to_int(self.shipping_cost, "shipping_cost", required=False)
        if self.sale_status not in ALLOWED_SALE_STATUS:
            raise ValueError(f"sale_status must be one of {sorted(ALLOWED_SALE_STATUS)}")
        if self.purchase_price < 0:
            raise ValueError("purchase_price must be >= 0")
        if self.sale_price is not None and self.sale_price < 0:
            raise ValueError("sale_price must be >= 0")
        if self.shipping_cost is not None and self.shipping_cost < 0:
            raise ValueError("shipping_cost must be >= 0")

    @property
    def profit(self) -> int | None:
        if self.sale_price is None:
            return None
        ship = self.shipping_cost or 0
        return self.sale_price - self.purchase_price - ship

    def to_row(self) -> dict[str, Any]:
        return {
            "product_no": self.product_no,
            "name": self.name,
            "store_name": self.store_name,
            "purchase_date": self.purchase_date.isoformat(),
            "purchase_price": self.purchase_price,
            "sale_status": self.sale_status,
            "listed_date": self.listed_date.isoformat() if self.listed_date else "",
            "sale_date": self.sale_date.isoformat() if self.sale_date else "",
            "sale_price": self.sale_price if self.sale_price is not None else "",
            "sales_channel": self.sales_channel or "",
            "shipping_cost": self.shipping_cost if self.shipping_cost is not None else "",
            "is_archived": self.is_archived,
            "revision": self.revision,
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Product":
        return cls(
            product_no=str(row.get("product_no", "")).strip(),
            name=str(row.get("name", "")).strip(),
            store_name=str(row.get("store_name", "")).strip(),
            purchase_date=row.get("purchase_date", ""),
            purchase_price=row.get("purchase_price", ""),
            sale_status=str(row.get("sale_status", "未出品")).strip() or "未出品",
            listed_date=row.get("listed_date", ""),
            sale_date=row.get("sale_date", ""),
            sale_price=row.get("sale_price", ""),
            sales_channel=str(row.get("sales_channel", "")).strip() or None,
            shipping_cost=row.get("shipping_cost", ""),
            is_archived=str(row.get("is_archived", "")).lower() in {"true", "1", "yes"},
            revision=str(row.get("revision", "")).strip(),
            updated_at=None,
        )

