import os

import mysql.connector

def connect_db():
    return mysql.connector.connect(
        host=(
            os.environ.get("DB_HOST")
            or os.environ.get("MYSQLHOST", "localhost")
        ),
        user=os.environ.get("DB_USER") or os.environ.get("MYSQLUSER", "root"),
        password=os.environ.get("DB_PASSWORD") or os.environ.get("MYSQLPASSWORD", ""),
        database=(
            os.environ.get("DB_NAME")
            or os.environ.get("MYSQLDATABASE", "finder_db")
        ),
        port=int(
            os.environ.get("DB_PORT")
            or os.environ.get("MYSQLPORT", "3306")
        )
    )