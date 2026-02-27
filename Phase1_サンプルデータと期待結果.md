# Phase 1 サンプルデータと期待結果

## 1. データモデル（必須項目、型、例）

| 項目 | 必須 | 型 | 例 |
|---|---|---|---|
| product_no | 必須（自動採番可） | 文字列 | `P00001` |
| name | 必須 | 文字列 | `Levi's 505` |
| store_name | 必須 | 文字列 | `Shibuya` |
| purchase_date | 必須 | `YYYY-MM-DD` | `2026-02-20` |
| purchase_price | 必須 | 整数 | `4000` |
| sale_status | 必須 | 列挙（未出品/出品済/売却済） | `出品済` |
| sale_date | 任意 | `YYYY-MM-DD` | `2026-02-24` |
| sale_price | 任意 | 整数 | `9000` |
| sales_channel | 任意 | 文字列 | `メルカリ` |
| is_archived | 任意 | 真偽値 | `false` |
| revision | 必須（内部管理） | 文字列 | `2026-02-26T12:00:00+00:00` |
| updated_at | 必須（内部管理） | ISO日時 | `2026-02-26T12:00:00+00:00` |

## 2. 保存先仕様（どこに何を保存するか）

- 保存先: Googleスプレッドシートの1ワークシート
- 1行目: ヘッダー（上記12項目）
- 2行目以降: 商品データ
- 主キー: `product_no`
- 競合制御: `revision` を比較して一致時のみ更新

## 3. サンプルデータ

### Create入力（例）

```json
{
  "name": "Levi's 505",
  "store_name": "Shibuya",
  "purchase_date": "2026-02-20",
  "purchase_price": 4000,
  "sale_status": "出品済"
}
```

### Create後の期待値（例）

```json
{
  "product_no": "P00001",
  "name": "Levi's 505",
  "store_name": "Shibuya",
  "purchase_date": "2026-02-20",
  "purchase_price": 4000,
  "sale_status": "出品済",
  "sale_date": "",
  "sale_price": "",
  "sales_channel": "",
  "is_archived": false,
  "revision": "<自動発行ISO日時>",
  "updated_at": "<自動発行ISO日時>"
}
```

### Update入力（例）

```json
{
  "product_no": "P00001",
  "expected_revision": "<直前のrevision>",
  "updates": {
    "sale_status": "売却済",
    "sale_price": 9000
  }
}
```

### Update後の期待値（例）

- `sale_status` が `売却済` になる
- `sale_price` が `9000` になる
- `revision` が新しい値に更新される
- `updated_at` が新しい時刻に更新される

## 4. 完了条件チェック（Phase 1）

- [x] 1件追加できる
- [x] 一覧で取得できる
- [x] 更新できる
- [x] 古いrevisionでの更新が拒否される

