import sys
import os
import site

user_site = site.getusersitepackages()
if os.path.exists(user_site) and user_site not in sys.path:
    sys.path.insert(0, user_site)

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# Ensure path includes root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.storage import load_accounts, save_accounts
from core.bot import BotRunner

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class DesktopApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Discord Voice Multi-Bot")
        self.root.geometry("880x640")
        self.root.minsize(750, 520)
        self.root.configure(bg="#0f0f1a")

        self.accounts = load_accounts()
        self.runners = {}

        self._style()
        self._build_ui()
        self._refresh_list()

        # Auto start all accounts on launch
        self.root.after(1000, self._start_all)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        BG = "#0f0f1a"
        PANEL = "#17172a"
        FG = "#f0f0f5"
        ACCENT = "#5865F2"

        s.configure(".", background=BG, foreground=FG, font=("Segoe UI", 9))
        s.configure("TFrame", background=BG)
        s.configure("Panel.TFrame", background=PANEL)
        s.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 9))
        s.configure("Header.TLabel", font=("Segoe UI", 13, "bold"), foreground="#ffffff")
        s.configure("Sub.TLabel", font=("Segoe UI", 8), foreground="#8a8aa3")

        s.configure("TButton", font=("Segoe UI", 9, "bold"), padding=(10, 5), relief="flat")
        s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff")
        s.map("Accent.TButton", background=[("active", "#4752c4")])

        s.configure("Green.TButton", background="#23a55a", foreground="#ffffff")
        s.map("Green.TButton", background=[("active", "#1b8547")])

        s.configure("Red.TButton", background="#da373c", foreground="#ffffff")
        s.map("Red.TButton", background=[("active", "#b82b30")])

        s.configure("Treeview", background="#121224", foreground=FG, fieldbackground="#121224",
                    font=("Segoe UI", 9), rowheight=30, borderwidth=0)
        s.configure("Treeview.Heading", background="#1e1e38", foreground="#ffffff",
                    font=("Segoe UI", 9, "bold"), padding=5)
        s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#ffffff")])

    def _build_ui(self):
        hdr = ttk.Frame(self.root)
        hdr.pack(fill="x", padx=14, pady=(12, 6))

        h_left = ttk.Frame(hdr)
        h_left.pack(side="left")
        ttk.Label(h_left, text="Discord Multi-Account Voice", style="Header.TLabel").pack(anchor="w")
        ttk.Label(h_left, text="Keep multiple selfbot accounts in voice channels 24/7", style="Sub.TLabel").pack(anchor="w")

        h_right = ttk.Frame(hdr)
        h_right.pack(side="right")
        ttk.Button(h_right, text="+ Add Account", style="Accent.TButton", command=self._add_dialog).pack(side="left", padx=3)
        ttk.Button(h_right, text="Start All", style="Green.TButton", command=self._start_all).pack(side="left", padx=3)
        ttk.Button(h_right, text="Stop All", style="Red.TButton", command=self._stop_all).pack(side="left", padx=3)

        tbl_frame = ttk.Frame(self.root)
        tbl_frame.pack(fill="both", expand=True, padx=14, pady=6)

        cols = ("name", "status", "info", "settings", "guild_id", "channel_id")
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=7)
        self.tree.heading("name", text="Account")
        self.tree.heading("status", text="Status")
        self.tree.heading("info", text="Detail")
        self.tree.heading("settings", text="Audio")
        self.tree.heading("guild_id", text="Server ID")
        self.tree.heading("channel_id", text="Voice ID")

        self.tree.column("name", width=120, anchor="w")
        self.tree.column("status", width=95, anchor="center")
        self.tree.column("info", width=150, anchor="w")
        self.tree.column("settings", width=95, anchor="center")
        self.tree.column("guild_id", width=150, anchor="w")
        self.tree.column("channel_id", width=150, anchor="w")

        self.tree.tag_configure("VOICE", foreground="#57f287")
        self.tree.tag_configure("ONLINE", foreground="#57f287")
        self.tree.tag_configure("CONNECTING", foreground="#fee75c")
        self.tree.tag_configure("RECONNECTING", foreground="#fee75c")
        self.tree.tag_configure("ERROR", foreground="#ed4245")
        self.tree.tag_configure("OFFLINE", foreground="#747f8d")

        self.tree.pack(fill="both", expand=True, side="left")
        scrl = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        scrl.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrl.set)

        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=14, pady=4)
        ttk.Button(bar, text="Start", style="Green.TButton", command=self._start_selected).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Stop", style="Red.TButton", command=self._stop_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit", command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete", command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Clear Log", command=self._clear_log).pack(side="right", padx=(4, 0))

        log_box = ttk.Frame(self.root)
        log_box.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        ttk.Label(log_box, text="Live Console Output", style="Sub.TLabel").pack(anchor="w", pady=(0, 2))
        self.log_area = scrolledtext.ScrolledText(
            log_box, height=9, bg="#080811", fg="#a6accd",
            font=("Consolas", 9), insertbackground="#5865F2",
            state="disabled", wrap="word", borderwidth=0
        )
        self.log_area.pack(fill="both", expand=True)

    def _refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for acc in self.accounts:
            name = acc["name"]
            status = "OFFLINE"
            info = ""
            if name in self.runners and self.runners[name].running:
                status = "RUNNING"
            m = "Muted" if acc.get("self_mute", True) else "Live"
            d = "Deaf" if acc.get("self_deaf", True) else "Open"
            audio_str = f"{m} / {d}"

            self.tree.insert("", "end", iid=name, values=(
                name, status, info, audio_str,
                acc["guild_id"], acc["channel_id"]
            ), tags=(status,))

    def _get_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Notice", "Pilih akun di tabel terlebih dahulu.")
            return None
        name = sel[0]
        for acc in self.accounts:
            if acc["name"] == name:
                return acc
        return None

    def _add_dialog(self):
        self._account_dialog("Add Account", {})

    def _edit_selected(self):
        acc = self._get_selected()
        if acc:
            self._account_dialog("Edit Account", acc)

    def _account_dialog(self, title, existing):
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.geometry("440x390")
        dlg.configure(bg="#121224")
        dlg.resizable(False, False)
        dlg.grab_set()

        fields = {}
        items = [
            ("name", "Account Name:"),
            ("token", "Discord Token:"),
            ("guild_id", "Server (Guild) ID:"),
            ("channel_id", "Voice Channel ID:"),
        ]

        for i, (k, lbl) in enumerate(items):
            ttk.Label(dlg, text=lbl, background="#121224").pack(anchor="w", padx=16, pady=(10 if i == 0 else 4, 1))
            entry = ttk.Entry(dlg, width=44)
            if k == "token":
                entry.config(show="*")
            entry.pack(fill="x", padx=16, pady=2)
            if existing.get(k):
                entry.insert(0, existing[k])
            fields[k] = entry

        mute_var = tk.BooleanVar(value=existing.get("self_mute", True))
        deaf_var = tk.BooleanVar(value=existing.get("self_deaf", True))

        chk_f = tk.Frame(dlg, bg="#121224")
        chk_f.pack(fill="x", padx=16, pady=10)

        c1 = tk.Checkbutton(chk_f, text="Self Mute", variable=mute_var, bg="#121224", fg="#f0f0f5",
                            selectcolor="#1e1e38", activebackground="#121224", activeforeground="#ffffff")
        c1.pack(side="left", padx=(0, 14))

        c2 = tk.Checkbutton(chk_f, text="Self Deafen", variable=deaf_var, bg="#121224", fg="#f0f0f5",
                            selectcolor="#1e1e38", activebackground="#121224", activeforeground="#ffffff")
        c2.pack(side="left")

        def _save():
            data = {k: v.get().strip() for k, v in fields.items()}
            data["self_mute"] = mute_var.get()
            data["self_deaf"] = deaf_var.get()

            if not all([data["name"], data["token"], data["guild_id"], data["channel_id"]]):
                messagebox.showerror("Error", "Semua kolom input wajib diisi.", parent=dlg)
                return

            for fid in ("guild_id", "channel_id"):
                if not data[fid].isdigit():
                    messagebox.showerror("Error", f"{fid} harus berupa deretan angka ID.", parent=dlg)
                    return

            if data["name"] != existing.get("name"):
                if any(a["name"] == data["name"] for a in self.accounts):
                    messagebox.showerror("Error", f"Nama '{data['name']}' sudah digunakan.", parent=dlg)
                    return

            if existing.get("name"):
                if existing["name"] in self.runners:
                    self.runners[existing["name"]].stop()
                    del self.runners[existing["name"]]
                for i, a in enumerate(self.accounts):
                    if a["name"] == existing["name"]:
                        self.accounts[i] = data
                        break
            else:
                self.accounts.append(data)

            save_accounts(self.accounts)
            self._refresh_list()
            dlg.destroy()

        ttk.Button(dlg, text="Save Account", style="Accent.TButton", command=_save).pack(fill="x", padx=16, pady=14)

    def _delete_selected(self):
        acc = self._get_selected()
        if not acc:
            return
        if not messagebox.askyesno("Confirm Delete", f"Hapus akun '{acc['name']}'?"):
            return
        if acc["name"] in self.runners:
            self.runners[acc["name"]].stop()
            del self.runners[acc["name"]]
        self.accounts = [a for a in self.accounts if a["name"] != acc["name"]]
        save_accounts(self.accounts)
        self._refresh_list()

    def _log_append(self, name, msg):
        def _do():
            self.log_area.config(state="normal")
            self.log_area.insert("end", msg + "\n")
            self.log_area.see("end")
            self.log_area.config(state="disabled")
        self.root.after(0, _do)

    def _clear_log(self):
        self.log_area.config(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.config(state="disabled")

    def _update_status(self, name, status, info):
        def _do():
            if self.tree.exists(name):
                self.tree.set(name, "status", status)
                self.tree.set(name, "info", info)
                self.tree.item(name, tags=(status,))
        self.root.after(0, _do)

    def _start_account(self, acc):
        name = acc["name"]
        if name in self.runners and self.runners[name].running:
            return
        runner = BotRunner(acc, on_log=self._log_append, on_status=self._update_status)
        self.runners[name] = runner
        runner.start()

    def _stop_account(self, acc):
        name = acc["name"]
        if name in self.runners:
            self.runners[name].stop()
            self._update_status(name, "OFFLINE", "")

    def _start_selected(self):
        acc = self._get_selected()
        if acc:
            self._start_account(acc)

    def _stop_selected(self):
        acc = self._get_selected()
        if acc:
            self._stop_account(acc)

    def _start_all(self):
        for acc in self.accounts:
            self._start_account(acc)

    def _stop_all(self):
        for acc in self.accounts:
            self._stop_account(acc)

    def _on_close(self):
        for runner in self.runners.values():
            if runner.running:
                runner.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    DesktopApp().run()
