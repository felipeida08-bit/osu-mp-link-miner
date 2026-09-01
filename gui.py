#!/usr/bin/env python3
"""Interface grafica para o osu MP Link Miner."""
import argparse
import os
import queue
import re
import sys
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from credential_store import load_credentials, save_credentials
from mp_miner import ApiError, OsuApi, iso_date, save, scan_queue, verify_match

def resource_path(relative):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def parse_match_id(value):
    match = re.search(r"(?:community/matches/)?(\d+)/?(?:\?.*)?$", value.strip())
    if not match:
        raise ValueError("Informe um MP ID ou link community/matches valido.")
    return int(match.group(1))


class MinerGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("osu! MP Link Miner")
        try:
            self._icon_image = tk.PhotoImage(
                file=resource_path("assets/osu-binoculars.png"))
            self.iconphoto(True, self._icon_image)
        except tk.TclError:
            self._icon_image = None
        self.geometry("880x700")
        self.minsize(760, 600)
        self.messages = queue.Queue()
        self.results = []
        self.last_output = None
        self.stop_event = threading.Event()

        saved_client_id, saved_secret = load_credentials()
        self.nickname = tk.StringVar()
        self.client_id = tk.StringVar(
            value=os.getenv("OSU_CLIENT_ID", saved_client_id)
        )
        self.client_secret = tk.StringVar(
            value=os.getenv("OSU_CLIENT_SECRET", saved_secret)
        )
        self.pages = tk.StringVar(value="0")
        self.workers = tk.StringVar(value="5")
        self.since = tk.StringVar()
        self.delay = tk.StringVar(value="1.0")
        self.format = tk.StringVar(value="json")
        self.output = tk.StringVar()
        self.direct_mp = tk.StringVar()
        self.status = tk.StringVar(
            value="Limite 0: busca do maior MP ID para o menor ate voce parar."
        )
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._poll)

    def _build(self):
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(11, weight=1)

        ttk.Label(
            root, text="osu! MP Link Miner", font=("Segoe UI", 18, "bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))

        fields = [
            ("Nickname", self.nickname, False),
            ("OAuth Client ID", self.client_id, False),
            ("OAuth Client Secret", self.client_secret, True),
        ]
        for row, (label, variable, secret) in enumerate(fields, 1):
            ttk.Label(root, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(
                root, textvariable=variable, show="*" if secret else ""
            ).grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)

        options = ttk.Frame(root)
        options.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        ttk.Label(options, text="Limite paginas (0=ate parar)").grid(row=0, column=0)
        ttk.Spinbox(
            options, from_=0, to=100000, textvariable=self.pages, width=8
        ).grid(row=0, column=1, padx=(6, 16))
        ttk.Label(options, text="Paralelas").grid(row=0, column=2)
        ttk.Spinbox(
            options, from_=1, to=10, textvariable=self.workers, width=5
        ).grid(row=0, column=3, padx=(6, 16))
        ttk.Label(options, text="Desde").grid(row=0, column=4)
        ttk.Entry(options, textvariable=self.since, width=12).grid(
            row=0, column=5, padx=(6, 16)
        )
        ttk.Label(options, text="Pausa (min 1s)").grid(row=0, column=6)
        ttk.Entry(options, textvariable=self.delay, width=6).grid(
            row=0, column=7, padx=(6, 0)
        )

        ttk.Label(root, text="Formato").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Combobox(
            root, textvariable=self.format, values=("json", "csv", "txt"),
            state="readonly", width=8,
        ).grid(row=5, column=1, sticky="w", pady=4)

        ttk.Label(root, text="Arquivo de saida").grid(
            row=6, column=0, sticky="w", pady=4
        )
        ttk.Entry(root, textvariable=self.output).grid(
            row=6, column=1, sticky="ew", pady=4
        )
        ttk.Button(root, text="Escolher...", command=self._choose_output).grid(
            row=6, column=2, padx=(8, 0), pady=4
        )

        direct = ttk.LabelFrame(root, text="Verificar um MP diretamente", padding=8)
        direct.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        direct.columnconfigure(0, weight=1)
        ttk.Entry(direct, textvariable=self.direct_mp).grid(
            row=0, column=0, sticky="ew"
        )
        self.verify_button = ttk.Button(
            direct, text="Verificar link/ID", command=self._verify
        )
        self.verify_button.grid(row=0, column=1, padx=(8, 0))

        actions = ttk.Frame(root)
        actions.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(10, 8))
        self.search_button = ttk.Button(
            actions, text="Iniciar fila", command=self._start
        )
        self.search_button.pack(side="left")
        self.stop_button = ttk.Button(
            actions, text="Parar", command=self._stop, state="disabled"
        )
        self.stop_button.pack(side="left", padx=8)
        ttk.Button(actions, text="Copiar link", command=self._copy).pack(side="left")
        self.open_button = ttk.Button(
            actions, text="Abrir arquivo", command=self._open_output, state="disabled"
        )
        self.open_button.pack(side="left", padx=8)

        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        ttk.Label(root, textvariable=self.status).grid(
            row=10, column=0, columnspan=3, sticky="w"
        )

        frame = ttk.Frame(root)
        frame.grid(row=11, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.listbox = tk.Listbox(frame, font=("Consolas", 10))
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.bind("<Double-Button-1>", self._open_link)

    def _credentials(self):
        nick = self.nickname.get().strip()
        client_id = self.client_id.get().strip()
        secret = self.client_secret.get()
        if not nick or not client_id or not secret:
            raise ValueError("Informe nickname, Client ID e Client Secret.")
        return nick, client_id, secret

    def _close(self):
        client_id = self.client_id.get().strip()
        secret = self.client_secret.get()
        try:
            if client_id and secret:
                save_credentials(client_id, secret)
        except OSError as exc:
            messagebox.showwarning(
                "Credenciais",
                f"Nao foi possivel salvar as credenciais com seguranca: {exc}",
            )
        self.stop_event.set()
        self.destroy()

    def _choose_output(self):
        fmt = self.format.get()
        path = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("Todos", "*.*")],
        )
        if path:
            self.output.set(path)

    def _set_busy(self, busy):
        state = "disabled" if busy else "normal"
        self.search_button.configure(state=state)
        self.verify_button.configure(state=state)
        self.stop_button.configure(state="normal" if busy else "disabled")
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()

    def _start(self):
        try:
            nick, client_id, secret = self._credentials()
            pages = int(self.pages.get())
            workers = int(self.workers.get())
            delay = float(self.delay.get().replace(",", "."))
            if pages < 0 or not 1 <= workers <= 10 or delay < 1.0:
                raise ValueError("Use pausa minima de 1.0 segundo.")
            since = iso_date(self.since.get().strip()) if self.since.get().strip() else None
        except (ValueError, argparse.ArgumentTypeError) as exc:
            messagebox.showerror("Valor invalido", str(exc))
            return

        fmt = self.format.get()
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", nick).strip("._") or "jogador"
        output = Path(self.output.get().strip() or f"resultados_{safe}.{fmt}")
        self.results = []
        self.listbox.delete(0, "end")
        self.stop_event = threading.Event()
        self._set_busy(True)
        self.open_button.configure(state="disabled")
        self.status.set("Preparando fila em ordem decrescente de MP ID...")
        args = (
            nick, client_id, secret, pages or None, workers,
            since, delay, fmt, output, self.stop_event,
        )
        threading.Thread(target=self._scan_worker, args=args, daemon=True).start()

    def _scan_worker(self, nick, client_id, secret, pages, workers,
                     since, delay, fmt, output, stop_event):
        try:
            api = OsuApi(client_id, secret, delay)
            user = api.user(nick)
            results = scan_queue(
                api, int(user["id"]), stop_event, workers=workers,
                since=since, max_pages=pages,
                on_progress=lambda info: self.messages.put(("progress", info)),
            )
            save(results, output, fmt)
            self.messages.put(
                ("scan_done", user.get("username", nick), results, output,
                 stop_event.is_set())
            )
        except (ApiError, OSError, KeyError, ValueError) as exc:
            self.messages.put(("error", str(exc)))

    def _verify(self):
        try:
            nick, client_id, secret = self._credentials()
            match_id = parse_match_id(self.direct_mp.get())
            delay = float(self.delay.get().replace(",", "."))
            if delay < 1.0:
                raise ValueError("Use pausa minima de 1.0 segundo.")
        except ValueError as exc:
            messagebox.showerror("Valor invalido", str(exc))
            return
        self.stop_event = threading.Event()
        self._set_busy(True)
        self.status.set(f"Verificando MP {match_id}...")
        threading.Thread(
            target=self._verify_worker,
            args=(nick, client_id, secret, delay, match_id),
            daemon=True,
        ).start()

    def _verify_worker(self, nick, client_id, secret, delay, match_id):
        try:
            api = OsuApi(client_id, secret, delay)
            user = api.user(nick)
            result = verify_match(api, match_id, int(user["id"]))
            self.messages.put(
                ("verify_done", user.get("username", nick), match_id, result)
            )
        except (ApiError, OSError, KeyError, ValueError) as exc:
            self.messages.put(("error", str(exc)))

    def _stop(self):
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.status.set("Parando a fila e salvando os resultados...")

    def _poll(self):
        try:
            while True:
                message = self.messages.get_nowait()
                kind = message[0]
                if kind == "progress":
                    info = message[1]
                    result = info["result"]
                    if result:
                        self.results.append(result)
                        self.listbox.insert(
                            "end", f"{result.match_id} | {result.name} | {result.link}"
                        )
                    self.status.set(
                        f"Pagina {info['page']} | verificadas {info['checked']} | "
                        f"encontradas {info['found']} | MP atual {info['match_id']}"
                    )
                elif kind == "error":
                    self._set_busy(False)
                    self.status.set("A operacao falhou.")
                    messagebox.showerror("Erro", message[1])
                elif kind == "scan_done":
                    _, user, self.results, self.last_output, stopped = message
                    self._set_busy(False)
                    self.open_button.configure(state="normal")
                    reason = "interrompida" if stopped else "concluida"
                    self.status.set(
                        f"Fila {reason}: {user}, {len(self.results)} partida(s). "
                        f"Salvo em {self.last_output}"
                    )
                elif kind == "verify_done":
                    _, user, match_id, result = message
                    self._set_busy(False)
                    if result:
                        if all(item.match_id != result.match_id for item in self.results):
                            self.results.insert(0, result)
                            self.listbox.insert(
                                0, f"{result.match_id} | {result.name} | {result.link}"
                            )
                        self.status.set(f"{user} participou do MP {match_id}.")
                    else:
                        self.status.set(f"{user} nao aparece no MP {match_id}.")
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
