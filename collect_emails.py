import argparse
import logging
import sys

from datetime import datetime

from utils.services import init_pg_conn, get_gmail_api_service, get_logger

# Configure module logger to output to stdout
_LOG = get_logger(__name__, logging.DEBUG)


class CollectEmails:
    def __init__(self, count=10):
        self.db_conn = init_pg_conn()
        self.gmail_service = get_gmail_api_service()
        self.count = count

    def read_emails_from_gmail(self):
        """
        Fetch emails from Gmail using the Gmail API.
        Returns email details a list of tuplesto be used in bulk insert query.
        Each email detail tuple is : (id, subject, from, to, date)
        """
        if not self.gmail_service:
            _LOG.debug("Failed to get Gmail API service.")
            return

        emails = []
        try:
            # Call the Gmail API to fetch INBOX
            results = (
                self.gmail_service.users()
                .messages()
                .list(userId="me", labelIds=["INBOX"], maxResults=self.count)
                .execute()
            )
            emails = results.get("messages", [])

            if not emails:
                _LOG.info("No emails found.")
                return
        except Exception as e:
            _LOG.error(f"An error occurred while listing emails from Gmail API: {e}")
            return

        email_values = [self.get_email_metadata(email["id"]) for email in emails]
        _LOG.info(f"Fetched {len(email_values)} emails from Gmail.")
        return email_values

    def get_email_metadata(self, email_id):
        """
        Fetch email metadata from Gmail API for a given email ID.
        Returns a tuple: (id, subject, from, to, date)
        """
        try:
            metadata = (
                self.gmail_service.users()
                .messages()
                .get(
                    userId="me",
                    id=email_id,
                    format="metadata",
                    metadataHeaders=["Subject", "From", "To", "Date"],
                )
                .execute()
            )
            header_map = {h["name"]: h["value"] for h in metadata["payload"]["headers"]}
            received_date = header_map.get("Date", "")
            if received_date:
                try:
                    received_date = datetime.strptime(
                        received_date.split(" (")[0], "%a, %d %b %Y %H:%M:%S %z"
                    )
                except ValueError:
                    _LOG.error(
                        f"Date parsing error for email ID {email_id}: {received_date}"
                    )
            return (
                metadata["id"],
                header_map.get("Subject", ""),
                header_map.get("From", ""),
                header_map.get("To", ""),
                received_date,
            )
        except Exception as e:
            _LOG.error(f"An error occurred while fetching email metadata: {e}")
            return None

    def fetch_and_store_emails_in_db(self):
        """
        Fetche emails from Gmail and store in PostgreSQL database.
        """
        email_values = self.read_emails_from_gmail()
        if not email_values:
            _LOG.info("No emails to store.")
            return

        _LOG.debug(f"Storing {len(email_values)} emails into the database.")
        if not self.db_conn:
            _LOG.error("No database connection available.")
            return

        insert_query = "INSERT INTO emails (id, subject_title, from_addr, to_addr, received_date) VALUES (%s, %s, %s, %s, %s);"
        try:
            with self.db_conn.cursor() as cursor:
                cursor.executemany(insert_query, email_values)
            self.db_conn.commit()
        except Exception as e:
            _LOG.error(
                f"An error occurred while inserting emails into the database: {e}"
            )
        finally:
            self.db_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process an integer argument.")
    parser.add_argument(
        "--count", type=int, default=10, help="Number of emails to collect"
    )
    args = parser.parse_args()

    if args.count <= 0:
        _LOG.error("Count must be a positive integer.")
    elif args.count > 100:
        _LOG.error(
            "Count exceeds the maximum limit of 100. You risk hitting API limits."
        )
    else:
        _LOG.info(f"Collecting {args.count} emails from Gmail and storing in DB.")

        collector = CollectEmails(count=args.count)
        collector.fetch_and_store_emails_in_db()
