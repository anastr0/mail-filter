import json
import os
import psycopg2
import pytest

from apply_rules import EmailFilterEngine, RuleValidationError
from collect_emails import CollectEmails


email_filter = EmailFilterEngine()
rules_path = os.path.join(os.path.dirname(__file__), "rules_test.json")


@pytest.fixture(scope="function")
def db_connection():
    """
    Pytest fixture that provides a psycopg2 connection with automatic rollback.
    """
    # Establish a new connection for the test function
    conn = psycopg2.connect(
        dbname="emaildb",
        user="atr",
        password="password",
        host="localhost",
    )
    # Disable autocommit to manage transactions manually
    conn.autocommit = False
    # Use yield to provide the connection to the test
    yield conn
    # Teardown phase: Rollback changes and close connection
    if conn:
        conn.rollback()  # Discard all changes made during the test
        conn.close()


@pytest.fixture(scope="function")
def db_cursor(db_connection):
    """
    Pytest fixture that provides a database cursor and automatically closes it.
    """
    cur = db_connection.cursor()
    yield cur
    cur.close()


def test_collect_emails():
    """Test collecting emails from Gmail.
    Needs valid Gmail API credentials set up.
    """
    collector = CollectEmails(count=2)
    emails = collector.read_emails_from_gmail()
    assert len(emails) == 2, "Should retrieve exactly 2 emails"


def test_rules_validation():
    """Test validation of rules from rules_test.json."""
    rules_path = os.path.join(os.path.dirname(__file__), "rules_test.json")
    with open(rules_path, "r") as f:
        try:
            rules = json.load(f)
        except json.JSONDecodeError:
            assert False, "rules.json is not a valid JSON file"
    email_filter = EmailFilterEngine()

    # test validate_ruleset with bad dict first
    with pytest.raises(RuleValidationError):
        email_filter.validate_ruleset({})

    # test rules.json rules. RuleValidationError will be raised otherwise
    for ruleset in rules["filters"]:
        email_filter.validate_ruleset(ruleset)


def test_rules_apply(db_cursor):
    """Test applying rules from rules_test.json on test emails in DB.
    All SQL operations are rolled back after test.
    """
    # empty table first and fill with test emails
    db_cursor.execute("DELETE FROM emails;")
    db_path = os.path.join(os.path.dirname(__file__), "emails_backup_db_test.pkl")
    with open(db_path, "rb") as pkl_file:
        import pickle

        emails = pickle.load(pkl_file)

        assert len(emails) > 0, "No emails found in test pickle file"
        query = "INSERT INTO emails (id, subject_title, from_addr, to_addr, received_date) VALUES (%s, %s, %s, %s, %s);"
        db_cursor.executemany(query, emails)

    # read rules from file
    rules_data = email_filter.read_rules_from_file(rules_path)

    # apply test ruleset and check filtered emails
    ruleset = rules_data["filters"][0]
    query = email_filter.build_rule_query(ruleset)
    assert query is not None, "Query should not be None"

    # assert query is as expected for a test ruleset
    assert (
        query
        == "SELECT id FROM emails WHERE (from_addr LIKE '%github.com%' AND received_date > (CURRENT_DATE - INTERVAL '10 days') AND subject_title LIKE '%GitHub%')"
    )

    # assert SQL query is correct by running in DB.
    db_cursor.execute(query)
    rows = db_cursor.fetchall()

    # assert expected number of filtered emails
    assert len(rows) == 2, "Filtered emails count should be non-negative"


# TODO : test actions on filtered emails
