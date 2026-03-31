from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
import tempfile
import unittest

from email_mcp.config import find_dotenv
from email_mcp.parsing import build_message_summary, parse_message_bytes


class ParsingTests(unittest.TestCase):
    def test_prefers_plain_text_and_lists_attachments(self) -> None:
        message = EmailMessage()
        message["Subject"] = "Quarterly update"
        message["From"] = "Sender Example <sender@example.com>"
        message["To"] = "reader@example.com"
        message["Date"] = "Mon, 30 Mar 2026 10:00:00 -0400"
        message.set_content("Hello team,\n\nThe report is attached.\n")

        message.add_attachment(
            b"fake-bytes",
            maintype="application",
            subtype="pdf",
            filename="report.pdf",
        )

        parsed = parse_message_bytes(
            message.as_bytes(),
            uid="42",
            flags=["\\Seen"],
            internal_date="30-Mar-2026 10:00:00 -0400",
            size=1234,
        )

        self.assertEqual(parsed.subject, "Quarterly update")
        self.assertEqual(parsed.sender, ["Sender Example <sender@example.com>"])
        self.assertEqual(parsed.attachments[0]["filename"], "report.pdf")
        self.assertIn("The report is attached.", parsed.text_body)

    def test_builds_html_fallback_snippet(self) -> None:
        message = EmailMessage()
        message["Subject"] = "HTML only"
        message["From"] = "alerts@example.com"
        message["To"] = "reader@example.com"
        message.set_content("<p>Hello <strong>world</strong></p>", subtype="html")

        summary = build_message_summary(message.as_bytes(), uid="99", flags=[], internal_date=None, size=None)

        self.assertEqual(summary["subject"], "HTML only")
        self.assertIn("Hello world", summary["snippet"])

    def test_find_dotenv_prefers_existing_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text("EMAIL_IMAP_HOST=imap.mail.me.com\n", encoding="utf-8")
            self.assertEqual(find_dotenv(dotenv_path), dotenv_path)


if __name__ == "__main__":
    unittest.main()
