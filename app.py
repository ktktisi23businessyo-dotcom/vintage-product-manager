from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from typing import Any

import streamlit as st
from google.oauth2.service_account import Credentials

from src.services.sheets_product_repository import ExternalUpdateDetectedError, SheetsProductRepository


def _get_gcp_credentials() -> Credentials | None:
    """Streamlit Cloud: Secrets から Google 認証情報を取得。ローカルでは None を返す。"""
    try:
        gcp = st.secrets.get("gcp") or {}
        raw = gcp.get("service_account")
    except (KeyError, Exception):
        return None
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, dict):
        return None
    # TOML 経由だと private_key の \n が文字列 "\\n" になることがあるため正規化
    info: dict[str, Any] = dict(raw)
    if "private_key" in info and isinstance(info["private_key"], str):
        info["private_key"] = info["private_key"].replace("\\n", "\n")
    try:
        creds = Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        # 念のため env にも設定（default() のフォールバック用）
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(info, f, ensure_ascii=False)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name
        return creds
    except Exception:
        return None


from src.utils.logger import get_app_logger, get_audit_logger, get_error_logger


DEFAULT_SPREADSHEET_ID = "1CIUsTt9e8oYievPy8-v6paJQVJPe_WZoogkUJet4wRg"
DEFAULT_WORKSHEET_NAME = "商品管理シート"
APP_LOGGER = get_app_logger()
ERROR_LOGGER = get_error_logger()
AUDIT_LOGGER = get_audit_logger()


def _required_text(value: str, label: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{label}は必須です。")
    return text


def _product_label(product_no: str, name: str, sale_status: str) -> str:
    return f"{product_no} | {name} | {sale_status}"


def _channel_options(repo: SheetsProductRepository) -> list[str]:
    options = [""]
    for ch in repo.list_sales_channels():
        if ch not in options:
            options.append(ch)
    return options


def _apply_list_filters(
    products: list,
    keyword: str,
    sale_status_filter: str,
    store_filter: str,
    channel_filter: str,
) -> list:
    keyword_norm = keyword.strip().lower()
    filtered = []
    for product in products:
        if sale_status_filter and product.sale_status != sale_status_filter:
            continue
        if store_filter and product.store_name != store_filter:
            continue
        if channel_filter and (product.sales_channel or "") != channel_filter:
            continue
        if keyword_norm:
            haystack = " ".join(
                [
                    str(product.product_no),
                    product.name or "",
                    product.store_name or "",
                    product.sales_channel or "",
                ]
            ).lower()
            if keyword_norm not in haystack:
                continue
        filtered.append(product)
    return filtered


def _sort_products(products: list, sort_rule: str) -> list:
    status_rank = {"未出品": 0, "出品済": 1, "売却済": 2}
    if sort_rule == "仕入日（新しい順）":
        return sorted(products, key=lambda p: p.purchase_date, reverse=True)
    if sort_rule == "仕入日（古い順）":
        return sorted(products, key=lambda p: p.purchase_date)
    if sort_rule == "仕入額（高い順）":
        return sorted(products, key=lambda p: p.purchase_price, reverse=True)
    if sort_rule == "仕入額（安い順）":
        return sorted(products, key=lambda p: p.purchase_price)
    if sort_rule == "販売状態（未出品→出品済→売却済）":
        return sorted(products, key=lambda p: status_rank.get(p.sale_status, 99))
    if sort_rule == "商品No（昇順）":
        return sorted(products, key=lambda p: str(p.product_no))
    return products


def _importance_label(product) -> str:
    if product.purchase_price >= 10000:
        return "高"
    if product.sale_status == "出品済":
        return "中"
    return "低"


def main() -> None:
    st.set_page_config(page_title="古着商品管理（MVP）", page_icon="👕", layout="centered")
    st.markdown(
        """
        <style>
        /* 温かいクリーム系のベース */
        .stApp { background: linear-gradient(180deg, #FFFBF5 0%, #FFF5E6 50%, #FFF0DB 100%); }
        /* サイドバー */
        [data-testid="stSidebar"] { background: #FFF8F0 !important; }
        [data-testid="stSidebar"] .stMarkdown { color: #5C4033 !important; }
        /* カード・フォームエリア */
        .stForm, [data-testid="stForm"] { background: rgba(255, 250, 240, 0.9) !important; border-radius: 12px; padding: 1rem; }
        /* タイトル */
        h1 { color: #6B4423 !important; font-weight: 600 !important; }
        h2, h3 { color: #7D5A3C !important; }
        /* メトリクス・成功メッセージ */
        [data-testid="stMetricValue"] { color: #8B6914 !important; }
        .stSuccess { background: #F5E6D3 !important; color: #5C4033 !important; border-radius: 8px; }
        .stInfo { background: #FFF5E6 !important; color: #5C4033 !important; border-radius: 8px; }
        /* ボタン */
        .stButton > button { background: #C4A35A !important; color: #FFFBF5 !important; border-radius: 8px; }
        .stButton > button:hover { background: #A68B3C !important; }
        /* 入力欄を濃い茶色で強調 */
        .stTextInput input, .stDateInput input { background: #F5E6D3 !important; border: 2px solid #6B4423 !important; color: #4A3728 !important; }
        input[type="number"], .stNumberInput input, [data-testid="stNumberInput"] input { background: #F5E6D3 !important; border: 2px solid #6B4423 !important; color: #4A3728 !important; }
        [data-testid="stNumberInput"] > div, [data-testid="stNumberInput"] div[data-baseweb="input"], [data-testid="stNumberInput"] [role="group"] { border: 2px solid #6B4423 !important; background: #F5E6D3 !important; border-radius: 4px !important; }
        [data-testid="stNumberInput"] input { box-sizing: border-box !important; }
        div[data-baseweb="select"] { background: #F5E6D3 !important; border: 2px solid #6B4423 !important; min-width: 200px !important; }
        div[data-baseweb="select"] > div { background: #F5E6D3 !important; color: #4A3728 !important; }
        /* 並び替えプルダウンの全文表示 */
        [data-baseweb="popover"] { min-width: 280px !important; }
        [data-baseweb="popover"] li, [data-baseweb="popover"] [role="option"] { white-space: normal !important; min-width: 260px !important; }
        ul[role="listbox"] { min-width: 280px !important; }
        ul[role="listbox"] li { white-space: normal !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("古着商品管理（MVP）")
    st.caption("Phase 2 / P2-01-03: 登録 + 一覧 + 最低限編集")

    # スプレッドシート設定は Secrets / 環境変数 / デフォルトで自動設定（ユーザーが触る必要なし）
    try:
        sheet_cfg = st.secrets.get("spreadsheet") or {}
        spreadsheet_id = sheet_cfg.get("id") or os.getenv("SPREADSHEET_ID") or DEFAULT_SPREADSHEET_ID
        worksheet_name = sheet_cfg.get("worksheet") or os.getenv("WORKSHEET_NAME") or DEFAULT_WORKSHEET_NAME
    except Exception:
        spreadsheet_id = os.getenv("SPREADSHEET_ID") or DEFAULT_SPREADSHEET_ID
        worksheet_name = os.getenv("WORKSHEET_NAME") or DEFAULT_WORKSHEET_NAME
    spreadsheet_id = str(spreadsheet_id or "").strip()
    worksheet_name = str(worksheet_name or "").strip()

    if not spreadsheet_id:
        st.error("Spreadsheet IDは必須です。")
        return
    if not worksheet_name:
        st.error("Worksheet名は必須です。")
        return

    try:
        gcp_creds = _get_gcp_credentials()
        repo = SheetsProductRepository(
            spreadsheet_id, worksheet_name, credentials=gcp_creds
        )
    except Exception as exc:
        ERROR_LOGGER.exception("Sheet connection failed: spreadsheet_id=%s worksheet_name=%s", spreadsheet_id, worksheet_name)
        st.error(f"シート接続に失敗しました: {exc}")
        return
    APP_LOGGER.info("Sheet connected: spreadsheet_id=%s worksheet_name=%s", spreadsheet_id, worksheet_name)
    channel_options = _channel_options(repo)

    flash_message = st.session_state.pop("flash_success", "")
    flash_record = st.session_state.pop("flash_record", None)
    if flash_message:
        st.success(flash_message)
    if flash_record:
        st.write(flash_record)

    st.markdown("### 1.商品登録")
    with st.form("create_product_form"):
        name = st.text_input("商品名 *")
        store_name = st.text_input("店舗名 *")
        purchase_date = st.date_input("仕入日 *", value=date.today())
        purchase_price = st.number_input("仕入額 *", min_value=0, step=100, value=0)
        sale_status = st.selectbox("販売状態 *", ["未出品", "出品済", "売却済"], index=0)
        listed_date = st.date_input("出品日（任意）", value=None)
        sales_channel = st.selectbox("販売先（任意）", options=channel_options, index=0)
        shipping_cost = st.number_input("送料（任意）", min_value=0, step=100, value=0)
        handling_fee = st.number_input("手数料（任意）", min_value=0, step=100, value=0)

        submitted = st.form_submit_button("保存する", type="primary")

    if submitted:
        payload: dict[str, object] = {}
        try:
            payload = {
                "name": _required_text(name, "商品名"),
                "store_name": _required_text(store_name, "店舗名"),
                "purchase_date": purchase_date.isoformat(),
                "purchase_price": int(purchase_price),
                "sale_status": sale_status,
                "listed_date": listed_date.isoformat() if listed_date else None,
                "sales_channel": sales_channel or None,
                "shipping_cost": int(shipping_cost) if shipping_cost > 0 else None,
                "handling_fee": int(handling_fee) if handling_fee > 0 else None,
            }
            created = repo.create_product(payload)
        except Exception as exc:
            ERROR_LOGGER.exception("Create failed: payload=%s", payload)
            st.error(f"保存に失敗しました: {exc}")
        else:
            AUDIT_LOGGER.info("CREATE success product_no=%s name=%s", created.product_no, created.name)
            st.session_state["flash_success"] = f"保存しました（商品No: {created.product_no}）"
            st.session_state["flash_record"] = {
                "product_no": created.product_no,
                "name": created.name,
                "store_name": created.store_name,
                "purchase_date": created.purchase_date.isoformat(),
                "purchase_price": created.purchase_price,
                "sale_status": created.sale_status,
            }
            st.rerun()
    else:
        st.info("必須項目を入力して「保存する」を押してください。")

    st.markdown("### 2.商品一覧")
    try:
        products = repo.list_products(include_archived=False)
    except Exception as exc:
        ERROR_LOGGER.exception("List failed")
        st.error(f"一覧取得に失敗しました: {exc}")
        return
    APP_LOGGER.info("List fetched count=%s", len(products))

    st.markdown("#### 検索・フィルタ・並び替え")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        keyword = st.text_input("検索", placeholder="商品No / 商品名 / 店舗名 / 販売先")
    with col2:
        status_options = [""] + sorted({p.sale_status for p in products})
        sale_status_filter = st.selectbox("販売状態", options=status_options, format_func=lambda x: x or "すべて")
    with col3:
        store_options = [""] + sorted({p.store_name for p in products if p.store_name})
        store_filter = st.selectbox("店舗名", options=store_options, format_func=lambda x: x or "すべて")
    with col4:
        channel_values = sorted({(p.sales_channel or "") for p in products if (p.sales_channel or "").strip()})
        channel_options = [""] + channel_values
        channel_filter = st.selectbox("販売先", options=channel_options, format_func=lambda x: x or "すべて")
    with col5:
        sort_rule = st.selectbox(
            "並び替え",
            options=[
                "商品No（昇順）",
                "仕入日（新しい順）",
                "仕入日（古い順）",
                "仕入額（高い順）",
                "仕入額（安い順）",
                "販売状態（未出品→出品済→売却済）",
            ],
            index=0,
        )
    col_a, col_b, col_c = st.columns([1, 1, 4])
    with col_a:
        importance_filter = st.selectbox(
            "重要度",
            options=["", "高", "中", "低"],
            format_func=lambda x: x or "すべて",
            key="importance_filter",
        )

    filtered_products = _apply_list_filters(
        products=products,
        keyword=keyword,
        sale_status_filter=sale_status_filter,
        store_filter=store_filter,
        channel_filter=channel_filter,
    )
    if importance_filter:
        filtered_products = [p for p in filtered_products if _importance_label(p) == importance_filter]
    filtered_products = _sort_products(filtered_products, sort_rule)

    st.metric("表示件数", len(filtered_products))

    st.markdown("### 3.商品編集")
    if not filtered_products:
        st.info("編集対象の商品がありません。先に商品登録してください。")
    else:
        labels = [_product_label(p.product_no, p.name, p.sale_status) for p in filtered_products]
        selected_label = st.selectbox("編集対象", labels)
        selected = filtered_products[labels.index(selected_label)]
        status_options = ["未出品", "出品済", "売却済"]
        status_index = status_options.index(selected.sale_status) if selected.sale_status in status_options else 0
        if selected.sales_channel and selected.sales_channel not in channel_options:
            channel_options = channel_options + [selected.sales_channel]
        channel_index = channel_options.index(selected.sales_channel) if selected.sales_channel in channel_options else 0
        with st.form("edit_product_form"):
            edit_name = st.text_input("商品名（編集） *", value=selected.name)
            edit_store_name = st.text_input("店舗名（編集） *", value=selected.store_name)
            edit_purchase_date = st.date_input("仕入日（編集） *", value=selected.purchase_date)
            edit_purchase_price = st.number_input(
                "仕入額（編集） *", min_value=0, step=100, value=int(selected.purchase_price)
            )
            edit_sale_status = st.selectbox("販売状態（編集） *", status_options, index=status_index)
            edit_listed_date = st.date_input(
                "出品日（編集・任意）",
                value=selected.listed_date,
            )
            edit_sale_date = st.date_input(
                "販売日（任意）",
                value=selected.sale_date,
            )
            edit_sale_price = st.number_input(
                "売上金（任意）",
                min_value=0,
                step=100,
                value=int(selected.sale_price) if selected.sale_price is not None else 0,
            )
            edit_shipping_cost = st.number_input(
                "送料（任意）",
                min_value=0,
                step=100,
                value=int(selected.shipping_cost) if selected.shipping_cost is not None else 0,
            )
            edit_handling_fee = st.number_input(
                "手数料（任意）",
                min_value=0,
                step=100,
                value=int(selected.handling_fee) if selected.handling_fee is not None else 0,
            )
            edit_sales_channel = st.selectbox("販売先（任意）", options=channel_options, index=channel_index)
            submitted_edit = st.form_submit_button("更新する")

        if submitted_edit:
            try:
                updates: dict[str, object] = {
                    "name": _required_text(edit_name, "商品名"),
                    "store_name": _required_text(edit_store_name, "店舗名"),
                    "purchase_date": edit_purchase_date.isoformat(),
                    "purchase_price": int(edit_purchase_price),
                    "sale_status": edit_sale_status,
                    "listed_date": edit_listed_date.isoformat() if edit_listed_date else None,
                    "sale_date": edit_sale_date.isoformat() if edit_sale_date else None,
                    "sale_price": int(edit_sale_price) if edit_sale_price > 0 else None,
                    "shipping_cost": int(edit_shipping_cost) if edit_shipping_cost > 0 else None,
                    "handling_fee": int(edit_handling_fee) if edit_handling_fee > 0 else None,
                    "sales_channel": edit_sales_channel or None,
                }
                updated = repo.update_product(
                    product_no=selected.product_no,
                    updates=updates,
                    expected_revision=selected.revision,
                )
            except ExternalUpdateDetectedError:
                ERROR_LOGGER.error(
                    "Update conflict product_no=%s expected_revision=%s",
                    selected.product_no,
                    selected.revision,
                )
                st.error("更新できませんでした。外部更新を検知しました。再読み込み後に再実行してください。")
            except Exception as exc:
                ERROR_LOGGER.exception("Update failed product_no=%s updates=%s", selected.product_no, updates)
                st.error(f"更新に失敗しました: {exc}")
            else:
                AUDIT_LOGGER.info("UPDATE success product_no=%s", updated.product_no)
                st.session_state["flash_success"] = f"更新しました（商品No: {updated.product_no}）"
                st.session_state["flash_record"] = {
                    "product_no": updated.product_no,
                    "name": updated.name,
                    "store_name": updated.store_name,
                    "purchase_date": updated.purchase_date.isoformat(),
                    "purchase_price": updated.purchase_price,
                    "sale_status": updated.sale_status,
                }
                st.rerun()

    rows = [
        {
            "商品No": product.product_no,
            "商品名": product.name,
            "店舗名": product.store_name,
            "仕入日": product.purchase_date.isoformat(),
            "仕入額": product.purchase_price,
            "送料": product.shipping_cost or "—",
            "手数料": product.handling_fee or "—",
            "状態": product.sale_status,
            "重要度": _importance_label(product),
        }
        for product in filtered_products
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
