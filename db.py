import mysql.connector

from config import MYSQL_CONFIG
from logger import logger


def get_connection():

    try:

        conn = mysql.connector.connect(
            host=MYSQL_CONFIG["host"],
            user=MYSQL_CONFIG["user"],
            password=MYSQL_CONFIG["password"],
            database=MYSQL_CONFIG["database"]
        )

        return conn

    except Exception:

        logger.exception(
            "Database connection failed."
        )

        raise


def execute_query(
    query,
    params=None,
    fetch_one=False,
    commit=False
):

    conn = None
    cursor = None

    try:

        conn = get_connection()

        cursor = conn.cursor(
            dictionary=True
        )

        cursor.execute(
            query,
            params
        )

        result = None

        if commit:

            conn.commit()

        else:

            if fetch_one:

                result = cursor.fetchone()

            else:

                result = cursor.fetchall()

        return result

    except Exception:

        logger.exception(
            "Database query failed."
        )

        raise

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()