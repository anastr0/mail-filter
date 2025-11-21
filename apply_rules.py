from utils import (
    init_pg_conn,
    get_gmail_api_service,
)

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


class EmailFilterEngine:
    def __init__(self):
        self.db_conn = init_pg_conn()
        self.gmail_service = get_gmail_api_service()

    def validate_rule(self, rule):
        field = rule.get("field")
        predicate = rule.get("predicate")
        value = rule.get("value")

        if field not in FIELD_ALIASES:
            raise RuleValidationError(f"Invalid field: {field}")

        if predicate not in SQL_PREDICATES:
            raise RuleValidationError(f"Invalid predicate: {predicate}")

        validator = RULES_VALIDATORS.get(predicate)
        if validator and not validator(value):
            raise RuleValidationError(
                f"Invalid value for predicate {predicate}: {value}"
            )

    def validate_ruleset(self, ruleset):
        overall_predicate = ruleset.get("overall_predicate")
        if overall_predicate not in OPERATORS:
            raise RuleValidationError(f"Invalid overall predicate: {overall_predicate}")

        for rule in ruleset.get("rules", []):
            self.validate_rule(rule)

    def read_rules_from_file(self, filepath):
        import json

        try:
            with open(filepath, "r") as file:
                data = json.load(file)
            return data
        except Exception as e:
            raise RuleValidationError(f"Error reading rules from file: {e}")

    def build_condition(self, rule):
        value = rule["value"]
        field = rule["field"]
        predicate = rule["predicate"]
        condition = FIELD_ALIASES[field] + SQL_PREDICATES[predicate].format(value)
        return condition

    def build_rule_query(self, ruleset):
        condition_list = [self.build_condition(rule) for rule in ruleset["rules"]]
        op = OPERATORS[ruleset["overall_predicate"]]
        condition = f" {op} ".join(condition_list)
        query = f"SELECT id FROM emails WHERE ({condition})"
        return query

    def apply_ruleset(self, ruleset):
        self.validate_ruleset(ruleset)
        query = self.build_rule_query(ruleset)

        with self.db_conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        # Apply actions to the filtered emails
        self.apply_actions(ruleset["actions"], rows)

    def apply_actions(self, actions, email_rows):
        # apply actions to the emails identified by email_rows using gmail_service

        for action in actions:
            if action[0] == "MARK_AS_READ":
                self.mark_emails_as_read(email_rows)
            elif action[0] == "MOVE_MESSAGE":
                # logic to move emails to a different folder using gmail_service
                self.move_emails_to_folder(email_rows, action[1])

    def mark_emails_as_read(self, email_rows):
        # logic to mark emails as read using gmail_service
        body = {
            "ids": [str(row[0]) for row in email_rows],
            "removeLabelIds": ["UNREAD"],
        }
        self.gmail_service.users().messages().batchModify(
            userId="me", body=body
        ).execute()

    def move_emails_to_folder(self, email_rows, folder_name):
        # logic to move emails to a different folder using gmail_service
        label_id = self.get_label_id(folder_name)
        body = {
            "ids": [str(row[0]) for row in email_rows],
            "addLabelIds": [label_id],
        }
        self.gmail_service.users().messages().batchModify(
            userId="me", body=body
        ).execute()


class RuleValidationError(Exception):
    """Custom exception for rule validation errors."""

    pass


if __name__ == "__main__":
    email_filter = EmailFilterEngine()
    rules_data = email_filter.read_rules_from_file("rules.json")

    for ruleset in rules_data.get("filters", []):
        try:
            email_filter.apply_ruleset(ruleset)
            print("Applied ruleset successfully.")
        except RuleValidationError as e:
            print(f"Rule validation error: {e}")
        except Exception as e:
            print(f"An error occurred while applying ruleset: {e}")
