import os
import pymysql
from dotenv import load_dotenv

# Load environment variables strictly from .env file
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

# System & Database Configuration strictly from .env (with sensible defaults for new installations)
SECRET_KEY = os.getenv("SECRET_KEY", "crm-default-secret-key-xyz123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "online_crm")


class Config:
    SECRET_KEY = SECRET_KEY
    DB_HOST = DB_HOST
    DB_PORT = DB_PORT
    DB_USER = DB_USER
    DB_PASSWORD = DB_PASSWORD
    DB_NAME = DB_NAME
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SEND_FILE_MAX_AGE_DEFAULT = 0
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024
    MAX_FORM_MEMORY_SIZE = 500 * 1024 * 1024
    MAX_FORM_PARTS = 500_000


def get_db_connection():
    try:
        return pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD or "",
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
    except Exception as e:
        print("Database connection failed: Check your database configuration in .env", e)
        return None


