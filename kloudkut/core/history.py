"""Scan history — SQLite-backed trend tracking."""
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, UTC
from pathlib import Path

_DB = Path(".kloudkut_history.db")
_logger = logging.getLogger(__name__)
_DDL = """CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scanned_at TEXT NOT NULL,
    total_findings INTEGER,
    monthly_savings REAL,
    annual_savings REAL,
    findings_json TEXT
)"""


@contextmanager
def _connect():
    conn = sqlite3.connect(_DB)
    try:
        conn.execute(_DDL)
        conn.commit()
        yield conn
    finally:
        conn.close()


def save_scan(findings: list) -> None:
    from dataclasses import asdict
    monthly = round(sum(f.monthly_cost for f in findings), 2)
    with _connect() as c:
        c.execute(
            "INSERT INTO scans (scanned_at, total_findings, monthly_savings, annual_savings, findings_json) VALUES (?,?,?,?,?)",
            (datetime.now(UTC).isoformat(), len(findings), monthly, round(monthly * 12, 2),
             json.dumps([asdict(f) for f in findings], default=str))
        )
        c.commit()


def get_trend(limit: int = 30) -> list[dict]:
    try:
        with _connect() as c:
            rows = c.execute(
                "SELECT scanned_at, total_findings, monthly_savings FROM scans ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [{"scanned_at": r[0], "total_findings": r[1], "monthly_savings": r[2]}
                for r in reversed(rows)]
    except sqlite3.Error as e:
        _logger.warning("get_trend failed: %s", e)
        return []


def get_delta() -> dict:
    try:
        with _connect() as c:
            rows = c.execute(
                "SELECT monthly_savings FROM scans ORDER BY id DESC LIMIT 2"
            ).fetchall()
        if len(rows) < 2:
            return {}
        current, previous = rows[0][0], rows[1][0]
        return {"current": current, "previous": previous, "delta": round(current - previous, 2)}
    except sqlite3.Error as e:
        _logger.warning("get_delta failed: %s", e)
        return {}
