from utils.services import (
    init_pg_conn,
    get_gmail_api_service,
)


def test_init_pg_conn():
    """
    Test the initialization of PostgreSQL connection.
    """
    conn = init_pg_conn()
    assert conn is not None

    cursor = conn.cursor()
    cursor.execute("SELECT 1;")
    result = cursor.fetchone()
    assert result[0] == 1

    cursor.close()
    conn.close()


def test_get_gmail_api_service():
    """
    Test the Gmail API service initialization.
    """
    service = get_gmail_api_service()
    assert service is not None

    profile = service.users().getProfile(userId="me").execute()
    assert "emailAddress" in profile
    assert profile["emailAddress"] is not None
