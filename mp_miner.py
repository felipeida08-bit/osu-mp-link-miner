#!/usr/bin/env python3
"""Busca MP links publicos do osu! por nickname usando a API oficial."""
import argparse
import csv
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API = "https://osu.ppy.sh/api/v2"
TOKEN = "https://osu.ppy.sh/oauth/token"


class ApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class MatchResult:
    match_id: int
    link: str
    name: str
    start_time: str
    end_time: str | None


def iso_date(value):
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use YYYY-MM-DD ou ISO 8601") from exc
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc)


class OsuApi:
    """Cliente thread-safe com renovacao de token e intervalo global."""

    def __init__(self, client_id, secret, delay=1.0):
        self.client_id = client_id
        self.secret = secret
        self.delay = max(float(delay), 1.0)
        self.token = None
        self.token_expires_at = 0.0
        self._token_lock = threading.Lock()
        self._rate_lock = threading.Lock()
        self._next_request = 0.0
        self._authenticate()

    def _authenticate(self):
        with self._token_lock:
            data = urlencode({
                "client_id": self.client_id,
                "client_secret": self.secret,
                "grant_type": "client_credentials",
                "scope": "public",
            }).encode()
            request = Request(TOKEN, data=data, method="POST", headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            })
            try:
                with urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode())
            except HTTPError as exc:
                if exc.code == 401:
                    raise ApiError("credenciais OAuth invalidas") from exc
                raise ApiError(f"OAuth retornou HTTP {exc.code}") from exc
            except (URLError, TimeoutError) as exc:
                raise ApiError(f"falha de rede no OAuth: {exc}") from exc
            self.token = payload.get("access_token")
            if not self.token:
                raise ApiError("OAuth nao retornou access_token")
            lifetime = int(payload.get("expires_in", 86400))
            self.token_expires_at = time.monotonic() + max(lifetime - 60, 1)

    def _ensure_token(self):
        if time.monotonic() < self.token_expires_at:
            return
        self._authenticate()

    def _wait_turn(self):
        with self._rate_lock:
            wait = self._next_request - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._next_request = time.monotonic() + self.delay

    def _request(self, request, retries=4):
        for attempt in range(retries + 1):
            self._wait_turn()
            try:
                with urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode())
            except HTTPError as exc:
                if (exc.code == 429 or exc.code >= 500) and attempt < retries:
                    wait = float(exc.headers.get("Retry-After", 2 ** attempt))
                    time.sleep(min(wait, 30))
                    continue
                if exc.code == 401:
                    raise ApiError("token OAuth recusado") from exc
                if exc.code == 404:
                    raise ApiError("jogador ou partida nao encontrado") from exc
                raise ApiError(f"osu api retornou HTTP {exc.code}") from exc
            except (URLError, TimeoutError) as exc:
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                raise ApiError(f"falha de rede: {exc}") from exc
        raise ApiError("numero maximo de tentativas excedido")

    def get(self, path, **params):
        self._ensure_token()
        clean = {key: value for key, value in params.items() if value is not None}
        url = f"{API}/{path}" + (f"?{urlencode(clean)}" if clean else "")
        request = Request(url, headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
        })
        return self._request(request)

    def user(self, nick):
        return self.get(f"users/@{quote(nick, safe='')}")

    def matches(self, cursor=None):
        return self.get("matches", limit=50, sort="id_desc", cursor_string=cursor)

    def match(self, match_id, before=None):
        return self.get(f"matches/{match_id}", limit=100, before=before)


def has_user(data, user_id):
    if any(user.get("id") == user_id for user in data.get("users", [])):
        return True
    for event in data.get("events", []):
        if event.get("user_id") == user_id:
            return True
        scores = (event.get("game") or {}).get("scores", [])
        if any(score.get("user_id") == user_id for score in scores):
            return True
    return False


def match_has_user(api, match_id, user_id, stop_event=None, initial=None):
    before = None
    seen = set()
    data = initial
    while not stop_event or not stop_event.is_set():
        data = data if data is not None else api.match(match_id, before)
        if has_user(data, user_id):
            return True
        events = data.get("events", [])
        if not events:
            return False
        oldest = min(int(event["id"]) for event in events)
        first = data.get("first_event_id")
        if first is None or oldest <= int(first) or oldest in seen:
            return False
        seen.add(oldest)
        before = oldest
        data = None
    return False


def result_from_match(item):
    match_id = int(item["id"])
    return MatchResult(
        match_id,
        f"https://osu.ppy.sh/community/matches/{match_id}",
        item.get("name", ""),
        item.get("start_time", ""),
        item.get("end_time"),
    )


def verify_match(api, match_id, user_id):
    data = api.match(match_id)
    if not match_has_user(api, match_id, user_id, initial=data):
        return None
    item = data.get("match") or {"id": match_id}
    item["id"] = match_id
    return result_from_match(item)


def scan_queue(api, user_id, stop_event, workers=5, since=None,
               max_pages=None, on_progress=None):
    """Consome matches em id_desc e entrega resultados na mesma ordem."""
    found = []
    cursor = None
    checked = 0
    page = 0
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="osu-mp")
    stopped = False
    try:
        while not stop_event.is_set() and (max_pages is None or page < max_pages):
            listing = api.matches(cursor)
            page += 1
            matches = sorted(
                listing.get("matches", []),
                key=lambda item: int(item["id"]),
                reverse=True,
            )
            if not matches:
                break
            page_items = []
            for item in matches:
                if since and iso_date(item["start_time"]) < since:
                    stopped = True
                    break
                page_items.append(item)
            futures = [
                executor.submit(match_has_user, api, int(item["id"]), user_id, stop_event)
                for item in page_items
            ]
            for item, future in zip(page_items, futures):
                if stop_event.is_set():
                    stopped = True
                    break
                present = future.result()
                checked += 1
                result = result_from_match(item) if present else None
                if result:
                    found.append(result)
                if on_progress:
                    on_progress({
                        "page": page,
                        "checked": checked,
                        "found": len(found),
                        "match_id": int(item["id"]),
                        "result": result,
                    })
            if stopped or stop_event.is_set():
                break
            cursor = listing.get("cursor_string")
            if not cursor:
                break
    finally:
        executor.shutdown(wait=not stop_event.is_set(), cancel_futures=True)
    return found


def scan(api, user_id, pages, since=None, progress=True):
    stop_event = threading.Event()

    def report(info):
        if progress:
            print(
                f"\rPagina {info['page']}/{pages}: {info['checked']} verificadas, "
                f"{info['found']} encontradas",
                end="",
                file=sys.stderr,
                flush=True,
            )

    results = scan_queue(
        api, user_id, stop_event, workers=1, since=since,
        max_pages=pages, on_progress=report,
    )
    if progress:
        print(file=sys.stderr)
    return results


def save(results, path, fmt):
    rows = [asdict(row) for row in results]
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    elif fmt == "csv":
        with path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=MatchResult.__annotations__)
            writer.writeheader()
            writer.writerows(rows)
    else:
        path.write_text(
            "\n".join(row["link"] for row in rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )


def make_parser():
    parser = argparse.ArgumentParser(
        description="Encontra MP links publicos do osu por jogador"
    )
    parser.add_argument("nickname")
    parser.add_argument("--pages", type=int, default=5, help="paginas de 50 partidas")
    parser.add_argument("--since", type=iso_date, help="data minima em UTC")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--format", choices=("json", "csv", "txt"), default="json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--client-id", default=os.getenv("OSU_CLIENT_ID"))
    parser.add_argument("--client-secret", default=os.getenv("OSU_CLIENT_SECRET"))
    return parser


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    if args.pages < 1 or args.delay < 1.0:
        parser.error("--pages deve ser positivo e --delay deve ser pelo menos 1.0")
    if not args.client_id or not args.client_secret:
        parser.error("defina OSU_CLIENT_ID e OSU_CLIENT_SECRET (veja README.md)")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", args.nickname).strip("._") or "jogador"
    output = args.output or Path(f"resultados_{safe}.{args.format}")
    try:
        api = OsuApi(args.client_id, args.client_secret, args.delay)
        user = api.user(args.nickname)
        print(f"Jogador: {user.get('username')} (ID {user['id']})", file=sys.stderr)
        results = scan(api, int(user["id"]), args.pages, args.since)
        save(results, output, args.format)
    except ApiError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nBusca interrompida.", file=sys.stderr)
        return 130
    print(f"{len(results)} partida(s) encontrada(s). Salvo em: {output}")
    for item in results:
        print(item.link)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
