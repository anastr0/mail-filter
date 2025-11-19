from google_auth_utils import get_gmail_api_service


def collect_emails():
    service = get_gmail_api_service()
    if not service:
        print("Failed to get Gmail API service.")
        return

    try:
        # Call the Gmail API to fetch INBOX
        results = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX"], maxResults=10)
            .execute()
        )
        messages = results.get("messages", [])

        if not messages:
            print("No messages found.")
            return

        print("Messages:", messages)
        for message in messages:
            msg = (
                service.users().messages().get(userId="me", id=message["id"]).execute()
            )
            print(f"Message ID: {msg['id']}")

    except Exception as e:
        print(f"An error occurred while fetching emails: {e}")


if __name__ == "__main__":
    collect_emails()
