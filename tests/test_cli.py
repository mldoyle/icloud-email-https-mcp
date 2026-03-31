from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from email_mcp.cli import generate_token, normalize_base_url, write_env_file


class CliTests(unittest.TestCase):
    def test_generate_token_length(self) -> None:
        token = generate_token()
        self.assertEqual(len(token), 64)

    def test_normalize_base_url_requires_https(self) -> None:
        self.assertEqual(
            normalize_base_url("https://example.up.railway.app/"),
            "https://example.up.railway.app",
        )
        with self.assertRaises(ValueError):
            normalize_base_url("http://127.0.0.1:8000")

    def test_write_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            write_env_file(
                path=env_path,
                email="user@icloud.com",
                app_password="app-password",
                auth_token="token",
                force=False,
            )
            content = env_path.read_text(encoding="utf-8")
            self.assertIn("EMAIL_IMAP_USERNAME=user@icloud.com", content)
            self.assertIn("EMAIL_MCP_AUTH_TOKEN=token", content)


if __name__ == "__main__":
    unittest.main()
