# CLAUDE.md

This file documents the codebase for AI assistants working on this repository.

## Project Overview

**sapporo-gomi-to-slack** is a minimal AWS Lambda application that sends daily Slack notifications about the next day's garbage collection type in Sapporo, Japan.

- Scrapes Sapporo city's text-to-speech garbage calendar page
- Parses Japanese natural-language HTML (e.g., "毎週月・水曜日は燃やせるごみは、...")
- Sends a Slack message every evening (22:00 JST) with tomorrow's garbage type

## Repository Structure

```
sapporo-gomi-to-slack/
├── app.py               # Entire application logic (164 lines)
├── requirements.txt     # Python dependencies (requests only)
├── README.md            # Setup and deploy instructions (Japanese)
└── .chalice/
    └── config.json      # Chalice deployment config + env vars
```

There are no subdirectories, no tests, and no CI/CD configuration.

## Tech Stack

- **Runtime**: Python 3 on AWS Lambda
- **Framework**: [AWS Chalice](https://aws.github.io/chalice/index) — handles Lambda packaging and CloudWatch Events scheduling
- **Trigger**: CloudWatch Events cron `Cron(0, 13, '?', '*', '*', '*')` → 13:00 UTC = 22:00 JST
- **Dependencies**: `requests` (HTTP scraping), stdlib only for everything else

## Key Environment Variables

Set in `.chalice/config.json` under `stages.dev.environment_variables`:

| Variable | Description |
|---|---|
| `SLACK_WEBHOOK` | Slack incoming webhook URL |
| `SAPPORO_GOMI_URI` | URL of the Sapporo city garbage calendar text-to-speech page |

These must be filled in before deploying. They are intentionally left blank in the repository (not committed with real values).

## Deployment

Requires the AWS CLI and Chalice installed and configured with AWS credentials.

```bash
pip install chalice requests
chalice deploy
```

Chalice automatically creates the Lambda function, IAM role, and CloudWatch Events rule. The deployed Lambda is named `sapporo-gomi-dev-every_hour`.

To remove:
```bash
chalice delete
```

## Application Logic (`app.py`)

### Entry point

```python
@app.schedule(Cron(0, 13, '?', '*', '*', '*'))
def every_hour(event):
    get_target_gomi_phrase()
```

### Call chain

1. `get_target_gomi_phrase()` — fetches and parses the HTML, sends Slack notification
2. `get_year_and_month_phrase(target_date)` — returns the current month in Japanese era format (e.g., `令和7年4月`). Reiwa year = `current_year - 2018`
3. `create_knowledge_dict(target, target_date)` — regex-strips HTML tags and progressively extracts each garbage type's schedule using `re.sub`
4. `what_type_is_by_knowledge(knowledge, target_date)` — returns tomorrow's garbage type string
5. `create_slack_body(target)` — formats the Slack message (returns `None` if no collection)
6. `send_slack(body)` — POSTs to the Slack webhook

### `Knowledge` class

A simple data container with class-level list attributes:
- `burnable` — 燃やせるごみ (every week on specific weekdays)
- `no_burnable` — 燃やせないごみ (specific dates)
- `pla` — 容器包装プラスチック (every week on specific weekdays)
- `pet` — びん・缶・ペットボトル (every week on specific weekdays)
- `paper` — 雑がみ (specific dates)
- `kusa` — 枝・葉・草 (specific dates)

### Schedule parsing helpers

- `get_days_knowledge_every_weeks(target, year, month)` — for "毎週X曜日" (recurring weekday) patterns; iterates every day of the month checking weekday name matches
- `get_days_knowledge_days(target)` — for "X日、Y日" (specific date) patterns; returns `[]` if "ありません" is in the text

### Slack message format

```
Channel: #iwama_gomi
Username: 札幌ごみの日
Text: 明日は、{garbage_type}です。
```

If `what_type_is_by_knowledge` returns `"何もない"`, no Slack message is sent.

## Known Limitations and Fragilities

- **No error handling**: Any network error, HTML format change, or missing env var will crash silently in Lambda (check CloudWatch Logs)
- **Regex-based HTML parsing**: Tightly coupled to Sapporo city's current text-to-speech HTML format; will break if the format changes
- **`Knowledge` class uses class-level (shared) attributes**: If the class were instantiated multiple times in one process, the lists would accumulate across instances
- **`get_days_knowledge_days` returns strings, not ints**: The day values from regex are strings (e.g., `"15"`), while `get_days_knowledge_every_weeks` returns ints; `what_type_is_by_knowledge` compares against `target_date.day` (int), so the string-based comparisons for `no_burnable`, `paper`, and `kusa` may never match
- **No tests**: There is no test suite
- **Hardcoded Slack channel**: `#iwama_gomi` is hardcoded in `send_slack()`
- **Commented-out REST route**: Lines 12–15 show an abandoned HTTP endpoint approach

## Conventions

- All user-facing strings (log messages, function docstrings) are in Japanese
- Debugging via `print()` — visible in CloudWatch Logs
- No logging framework; no structured logging
- Single-file application — keep all logic in `app.py`

## Development Notes

- There is no local run mode; the Lambda handler requires real environment variables and a live Sapporo city URL
- To test locally, set environment variables and call `get_target_gomi_phrase()` directly in a Python REPL
- The `.gitignore` excludes `.chalice/deployments/`, `.chalice/venv/`, and `vendor/` — do not commit those
- Do not commit real values for `SLACK_WEBHOOK` or `SAPPORO_GOMI_URI` to the repository
