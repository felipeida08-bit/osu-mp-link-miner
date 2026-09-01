#!/usr/bin/env python3
"""Busca MP links publicos do osu! por nickname usando a API oficial."""
import argparse, csv, json, os, re, sys, time
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
    def __init__(self, client_id, secret, delay=.15):
        self.delay = delay
        data = urlencode({"client_id": client_id, "client_secret": secret,
            "grant_type": "client_credentials", "scope": "public"}).encode()
        request = Request(TOKEN, data=data, method="POST", headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"})
        self.token = self._request(request).get("access_token")
        if not self.token:
            raise ApiError("OAuth nao retornou access_token")

    def _request(self, request, retries=4):
        for attempt in range(retries + 1):
            try:
                with urlopen(request, timeout=30) as response:
                    result = json.loads(response.read().decode())
                time.sleep(self.delay)
                return result
            except HTTPError as exc:
                if (exc.code == 429 or exc.code >= 500) and attempt < retries:
                    wait = float(exc.headers.get("Retry-After", 2 ** attempt))
                    time.sleep(min(wait, 30)); continue
                if exc.code == 401:
                    raise ApiError("credenciais OAuth invalidas") from exc
                if exc.code == 404:
                    raise ApiError("jogador ou partida nao encontrado") from exc
                raise ApiError(f"osu api retornou HTTP {exc.code}") from exc
            except (URLError, TimeoutError) as exc:
                if attempt < retries:
                    time.sleep(2 ** attempt); continue
                raise ApiError(f"falha de rede: {exc}") from exc

    def get(self, path, **params):
        clean = {k: v for k, v in params.items() if v is not None}
        url = f"{API}/{path}" + (f"?{urlencode(clean)}" if clean else "")
        return self._request(Request(url, headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}"}))

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

def match_has_user(api, match_id, user_id):
    before, seen = None, set()
    while True:
        data = api.match(match_id, before)
        if has_user(data, user_id):
            return True
        events = data.get("events", [])
        if not events:
            return False
        oldest = min(int(event["id"]) for event in events)
        first = data.get("first_event_id")
        if first is None or oldest <= int(first) or oldest in seen:
            return False
        seen.add(oldest); before = oldest

def scan(api, user_id, pages, since=None, progress=True):
    found, cursor, checked = [], None, 0
    for page in range(1, pages + 1):
        listing = api.matches(cursor)
        matches = listing.get("matches", [])
        if not matches:
            break
        stop = False
        for item in matches:
            if since and iso_date(item["start_time"]) < since:
                stop = True; break
            checked += 1
            if progress:
                print(f"\rPagina {page}/{pages}: {checked} verificadas, {len(found)} encontradas",
                    end="", file=sys.stderr, flush=True)
            match_id = int(item["id"])
            if match_has_user(api, match_id, user_id):
                found.append(MatchResult(match_id,
                    f"https://osu.ppy.sh/community/matches/{match_id}",
                    item.get("name", ""), item["start_time"], item.get("end_time")))
        if stop:
            break
        cursor = listing.get("cursor_string")
        if not cursor:
            break
    if progress:
        print(file=sys.stderr)
    return found

def save(results, path, fmt):
    rows = [asdict(row) for row in results]
    if fmt == "json":
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif fmt == "csv":
        with path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=MatchResult.__annotations__)
            writer.writeheader(); writer.writerows(rows)
    else:
        path.write_text("\n".join(row["link"] for row in rows) + ("\n" if rows else ""),
            encoding="utf-8")

def make_parser():
    p = argparse.ArgumentParser(description="Encontra MP links publicos do osu por jogador")
    p.add_argument("nickname")
    p.add_argument("--pages", type=int, default=5, help="paginas de 50 partidas")
    p.add_argument("--since", type=iso_date, help="data minima em UTC")
    p.add_argument("--delay", type=float, default=.15)
    p.add_argument("--format", choices=("json", "csv", "txt"), default="json")
    p.add_argument("--output", type=Path)
    p.add_argument("--client-id", default=os.getenv("OSU_CLIENT_ID"))
    p.add_argument("--client-secret", default=os.getenv("OSU_CLIENT_SECRET"))
    return p

def main(argv=None):
    p = make_parser(); args = p.parse_args(argv)
    if args.pages < 1 or args.delay < 0:
        p.error("--pages deve ser positivo e --delay nao pode ser negativo")
    if not args.client_id or not args.client_secret:
        p.error("defina OSU_CLIENT_ID e OSU_CLIENT_SECRET (veja README.md)")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", args.nickname).strip("._") or "jogador"
    output = args.output or Path(f"resultados_{safe}.{args.format}")
    try:
        api = OsuApi(args.client_id, args.client_secret, args.delay)
        user = api.user(args.nickname)
        print(f"Jogador: {user.get('username')} (ID {user['id']})", file=sys.stderr)
        results = scan(api, int(user["id"]), args.pages, args.since)
        save(results, output, args.format)
    except ApiError as exc:
        print(f"Erro: {exc}", file=sys.stderr); return 1
    except KeyboardInterrupt:
        print("\nBusca interrompida.", file=sys.stderr); return 130
    print(f"{len(results)} partida(s) encontrada(s). Salvo em: {output}")
    for item in results:
        print(item.link)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
