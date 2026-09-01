import tempfile
import unittest
from pathlib import Path

from credential_store import load_credentials, save_credentials


class CredentialStoreTests(unittest.TestCase):
    def test_round_trip_uses_encrypted_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            save_credentials("12345", "segredo-super-secreto", path)

            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("segredo-super-secreto", raw)
            self.assertEqual(
                ("12345", "segredo-super-secreto"), load_credentials(path)
            )

    def test_invalid_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            path.write_text("arquivo invalido", encoding="utf-8")
            self.assertEqual(("", ""), load_credentials(path))


if __name__ == "__main__":
    unittest.main()
