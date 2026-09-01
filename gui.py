#!/usr/bin/env python3
"""Interface grafica para o osu MP Link Miner."""
import os
import queue
import re
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from mp_miner import ApiError, OsuApi, iso_date, save, scan


class MinerGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("osu! MP Link Miner")
        self.geometry("820x620")
        self.minsize(700, 520)
        self.messages = queue.Queue()
        self.results = []
        self.last_output = None

        self.nickname = tk.StringVar()
        self.client_id = tk.StringVar(value=os.getenv("OSU_CLIENT_ID", ""))
        self.client_secret = tk.StringVar(value=os.getenv("OSU_CLIENT_SECRET", ""))
        self.pages = tk.StringVar(value="5")
        self.since = tk.StringVar()
        self.delay = tk.StringVar(value="0.15")
        self.format = tk.StringVar(value="json")
        self.output = tk.StringVar()
        self.status = tk.StringVar(value="Preencha os dados e clique em Buscar.")
        self._build()
        self.after(100, self._poll)

    def _build(self):
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(9, weight=1)

        ttk.Label(root, text="osu! MP Link Miner",
                  font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))

        fields = [
            ("Nickname", self.nickname, False),
            ("OAuth Client ID", self.client_id, False),
            ("OAuth Client Secret", self.client_secret, True),
        ]
        for row, (label, variable, secret) in enumerate(fields, 1):
            ttk.Label(root, text=label).grid(row=row, column=0, sticky="w", pady=4)
            entry = ttk.Entry(root, textvariable=variable, show="*" if secret else "")
            entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)

        options = ttk.Frame(root)
        options.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        ttk.Label(options, text="Paginas (50 partidas cada)").grid(row=0, column=0)
        ttk.Spinbox(options, from_=1, to=100000, textvariable=self.pages,
                    width=8).grid(row=0, column=1, padx=(6, 18))
        ttk.Label(options, text="Desde (AAAA-MM-DD)").grid(row=0, column=2)
        ttk.Entry(options, textvariable=self.since, width=14).grid(
            row=0, column=3, padx=(6, 18))
        ttk.Label(options, text="Pausa (s)").grid(row=0, column=4)
        ttk.Entry(options, textvariable=self.delay, width=7).grid(
            row=0, column=5, padx=(6, 0))

        ttk.Label(root, text="Formato").grid(row=5, column=0, sticky="w", pady=4)
        format_box = ttk.Combobox(root, textvariable=self.format,
                                  values=("json", "csv", "txt"),
                                  state="readonly", width=8)
        format_box.grid(row=5, column=1, sticky="w", pady=4)

        ttk.Label(root, text="Arquivo de saida").grid(
            row=6, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.output).grid(
            row=6, column=1, sticky="ew", pady=4)
        ttk.Button(root, text="Escolher...", command=self._choose_output).grid(
            row=6, column=2, padx=(8, 0), pady=4)

        actions = ttk.Frame(root)
        actions.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(10, 8))
        self.search_button = ttk.Button(actions, text="Buscar partidas",
                                        command=self._start)
        self.search_button.pack(side="left")
        ttk.Button(actions, text="Copiar link", command=self._copy).pack(
            side="left", padx=8)
        self.open_button = ttk.Button(actions, text="Abrir arquivo",
                                      command=self._open_output, state="disabled")
        self.open_button.pack(side="left")

        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        ttk.Label(root, textvariable=self.status).grid(
            row=9, column=0, columnspan=3, sticky="nw")

        list_frame = ttk.Frame(root)
        list_frame.grid(row=10, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        root.rowconfigure(10, weight=1)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.listbox = tk.Listbox(list_frame, font=("Consolas", 10))
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                  command=self.listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.bind("<Double-Button-1>", self._open_link)

    def _choose_output(self):
        fmt = self.format.get()
        path = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("Todos", "*.*")])
        if path:
            self.output.set(path)

    def _start(self):
        nick = self.nickname.get().strip()
        if not nick or not self.client_id.get().strip() or not self.client_secret.get():
            messagebox.showerror("Dados incompletos",
                                 "Informe nickname, Client ID e Client Secret.")
            return
        try:
            pages = int(self.pages.get())
            delay = float(self.delay.get().replace(",", "."))
            if pages < 1 or delay < 0:
                raise ValueError
            since = iso_date(self.since.get().strip()) if self.since.get().strip() else None
        except (ValueError, argparse.ArgumentTypeError):
            messagebox.showerror("Valor invalido",
                                 "Revise paginas, data (AAAA-MM-DD) e pausa.")
            return

        fmt = self.format.get()
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", nick).strip("._") or "jogador"
        output = Path(self.output.get().strip() or f"resultados_{safe}.{fmt}")
        self.search_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        self.listbox.delete(0, "end")
        self.status.set("Buscando partidas publicas... Isso pode demorar.")
        self.progress.start(12)
        args = (nick, self.client_id.get().strip(), self.client_secret.get(),
                pages, since, delay, fmt, output)
        threading.Thread(target=self._worker, args=args, daemon=True).start()

    def _worker(self, nick, client_id, secret, pages, since, delay, fmt, output):
        try:
            api = OsuApi(client_id, secret, delay)
            user = api.user(nick)
            results = scan(api, int(user["id"]), pages, since, progress=False)
            save(results, output, fmt)
            self.messages.put(("done", user.get("username", nick), results, output))
        except (ApiError, OSError, KeyError, ValueError) as exc:
            self.messages.put(("error", str(exc)))

    def _poll(self):
        try:
            while True:
                message = self.messages.get_nowait()
                self.progress.stop()
                self.search_button.configure(state="normal")
                if message[0] == "error":
                    self.status.set("A busca falhou.")
                    messagebox.showerror("Erro", message[1])
                else:
                    _, user, self.results, self.last_output = message
                    for item in self.results:
                        self.listbox.insert("end", f"{item.name}  |  {item.link}")
                    self.status.set(
                        f"{user}: {len(self.results)} partida(s). Salvo em {self.last_output}")
                    self.open_button.configure(state="normal")
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _selected_link(self):
        selection = self.listbox.curselection()
        return self.results[selection[0]].link if selection else None

    def _copy(self):
        link = self._selected_link()
        if link:
            self.clipboard_clear()
            self.clipboard_append(link)
            self.status.set("Link copiado.")

    def _open_link(self, _event=None):
        link = self._selected_link()
        if link:
            webbrowser.open(link)

    def _open_output(self):
        if self.last_output:
            os.startfile(self.last_output.resolve())


if __name__ == "__main__":
    MinerGui().mainloop()
