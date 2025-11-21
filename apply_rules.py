from pprint import pprint

from utils import (
    init_pg_conn,
    RULES_VALIDATORS,
    SQL_PREDICATES,
    FIELD_ALIASES,
    OPERATORS,
    get_gmail_api_service,
)


def read_emails_from_db(conn):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, subject_title, from_addr, to_addr, received_date FROM emails"
        )
        rows = cursor.fetchall()
    emails = [
        {
            "id": row[0],
            "subject_title": row[1],
            "from_addr": row[2],
            "to_addr": row[3],
            "received_date": row[4],
        }
        for row in rows
    ]
    return emails


def read_json_file():
    import json

    try:
        with open("rules.json", "r") as file:
            data = json.load(file)
        print("JSON data loaded successfully:")
        return data
    except FileNotFoundError:
        print("Error: 'data.json' not found. Please ensure the file exists.")
    except json.JSONDecodeError:
        print(
            "Error: Could not decode JSON from the file. Check for valid JSON format."
        )
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def build_condition(rule):
    value = rule["value"]
    field = rule["field"]
    predicate = rule["predicate"]
    condition = FIELD_ALIASES[field] + SQL_PREDICATES[predicate].format(value)
    return condition


def build_query(ruleset):
    condition_list = [build_condition(rule) for rule in ruleset["rules"]]
    op = OPERATORS[ruleset["overall_predicate"]]
    condition = f" {op} ".join(condition_list)
    query = f"SELECT id FROM emails WHERE ({condition})"
    return query


def read_rules():
    data = read_json_file()

    # TODO : validate rule set
    # TODO : return all rulesets
    return data["filters"][0]


def apply_actions(actions):
    pass


def apply_rules():
    conn = init_pg_conn()
    emails = read_emails_from_db(conn)

    print("All stored emails")
    pprint(emails)

    ruleset = read_rules()
    q = build_query(ruleset)

    with conn.cursor() as cursor:
        cursor.execute(q)
        rows = cursor.fetchall()
    conn.close()

    # apply actions
    apply_actions(ruleset["actions"])




RULES_VALIDATORS = {
    "RULES": {
        "FIELDS": ["FROM", "TO", "SUBJECT", "RECEIVED_DATE"],
        "PREDICATES": [
            "CONTAINS",
            "DOES_NOT_CONTAIN",
            "EQUALS",
            "NOT_EQUAL",
            "LESS_THAN",
            "GREATER_THAN",
        ],
        "OVERALL_PREDICATES": ["ALL", "ANY"],
        "STRING_VALUE": {
            "FIELDS": ["FROM", "TO", "SUBJECT"],
            "PREDICATES": ["CONTAINS", "DOES_NOT_CONTAIN", "EQUALS", "NOT_EQUAL"],
        },
        "TIME_VALUE": {  #
            "FIELDS": [
                "RECEIVED_DATE",
            ],
            "PREDICATES": ["LESS_THAN", "GREATER_THAN"],
        },
    },
    "ACTIONS": ["MARK_AS_READ", "MOVE_MESSAGE"],
}

SQL_PREDICATES = {
    "CONTAINS": " LIKE '%{}%'",
    "DOES_NOT_CONTAIN": " NOT LIKE '%{}%'",
    "EQUALS": " = '{}'",
    "NOT_EQUAL": " != '{}'",
    "LESS_THAN": " < (NOW() - INTERVAL '{}')",  # val can be "2 days"/ "3 months"
    "GREATER_THAN": " > (NOW() + INTERVAL '{}')",
}

FIELD_ALIASES = {
    "FROM": "from_addr",
    "TO": "to_addr",
    "SUBJECT": "subject_title",
    "RECEIVED_DATE": "received_date",
}

OPERATORS = {"ANY": "OR", "ALL": "AND"}
if __name__ == "__main__":
    apply_rules()
