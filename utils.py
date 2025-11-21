import os.path
import psycopg2

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


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


def get_gmail_api_service():
    """
    returns Gmail API service
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("secrets/token.json"):
        creds = Credentials.from_authorized_user_file("secrets/token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "secrets/credentials.json", SCOPES
            )

            FIXED_PORT = 8080
            flow.redirect_uri = f"http://localhost:{FIXED_PORT}/"
            creds = flow.run_local_server(
                port=FIXED_PORT, host="localhost", open_browser=True
            )
        # Save the credentials for the next run
        with open("secrets/token.json", "w") as token:
            token.write(creds.to_json())

    try:
        # Build Gmail API service and return it
        service = build("gmail", "v1", credentials=creds)
        return service

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f"An error occurred: {error}")
        return
    

def api_request_callback(request_id, response, exception):
    """Handles the response for a single request in the batch of Gmail API calls."""
    if exception is not None:
        # Handle the exception (e.g., print the error)
        print(f"Request ID {request_id} failed: {exception}")
    else:
        # Process the response (e.g., print data)
        print(f"Request ID {request_id} succeeded. Data: {response}")


def get_new_gmail_api_batch_request():
    """
    Return a new batch request from google api client to process multiple API calls in 1 HTTP request.
    NB: this doesn't help with quotas, but reduce network overhead 
    """
    service = get_gmail_api_service()
    batch = service.new_batch_http_request(callback=api_request_callback)


def init_pg_conn():
    """Initialize and return a PostgreSQL database connection."""
    conn = None
    try:
        conn = psycopg2.connect(
            host="localhost", database="emaildb", user="atr", password="password"
        )
        print("Connected to PostgreSQL successfully!")
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
    return conn
