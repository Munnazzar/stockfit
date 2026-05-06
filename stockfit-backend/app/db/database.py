from typing import Generator

import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor

from app.core.config import get_settings


def get_db() -> Generator[psycopg2.extensions.connection, None, None]:
    settings = get_settings()
    conn = psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        cursor_factory=RealDictCursor,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
