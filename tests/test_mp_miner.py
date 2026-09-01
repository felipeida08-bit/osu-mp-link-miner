import tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from mp_miner import MatchResult, has_user, match_has_user, save, scan

class FakeApi:
    def __init__(self):
        self.calls = []
    def matches(self, cursor=None):
        return {"matches": [
            {"id": 20, "name": "sim", "start_time": "2026-08-02T12:00:00Z", "end_time": None},
            {"id": 19, "name": "nao", "start_time": "2026-08-01T12:00:00Z", "end_time": None}
        ], "cursor_string": None}
    def match(self, match_id, before=None):
        self.calls.append((match_id, before))
        if match_id == 20 and before is None:
            return {"users": [], "events": [{"id": 200}], "first_event_id": 100}
        if match_id == 20:
            return {"users": [{"id": 42}], "events": [{"id": 100}], "first_event_id": 100}
        return {"users": [], "events": [{"id": 50}], "first_event_id": 50}

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
    def test_txt(self):
        row = MatchResult(1, "https://osu.ppy.sh/community/matches/1", "x", "x", None)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "links.txt"
            save([row], path, "txt")
            self.assertEqual(path.read_text(), row.link + "\n")

if __name__ == "__main__":
    unittest.main()
