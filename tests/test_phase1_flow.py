from __future__ import annotations

import pytest

from src.models.product import Product
from src.services.in_memory_product_repository import (
    ExternalUpdateDetectedError,
    InMemoryProductRepository,
)


def test_product_model_validation() -> None:
    product = Product(
        product_no="P00001",
        name="Levi's 501",
        store_name="Tokyo",
        purchase_date="2026-02-26",
        purchase_price=3000,
        sale_status="未出品",
    )
    assert product.product_no == "P00001"
    assert product.profit is None

    with pytest.raises(ValueError):
        Product(
            product_no="P00002",
            name="",
            store_name="Tokyo",
            purchase_date="2026-02-26",
            purchase_price=3000,
            sale_status="未出品",
        )


def test_phase1_create_list_update_flow() -> None:
    repo = InMemoryProductRepository()

    created = repo.create_product(
        {
            "name": "Levi's 505",
            "store_name": "Shibuya",
            "purchase_date": "2026-02-20",
            "purchase_price": 4000,
            "sale_status": "出品済",
        }
    )
    assert created.product_no == "P00001"

    products = repo.list_products()
    assert len(products) == 1
    assert products[0].name == "Levi's 505"

    updated = repo.update_product(
        product_no=created.product_no,
        updates={"sale_status": "売却済", "sale_price": 9000},
        expected_revision=created.revision,
    )
    assert updated.sale_status == "売却済"
    assert updated.sale_price == 9000
    assert updated.profit == 5000


def test_external_update_detection() -> None:
    repo = InMemoryProductRepository()
    created = repo.create_product(
        {
            "name": "Barbour Jacket",
            "store_name": "Harajuku",
            "purchase_date": "2026-02-01",
            "purchase_price": 8000,
            "sale_status": "未出品",
        }
    )

    # 先に1回更新してrevisionを進める
    repo.update_product(
        product_no=created.product_no,
        updates={"sale_status": "出品済"},
        expected_revision=created.revision,
    )

    # 古いrevisionでの更新は拒否される
    with pytest.raises(ExternalUpdateDetectedError):
        repo.update_product(
            product_no=created.product_no,
            updates={"sale_status": "売却済"},
            expected_revision=created.revision,
        )

