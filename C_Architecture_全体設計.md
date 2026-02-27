# C. Architecture（全体設計）

## 1. 画面構成 / 画面遷移（ざっくり）

1. 接続設定画面  
   - Spreadsheet URL/ID、シート名、接続テスト
2. 商品一覧画面  
   - 検索、フィルタ、並び替え、詳細遷移
3. 商品登録画面  
   - 必須項目入力、保存
4. 商品編集画面  
   - 更新、外部更新検知、保存
5. ダッシュボード画面  
   - 期間指定、売上/仕入/利益、販売先別集計

基本遷移: `一覧 -> 登録`、`一覧 -> 編集`、`一覧 -> ダッシュボード`。

## 2. データモデル（エンティティと主要項目）

### 商品（Product）

- `product_no`（主キー、文字列）
- `name`（商品名、文字列）
- `store_name`（店舗名、文字列）
- `purchase_date`（仕入日、日付）
- `purchase_price`（仕入額、数値）
- `sale_status`（未出品/出品済/売却済）
- `sale_date`（売却日、日付/任意）
- `sale_price`（売却額、数値/任意）
- `sales_channel`（販売先、文字列/任意）
- `is_archived`（論理削除フラグ、真偽値）
- `revision`（更新印、文字列または数値）
- `updated_at`（最終更新日時、日時）

### 集計ビュー（Dashboard View）

- `period_from` / `period_to`
- `total_sales`
- `total_purchase`
- `total_profit`
- `sales_by_channel`

## 3. 外部連携（役割と流れ）

### MVP（現在）

- Google Sheets API + gspread
  - 役割: 永続化、参照、更新、競合検知用revision保持
  - 流れ: アプリ -> 読込/検証 -> シート更新/再読込

### 将来拡張（Phase 4以降）

- LINE/Slack webhook（任意）
  - 役割: 通知・コマンド連携
  - 流れ: webhook受信 -> コマンド解釈 -> データ取得 -> 応答送信
  - 備考: MVP外。導入時にセキュリティと再送設計を追加定義する

## 4. ディレクトリ構成（案）

```text
project-root/
  app.py
  requirements.txt
  .env.example
  src/
    ui/
      pages/
        settings.py
        products_list.py
        product_form.py
        dashboard.py
    services/
      sheets_client.py
      product_service.py
      dashboard_service.py
    models/
      product.py
      schema.py
    utils/
      validators.py
      logger.py
  tests/
    test_product_service.py
    test_dashboard_service.py
  docs/
    A_Background_背景狙い.md
    B_PRD_要件定義.md
    C_Architecture_全体設計.md
    D_PhasePlan_フェーズ計画進捗ログ.md
    進捗管理表.md
```

## 5. ログ方針（どこに何を出すか）

- アプリログ: `logs/app.log`
  - 画面遷移、主要操作開始/終了、処理時間
- エラーログ: `logs/error.log`
  - 接続失敗、認証失敗、バリデーション失敗、API例外
- 監査ログ（最低限）: `logs/audit.log`
  - 登録/更新/アーカイブ（対象`product_no`、時刻、結果）
- 開発時はコンソールにも同内容を出力し、運用時はファイル優先

