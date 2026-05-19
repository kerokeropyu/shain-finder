"""Edit and create dialogs for employee records."""
import re
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

import audit_log
import db

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CHANGED = "#f0a000"
_LW = 10   # label width (chars)
_EW = 220  # entry width (px)
_BG = "#2b2b2b"
_FG = "#cccccc"


def _str_var(val) -> tk.StringVar:
    return tk.StringVar(value="" if val is None else str(val))


def _label(parent, text: str, row: int, col: int = 0) -> None:
    tk.Label(parent, text=text, anchor="e", width=_LW,
             bg=_BG, fg=_FG).grid(row=row, column=col, sticky="e", padx=(8, 4), pady=3)


def _entry(parent, var: tk.StringVar, row: int, col: int = 1, *,
           width: int = _EW, state: str = "normal") -> ctk.CTkEntry:
    e = ctk.CTkEntry(parent, textvariable=var, width=width, state=state)
    e.grid(row=row, column=col, sticky="w", padx=(0, 8), pady=3)
    return e


def _tracked_entry(parent, var: tk.StringVar, original,
                   row: int, col: int = 1, *, width: int = _EW) -> ctk.CTkEntry:
    e = _entry(parent, var, row, col, width=width)
    orig_str = "" if original is None else str(original)
    default_color = e.cget("text_color")
    var.trace_add("write", lambda *_: e.configure(
        text_color=_CHANGED if var.get() != orig_str else default_color))
    return e


def _int_validate(val: str) -> bool:
    s = val.strip()
    return not s or s.lstrip("-").isdigit()


class EditDialog(tk.Toplevel):
    def __init__(self, parent, employee_id: str, branch_names: list[str],
                 branch_map: dict, branch_id_map: dict, occupations: list[str],
                 company_code: int, on_saved=None):
        super().__init__(parent)
        self.title(f"社員情報編集 — {employee_id}")
        self.geometry("520x640")
        self.minsize(420, 500)
        self.configure(bg=_BG)
        self.grab_set()

        self._eid = employee_id
        self._branch_names = branch_names
        self._branch_map = branch_map
        self._branch_id_map = branch_id_map
        self._occupations = occupations
        self._company_code = company_code
        self._on_saved = on_saved

        self._emp_vars: dict[str, tk.StringVar] = {}
        self._dept_vars: list[dict[str, tk.StringVar]] = []
        self._dept_originals: list[dict] = []
        self._dept_ids: list = []
        self._save_btn: ctk.CTkButton | None = None

        self._status_lbl = ctk.CTkLabel(self, text="読み込み中...")
        self._status_lbl.pack(pady=20)
        threading.Thread(target=self._load, daemon=True).start()

    # ── データ取得 ────────────────────────────────────

    def _load(self) -> None:
        try:
            emp = db.get_employee(self._eid)
            depts = db.get_dept_members(self._eid, self._company_code)
            self.after(0, self._populate, emp, depts)
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("エラー", str(exc), parent=self))
            self.after(0, self.destroy)

    def _populate(self, emp: dict | None, depts: list[dict]) -> None:
        if emp is None:
            messagebox.showerror("エラー", "社員データが見つかりません。", parent=self)
            self.destroy()
            return

        for w in self.winfo_children():
            w.destroy()

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        self._build_emp_section(scroll, emp)
        self._build_dept_section(scroll, depts)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=8)
        self._save_btn = ctk.CTkButton(btn_frame, text="保存", width=100, command=self._save)
        self._save_btn.pack(side="right", padx=12)
        ctk.CTkButton(btn_frame, text="キャンセル", width=100,
                      fg_color="gray40", command=self.destroy).pack(side="right", padx=4)

    # ── フォーム構築 ──────────────────────────────────

    def _build_emp_section(self, parent, emp: dict) -> None:
        sec = ctk.CTkFrame(parent)
        sec.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(sec, text="■ 社員マスタ", anchor="w").pack(anchor="w", padx=8, pady=(6, 2))
        grid = tk.Frame(sec, bg=_BG)
        grid.pack(fill="x", padx=8, pady=(0, 6))

        fields = [
            ("社員番号", "employee_id",   False),
            ("氏名",     "employee_name", True),
            ("カナ",     "employee_kana", True),
            ("メール",   "employee_mail", True),
            ("SEQ",      "seq",           True),
            ("備考",     "note",          True),
        ]
        for i, (lbl, col, editable) in enumerate(fields):
            var = _str_var(emp.get(col))
            self._emp_vars[col] = var
            _label(grid, lbl, i)
            if editable:
                _tracked_entry(grid, var, emp.get(col), i)
            else:
                _entry(grid, var, i, state="disabled")

    def _build_dept_section(self, parent, depts: list[dict]) -> None:
        sec = ctk.CTkFrame(parent)
        sec.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(sec, text="■ 所属情報", anchor="w").pack(anchor="w", padx=8, pady=(6, 2))

        if not depts:
            ctk.CTkLabel(sec, text="所属レコードなし", text_color="gray60").pack(pady=8)
            return

        from tkinter import ttk
        nb = ttk.Notebook(sec)
        nb.pack(fill="x", padx=8, pady=(0, 6))

        for dm in depts:
            tab_lbl = self._branch_id_map.get(dm["branch_id"], dm["branch_id"] or "不明")
            frame = tk.Frame(nb, bg=_BG)
            nb.add(frame, text=tab_lbl)
            self._build_dept_tab(frame, dm)

    def _build_dept_tab(self, parent: tk.Frame, dm: dict) -> None:
        orig_str = {k: ("" if v is None else str(v)) for k, v in dm.items()}
        occ_all = [""] + self._occupations

        branch_var = _str_var(self._branch_id_map.get(dm["branch_id"], dm["branch_id"]))
        order_var  = _str_var(dm.get("dept_sort_order"))
        main_var   = _str_var(dm.get("main_occupation"))
        sub_var    = _str_var(dm.get("sub_occupation"))
        seq_var    = _str_var(dm.get("seq"))
        note_var   = _str_var(dm.get("note"))

        self._dept_vars.append({
            "branch_name": branch_var, "dept_sort_order": order_var,
            "main_occupation": main_var, "sub_occupation": sub_var,
            "seq": seq_var, "note": note_var,
        })
        self._dept_originals.append(orig_str)
        self._dept_ids.append(dm["dept_member_id"])

        orig_bn   = self._branch_id_map.get(dm["branch_id"], dm["branch_id"] or "")
        orig_main = orig_str.get("main_occupation", "")
        orig_sub  = orig_str.get("sub_occupation", "")

        # 支店
        _label(parent, "支店", 0)
        b_cb = ctk.CTkComboBox(parent, variable=branch_var,
                               values=[""] + self._branch_names, width=_EW)
        b_cb.grid(row=0, column=1, sticky="w", padx=(0, 8), pady=3)
        b_def = b_cb.cget("text_color")
        branch_var.trace_add("write", lambda *_: b_cb.configure(
            text_color=_CHANGED if branch_var.get() != orig_bn else b_def))

        # 所属順
        _label(parent, "所属順", 1)
        _tracked_entry(parent, order_var, dm.get("dept_sort_order"), 1)

        # 職種（相互排他）
        _label(parent, "主職種", 2)
        m_cb = ctk.CTkComboBox(parent, variable=main_var, values=occ_all, width=_EW)
        m_cb.grid(row=2, column=1, sticky="w", padx=(0, 8), pady=3)
        m_def = m_cb.cget("text_color")

        _label(parent, "副職種", 3)
        s_cb = ctk.CTkComboBox(parent, variable=sub_var, values=occ_all, width=_EW)
        s_cb.grid(row=3, column=1, sticky="w", padx=(0, 8), pady=3)
        s_def = s_cb.cget("text_color")

        _lock = False

        def _sync_occ(*_):
            nonlocal _lock
            if _lock:
                return
            _lock = True
            try:
                m, s = main_var.get(), sub_var.get()
                m_cb.configure(values=[o for o in occ_all if o != s],
                               text_color=_CHANGED if m != orig_main else m_def)
                s_cb.configure(values=[o for o in occ_all if o != m],
                               text_color=_CHANGED if sub_var.get() != orig_sub else s_def)
                if m and m == s:
                    sub_var.set("")
            finally:
                _lock = False

        main_var.trace_add("write", _sync_occ)
        sub_var.trace_add("write", _sync_occ)

        _label(parent, "SEQ", 4)
        _tracked_entry(parent, seq_var, dm.get("seq"), 4)
        _label(parent, "備考", 5)
        _tracked_entry(parent, note_var, dm.get("note"), 5)

    # ── 保存 ──────────────────────────────────────────

    def _save(self) -> None:
        emp_seq = self._emp_vars["seq"].get().strip()
        if not _int_validate(emp_seq):
            messagebox.showwarning("入力エラー", "社員マスタのSEQは整数で入力してください。", parent=self)
            return

        for i, v in enumerate(self._dept_vars):
            for fname, label in [("dept_sort_order", "所属順"), ("seq", "SEQ")]:
                if not _int_validate(v[fname].get()):
                    messagebox.showwarning("入力エラー",
                        f"所属情報タブ{i+1}の{label}は整数で入力してください。", parent=self)
                    return

        emp_data = {k: (var.get() or None) for k, var in self._emp_vars.items()}
        emp_data["seq"] = int(emp_seq) if emp_seq else None

        dept_updates = []
        for v, did in zip(self._dept_vars, self._dept_ids):
            bn = v["branch_name"].get()
            d_ord = v["dept_sort_order"].get().strip()
            d_seq = v["seq"].get().strip()
            dept_updates.append({
                "dept_member_id":  did,
                "branch_id":       self._branch_map.get(bn),
                "dept_sort_order": int(d_ord) if d_ord else None,
                "main_occupation": v["main_occupation"].get() or None,
                "sub_occupation":  v["sub_occupation"].get() or None,
                "seq":             int(d_seq) if d_seq else None,
                "note":            v["note"].get() or None,
            })

        if self._save_btn:
            self._save_btn.configure(state="disabled", text="保存中...")
        threading.Thread(target=self._do_save, args=(emp_data, dept_updates), daemon=True).start()

    def _do_save(self, emp_data: dict, dept_updates: list[dict]) -> None:
        try:
            audit_log.log_before_update("mst_employees",
                                        {k: v.get() for k, v in self._emp_vars.items()})
            db.update_employee(emp_data)

            for du in dept_updates:
                orig = next((o for i, o in enumerate(self._dept_originals)
                             if self._dept_ids[i] == du["dept_member_id"]), {})
                audit_log.log_before_update("mst_dept_members", orig)
                db.update_dept_member(du)

            self.after(0, self._finish)
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("保存エラー", str(exc), parent=self))
            self.after(0, lambda: self._save_btn and
                       self._save_btn.configure(state="normal", text="保存"))

    def _finish(self) -> None:
        if self._on_saved:
            self._on_saved()
        self.destroy()


class CreateDialog(tk.Toplevel):
    def __init__(self, parent, branch_names: list[str], branch_map: dict,
                 occupations: list[str], company_code: int, on_saved=None):
        super().__init__(parent)
        self.title("社員新規登録")
        self.geometry("520x620")
        self.minsize(420, 480)
        self.configure(bg=_BG)
        self.grab_set()

        self._branch_names = branch_names
        self._branch_map = branch_map
        self._occupations = occupations
        self._company_code = company_code
        self._on_saved = on_saved
        self._save_btn: ctk.CTkButton | None = None

        self._ev: dict[str, tk.StringVar] = {}
        self._dv: dict[str, tk.StringVar] = {}
        self._m_cb: ctk.CTkComboBox | None = None
        self._s_cb: ctk.CTkComboBox | None = None

        self._build_form()

    def _build_form(self) -> None:
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        # ── 社員マスタ ──
        emp_sec = ctk.CTkFrame(scroll)
        emp_sec.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(emp_sec, text="■ 社員マスタ", anchor="w").pack(anchor="w", padx=8, pady=(6, 2))
        eg = tk.Frame(emp_sec, bg=_BG)
        eg.pack(fill="x", padx=8, pady=(0, 6))

        for col in ("employee_id", "employee_name", "employee_kana",
                    "employee_mail", "seq", "note"):
            self._ev[col] = tk.StringVar()

        for i, (lbl, col) in enumerate([
            ("社員番号", "employee_id"),
            ("氏名",     "employee_name"),
            ("カナ",     "employee_kana"),
            ("メール",   "employee_mail"),
            ("SEQ",      "seq"),
            ("備考",     "note"),
        ]):
            _label(eg, lbl, i)
            _entry(eg, self._ev[col], i)

        # ── 所属情報 ──
        dept_sec = ctk.CTkFrame(scroll)
        dept_sec.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(dept_sec, text="■ 所属情報", anchor="w").pack(anchor="w", padx=8, pady=(6, 2))
        dg = tk.Frame(dept_sec, bg=_BG)
        dg.pack(fill="x", padx=8, pady=(0, 6))

        for col in ("branch_name", "dept_sort_order", "main_occupation",
                    "sub_occupation", "seq", "note"):
            self._dv[col] = tk.StringVar()

        occ_all = [""] + self._occupations

        _label(dg, "支店", 0)
        ctk.CTkComboBox(dg, variable=self._dv["branch_name"],
                        values=[""] + self._branch_names, width=_EW).grid(
            row=0, column=1, sticky="w", padx=(0, 8), pady=3)

        _label(dg, "所属順", 1)
        _entry(dg, self._dv["dept_sort_order"], 1)

        _label(dg, "主職種", 2)
        self._m_cb = ctk.CTkComboBox(dg, variable=self._dv["main_occupation"],
                                     values=occ_all, width=_EW)
        self._m_cb.grid(row=2, column=1, sticky="w", padx=(0, 8), pady=3)

        _label(dg, "副職種", 3)
        self._s_cb = ctk.CTkComboBox(dg, variable=self._dv["sub_occupation"],
                                     values=occ_all, width=_EW)
        self._s_cb.grid(row=3, column=1, sticky="w", padx=(0, 8), pady=3)

        _lock = False

        def _sync(*_):
            nonlocal _lock
            if _lock:
                return
            _lock = True
            try:
                m, s = self._dv["main_occupation"].get(), self._dv["sub_occupation"].get()
                self._m_cb.configure(values=[o for o in occ_all if o != s])
                self._s_cb.configure(values=[o for o in occ_all if o != m])
                if m and m == s:
                    self._dv["sub_occupation"].set("")
            finally:
                _lock = False

        self._dv["main_occupation"].trace_add("write", _sync)
        self._dv["sub_occupation"].trace_add("write", _sync)

        _label(dg, "SEQ",  4)
        _entry(dg, self._dv["seq"],  4)
        _label(dg, "備考", 5)
        _entry(dg, self._dv["note"], 5)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=8)
        self._save_btn = ctk.CTkButton(btn_frame, text="登録", width=100, command=self._save)
        self._save_btn.pack(side="right", padx=12)
        ctk.CTkButton(btn_frame, text="キャンセル", width=100,
                      fg_color="gray40", command=self.destroy).pack(side="right", padx=4)

    def _save(self) -> None:
        mail = self._ev["employee_mail"].get().strip()
        if mail and not _EMAIL_RE.match(mail):
            messagebox.showwarning("入力エラー", "メールアドレスの形式が正しくありません。", parent=self)
            return

        for label, key in [("社員マスタのSEQ", "seq")]:
            if not _int_validate(self._ev[key].get()):
                messagebox.showwarning("入力エラー", f"{label}は整数で入力してください。", parent=self)
                return

        for label, key in [("所属順", "dept_sort_order"), ("所属SEQ", "seq")]:
            if not _int_validate(self._dv[key].get()):
                messagebox.showwarning("入力エラー", f"{label}は整数で入力してください。", parent=self)
                return

        emp_seq = self._ev["seq"].get().strip()
        d_ord   = self._dv["dept_sort_order"].get().strip()
        d_seq   = self._dv["seq"].get().strip()

        emp_data = {
            "employee_id":   self._ev["employee_id"].get().strip() or None,
            "employee_name": self._ev["employee_name"].get() or None,
            "employee_kana": self._ev["employee_kana"].get() or None,
            "employee_mail": mail or None,
            "seq":           int(emp_seq) if emp_seq else None,
            "note":          self._ev["note"].get() or None,
        }
        bn = self._dv["branch_name"].get()
        dept_data = {
            "employee_id":     emp_data["employee_id"],
            "branch_id":       self._branch_map.get(bn),
            "dept_sort_order": int(d_ord) if d_ord else None,
            "main_occupation": self._dv["main_occupation"].get() or None,
            "sub_occupation":  self._dv["sub_occupation"].get() or None,
            "seq":             int(d_seq) if d_seq else None,
            "note":            self._dv["note"].get() or None,
        }

        if self._save_btn:
            self._save_btn.configure(state="disabled", text="登録中...")
        threading.Thread(target=self._do_save, args=(emp_data, dept_data), daemon=True).start()

    def _do_save(self, emp_data: dict, dept_data: dict) -> None:
        try:
            audit_log.log_insert("mst_employees", emp_data)
            db.insert_employee(emp_data)
            if dept_data.get("branch_id") is not None:
                audit_log.log_insert("mst_dept_members", dept_data)
                db.insert_dept_member(dept_data, self._company_code)
            self.after(0, self._finish)
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("登録エラー", str(exc), parent=self))
            self.after(0, lambda: self._save_btn and
                       self._save_btn.configure(state="normal", text="登録"))

    def _finish(self) -> None:
        if self._on_saved:
            self._on_saved()
        self.destroy()
