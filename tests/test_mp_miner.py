import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

from gui import parse_match_id
from mp_miner import (
    MatchResult, has_user, match_has_user, save, scan, scan_queue, verify_match,
)


class FakeApi:
    def __init__(self):
        self.calls = []

    def matches(self, cursor=None):
        return {
            "matches": [
                {"id": 20, "name": "sim", "start_time": "2026-08-02T12:00:00Z", "end_time": None},
                {"id": 19, "name": "nao", "start_time": "2026-08-01T12:00:00Z", "end_time": None},
            ],
            "cursor_string": None,
        }

    def match(self, match_id, before=None):
        self.calls.append((match_id, before))
        if match_id == 20 and before is None:
            return {
                "match": {"id": 20, "name": "sim", "start_time": "2026-08-02T12:00:00Z"},
                "users": [], "events": [{"id": 200}], "first_event_id": 100,
            }
        if match_id == 20:
            return {"users": [{"id": 42}], "events": [{"id": 100}], "first_event_id": 100}
        return {"users": [], "events": [{"id": 50}], "first_event_id": 50}


class QueueApi:
    def matches(self, cursor=None):
        return {
            "matches": [
                {"id": 10, "name": "dez", "start_time": "2026-08-01T10:00:00Z"},
                {"id": 30, "name": "trinta", "start_time": "2026-08-01T12:00:00Z"},
                {"id": 20, "name": "vinte", "start_time": "2026-08-01T11:00:00Z"},
            ],
            "cursor_string": None,
        }

    def match(self, match_id, before=None):
        users = [{"id": 42}] if match_id in {30, 10} else []
        return {
            "match": {"id": match_id, "name": str(match_id),
                      "start_time": "2026-08-01T12:00:00Z"},
            "users": users, "events": [{"id": match_id}],
            "first_event_id": match_id,
        }


class Tests(unittest.TestCase):
    def test_score_detecta_usuario(self):
        data = {"events": [{"game": {"scores": [{"user_id": 42}]}}]}
        self.assertTrue(has_user(data, 42))

    def test_pagina_eventos_antigos(self):
        api = FakeApi()
        self.assertTrue(match_has_user(api, 20, 42))
        self.assertEqual(api.calls, [(20, None), (20, 200)])

    def test_data_minima(self):
        result = scan(FakeApi(), 42, 1,
            datetime(2026, 8, 2, tzinfo=timezone.utc), False)
        self.assertEqual([item.match_id for item in result], [20])

    def test_fila_preserva_ordem_decrescente_com_concorrencia(self):
        progress = []
        result = scan_queue(QueueApi(), 42, threading.Event(), workers=3,
            max_pages=1, on_progress=progress.append)
        self.assertEqual([item.match_id for item in result], [30, 10])
        self.assertEqual([item["match_id"] for item in progress], [30, 20, 10])

    def test_cancelamento_para_consumo_da_fila(self):
        stop = threading.Event()
        progress = []
        def callback(info):
            progress.append(info)
            stop.set()
        scan_queue(QueueApi(), 42, stop, workers=2, max_pages=None,
                   on_progress=callback)
        self.assertEqual(len(progress), 1)

    def test_verificacao_direta(self):
        self.assertEqual(verify_match(QueueApi(), 30, 42).match_id, 30)
        self.assertIsNone(verify_match(QueueApi(), 20, 42))

    def test_parse_mp_link(self):
        self.assertEqual(
            parse_match_id("https://osu.ppy.sh/community/matches/121788519"),
            121788519)
        self.assertEqual(parse_match_id("121788519"), 121788519)
        with self.assertRaises(ValueError):
            parse_match_id("sem-id")

    def test_txt(self):
        row = MatchResult(1, "https://osu.ppy.sh/community/matches/1", "x", "x", None)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "links.txt"
            save([row], path, "txt")
            self.assertEqual(path.read_text(), row.link + "\n")


if __name__ == "__main__":
    unittest.main()
