# mail-filter

Perform rule based operations on emails using Gmail API

## Prerequisites
- Python 3.11
- Docker & Docker Compose (for PostgreSQL)

## Setup postgres DB
Following create a database `emaildb` and a table `emails` with initial schema from `./init_db/init.sql`

Alternatively, a postgres db can be setup manually, run `init_db/init.sql` for initial schema and expose to port `5432`.

```bash
docker compose up
```

## Install python dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

## Configure Gmail API credentials

1. Create OAuth credentials in Google Cloud Console (Desktop app / OAuth client) under a project following https://developers.google.com/workspace/gmail/api/quickstart/python.
2. Save the JSON file as `secrets/credentials.json`
3. Also whitelist your test user email under `APIs & Services ==> OAuth Consent Screen ==> Audience ==> Test users`  

On first run the app will create `secrets/token.json` after you authorize; that file is persisted at `secrets/token.json`

## Run scripts to apply ruleset

### To collect emails from your inbox.

The default count is set to collect 10 emails per run from Gmail. However it can be changed with an arg `count=[0<x<100]` 

```bash
python collect_emails.py
python collect emails.py --count 20
```

> You can use util functions in backup_utils.py to backup stored emails in DB, purge DB and restore pkl emails to DB. 
```python
from utils.backup import (
    backup_emails_to_pkl,
    purge_emails_table,
    restore_emails_from_pkl
)
# backup emails in DB to a pkl 
backup_emails_to_pkl()

# purge emails in db
purge_emails_table()

restore_emails_from_pkl()
```

### Define rules in `rules.json`

Sample rules.json can be edited to add custom rules/filters personalised for your inbox.
Refer `apply_rules.RULES_VALIDATORS` to get ruleset clauses that can be used.


An important rule to follow would be :-
Use `apply_rules.RULES_VALIDATORS['RULES']['STRING_VALUE']` only for string values
    `apply_rules.RULES_VALIDATORS['RULES']['TIME_VALUE'] only for time values like '2 days'/ '2 months'`

Usage instructions for rules.json:
- The rules.json file should contain a list of rulesets. Each ruleset is a dictionary with the following structure:
```json
{
    "name": "Ruleset Name",
    "description": "Description of the ruleset",
    "overall_predicate": "'ALL' or 'ANY'",
    "rules": [
        {
            "field": "'FROM' or 'TO' or 'SUBJECT' or 'RECEIVED_DATE'",
            "predicate": "'CONTAINS' or 'DOES_NOT_CONTAIN' or 'EQUALS' or 'NOT_EQUAL' or 'LESS_THAN' or 'GREATER_THAN', 
                            'LESS_THAN' and 'GREATER_THAN' only for 'RECEIVED_DATE'
                            Rest for string fields,",
            "value": "'string value' or 'time interval' (e.g., '2 days')"
        }
    ],
    "actions": [
        ["'MARK_AS_READ' or 'MOVE_MESSAGE', 'optional folder name if 'MOVE_MESSAGE'"],
    ]
}
```

3. To apply rules to emails

```bash
python apply_rules.py
```
