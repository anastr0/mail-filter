from pprint import pprint

from utils import init_pg_conn

def read_emails_from_db(conn):
    cursor = conn.cursor()
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

def apply_rules():
    conn = init_pg_conn()
    emails = read_emails_from_db(conn)

    print("All stored emails")
    pprint(emails)

if __name__=='__main__':
    apply_rules()

