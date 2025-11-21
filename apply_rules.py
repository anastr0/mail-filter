import logging

from utils.services import init_pg_conn, get_gmail_api_service, get_logger


# Configure module logger to output to stdout
_LOG = get_logger(__name__, logging.DEBUG)


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
        "TIME_VALUE": {
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
        self.gmail_labels = self.fetch_gmail_labels()

    def fetch_gmail_labels(self):
        """Fetch existing Gmail labels for the user.
        This is needed to validate folder names in MOVE_MESSAGE action."""
        try:
            results = self.gmail_service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])
            label_dict = {label["name"].lower(): label["id"] for label in labels}
            return label_dict
        except Exception as e:
            _LOG.error(f"An error occurred while fetching Gmail labels: {e}")
            raise

    def validate_rule(self, rule):
        """Validate individual rule structure and values."""
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
        """Validate the entire ruleset structure and values."""
        overall_predicate = ruleset.get("overall_predicate")
        if overall_predicate not in OPERATORS:
            raise RuleValidationError(f"Invalid overall predicate: {overall_predicate}")

        for rule in ruleset.get("rules", []):
            self.validate_rule(rule)

    def read_rules_from_file(self, filepath):
        """
        read rulesets from json file "rules.json"
        """
        import json

        try:
            with open(filepath, "r") as file:
                data = json.load(file)
            _LOG.debug(f"Loaded rules from {filepath}\n")
            return data
        except Exception as e:
            raise RuleValidationError(f"Error reading rules from file: {e}")

    def build_condition(self, rule):
        """Build SQL condition from given rule
        Eg. {"field": "FROM", "predicate": "CONTAINS", "value": "example.com"}
        becomes "from_addr LIKE '%example.com%'"
        """
        value = rule["value"]
        field = rule["field"]
        predicate = rule["predicate"]
        condition = FIELD_ALIASES[field] + SQL_PREDICATES[predicate].format(value)
        return condition

    def build_rule_query(self, ruleset):
        """Build SQL query from the entire ruleset.
        Combines individual rule conditions using the overall predicate (AND/OR).
        Eg. For ruleset with overall_predicate "ANY" and two rules(condition),
        it becomes "SELECT id FROM emails WHERE (condition1 OR condition2)"
        """
        condition_list = [self.build_condition(rule) for rule in ruleset["rules"]]
        op = OPERATORS[ruleset["overall_predicate"]]
        condition = f" {op} ".join(condition_list)
        query = f"SELECT id FROM emails WHERE ({condition})"
        return query

    def apply_ruleset(self, ruleset):
        """
        Use given ruleset to filter emails from DB
        ,perform actions on them in Gmail with Gmail API.
        """
        # self.validate_ruleset(ruleset)
        query = self.build_rule_query(ruleset)
        _LOG.debug(
            f"Query built successfully for ruleset: {ruleset['name']}.\n Executing Query: {query}\n..."
        )

        with self.db_conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        _LOG.debug(
            f"Filtered {len(rows)} emails from DB for ruleset: {ruleset['name']}.\nApplying actions...\n"
        )
        # Apply actions to the filtered emails

        if rows:
            self.apply_actions(ruleset["actions"], [row[0] for row in rows])
        else:
            _LOG.info(
                f"No emails matched for ruleset: {ruleset['name']}. No actions applied.\n"
            )

    def apply_actions(self, actions, email_rows):
        """apply actions to the emails identified by email_rows using gmail_service"""

        for action in actions:
            if action[0] == "MARK_AS_READ":
                self.mark_emails_as_read(email_rows)
            elif action[0] == "MOVE_MESSAGE":
                # logic to move emails to a different folder using gmail_service
                self.move_emails_to_folder(email_rows, action[1])

    def mark_emails_as_read(self, email_rows):
        """
        action MARK_READ: mark emails as read using gmail_service
        """

        _LOG.debug(f"Emails : {email_rows}")
        body = {
            "ids": email_rows,
            "removeLabelIds": ["UNREAD"],
        }
        self.gmail_service.users().messages().batchModify(
            userId="me", body=body
        ).execute()
        _LOG.debug(f"Marked {len(email_rows)} emails as read.")

    def move_emails_to_folder(self, email_rows, folder_name):
        """
        action MOVE_MESSAGE: move emails to a different folder using gmail_service
        """
        if folder_name.lower() not in self.gmail_labels:
            _LOG.error(f"Label '{folder_name}' does not exist in Gmail.")
            return

        label_id = self.gmail_labels[folder_name.lower()]
        body = {
            "ids": email_rows,
            "addLabelIds": [label_id],
        }
        self.gmail_service.users().messages().batchModify(
            userId="me", body=body
        ).execute()
        _LOG.info(f"Moved {len(email_rows)} emails to folder '{folder_name}'.")


class RuleValidationError(Exception):
    """Custom exception for rule validation errors."""

    pass


if __name__ == "__main__":
    email_filter = EmailFilterEngine()
    rules_data = email_filter.read_rules_from_file("rules.json")

    # iterate through each ruleset and apply respective actions
    for ruleset in rules_data.get("filters", []):
        try:
            email_filter.apply_ruleset(ruleset)
            _LOG.info(
                f"Applied ruleset: '{ruleset['name']}' with desc: '{ruleset['description']}' successfully."
            )
        except RuleValidationError as e:
            _LOG.error(f"Rule validation error: {e}")
        except Exception as e:
            _LOG.error(f"An error occurred while applying ruleset: {e}")

    _LOG.info("Email filtering process completed.")
