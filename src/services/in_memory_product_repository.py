from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.models.product import Product


class ExternalUpdateDetectedError(RuntimeError):
    pass


class InMemoryProductRepository:
    def __init__(self) -> None:
        self._products: dict[str, Product] = {}

    def _now_revision(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _next_product_no(self) -> str:
        max_seq = 0
        for product_no in self._products:
            if product_no.startswith("P") and product_no[1:].isdigit():
                max_seq = max(max_seq, int(product_no[1:]))
        return f"P{max_seq + 1:05d}"

    def list_products(self, include_archived: bool = False) -> list[Product]:
        values = list(self._products.values())
        if include_archived:
            return values
        return [item for item in values if not item.is_archived]

    def create_product(self, payload: dict[str, Any]) -> Product:
        data = dict(payload)
        data.setdefault("product_no", self._next_product_no())
        data["revision"] = self._now_revision()
        data["updated_at"] = datetime.now(timezone.utc)
        product = Product(**data)
        if product.product_no in self._products:
            raise ValueError(f"product_no already exists: {product.product_no}")
        self._products[product.product_no] = product
        return product

    def update_product(self, product_no: str, updates: dict[str, Any], expected_revision: str) -> Product:
        current = self._products.get(product_no)
        if not current:
            raise KeyError(f"product_no not found: {product_no}")
        if current.revision != expected_revision:
            raise ExternalUpdateDetectedError("external update detected")

        merged = current.to_row()
        merged.update(updates)
        merged["product_no"] = product_no
        merged["revision"] = self._now_revision()
        merged["updated_at"] = datetime.now(timezone.utc)
        updated = Product.from_row(merged)
        self._products[product_no] = updated
        return updated

