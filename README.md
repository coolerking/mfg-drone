# mfg_drone

Tello EDU を Wi-Fi 経由で制御し、ブラウザ上から手動操作・カメラ映像確認・対象オブジェクトの
自動追従を行う学習用 Web アプリケーション。フィジカル AI の「知覚 → 判断 → 制御」ループを
手元で体験することを目的とする。

> **安全に関する最重要事項**
> 本リポジトリは実機（プロペラを持つ飛行体）を動かすソフトウェアを含む。
> 機能を追加・変更する前に必ず [`docs/safety.md`](docs/safety.md) を読むこと。
> 安全機構（フェイルセーフ、緊急着陸、レート制限、ウォッチドッグ）に関わるコードを
> 変更する際は、AI エージェント（Claude Code 含む）が単独で確定させず、必ず人間のレビューを通すこと。

## 何を作るか

ブラウザから操作する単一ユーザー向けの開発用ツール。

- Tello EDU との接続確立 / 切断
- 手動飛行操作（カメラ映像を見ながら）
- 映像内の対象オブジェクトを矩形で指定
- 指定対象の自動追従の開始 / 停止
- どの状態からでも受理される緊急着陸

詳細な機能要件は [`docs/spec.md`](docs/spec.md) を参照。

## スコープ外（このプロジェクトでは作らない）

意図しない肥大化を防ぐため、以下は明示的にスコープ外とする。

- 屋外飛行・長距離飛行・GPS を前提とした機能（Tello EDU は屋内向け 80g 機）
- 複数機の編隊飛行（将来課題。初版は 1 機のみ）
- 複数オブジェクトの同時追従（初版は単一対象のみ）
- 機体オンボードでの推論（推論はすべて PC 側で行う）
- マルチユーザー / 認証 / 公開ネットワークへのデプロイ（ローカル LAN 内利用のみ）
- 録画・撮影データのクラウド保存

## ハードウェア / ネットワーク前提

| 項目 | 値 |
| --- | --- |
| 機体 | Ryze Tech / DJI Tello EDU（SDK 2.0） |
| 接続方式 | ステーションモード（Tello を自宅 LAN の子機として接続） |
| 機体 IP | DHCP 予約で固定する想定（例: `192.168.1.50`） |
| 通信 | UDP（コマンド :8889 / ステート :8890 / 映像 :11111） |
| 開発機 | Ubuntu、Tello と同一セグメントに配置 |

ステーションモードへの切り替え手順は [`docs/architecture.md`](docs/architecture.md) を参照。

## 技術スタック

- バックエンド: Python 3.11+ / FastAPI / djitellopy / OpenCV
- フロントエンド: 素の HTML / CSS / JavaScript（ビルド不要）
- パッケージ管理: [uv](https://docs.astral.sh/uv/)

## セットアップ（Ubuntu）

```bash
# uv の導入（未インストールの場合）
curl -LsSf https://astral.sh/uv/install.sh | sh

cd ~/projects/mfg_drone

# 依存解決と仮想環境作成
uv sync

# 環境変数ファイルを用意
cp .env.example .env
#  → .env を編集して TELLO_IP などを設定

# モックモード（実機なし）で起動して UI を確認
uv run uvicorn backend.app.main:app --reload
#  → ブラウザで http://localhost:8000 を開く
```

> 初回は必ず **モックモード**（`TELLO_MODE=mock`）で UI とロジックを確認すること。
> 実機での飛行確認は人間が立ち会うステップに分離する。詳細は `docs/safety.md`。

## ドキュメント

| ファイル | 内容 |
| --- | --- |
| [`docs/spec.md`](docs/spec.md) | 機能要件（ユーザーストーリー + 受け入れ条件）＝リビングスペック |
| [`docs/architecture.md`](docs/architecture.md) | モジュール構成・状態機械・API 仕様 |
| [`docs/safety.md`](docs/safety.md) | 安全要件とガードレール（**変更前に必読**） |
| [`docs/milestones.md`](docs/milestones.md) | 検証可能な単位に分割した開発マイルストーン |
| [`reference/tello-sdk2.md`](reference/tello-sdk2.md) | Tello SDK 2.0 コマンド一次情報 |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code 向けの作業ガイドとガードレール |

## 免責

本ソフトウェアは学習目的。飛行に際しては航空法・各自治体のルール・第三者の安全に
十分配慮し、自己責任で運用すること。
