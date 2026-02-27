# Streamlit Cloud デプロイ手順

## 4. Google認証情報の設定

### 手順

**1. サイトを開く**

- [https://share.streamlit.io](https://share.streamlit.io) にアクセス
- GitHub でログイン済みの状態にする

**2. アプリの設定を開く**

- デプロイしたアプリの **名前** をクリック
- 右上の **「⋮」（3点メニュー）** をクリック
- **「Settings」** を選択

**3. Secrets を設定**

- 左メニューから **「Secrets」** をクリック
- 下のテキスト欄に、次の形式で貼り付け：

```toml
[gcp]
service_account = """
ここに service-account.json の内容をそのまま貼り付け
"""
```

**4. service-account.json の内容を取得**

- ローカルの `service-account.json` をテキストエディタで開く
- 中身全体をコピー（`{` から `}` まで）
- 上記の `"""` と `"""` の間に貼り付ける

**例（実際の値はあなたのファイルに合わせてください）：**

```toml
[gcp]
service_account = """
{
  "type": "service_account",
  "project_id": "あなたのプロジェクトID",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",
  "client_email": "...@....iam.gserviceaccount.com",
  "client_id": "...",
  ...
}
"""
```

**5. 保存**

- **「Save」** ボタンをクリック
- アプリが自動で再起動する（数分かかることがあります）

---

### 注意事項

- `service-account.json` は **絶対に GitHub にプッシュしない** でください
- Secrets に貼り付ける際、JSON の `\n` は `\\n` のようにエスケープが必要な場合があります（貼り付けたままの形式で問題ないことが多いです）
- エラーが出る場合は、JSON が 1 行になっているか、改行を削除して貼り直してみてください
