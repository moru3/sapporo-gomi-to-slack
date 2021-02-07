# 札幌ゴミ情報

札幌市公式のゴミ収集日カレンダーの音声読み上げ用のフォーマットを分析して、明日の収集ゴミをSlackに通知するアプリ。
AWS Lamdaで動作し、Cloud Watch Eventsで発火する。デフォルトでは日本時間22時。（動作時刻を変更したい場合はapp.pyを編集する。）

## 注意点

札幌市ゴミ収集情報のフォーマットが、自然言語でプログラマブルな形式になっていないため、このフォーマットが崩れたりした場合は正しく動作しなくなります。
また、数少ないサンプルを元に分類コードを書いたので、そもそも正しくない場合があります。

## 利用フレームワーク・サービス

- AWS Chalice
- Slackアプリ（自分のアプリを作成し、Webhook URLを取得する必要がある。）
- 札幌市家庭ごみ収集日カレンダー、音声読み上げ用(https://www.city.sapporo.jp/seiso/kaisyu/yomiage/index.html)

## setup

./chalice/config.json への環境変数設定が必要。

**sample**

```json
{
  "version": "2.0",
  "app_name": "sapporo-gomi",
  "stages": {
    "dev": {
      "api_gateway_stage": "api",
      "environment_variables": {
        "SLACK_WEBHOOK": "https://hooks.slack.com/services/XXXXXXXXXXXX",
        "SAPPORO_GOMI_URI": "https://www.city.sapporo.jp/seiso/kaisyu/yomiage/carender/XXXXXXXXXXXXXXXXXXXXXX"
      }
    }
  }
}
```
## deploy

AWS Chaliceを利用している。Chaliceのセットアップを行い、以下のコマンドでdeployを行う。
https://aws.github.io/chalice/index

```
chalice deploy
```

**動作例**

```
$ chalice deploy
Creating deployment package.
Creating IAM role: sapporo-gomi-dev
Creating lambda function: sapporo-gomi-dev-every_hour
Resources deployed:
  - Lambda ARN: arn:aws:lambda:ap-northeast-1:534204886473:function:sapporo-gomi-dev-every_hour
```