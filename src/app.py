import threading
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk

import customtkinter as ctk

from . import db
from .dialogs import CreateDialog, EditDialog

_COLUMNS = ("employee_id", "branch_name", "employee_name", "valid_from", "valid_to")
_HEADERS = ("社員番号", "支店", "氏名", "有効from", "有効to")
_WIDTHS = (100, 180, 130, 90, 90)
_STRETCH = {"branch_name", "employee_name"}

_TREE_BG = "#3c3c3c"
_TREE_FG = "#eeeeee"
_TREE_SEL = "#505050"
_TREE_HEAD = "#2b2b2b"


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("社員検索")
        self.geometry("600x400")
        self.minsize(480, 300)

        self._branch_map: dict[str, str | None] = {"すべて": None}
        self._branch_id_map: dict[str, str] = {}
        self._occupation_values: list[str] = []
        self._company_code: int = 1
        self._search_seq: int = 0
        self._pending_after: str | None = None

        self._build_ui()
        self.after(0, self._init_config)

    # ── 初期化 ──────────────────────────────────────

    def _init_config(self) -> None:
        try:
            self._company_code = db.get_company_code()
            self._occupation_values = db.get_occupation_values()
        except Exception as exc:
            messagebox.showerror("設定エラー", f"設定ファイルの読み込みに失敗しました。\n{exc}")
            return
        self._load_branches()

    # ── UI構築 ──────────────────────────────────────

    def _build_ui(self) -> None:
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))

        ctk.CTkLabel(top, text="氏名:").pack(side="left")
        self._name_var = tk.StringVar()
        self._name_var.trace_add("write", self._on_name_changed)
        ctk.CTkEntry(top, textvariable=self._name_var, width=160).pack(
            side="left", padx=(4, 12)
        )

        ctk.CTkLabel(top, text="支店:").pack(side="left")
        self._branch_var = tk.StringVar(value="すべて")
        self._branch_combo = ctk.CTkComboBox(
            top,
            variable=self._branch_var,
            values=["すべて"],
            width=170,
            command=lambda _: self._search_now(),
        )
        self._branch_combo.pack(side="left", padx=(4, 12))

        self._search_btn = ctk.CTkButton(
            top, text="検索", width=70, command=self._search_now
        )
        self._search_btn.pack(side="left")

        ctk.CTkButton(
            top, text="新規作成", width=80, command=self._open_create_dialog
        ).pack(side="left", padx=(8, 0))

        self._menu_btn = ctk.CTkButton(
            top, text="▼", width=36, command=self._show_menu
        )
        self._menu_btn.pack(side="right")

        self._menu = tk.Menu(self, tearoff=False)
        self._menu.add_command(label="支店コード確認", command=self._open_branch_dialog)

        self._status_var = tk.StringVar(value="")
        status = ctk.CTkLabel(
            self,
            textvariable=self._status_var,
            anchor="w",
            fg_color=("gray80", "gray17"),
            corner_radius=0,
            height=26,
        )
        status.pack(fill="x", side="bottom")

        table_frame = tk.Frame(self, bg=_TREE_BG)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        self._tree = self._build_treeview(table_frame)

    def _build_treeview(self, parent: tk.Frame) -> ttk.Treeview:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "S.Treeview",
            background=_TREE_BG,
            foreground=_TREE_FG,
            fieldbackground=_TREE_BG,
            rowheight=26,
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "S.Treeview.Heading",
            background=_TREE_HEAD,
            foreground=_TREE_FG,
            relief="flat",
        )
        style.map(
            "S.Treeview",
            background=[("selected", _TREE_SEL)],
            foreground=[("selected", _TREE_FG)],
        )

        vsb = ttk.Scrollbar(parent, orient="vertical")
        hsb = ttk.Scrollbar(parent, orient="horizontal")
        tree = ttk.Treeview(
            parent,
            columns=_COLUMNS,
            show="headings",
            style="S.Treeview",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
        )
        vsb.configure(command=tree.yview)
        hsb.configure(command=tree.xview)

        for col, header, width in zip(_COLUMNS, _HEADERS, _WIDTHS):
            tree.heading(col, text=header)
            tree.column(col, width=width, minwidth=50, stretch=(col in _STRETCH))

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True)

        tree.bind("<ButtonRelease-1>", self._on_cell_click)
        tree.bind("<Double-ButtonRelease-1>", self._on_row_dblclick)
        return tree

    # ── メニュー ────────────────────────────────────

    def _show_menu(self) -> None:
        btn = self._menu_btn
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        self._menu.tk_popup(x, y)

    def _open_branch_dialog(self) -> None:
        win = tk.Toplevel(self)
        win.title("支店コード一覧")
        win.geometry("420x400")
        win.minsize(320, 200)
        win.configure(bg=_TREE_BG)

        cols = ("branch_id", "branch_name", "seq")
        headers = ("支店コード", "支店名", "SEQ")
        widths = (100, 220, 60)

        frame = tk.Frame(win, bg=_TREE_BG)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        vsb = ttk.Scrollbar(frame, orient="vertical")
        tree = ttk.Treeview(
            frame,
            columns=cols,
            show="headings",
            style="S.Treeview",
            yscrollcommand=vsb.set,
        )
        vsb.configure(command=tree.yview)

        for col, header, width in zip(cols, headers, widths):
            tree.heading(col, text=header)
            tree.column(col, width=width, minwidth=40, stretch=(col == "branch_name"))

        vsb.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)

        status = ctk.CTkLabel(
            win,
            text="読み込み中...",
            anchor="w",
            fg_color=("gray80", "gray17"),
            corner_radius=0,
            height=24,
        )
        status.pack(fill="x", side="bottom")

        def fetch() -> None:
            try:
                rows = db.get_branches_with_seq()
                win.after(0, apply, rows)
            except Exception as exc:
                win.after(0, lambda: messagebox.showerror("エラー", f"支店一覧の取得に失敗しました。\n{exc}", parent=win))
                win.after(0, lambda: status.configure(text=""))

        def apply(rows: list[tuple]) -> None:
            for row in rows:
                tree.insert("", "end", values=row)
            status.configure(text=f"{len(rows)} 件")

        threading.Thread(target=fetch, daemon=True).start()

    # ── 支店読み込み ────────────────────────────────

    def _load_branches(self) -> None:
        self._status_var.set("支店一覧を読み込み中...")
        threading.Thread(target=self._fetch_branches, daemon=True).start()

    def _fetch_branches(self) -> None:
        try:
            rows = db.get_branches()
            self.after(0, self._apply_branches, rows)
        except Exception as exc:
            self.after(0, messagebox.showerror, "エラー", f"支店一覧の取得に失敗しました。\n{exc}")
            self.after(0, self._status_var.set, "")

    def _apply_branches(self, rows: list[tuple]) -> None:
        self._branch_map = {"すべて": None}
        self._branch_id_map = {}
        names = ["すべて"]
        for branch_id, branch_name in rows:
            self._branch_map[branch_name] = branch_id
            self._branch_id_map[branch_id] = branch_name
            names.append(branch_name)
        self._branch_combo.configure(values=names)
        self._status_var.set("")

    # ── 検索 ────────────────────────────────────────

    def _on_name_changed(self, *_) -> None:
        if self._pending_after:
            self.after_cancel(self._pending_after)
        self._pending_after = self.after(300, self._search_now)

    def _search_now(self) -> None:
        if self._pending_after:
            self.after_cancel(self._pending_after)
            self._pending_after = None

        name = self._name_var.get()
        branch_id = self._branch_map.get(self._branch_var.get())

        self._search_seq += 1
        seq = self._search_seq
        self._set_busy(True)

        threading.Thread(
            target=self._run_search,
            args=(name, branch_id, seq),
            daemon=True,
        ).start()

    def _run_search(self, name: str, branch_id: str | None, seq: int) -> None:
        try:
            rows = db.search_employees(name, branch_id, self._company_code)
            if seq == self._search_seq:
                self.after(0, self._show_results, rows)
        except Exception as exc:
            if seq == self._search_seq:
                self.after(0, self._on_search_error, exc)

    def _show_results(self, rows: list[tuple]) -> None:
        self._set_busy(False)
        for item in self._tree.get_children():
            self._tree.delete(item)

        if not rows:
            self._status_var.set("該当者なし")
            return

        for row in rows:
            values: list[str] = []
            for i, v in enumerate(row):
                if i in (3, 4) and isinstance(v, (datetime, date)):
                    values.append(v.strftime("%Y/%m/%d"))
                else:
                    values.append("" if v is None else str(v))
            self._tree.insert("", "end", values=values)

        self._status_var.set("")

    def _on_search_error(self, exc: Exception) -> None:
        self._set_busy(False)
        messagebox.showerror("エラー", f"検索に失敗しました。\n{exc}")

    def _set_busy(self, busy: bool) -> None:
        if busy:
            self._search_btn.configure(state="disabled", text="検索中...")
        else:
            self._search_btn.configure(state="normal", text="検索")

    # ── 編集・新規作成 ───────────────────────────────

    def _on_row_dblclick(self, event: tk.Event) -> None:
        row_id = self._tree.identify_row(event.y)
        if not row_id:
            return
        employee_id = self._tree.item(row_id, "values")[0]
        self._open_edit_dialog(str(employee_id))

    def _open_edit_dialog(self, employee_id: str) -> None:
        branch_names = [n for n in self._branch_map if n != "すべて"]
        EditDialog(
            self,
            employee_id=employee_id,
            branch_names=branch_names,
            branch_map={k: v for k, v in self._branch_map.items() if k != "すべて"},
            branch_id_map=self._branch_id_map,
            occupations=self._occupation_values,
            company_code=self._company_code,
            on_saved=self._search_now,
        )

    def _open_create_dialog(self) -> None:
        branch_names = [n for n in self._branch_map if n != "すべて"]
        CreateDialog(
            self,
            branch_names=branch_names,
            branch_map={k: v for k, v in self._branch_map.items() if k != "すべて"},
            occupations=self._occupation_values,
            company_code=self._company_code,
            on_saved=self._search_now,
        )

    # ── セルクリック ────────────────────────────────

    def _on_cell_click(self, event: tk.Event) -> None:
        if self._tree.identify_region(event.x, event.y) != "cell":
            return
        col = self._tree.identify_column(event.x)
        row_id = self._tree.identify_row(event.y)
        if not row_id:
            return
        col_index = int(col.lstrip("#")) - 1
        value = self._tree.item(row_id, "values")[col_index]
        self.clipboard_clear()
        self.clipboard_append(str(value))
        self._status_var.set(f"コピーしました：{value}")
