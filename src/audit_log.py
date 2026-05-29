"""CSV audit logger — retains logs for 365 days."""
import csv
import io
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_handler = TimedRotatingFileHandler(
    _LOG_DIR / "audit.csv",
    when="midnight",
    interval=1,
    backupCount=365,
    encoding="utf-8-sig",
)
_handler.setFormatter(logging.Formatter("%(message)s"))

_logger = logging.getLogger("audit")
_logger.setLevel(logging.INFO)
_logger.addHandler(_handler)
_logger.propagate = False


def _to_csv_line(row: dict) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(row.keys()))
    writer.writerow(row)
    return buf.getvalue().rstrip("\r\n")


def _header_line(fields: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(fields)
    return buf.getvalue().rstrip("\r\n")


def log_before_update(table: str, data: dict) -> None:
    row = {"action": "BEFORE_UPDATE", "table": table, **data}
    _logger.info(_to_csv_line(row))


def log_insert(table: str, data: dict) -> None:
    row = {"action": "INSERT", "table": table, **data}
    _logger.info(_to_csv_line(row))
