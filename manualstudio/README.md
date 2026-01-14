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
- **LLM**: OpenAI GPT-4o
- **PPTX生成**: python-pptx

## セットアップ

### 必要条件

- Docker & Docker Compose
- OpenAI APIキー

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
# 必須: OpenAI APIキー
OPENAI_API_KEY=sk-your-api-key-here

# オプション: その他の設定
MAX_VIDEO_MINUTES=15
MAX_VIDEO_SIZE_MB=1024
```

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

### 2. 処理の確認

ジョブ詳細ページで処理状況を確認できます:
- **QUEUED**: 待機中
- **RUNNING**: 処理中（ステージと進捗率を表示）
- **SUCCEEDED**: 完了
- **FAILED**: 失敗（エラーメッセージを表示）

### 3. 結果のダウンロード

処理完了後、以下をダウンロードできます:
- **PPTX**: PowerPointスライド
- **frames.zip**: 抽出されたフレーム画像

### 4. 手順の編集とPPTX再生成

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

### ジョブ状態取得
```
GET /api/jobs/{job_id}

Response: { "job_id", "status", "stage", "progress", ... }
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
| `OPENAI_API_KEY` | OpenAI APIキー | (必須) |
| `LLM_PROVIDER` | LLMプロバイダー | openai |
| `TRANSCRIBE_PROVIDER` | 文字起こしプロバイダー | openai |
| `MAX_VIDEO_MINUTES` | 動画の最大長さ（分） | 15 |
| `MAX_VIDEO_SIZE_MB` | 動画の最大サイズ（MB） | 1024 |
| `LOG_LEVEL` | ログレベル | INFO |

## トラブルシューティング

### よくある問題

#### 1. 「OPENAI_API_KEY not configured」エラー

`.env` ファイルに `OPENAI_API_KEY` が設定されていません。

```bash
# .envファイルを確認
cat .env | grep OPENAI

# 設定されていない場合は追加
echo "OPENAI_API_KEY=sk-your-key-here" >> .env

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

```bash
cd backend

# 開発用依存関係のインストール
pip install -r requirements-dev.txt

# 全テストを実行
pytest tests/

# 詳細出力で実行
pytest tests/ -v

# 特定のテストファイルを実行
pytest tests/test_e2e.py
pytest tests/test_api_steps.py

# カバレッジレポート付きで実行
pytest tests/ --cov=app --cov-report=html
```

テストは mock プロバイダーを使用するため、OpenAI APIキーは不要です。

#### テストファイル構成

- `tests/conftest.py` - pytest フィクスチャ（テストDB、モックストレージ、クライアント）
- `tests/test_e2e.py` - E2Eスモークテスト
- `tests/test_api_steps.py` - Steps API のユニットテスト
- `tests/test_utils.py` - ユーティリティ関数のテスト
- `tests/fixtures/` - テスト用フィクスチャデータ

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
- [ ] スライドテンプレートのカスタマイズ
- [ ] 複数言語対応の強化
- [ ] Azure/AWS Transcribe対応
- [ ] Claude対応（Anthropic API）
- [ ] バッチ処理（複数動画の一括処理）

## ライセンス

MIT License
