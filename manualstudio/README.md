# ManualStudio

画面録画（MP4/MOV）から操作マニュアル用スライド（PPTX）と手順JSONを自動生成するWebアプリケーション。

## 機能概要

- 画面録画動画をアップロード
- 音声の自動文字起こし（OpenAI Whisper）
- 画面転換の自動検出（PySceneDetect）
- LLMによる操作手順の構造化（OpenAI GPT-4）
- PowerPointスライドの自動生成
- Webブラウザでの結果プレビュー

## アーキテクチャ

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   FastAPI   │────▶│   Celery    │
│  (Jinja2)   │     │   Backend   │     │   Worker    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                   │
                           ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  PostgreSQL │     │    MinIO    │
                    │    (DB)     │     │  (Storage)  │
                    └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Redis    │
                    │  (Broker)   │
                    └─────────────┘
```

## 技術スタック

- **Backend**: Python 3.11+, FastAPI, Celery
- **Database**: PostgreSQL 15
- **Cache/Broker**: Redis 7
- **Storage**: MinIO (S3互換)
- **動画処理**: FFmpeg, PySceneDetect
- **音声認識**: OpenAI Whisper API
- **LLM**: OpenAI GPT-4o / Anthropic Claude
- **PPTX生成**: python-pptx

## セットアップ

### 必要条件

- Docker & Docker Compose
- OpenAI APIキー または Anthropic APIキー

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd manualstudio
```

### 2. 環境変数の設定

```bash
cp .env.example .env
```

`.env` ファイルを編集し、必要な値を設定:

```bash
# LLMプロバイダーの選択（openai, anthropic, mock）
LLM_PROVIDER=openai

# OpenAIを使用する場合
OPENAI_API_KEY=sk-your-api-key-here

# Anthropic Claudeを使用する場合
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-your-api-key-here
# ANTHROPIC_MODEL=claude-sonnet-4-20250514  # オプション（デフォルト）
# ANTHROPIC_MAX_TOKENS=4000  # オプション（デフォルト）

# オプション: その他の設定
MAX_VIDEO_MINUTES=15
MAX_VIDEO_SIZE_MB=1024
```

### LLMプロバイダーについて

ManualStudioはOpenAIとAnthropic Claudeの両方に対応しています：

| プロバイダー | 設定値 | 必要なAPIキー | デフォルトモデル |
|------------|-------|--------------|-----------------|
| OpenAI | `openai` | `OPENAI_API_KEY` | gpt-4o |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 |
| Mock（テスト用） | `mock` | なし | - |

**Anthropicを使う場合:**
```bash
# .envに以下を設定
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-xxx

# オプション: 別のモデルを指定
ANTHROPIC_MODEL=claude-opus-4-20250514
ANTHROPIC_MAX_TOKENS=8000
```

**注意事項:**
- CIテストではmockプロバイダーを使用するため、実APIは呼び出されません
- 実APIでの動作確認は手動スモークテストで行ってください（後述）

### 3. 起動

```bash
docker-compose up --build
```

初回起動時は以下が自動的に行われます:
- PostgreSQLのデータベース作成
- MinIOのバケット作成
- データベースマイグレーション

### 4. アクセス

- **Web UI**: http://localhost:8000
- **MinIO Console**: http://localhost:9001 (admin: minioadmin/minioadmin)

## 使い方

### 1. 動画のアップロード

1. ブラウザで http://localhost:8000 にアクセス
2. 画面録画ファイル（MP4/MOV）を選択
3. タイトルと目的を入力（任意）
4. 「アップロードして生成開始」をクリック

**バッチアップロード（複数ファイル）:**
1. 「バッチモード」チェックボックスをオンにする
2. 複数の動画ファイルを選択（最大10件）
3. タイトル接頭辞と共通の目的を入力
4. 「バッチアップロード開始」をクリック
5. 処理結果が表示されたら「ジョブ一覧を見る」で確認

### 2. ジョブ一覧と管理

http://localhost:8000/jobs でジョブ一覧を確認・管理できます:

- **フィルタ**: ステータス（QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELED）で絞り込み
- **検索**: タイトルや目的で検索
- **ページング**: 20件ずつ表示、ページ切り替え
- **自動更新**: 処理中のジョブがある場合は5秒ごとに自動更新

**ジョブ操作:**
- **キャンセル**: QUEUED/RUNNINGのジョブをキャンセル
- **リトライ**: FAILEDのジョブを再実行

### 3. 処理の確認

ジョブ詳細ページで処理状況を確認できます:
- **QUEUED**: 待機中
- **RUNNING**: 処理中（ステージと進捗率を表示）
- **SUCCEEDED**: 完了
- **FAILED**: 失敗（エラーメッセージを表示）
- **CANCELED**: キャンセル済み

### 4. 結果のダウンロード

処理完了後、以下の形式でダウンロードできます:
- **PPTX**: PowerPointスライド（プレゼンテーション用）
- **Markdown (.md)**: テキスト形式のマニュアル（Notion/GitHub/Confluence向け）
- **HTML (.html)**: スタンドアロンのWebページ（メール添付/社内ポータル向け）
- **frames.zip**: 抽出されたフレーム画像

**用途別おすすめ形式:**
| 用途 | 推奨形式 |
|------|---------|
| プレゼンテーション/研修 | PPTX |
| ナレッジベース（Notion等）| Markdown |
| メール添付/Webポータル | HTML |
| 画像の再利用 | frames.zip |

### 5. 手順の編集とPPTX再生成

処理完了後、生成された手順を編集してPPTXを再生成できます:

1. ジョブ詳細ページで「ステッププレビュー」をクリック
2. 「編集モード」ボタンをクリックして編集モードに切り替え
3. 各ステップのテロップ、操作説明、ナレーションなどを編集
4. 「保存」ボタンをクリックして変更を保存（新しいバージョンが作成されます）
5. 「PPTX再生成」ボタンをクリックして更新されたPPTXを生成

編集可能な項目:
- タイトル、目的
- 各ステップのテロップ（15文字以内推奨）
- 操作説明、操作対象
- ナレーション
- 注意事項

バージョン履歴により、過去の編集内容も保持されます。

### 6. テーマ設定（企業向けカスタマイズ）

生成されるPPTXにロゴ、カラー、フッターを設定できます：

1. ステッププレビューページで「テーマ設定」セクションを展開
2. 以下を設定:
   - **プライマリカラー**: タイトルと見出しの色（#RRGGBB形式）
   - **フッターテキスト**: 各スライド下部に表示するテキスト（例: © 2026 Your Company）
   - **ロゴ画像**: 各スライド右上に表示するロゴ（PNG/JPG、最大1MB）
3. 「テーマを保存」をクリックして設定を保存
4. 「保存してPPTX再生成」をクリックすると保存と再生成を一度に実行

**ロゴ仕様:**
- 形式: PNG, JPG, JPEG
- サイズ上限: 1MB
- 推奨サイズ: 約120×60px（自動リサイズされます）

**注意:**
- テーマ設定は動画の再処理を行わず、既存のフレームを使用してPPTXのみを再生成します
- フッターとロゴの表示/非表示はチェックボックスで切り替え可能

## 処理パイプライン

1. **INGEST**: 動画のアップロードと検証
2. **EXTRACT_AUDIO**: 音声トラックの抽出
3. **TRANSCRIBE**: 音声の文字起こし
4. **DETECT_SCENES**: 画面転換の検出
5. **EXTRACT_FRAMES**: 代表フレームの抽出
6. **GENERATE_STEPS**: LLMによる手順生成
7. **GENERATE_PPTX**: スライド生成
8. **FINALIZE**: 成果物の保存

## API仕様

### ジョブ作成
```
POST /api/jobs
Content-Type: multipart/form-data

Fields:
- video_file: 動画ファイル (必須)
- title: タイトル (任意)
- goal: 目的 (任意)
- language: 言語コード (デフォルト: ja)

Response: { "job_id": "uuid", "status": "QUEUED" }
```

### ジョブ一覧取得
```
GET /api/jobs?status=QUEUED&q=検索キーワード&page=1&page_size=20&sort=-created_at

Query Parameters:
- status: ステータスでフィルタ (QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELED)
- q: タイトル/目的で検索
- page: ページ番号 (デフォルト: 1)
- page_size: 1ページあたりの件数 (デフォルト: 20、最大: 100)
- sort: ソート順 (created_at / -created_at)

Response: {
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

### バッチジョブ作成
```
POST /api/jobs/batch
Content-Type: multipart/form-data

Fields:
- video_files: 動画ファイル（複数、最大10件）
- title_prefix: タイトル接頭辞 (任意)
- goal: 共通の目的 (任意)
- language: 言語コード (デフォルト: ja)

Response: {
  "created": [{"job_id": "uuid", "file": "filename", "status": "QUEUED"}, ...],
  "errors": [{"file": "filename", "error": "エラーメッセージ"}, ...],
  "total_created": 3,
  "total_errors": 0
}
```

### ジョブ状態取得
```
GET /api/jobs/{job_id}

Response: { "job_id", "status", "stage", "progress", ... }
```

### ジョブキャンセル
```
POST /api/jobs/{job_id}/cancel

Constraints:
- QUEUED または RUNNING のジョブのみキャンセル可能
- その他のステータスでは 409 Conflict を返す

Response: { "job_id": "uuid", "status": "CANCELED", "message": "..." }
```

### ジョブリトライ
```
POST /api/jobs/{job_id}/retry

Constraints:
- FAILED のジョブのみリトライ可能
- その他のステータスでは 409 Conflict を返す
- ジョブを最初から再実行

Response: { "job_id": "uuid", "status": "QUEUED", "trace_id": "...", "message": "..." }
```

### steps.json取得
```
GET /api/jobs/{job_id}/steps?version=N

Response: { "version": N, "edit_source": "llm", "steps_json": {...} }
```

### steps.json更新
```
PUT /api/jobs/{job_id}/steps
Content-Type: application/json

Body: { "steps_json": {...}, "edit_note": "編集メモ" }
Response: { "job_id": "uuid", "version": N, "message": "..." }
```

### バージョン履歴取得
```
GET /api/jobs/{job_id}/steps/versions

Response: { "current_version": N, "versions": [...] }
```

### PPTX再生成
```
POST /api/jobs/{job_id}/regenerate/pptx

Response: { "job_id": "uuid", "status": "RUNNING", "task_id": "..." }
```

### PPTXダウンロード
```
GET /api/jobs/{job_id}/download/pptx

Response: Redirect to presigned URL
```

### Markdownダウンロード
```
GET /api/jobs/{job_id}/download/markdown

Content-Type: text/markdown; charset=utf-8
Content-Disposition: attachment; filename*=UTF-8''...

Response: Markdown形式のマニュアルテキスト
```

**出力内容:**
- タイトル、目的
- 全ステップ（番号、テロップ、操作説明、注意事項）
- よくある間違いと対処法
- 確認クイズ

### HTMLダウンロード
```
GET /api/jobs/{job_id}/download/html

Content-Type: text/html; charset=utf-8
Content-Disposition: attachment; filename*=UTF-8''...

Response: 完全なHTMLドキュメント（CSS含む、スタンドアロン）
```

**特徴:**
- スタンドアロンHTMLファイル（外部依存なし）
- レスポンシブデザイン
- XSS対策済み（全ユーザー入力をエスケープ）

### テーマ取得
```
GET /api/jobs/{job_id}/theme

Response: {
  "primary_color": "#667EEA",
  "footer_text": null,
  "logo_uri": null,
  "show_logo": true,
  "show_footer": true
}
```

### テーマ更新
```
PUT /api/jobs/{job_id}/theme
Content-Type: application/json

Body: {
  "primary_color": "#FF0000",
  "footer_text": "© 2026 Company",
  "show_logo": true,
  "show_footer": true
}

Response: {
  "job_id": "uuid",
  "theme": {...},
  "message": "Theme updated successfully..."
}
```

### ロゴアップロード
```
POST /api/jobs/{job_id}/theme/logo
Content-Type: multipart/form-data

Fields:
- logo_file: PNG/JPG画像 (必須、最大1MB)

Response: {
  "job_id": "uuid",
  "logo_uri": "s3://bucket/jobs/{job_id}/assets/logo.png",
  "message": "Logo uploaded successfully..."
}
```

## steps.json スキーマ

```json
{
  "title": "マニュアルタイトル",
  "goal": "このマニュアルの目的",
  "language": "ja",
  "source": {
    "video_duration_sec": 120.5,
    "video_fps": 30,
    "resolution": "1920x1080",
    "transcription_provider": "openai",
    "llm_provider": "openai"
  },
  "steps": [
    {
      "no": 1,
      "start": "00:00",
      "end": "00:20",
      "shot": "00:10",
      "frame_file": "step_001.png",
      "telop": "アプリを起動",
      "action": "デスクトップのアイコンをダブルクリックします",
      "target": "アプリアイコン",
      "narration": "まず、デスクトップにあるアプリのアイコンをダブルクリックして起動してください。",
      "caution": "管理者権限が必要な場合があります"
    }
  ],
  "common_mistakes": [
    {"mistake": "よくあるミス", "fix": "対処法"}
  ],
  "quiz": [
    {"type": "choice", "q": "質問", "choices": ["A", "B", "C", "D"], "a": "A"}
  ]
}
```

## 設定オプション

| 環境変数 | 説明 | デフォルト |
|---------|------|-----------|
| `DATABASE_URL` | PostgreSQL接続URL | (docker-compose設定) |
| `REDIS_URL` | Redis接続URL | (docker-compose設定) |
| `S3_ENDPOINT_URL` | S3/MinIOエンドポイント | http://minio:9000 |
| `S3_BUCKET` | ストレージバケット名 | manualstudio |
| `OPENAI_API_KEY` | OpenAI APIキー | (LLM_PROVIDER=openai時必須) |
| `ANTHROPIC_API_KEY` | Anthropic APIキー | (LLM_PROVIDER=anthropic時必須) |
| `ANTHROPIC_MODEL` | Anthropicモデル | claude-sonnet-4-20250514 |
| `ANTHROPIC_MAX_TOKENS` | Anthropic最大トークン数 | 4000 |
| `LLM_PROVIDER` | LLMプロバイダー (openai/anthropic/mock) | openai |
| `TRANSCRIBE_PROVIDER` | 文字起こしプロバイダー | openai |
| `MAX_VIDEO_MINUTES` | 動画の最大長さ（分） | 15 |
| `MAX_VIDEO_SIZE_MB` | 動画の最大サイズ（MB） | 1024 |
| `LOG_LEVEL` | ログレベル | INFO |

## トラブルシューティング

### よくある問題

#### 1. 「OPENAI_API_KEY not configured」または「ANTHROPIC_API_KEY not configured」エラー

`.env` ファイルに使用するプロバイダーのAPIキーが設定されていません。

```bash
# .envファイルを確認
cat .env | grep -E "(OPENAI|ANTHROPIC|LLM_PROVIDER)"

# OpenAI使用時
echo "LLM_PROVIDER=openai" >> .env
echo "OPENAI_API_KEY=sk-your-key-here" >> .env

# Anthropic使用時
echo "LLM_PROVIDER=anthropic" >> .env
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> .env

# コンテナを再起動
docker-compose restart backend worker
```

#### 2. 「Video too long」エラー

動画が最大長さ（デフォルト15分）を超えています。

```bash
# .envで上限を変更
MAX_VIDEO_MINUTES=30
```

#### 3. 処理が RUNNING のまま進まない

Celeryワーカーのログを確認:

```bash
docker-compose logs -f worker
```

ワーカーを再起動:

```bash
docker-compose restart worker
```

#### 4. MinIOに接続できない

MinIOの起動を確認:

```bash
docker-compose ps minio
docker-compose logs minio
```

#### 5. 「ffprobe failed」エラー

動画ファイルが破損している可能性があります。別の動画ファイルで試してください。

### ログの確認

```bash
# 全サービスのログ
docker-compose logs -f

# 特定サービスのログ
docker-compose logs -f backend
docker-compose logs -f worker

# Trace IDで検索
docker-compose logs | grep "abc12345"
```

### データベースの確認

```bash
docker-compose exec postgres psql -U manualstudio -d manualstudio

# ジョブ一覧
SELECT id, status, stage, progress, error_message FROM jobs;
```

### ストレージの確認

MinIO Console (http://localhost:9001) にアクセスして、バケット内のファイルを確認できます。

## 開発

### ローカル開発環境

```bash
# バックエンドの依存関係インストール
cd backend
pip install -r requirements.txt -r requirements-worker.txt

# 開発用サーバー起動（DB/Redis/MinIOはDockerで）
docker-compose up postgres redis minio minio-init -d

# FastAPI起動
uvicorn app.main:app --reload

# Celeryワーカー起動（別ターミナル）
celery -A app.workers.celery_app worker --loglevel=info
```

### テスト

#### ユニットテスト（Docker不要）

```bash
cd backend

# 開発用依存関係のインストール
pip install -r requirements-dev.txt

# 全テストを実行（mockプロバイダーを使用、APIキー不要）
TRANSCRIBE_PROVIDER=mock LLM_PROVIDER=mock pytest tests/ -v

# 特定のテストファイルを実行
pytest tests/test_e2e.py
pytest tests/test_api_steps.py
pytest tests/test_security.py
pytest tests/test_pptx_regeneration.py

# カバレッジレポート付きで実行
pytest tests/ --cov=app --cov-report=html
```

テストは mock プロバイダーを使用するため、OpenAI APIキーは不要です。

#### Docker E2Eスモークテスト

Docker環境でフルパイプラインをテストする場合：

```bash
# mockプロバイダーでDocker起動
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d

# E2Eスモークテスト実行（ffmpegでテスト動画を生成）
./scripts/e2e_smoke_test.sh http://localhost:8000

# 終了
docker compose down
```

#### 手動スモークテスト（実API）

CIでは外部APIを呼び出しません。実APIでの動作確認は手動で行ってください：

```bash
# 1. Docker環境を起動（Anthropicの場合）
LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-xxx docker-compose up -d

# 2. テスト用動画をアップロード
curl -X POST http://localhost:8000/api/jobs \
  -F "video_file=@sample.mp4" \
  -F "title=Test" \
  -F "goal=Testing Anthropic"

# 3. ジョブ状態を確認
curl http://localhost:8000/api/jobs/{job_id}

# 4. steps.jsonを確認（llm_providerがanthropicになっていること）
curl http://localhost:8000/api/jobs/{job_id}/steps | jq '.steps_json.source.llm_provider'
# 期待値: "anthropic"
```

**確認ポイント:**
- ジョブがSUCCEEDEDになること
- `steps.json` の `source.llm_provider` が設定したプロバイダー名になっていること
- 生成されたstepsがJSON schema準拠であること

#### CI（GitHub Actions）

PRを作成すると自動的にCIが実行されます：
- Python 3.11でユニットテスト実行
- ruffによるlint/format チェック
- mockプロバイダーを使用（外部API不要、実APIは呼び出されません）

ローカルでCIと同じ環境を再現する場合：

```bash
cd backend
pip install ruff

# lintチェック
ruff check app/ tests/

# formatチェック
ruff format app/ tests/ --check
```

#### テストファイル構成

| ファイル | 説明 |
|---------|------|
| `tests/conftest.py` | pytest フィクスチャ（テストDB、モックストレージ、クライアント）|
| `tests/test_e2e.py` | E2Eスモークテスト |
| `tests/test_api_steps.py` | Steps API のユニットテスト |
| `tests/test_jobs_api.py` | ジョブ一覧/バッチ/キャンセル/リトライのテスト |
| `tests/test_export.py` | Markdown/HTMLエクスポートのテスト（XSS防止含む）|
| `tests/test_pptx_regeneration.py` | PPTX再生成のテスト |
| `tests/test_security.py` | セキュリティ回帰テスト |
| `tests/test_theme.py` | テーマ設定のテスト |
| `tests/test_llm_provider.py` | LLMプロバイダー選択のテスト |
| `tests/test_utils.py` | ユーティリティ関数のテスト |
| `tests/fixtures/` | テスト用フィクスチャデータ |

#### 環境変数（テスト用）

| 変数 | 説明 | テスト時の値 |
|------|------|-------------|
| `TRANSCRIBE_PROVIDER` | 文字起こしプロバイダー | `mock` |
| `LLM_PROVIDER` | LLMプロバイダー | `mock` |
| `DATABASE_URL` | データベースURL | `sqlite:///:memory:` (ユニットテスト) |

### Python バージョン

- **推奨**: Python 3.11+
- **注意**: Python 3.9/3.10では一部のライブラリ（python-pptx等）の動作が異なる場合があります

### マイグレーション

```bash
# 新しいマイグレーション作成
alembic revision --autogenerate -m "description"

# マイグレーション適用
alembic upgrade head

# ダウングレード
alembic downgrade -1
```

## 制限事項

- 動画の最大長さ: 15分（設定変更可能）
- 動画の最大サイズ: 1GB（設定変更可能）
- 対応フォーマット: MP4, MOV, AVI, MKV, WebM
- 音声なし動画: 文字起こしはスキップされ、フレームのみで手順生成

## 今後の拡張

- [x] 手順の手動編集機能
- [x] PPTX再生成機能
- [x] バージョン履歴管理
- [x] テーマ設定（ロゴ/カラー/フッター）
- [x] Claude対応（Anthropic API）
- [x] ジョブ一覧・検索・フィルタ
- [x] バッチ処理（複数動画の一括処理）
- [x] ジョブキャンセル・リトライ
- [x] エクスポート拡充（Markdown/HTML）
- [ ] SRTエクスポート（字幕ファイル）※後述
- [ ] スライドテンプレートのカスタマイズ
- [ ] 複数言語対応の強化
- [ ] Azure/AWS Transcribe対応

### SRTエクスポートについて

現在、SRT（字幕）エクスポートは未実装です。理由と今後の計画：

**見送り理由:**
- 現在のパイプラインでは、transcript segments（タイムスタンプ付きの文字起こしデータ）がジョブ完了後に保存されていない
- steps.jsonにはステップ単位の時間範囲はあるが、単語レベルのタイムスタンプは含まれていない

**実装ロードマップ:**
1. transcript segmentsのDB/Storage保存を追加（パイプライン変更）
2. GET /api/jobs/{job_id}/download/srt エンドポイントを追加
3. ステップのナレーションをSRT形式に変換するロジック実装

## ライセンス

MIT License
