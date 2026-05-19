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


def get_occupation_values() -> list[str]:
    raw = _config()["occupation"]["values"]
    return [v.strip() for v in raw.split(",") if v.strip()]


# ── 編集用取得 ────────────────────────────────────────


def get_employee(employee_id: str) -> dict | None:
    with closing(_connect()) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT employee_id, employee_name, employee_kana,
                       employee_mail, seq, note, created_at, updated_at
                FROM mst_employees
                WHERE employee_id = :eid
            """, {"eid": employee_id})
            row = cur.fetchone()
            if not row:
                return None
            cols = ["employee_id", "employee_name", "employee_kana",
                    "employee_mail", "seq", "note", "created_at", "updated_at"]
            return dict(zip(cols, row))


def get_dept_members(employee_id: str, company_code: int) -> list[dict]:
    with closing(_connect()) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dept_member_id, employee_id, branch_id,
                       dept_sort_order, main_occupation, sub_occupation,
                       seq, note, created_at, updated_at
                FROM mst_dept_members
                WHERE employee_id = :eid
                  AND company_code = :cc
                  AND seq > 0
                ORDER BY dept_sort_order, dept_member_id
            """, {"eid": employee_id, "cc": company_code})
            cols = ["dept_member_id", "employee_id", "branch_id",
                    "dept_sort_order", "main_occupation", "sub_occupation",
                    "seq", "note", "created_at", "updated_at"]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


# ── 更新 ──────────────────────────────────────────────


def update_employee(data: dict) -> None:
    with closing(_connect()) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE mst_employees
                SET employee_name = :employee_name,
                    employee_kana = :employee_kana,
                    employee_mail = :employee_mail,
                    seq           = :seq,
                    note          = :note,
                    updated_at    = SYSDATE
                WHERE employee_id = :employee_id
            """, data)
        conn.commit()


def update_dept_member(data: dict) -> None:
    with closing(_connect()) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE mst_dept_members
                SET branch_id        = :branch_id,
                    dept_sort_order  = :dept_sort_order,
                    main_occupation  = :main_occupation,
                    sub_occupation   = :sub_occupation,
                    seq              = :seq,
                    note             = :note,
                    updated_at       = SYSDATE
                WHERE dept_member_id = :dept_member_id
            """, data)
        conn.commit()


# ── 登録 ──────────────────────────────────────────────


def insert_employee(data: dict) -> None:
    with closing(_connect()) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO mst_employees
                    (employee_id, employee_name, employee_kana,
                     employee_mail, seq, note, created_at, updated_at)
                VALUES
                    (:employee_id, :employee_name, :employee_kana,
                     :employee_mail, :seq, :note, SYSDATE, SYSDATE)
            """, data)
        conn.commit()


def insert_dept_member(data: dict, company_code: int) -> None:
    with closing(_connect()) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO mst_dept_members
                    (employee_id, company_code, branch_id,
                     dept_sort_order, main_occupation, sub_occupation,
                     seq, note, created_at, updated_at)
                VALUES
                    (:employee_id, :company_code, :branch_id,
                     :dept_sort_order, :main_occupation, :sub_occupation,
                     :seq, :note, SYSDATE, SYSDATE)
            """, {**data, "company_code": company_code})
        conn.commit()


def get_branches_with_seq() -> list[tuple]:
    with closing(_connect()) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT branch_id, branch_name, seq
                FROM mst_branches
                WHERE seq > 0
                  AND is_deleted = 0
                ORDER BY branch_name
            """)
            return cur.fetchall()


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
