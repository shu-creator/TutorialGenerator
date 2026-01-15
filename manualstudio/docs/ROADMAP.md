# ManualStudio ロードマップ

## 現在の状態（Sprint 2完了時点）

### 完了済み機能
- [x] 基本パイプライン（動画→音声→文字起こし→LLM→PPTX）
- [x] 手順編集機能（PUT /api/jobs/{id}/steps）
- [x] PPTX再生成機能（POST /api/jobs/{id}/regenerate/pptx）
- [x] バージョン履歴管理（steps_versions テーブル）
- [x] Mock プロバイダー（テスト用）
- [x] CI/CD（GitHub Actions）
- [x] セキュリティテスト（パストラバーサル等）

---

## P2: テーマ設定機能（設計案）

### 概要
ジョブ単位でPPTXのテーマ（ロゴ、カラー、フッター）をカスタマイズ可能にする。

### データベース設計

```sql
-- jobs テーブルに追加
ALTER TABLE jobs ADD COLUMN theme_config JSONB;
```

```python
# theme_config JSON スキーマ
{
    "logo_uri": "s3://bucket/logos/company.png",  # Optional
    "primary_color": "#667eea",                    # Hex color
    "secondary_color": "#764ba2",                  # Hex color
    "footer_text": "© 2024 Company Name",          # Optional
    "font_family": "Noto Sans JP"                  # Optional
}
```

### API 変更

```
POST /api/jobs
  + theme_config: JSON (optional)

PUT /api/jobs/{job_id}/theme
  Body: { "logo_uri": "...", "primary_color": "...", ... }
  Response: { "job_id": "...", "message": "Theme updated" }

GET /api/jobs/{job_id}/theme
  Response: { "theme_config": {...} }
```

### 実装ポイント

1. **ロゴアップロード**
   - 新規エンドポイント: `POST /api/logos`
   - S3に保存、URI を返却
   - ファイル形式: PNG/SVG、最大1MB

2. **PPTXGenerator 拡張**
   - `generate()` メソッドに `theme_config` パラメータ追加
   - ロゴ: タイトルスライドと各スライドフッターに配置
   - カラー: テロップ背景、アクセントカラーに適用

3. **バリデーション**
   - カラーコード: `#[0-9a-fA-F]{6}` パターン
   - ロゴURI: S3 URI形式チェック

### 影響範囲
- `app/db/models.py` - Job モデルに theme_config 追加
- `app/api/routes.py` - テーマ関連エンドポイント追加
- `app/services/pptx_generator.py` - テーマ適用ロジック
- `alembic/versions/` - マイグレーション追加

---

## P3: Anthropic/Claude プロバイダー（設計案）

### 概要
OpenAI に加えて Anthropic Claude を LLM プロバイダーとして使用可能にする。

### 環境変数

```bash
# 新規追加
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-20250514  # Default

# 既存（LLM_PROVIDER で切り替え）
LLM_PROVIDER=anthropic  # or "openai" or "mock"
```

### プロバイダー抽象化

現在の構造（既に抽象化済み）:

```
LLMProvider (ABC)
├── OpenAILLMProvider
├── AnthropicLLMProvider  # 既存だが未テスト
└── MockLLMProvider
```

### 実装チェックリスト

1. **AnthropicLLMProvider 検証**
   - [ ] 既存実装の動作確認
   - [ ] エラーハンドリングの強化
   - [ ] レスポンス形式の差異対応

2. **設定**
   - [ ] `ANTHROPIC_MODEL` 環境変数追加
   - [ ] モデル選択のバリデーション

3. **テスト**
   - [ ] MockLLMProvider で Anthropic レスポンス形式をシミュレート
   - [ ] 切り替えテスト（openai ⇔ anthropic）

4. **ドキュメント**
   - [ ] README に Anthropic 設定方法を追記
   - [ ] モデル比較表（GPT-4o vs Claude 3.5 Sonnet）

### Anthropic 固有の考慮事項

- **レスポンス形式**: `message.content[0].text` でテキスト取得
- **JSON モード**: Claude は `response_format={"type": "json_object"}` 非対応
  - 代替: プロンプトで JSON 出力を強く指示
- **レート制限**: Tier による差異を考慮

### コード変更例

```python
# app/services/llm.py

class AnthropicLLMProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        # ...

    def generate(self, prompt: str, system_prompt: str) -> str:
        # JSON出力を強制するプロンプト修正
        json_prompt = f"{prompt}\n\n必ずJSONのみを出力してください。"
        # ...
```

---

## P4以降の候補機能

| 優先度 | 機能 | 説明 |
|--------|------|------|
| P4 | バッチ処理 | 複数動画の一括処理 |
| P4 | Azure/AWS Transcribe | 追加の文字起こしプロバイダー |
| P5 | スライドテンプレート | PPTXテンプレートのアップロード・適用 |
| P5 | 多言語対応強化 | 英語・中国語等の最適化 |
| P6 | Webhook通知 | 処理完了時の外部通知 |
| P6 | ユーザー認証 | マルチテナント対応 |

---

## 開発ガイドライン

### 新規プロバイダー追加時のチェックリスト

1. `app/services/` に Provider クラス追加
2. `get_xxx_service()` 関数で Provider 選択ロジック追加
3. `tests/fixtures/` に対応フィクスチャ追加
4. Mock プロバイダーで新形式をシミュレート
5. README に設定方法を追記
6. CI で Mock プロバイダーを使用してテスト

### テスト方針

- ユニットテスト: Mock プロバイダーで外部依存なし
- E2E テスト: Docker + Mock プロバイダー
- 本番検証: 手動で実APIを使用（CI外）
