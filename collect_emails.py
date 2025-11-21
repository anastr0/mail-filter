import argparse

from datetime import datetime

from utils import init_pg_conn, get_gmail_api_service


def get_email_metadata(service, email_id):
    """
    Fetch email metadata from Gmail API for a given email ID.
    Returns a tuple: (id, subject, from, to, date)
    """
    try:
        metadata = (
            service.users()
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
                print(f"Date parsing error for email ID {email_id}: {received_date}")
        return (
            metadata["id"],
            header_map.get("Subject", ""),
            header_map.get("From", ""),
            header_map.get("To", ""),
            received_date,
        )
    except Exception as e:
        print(f"An error occurred while fetching email metadata: {e}")
        return None


def read_emails_from_gmail():
    """
    Fetch emails from Gmail using the Gmail API.
    Returns email details a list of tuplesto be used in bulk insert query.
    Each email detail tuple is : (id, subject, from, to, date)
    """
    service = get_gmail_api_service()
    if not service:
        print("Failed to get Gmail API service.")
        return

    emails = []
    try:
        # Call the Gmail API to fetch INBOX
        results = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX"], maxResults=10)
            .execute()
        )
        emails = results.get("messages", [])

        if not emails:
            print("No emails found.")
            return
    except Exception as e:
        print(f"An error occurred while listing emails from Gmail API: {e}")
        return

    email_values = [get_email_metadata(service, email["id"]) for email in emails]
    return email_values


def store_emails_in_db():
    """
    Store emails fetched from Gmail into PostgreSQL database.
    """
    email_values = read_emails_from_gmail()
    if not email_values:
        print("No emails to store.")
        return

    print(f"Storing {len(email_values)} emails into the database.")
    conn = init_pg_conn()
    if not conn:
        print("No database connection available.")
        return

    insert_query = "INSERT INTO emails (id, subject_title, from_addr, to_addr, received_date) VALUES (%s, %s, %s, %s, %s);"
    try:
        with conn.cursor() as cursor:
            cursor.executemany(insert_query, email_values)
        conn.commit()
    except Exception as e:
        print(f"An error occurred while inserting emails into the database: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process an integer argument.")
    parser.add_argument("count", type=int, help="Number of emails to collect")
    args = parser.parse_args()

    if args.count <= 0:
        print("Count must be a positive integer.")
    elif args.count > 100:
        print("Count exceeds the maximum limit of 100. You risk hitting API limits.")
    else:
        print(f"Collecting {args.count} emails from Gmail and storing in DB.")
        store_emails_in_db()
