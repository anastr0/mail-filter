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

        email_values = self.get_email_details(emails)
        _LOG.debug(f"Fetched {len(email_values)} emails from Gmail.")
        return email_values

    def get_new_gmail_api_batch_request(self, callback):
        """
        Create a new batch request for Gmail API.
        """
        try:
            batch = self.gmail_service.new_batch_http_request(callback=callback)
            return batch
        except Exception as e:
            _LOG.error(f"An error occurred while creating Gmail API batch request: {e}")
            raise

    def email_metadata_callback(self, request_id, response, exception, results):
        """Handles the response for a single request in the batch of Gmail API calls."""
        if exception is not None:
            _LOG.debug(f"Request ID {request_id} failed: {exception}")
        else:
            _LOG.debug(f"Request ID {request_id} succeeded.")
            header_map = {h["name"]: h["value"] for h in response["payload"]["headers"]}
            received_date = header_map.get("Date", "")
            if received_date:
                try:
                    received_date = datetime.strptime(
                        received_date.split(" (")[0], "%a, %d %b %Y %H:%M:%S %z"
                    )
                except ValueError:
                    _LOG.error(
                        f"Date parsing error for email ID {response['id']}: {received_date}"
                    )
            results.append(
                (
                    response["id"],
                    header_map.get("Subject", ""),
                    header_map.get("From", ""),
                    header_map.get("To", ""),
                    received_date,
                )
            )

    def get_email_details(self, emails):
        """
        Fetch email metadata (subject, from, to, date) for a list of email IDs
        using batch requests to Gmail API.
        Returns a list of tuples with email details.
        Each email detail tuple is : (id, subject, from, to, date)"""
        email_values = []

        # create batch with a small wrapper to pass `results` into callback
        # this is needed to gather email metadata from individual req callback invocations in batch
        def callback_wrapper(request_id, response, exception, _results=email_values):
            self.email_metadata_callback(request_id, response, exception, _results)

        batch = self.get_new_gmail_api_batch_request(callback=callback_wrapper)
        for email in emails:
            metadata_req = (
                self.gmail_service.users()
                .messages()
                .get(
                    userId="me",
                    id=email["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From", "To", "Date"],
                )
            )
            batch.add(metadata_req, request_id=f"get-email-metadata-{email['id']}")

        try:
            batch.execute()
        except Exception as e:
            _LOG.error(
                f"An error occurred while executing Gmail API batch request: {e}"
            )

        if not email_values:
            _LOG.debug("No email metadata fetched in batch request.")
        else:
            _LOG.debug(
                f"Fetched metadata for {len(email_values)} emails in batch request."
            )
        return email_values

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
