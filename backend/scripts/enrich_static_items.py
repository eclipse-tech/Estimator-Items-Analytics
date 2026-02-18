import csv
import os
import sys
from mysql.connector import Error

# -------------------------------------------------
# Ensure project root (/app) is on sys.path BEFORE local imports
# -------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# -------------------------------------------------
# Imports from project (now that ROOT_DIR is on sys.path)
# -------------------------------------------------
from dbConfig.mysqlConnectionConfig import get_mysql_connection
from utils.constants import QUERY_BRAHMA, QUERY_RESULT_CSV_PATH, APP_ENVIRONMENT


# -------------------------------------------------
# Core method
# -------------------------------------------------


def fetch_items_and_write_csv(environment: str, output_file: str):
    connection = None
    cursor = None
    tunnel = None

    try:
        connection, tunnel = get_mysql_connection(environment)
        cursor = connection.cursor(dictionary=True)

        cursor.execute(QUERY_BRAHMA)
        rows = cursor.fetchall()

        if not rows:
            print("⚠️ No data found.")
            return

        # Ensure output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Write CSV
        with open(output_file, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        print(f"✅ Data written to {output_file}")

    except (Error, ValueError) as e:
        # Don't crash container startup if DB isn't reachable/configured.
        # entrypoint.sh already runs this script with `|| true`, but avoiding a traceback
        # keeps logs cleaner and makes behavior explicit.
        print(
            f"⚠️ Skipping DB enrichment (cannot connect for env={environment!r}): {e}")
        return
    except Exception as e:
        # Catch-all for unexpected issues (e.g. missing optional tunnel credentials).
        print(f"⚠️ Skipping DB enrichment due to unexpected error: {e}")
        return

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
        if tunnel:
            tunnel.stop()

# -------------------------------------------------
# Script entry point
# -------------------------------------------------


if __name__ == "__main__":
    fetch_items_and_write_csv(APP_ENVIRONMENT, QUERY_RESULT_CSV_PATH)
