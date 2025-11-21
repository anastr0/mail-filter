import logging
from services import init_pg_conn, get_logger

_LOG = get_logger(__name__, logging.DEBUG)

"""
Backup scripts to backup and restore emails from Postgres DB to pkl file and vice versa.

Needed to avoid hitting quotas/limits on Gmail API while testing.
"""


def backup_emails_to_pkl():
    conn = init_pg_conn()
    if not conn:
        _LOG.debug("No database connection available.")
        return

    select_query = (
        "SELECT id, subject_title, from_addr, to_addr, received_date FROM emails;"
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(select_query)
            emails = cursor.fetchall()

        import pickle

        with open("../bkp/emails_backup_db.pkl", "wb") as pkl_file:
            pickle.dump(emails, pkl_file)
        _LOG.debug(f"Backed up {len(emails)} emails to emails_backup.pkl")
    except Exception as e:
        _LOG.debug(f"An error occurred while backing up emails to pkl: {e}")
    finally:
        conn.close()


# TODO : purge postgres db table emails
def purge_emails_table():
    conn = init_pg_conn()
    if not conn:
        _LOG.debug("No database connection available.")
        return

    delete_query = "DELETE FROM emails;"
    try:
        with conn.cursor() as cursor:
            cursor.execute(delete_query)
        conn.commit()
        _LOG.debug("Purged all emails from the emails table.")
    except Exception as e:
        _LOG.debug(f"An error occurred while purging emails table: {e}")
    finally:
        conn.close()


# TODO : restore emails from pkl file to postgres db
def restore_emails_from_pkl():
    conn = init_pg_conn()
    if not conn:
        _LOG.debug("No database connection available.")
        return

    import pickle

    try:
        with open("../bkp/emails_backup.pkl_db", "rb") as pkl_file:
            emails = pickle.load(pkl_file)

        insert_query = "INSERT INTO emails (id, subject_title, from_addr, to_addr, received_date) VALUES (%s, %s, %s, %s, %s);"
        with conn.cursor() as cursor:
            cursor.executemany(insert_query, emails)
        conn.commit()
        _LOG.debug(
            f"Restored {len(emails)} emails from emails_backup.pkl to the database."
        )
    except Exception as e:
        _LOG.debug(f"An error occurred while restoring emails from pkl: {e}")
    finally:
        conn.close()
