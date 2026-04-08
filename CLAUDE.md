# CLAUDE.md

このファイルは、本リポジトリを扱うAIアシスタント向けのコードベース解説です。

## プロジェクト概要

**sapporo-gomi-to-slack** は、札幌市のゴミ収集日を毎日Slackに通知するミニマルなAWS Lambdaアプリケーションです。

- 札幌市公式の音声読み上げ用ゴミカレンダーページをスクレイピング
- 日本語の自然言語HTML（例：「毎週月・水曜日は燃やせるごみは、...」）を正規表現で解析
- 毎日22時（JST）にSlackへ「明日のゴミ種別」を通知

## リポジトリ構成

```
sapporo-gomi-to-slack/
├── app.py               # アプリケーション全体のロジック（164行）
├── requirements.txt     # Python依存ライブラリ（requestsのみ）
├── README.md            # セットアップ・デプロイ手順（日本語）
└── .chalice/
    └── config.json      # Chaliceデプロイ設定 + 環境変数
```

サブディレクトリ・テスト・CI/CD設定は存在しません。

## 技術スタック

- **ランタイム**: Python 3 on AWS Lambda
- **フレームワーク**: [AWS Chalice](https://aws.github.io/chalice/index) — Lambdaパッケージング・CloudWatch Eventsスケジュール管理
- **トリガー**: CloudWatch Events cron `Cron(0, 13, '?', '*', '*', '*')` → UTC 13:00 = JST 22:00
- **依存ライブラリ**: `requests`（HTTPスクレイピング）、その他は標準ライブラリのみ

## 環境変数

`.chalice/config.json` の `stages.dev.environment_variables` に設定します。

| 変数名 | 説明 |
|---|---|
| `SLACK_WEBHOOK` | SlackのIncoming Webhook URL |
| `SAPPORO_GOMI_URI` | 札幌市ゴミカレンダー音声読み上げページのURL |

デプロイ前に必ず設定が必要です。実際の値はリポジトリにコミットしないでください。

## デプロイ手順

AWS CLIとChaliceをインストール・設定した上で実行します。

```bash
pip install chalice requests
chalice deploy
```

Chaliceが自動的にLambda関数・IAMロール・CloudWatch Eventsルールを作成します。デプロイされるLambda名は `sapporo-gomi-dev-every_hour` です。

削除する場合：

```bash
chalice delete
```

## アプリケーションロジック（`app.py`）

### エントリーポイント

```python
@app.schedule(Cron(0, 13, '?', '*', '*', '*'))
def every_hour(event):
    get_target_gomi_phrase()
```

### 呼び出しの流れ

1. `get_target_gomi_phrase()` — HTMLを取得・解析し、Slack通知を送信
2. `get_year_and_month_phrase(target_date)` — 当月を「令和X年Y月」形式で返す（令和年 = `西暦年 - 2018`）
3. `create_knowledge_dict(target, target_date)` — `re.sub` で逐次的に各ゴミ種別のスケジュールを抽出し `Knowledge` オブジェクトに格納
4. `what_type_is_by_knowledge(knowledge, target_date)` — 明日のゴミ種別を文字列で返す
5. `create_slack_body(target)` — Slackメッセージを整形（収集なしの場合は `None` を返す）
6. `send_slack(body)` — Slack WebhookにPOST

### `Knowledge` クラス

各ゴミ種別の収集日リストを保持するデータコンテナです。

| 属性 | ゴミ種別 | スケジュール形式 |
|---|---|---|
| `burnable` | 燃やせるごみ | 毎週X曜日 |
| `no_burnable` | 燃やせないごみ | 特定日 |
| `pla` | 容器包装プラスチック | 毎週X曜日 |
| `pet` | びん・缶・ペットボトル | 毎週X曜日 |
| `paper` | 雑がみ | 特定日 |
| `kusa` | 枝・葉・草 | 特定日 |

### スケジュール解析ヘルパー

- `get_days_knowledge_every_weeks(target, year, month)` — 「毎週X曜日」パターン用。その月の全日付を走査して曜日名を照合し、該当日を返す
- `get_days_knowledge_days(target)` — 「X日、Y日」パターン用。「ありません」が含まれる場合は `[]` を返す

### Slackメッセージ形式

```
チャンネル: #iwama_gomi
ユーザー名: 札幌ごみの日
テキスト:   明日は、{ゴミ種別}です。
```

`what_type_is_by_knowledge` が `"何もない"` を返した場合はSlack通知を送信しません。

## 既知の問題・脆弱性

- **エラーハンドリングなし**: ネットワークエラー・HTML形式変更・環境変数未設定など、あらゆるエラーでサイレントクラッシュします（CloudWatch Logsを確認してください）
- **正規表現によるHTML解析**: 札幌市の音声読み上げHTML形式に強く依存しており、形式が変わると動作しなくなります
- **`Knowledge` クラスのクラス変数**: リストがクラス変数として定義されているため、複数インスタンス化すると値が共有されます
- **型の不一致バグ**: `get_days_knowledge_days` は文字列のリストを返すのに対し、`what_type_is_by_knowledge` では `target_date.day`（整数）と比較します。そのため `no_burnable`・`paper`・`kusa` の判定が常に失敗する可能性があります
- **テストなし**: テストスイートが存在しません
- **Slackチャンネルのハードコード**: `#iwama_gomi` が `send_slack()` にハードコードされています
- **コメントアウトされたRESTルート**: 12〜15行目にある `@app.route('/')` は廃止されたアプローチの名残です

## コーディング規約

- ユーザー向け文字列・docstring・ログ出力はすべて日本語
- デバッグは `print()` で実施（CloudWatch Logsで確認可能）
- ロギングフレームワークは使用しない
- ロジックはすべて `app.py` 1ファイルに集約する

## ローカル開発メモ

- ローカル実行モードはありません。動作確認は環境変数を設定した上でPython REPLから `get_target_gomi_phrase()` を直接呼び出してください
- `.gitignore` により `.chalice/deployments/`・`.chalice/venv/`・`vendor/` はGit管理外です。これらはコミットしないでください
- `SLACK_WEBHOOK` および `SAPPORO_GOMI_URI` の実際の値はリポジトリにコミットしないでください
