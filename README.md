# mail-filter

A small utility to collect Gmail messages into a local PostgreSQL store and apply rule-based filters and actions using the Gmail API.

Follow instructions below for setup, common workflows (collecting messages, defining rules, applying rules), and debugging tips.

## Table of contents
- [Purpose](#purpose)
- [Requirements](#requirements)
- [Quick setup](#quick-setup)
    - [PostgreSQL (Docker) setup](#postgresql-docker-setup)
    - [Python environment & dependencies](#python-environment-and-dependencies)
    - [Configure Gmail API credentials](#configure-gmail-api-credentials)
- [Collect emails](#collect-emails)
- [Define rules](#define-rules)
- [Apply rules](#apply-rules)
    - [Backup, restore, and maintenance utilities](#backup-restore-and-maintenance-utilities)
- [Running tests](#running-tests)
- [Working diagram](#working-diagram)
- [Project layout](#project-layout)
- [Troubleshooting & tips](#troubleshooting--tips)
- [Security & privacy](#security--privacy)
- [Contributing](#contributing)
- [License](#license)

# Purpose
mail-filter is intended to:
- Fetch messages from your Gmail account and persist them into a PostgreSQL table for offline filtering.
- Let you author JSON rule sets that translate to SQL filters and map results to Gmail actions (e.g., mark as read, move to folder).
- Provide utilities to backup/restore the persisted messages.

## Requirements
- Python 3.11
- Docker & Docker Compose (for optional PostgreSQL local setup)
- A Google account for Gmail API access

## Quick setup
1. Start PostgreSQL (recommended: Docker Compose).
2. Create & activate a Python venv, install dependencies.
3. Place your Gmail OAuth credential JSON at `secrets/credentials.json`.
4. Run the email collector and then apply your rules.

Detailed steps below.
#### PostgreSQL (Docker) setup
A docker-compose setup is included to create a local Postgres instance and initialize the schema.

From repository root:
```bash
docker compose up -d
```

This will:
- Start Postgres on port 5432 (default compose).
- Run initialization SQL in `init_db/init.sql` to create database `emaildb` and table `emails`.

If you prefer a manually managed Postgres:
- Create database `emaildb`.
- Run `init_db/init.sql` to create the `emails` table and initial schema.

#### Python environment & dependencies
Create and activate a virtual environment, then install requirements:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Configure Gmail API credentials
1. Follow https://developers.google.com/workspace/gmail/api/quickstart/python to create OAuth 2.0 credentials (Desktop app / OAuth client).
2. Save the downloaded client credentials JSON as `secrets/credentials.json`.
3. In Google Cloud Console, under OAuth Consent Screen → Test users, add the Gmail account(s) you will use for testing.
4. On the first run, the app will open a consent page and persist tokens at `secrets/token.json`. Keep `token.json` secure.

## Collect emails
Collect messages from your inbox and persist to the Postgres `emails` table.

Default (collects 10 messages):
```bash
python collect_emails.py
```

Collect a custom number (example: 20):
```bash
python collect_emails.py --count 20
```

Notes:
- The collector uses the Gmail API to fetch messages and then persists them to the DB.
- Use the `--count` argument to adjust how many messages are fetched per run.

## Define rules
Rules are defined in JSON as an array of rulesets. Each ruleset filters a set of emails in the DB and applies actions on them in Gmail using Gmail API.

Minimal example (one ruleset):
```json
{
    "filters": [
        {
            "name": "github_notifications",
            "description": "Filter GitHub Notifications",
            "rules": [
                {"field": "FROM", "predicate": "CONTAINS", "value": "github.com"},
                {"field": "RECEIVED_DATE", "predicate": "LESS_THAN", "value": "10 days"},
                {"field": "SUBJECT", "predicate": "CONTAINS", "value": "GitHub" }
            ],
            "overall_predicate": "ALL",
            "actions": [
                ["MARK_AS_READ", null],
                ["MOVE_MESSAGE", "git"]
            ]
        }
    ]
} 

```

### Field and predicate guidance for building rules.json

Following are allowed fields and predicates for each value type 
- String value: 
  - Fields: FROM, TO, SUBJECT
  - Predicates: CONTAINS, DOES_NOT_CONTAIN, EQUALS, NOT_EQUAL
  - Use apply_rules.RULES_VALIDATORS['RULES']['STRING_VALUE']-compatible values.
- Time value: (Eg. "2 days"/ "3 months")
  - Fields: RECEIVED_DATE
  - Predicates: LESS_THAN, GREATER_THAN
  - Use time-interval strings like "2 days", "3 months" recognized by the code.
  - Use apply_rules.RULES_VALIDATORS['RULES']['TIME_VALUE']-compatible values.

Actions:
- MARK_AS_READ: marks matching messages as read
- MOVE_MESSAGE: moves message to specified folder/label (second element in the action array)
- Additional actions supported by the code are listed in the codebase — check apply_rules for the full set.

Practical tips:
- Start with an "ANY" overall_predicate while testing to see matches quickly.
- Test rules on a small set of fetched messages first (use `--count`).

## Apply rules

To apply configured rulesets in rules.json to messages in the DB and trigger Gmail actions:
```bash
python apply_rules.py
```

What happens:
- Rulesets in `rules.json` are converted into SQL filters to select matching messages from the DB.
- Actions are performed on matching messages via the Gmail API (e.g., move labels, mark as read).

Dry-run / logging:
- Check the log output to verify which messages matched which rules before applying destructive actions.
- If you want to batch or limit actions, consider modifying the script or DB query limits.

#### Backup, restore, and maintenance utilities
Utilities are available in `utils/backup.py`:

- Backup emails from DB to a pickle:
  - backup_emails_to_pkl(output_path="emails_backup.pkl")
- Purge all emails in DB:
  - purge_emails_table()
- Restore emails from a pickle file into DB:
  - restore_emails_from_pkl("emails_backup.pkl")

Example usage:
```python
from utils.backup import backup_emails_to_pkl, purge_emails_table, restore_emails_from_pkl

# Backup
backup_emails_to_pkl()

# Purge DB (be careful!)
purge_emails_table()

# Restore from previously created backup
restore_emails_from_pkl()
```

## Running tests

Run the test suite with:
```bash
pytest
```

If tests require a live DB, make sure the Docker Postgres instance is running and accessible.

## Working diagram

![working](/working_diagram.png "Working Diagram")

## Project layout
- collect_emails.py — fetches messages from Gmail and stores in DB
- apply_rules.py — loads rules.json, selects matching messages, and applies actions
- utils/ — helper modules (backup, db helpers, gmail helper functions)
- init_db/init.sql — DB initialization SQL
- rules.json — user-editable rules file
- secrets/ — credentials.json and generated token.json (not tracked in VCS)

## Troubleshooting & tips
- credentials.json missing: create OAuth credentials in Google Cloud Console and save to `secrets/credentials.json`.
- Permission / OAuth consent errors: ensure your test Gmail address is added under OAuth Consent → Test users.
- DB connection issues: confirm Postgres is running at the expected host/port and credentials in your environment (or default config) match.
- Unexpected rule matches: inspect generated SQL in apply_rules or add logging to see exact filters.

## Security & privacy
- Do not commit `secrets/credentials.json` or `secrets/token.json` to source control.
- Handle backups (pickles) with care — they contain message data.

## Contributing
- Open an issue or PR with improvements.
- Add tests for new behaviors or rule types.

## License
See repository license (if any) or add an appropriate license for your project.
