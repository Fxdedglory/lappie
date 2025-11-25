# echo: file_searcher init_db v0.1.1 2025-11-24

"""
Init script to apply db/db_schema.sql to the configured Postgres database.

Sections:
  1) Imports & constants
  2) Environment loading / config
  3) Connection factory
  4) DDL loader
  5) Main entrypoint
"""

# =====================================================
# 1) Imports & constants
# =====================================================

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


# =====================================================
# 2) Environment loading / config
# =====================================================

def load_config() -> dict:
    """
    Load database configuration from .env at project root.

    Expected keys:
      PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD

    Returns:
        dict with keys: host, port, dbname, user, password
    """
    # Resolve project root: src/file_searcher/init_db.py -> src -> project root
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent

    # Explicitly load .env from project root
    env_path = project_root / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
    else:
        # Fallback: default dotenv behavior (current working directory)
        load_dotenv()

    host = os.getenv("PGHOST", "localhost")
    port = int(os.getenv("PGPORT", "5432"))
    dbname = os.getenv("PGDATABASE", "file_searcher")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD")

    if password is None:
        raise RuntimeError("PGPASSWORD is not set in .env")

    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
        "project_root": project_root,
    }


# =====================================================
# 3) Connection factory
# =====================================================

def get_conn(config: dict):
    """
    Create a psycopg2 connection using the provided config dict.

    Keys used:
      host, port, dbname, user, password
    """
    conn = psycopg2.connect(
        host=config["host"],
        port=config["port"],
        dbname=config["dbname"],
        user=config["user"],
        password=config["password"],
    )
    return conn


# =====================================================
# 4) DDL loader
# =====================================================

def resolve_ddl_path(project_root: Path) -> Path:
    """
    Resolve the path to db_schema.sql.

    Current convention:
      E:/lappie/dev/file_searcher/db/db_schema.sql

    Fallback:
      project_root / "db_schema.sql"  (if needed)
    """
    db_folder_path = project_root / "db" / "db_schema.sql"
    root_path = project_root / "db_schema.sql"

    if db_folder_path.is_file():
        return db_folder_path
    if root_path.is_file():
        return root_path

    raise FileNotFoundError(
        f"DDL file not found. Tried:\n"
        f"  - {db_folder_path}\n"
        f"  - {root_path}"
    )


def run_ddl() -> None:
    """
    Load db_schema.sql and execute it against the configured database.

    This is intended to be idempotent:
      - CREATE SCHEMA IF NOT EXISTS
      - CREATE TABLE IF NOT EXISTS
      - etc.
    """
    config = load_config()
    project_root: Path = config["project_root"]

    ddl_path = resolve_ddl_path(project_root)
    ddl_sql = ddl_path.read_text(encoding="utf-8")

    conn = get_conn(config)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(ddl_sql)
        print(f"DDL executed successfully from: {ddl_path}")
    finally:
        conn.close()


# =====================================================
# 5) Main entrypoint
# =====================================================

if __name__ == "__main__":
    run_ddl()
