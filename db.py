import configparser
from contextlib import closing
from pathlib import Path

import oracledb

_CONFIG_PATH = Path(__file__).parent / "config.ini"


def _config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if not cfg.read(_CONFIG_PATH, encoding="utf-8"):
        raise FileNotFoundError(f"設定ファイルが見つかりません: {_CONFIG_PATH}")
    return cfg


def _connect() -> oracledb.Connection:
    cfg = _config()
    o = cfg["oracle"]
    dsn = f"{o['host']}:{o['port']}/{o['service']}"
    return oracledb.connect(user=o["user"], password=o["password"], dsn=dsn)


def get_company_code() -> int:
    return int(_config()["app"]["company_code"])


def get_branches() -> list[tuple]:
    with closing(_connect()) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT branch_id, branch_name
                FROM mst_branches
                WHERE seq > 0
                  AND is_deleted = 0
                ORDER BY branch_name
            """)
            return cur.fetchall()


def search_employees(
    name: str,
    branch_id: str | None,
    company_code: int,
) -> list[tuple]:
    with closing(_connect()) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    e.employee_id,
                    LISTAGG(b.branch_name, ', ')
                        WITHIN GROUP (ORDER BY b.branch_name) AS department_name,
                    e.employee_name,
                    e.valid_from,
                    e.valid_to
                FROM mst_employees e
                LEFT JOIN mst_dept_members d
                    ON e.employee_id = d.employee_id
                    AND d.company_code = :company_code
                    AND d.seq > 0
                LEFT JOIN mst_branches b
                    ON d.branch_id = b.branch_id
                    AND b.seq > 0
                    AND b.is_deleted = 0
                WHERE e.employee_name LIKE :name
                    AND e.seq > 0
                    AND e.is_deleted = 0
                    AND TRUNC(SYSDATE) BETWEEN e.valid_from AND e.valid_to
                    AND (:branch_id IS NULL OR d.branch_id = :branch_id)
                GROUP BY
                    e.employee_id,
                    e.employee_name,
                    e.valid_from,
                    e.valid_to
                ORDER BY e.employee_id
            """, {
                "company_code": company_code,
                "name": f"%{name}%",
                "branch_id": branch_id,
            })
            return cur.fetchall()
