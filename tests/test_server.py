from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from email_mcp.config import AppConfig, MailboxConfig
from email_mcp.server import BearerTokenAuthMiddleware, create_http_app


async def ok_endpoint(_request):
    return JSONResponse({"ok": True})


class ServerMiddlewareTests(unittest.TestCase):
    def test_rejects_missing_token(self) -> None:
        app = Starlette(
            routes=[Route("/mcp", ok_endpoint)],
            middleware=[Middleware(BearerTokenAuthMiddleware, token="secret")],
        )

        with TestClient(app) as client:
            response = client.get("/mcp")

        self.assertEqual(response.status_code, 401)

    def test_allows_health_without_token(self) -> None:
        app = Starlette(
            routes=[
                Route("/mcp", ok_endpoint),
                Route("/health", ok_endpoint),
            ],
            middleware=[
                Middleware(
                    BearerTokenAuthMiddleware,
                    token="secret",
                    exempt_paths={"/health"},
                )
            ],
        )

        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)

    def test_allows_valid_token(self) -> None:
        app = Starlette(
            routes=[Route("/mcp", ok_endpoint)],
            middleware=[Middleware(BearerTokenAuthMiddleware, token="secret")],
        )

        with TestClient(app) as client:
            response = client.get("/mcp", headers={"Authorization": "Bearer secret"})

        self.assertEqual(response.status_code, 200)

    def test_allows_root_setup_page_without_token(self) -> None:
        app = Starlette(
            routes=[Route("/", ok_endpoint)],
            middleware=[
                Middleware(
                    BearerTokenAuthMiddleware,
                    token="secret",
                    exempt_paths={"/"},
                )
            ],
        )

        with TestClient(app) as client:
            response = client.get("/")

        self.assertEqual(response.status_code, 200)

    def test_setup_page_json_shows_public_configuration_without_token_value(self) -> None:
        with patch("email_mcp.server.load_dotenv", return_value=None):
            with patch.dict(
                os.environ,
                {
                    "EMAIL_USERNAME": "user@icloud.com",
                    "APP_SPECIFIC_PASSWORD": "app-password",
                    "EMAIL_MCP_AUTH_TOKEN": "super-secret-token",
                    "RAILWAY_PUBLIC_DOMAIN": "icloud-email-https-mcp-production.up.railway.app",
                },
                clear=False,
            ):
                with TestClient(create_http_app()) as client:
                    response = client.get("/setup.json")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["mcp_url"],
            "https://icloud-email-https-mcp-production.up.railway.app/mcp",
        )
        self.assertEqual(body["header_name"], "Authorization")
        self.assertTrue(body["auth_token_configured"])
        self.assertEqual(
            body["header_value_hint"],
            "Bearer <copy EMAIL_MCP_AUTH_TOKEN from Railway Variables>",
        )
        self.assertNotIn("super-secret-token", response.text)

    def test_setup_page_html_lists_missing_variables(self) -> None:
        payload = {
            "service_name": "icloud-email-https-mcp",
            "base_url": "https://example.up.railway.app",
            "mcp_url": "https://example.up.railway.app/mcp",
            "header_name": "Authorization",
            "header_value_hint": "Bearer <copy EMAIL_MCP_AUTH_TOKEN from Railway Variables>",
            "apple_app_password_url": "https://support.apple.com/en-ca/102654",
            "ready": False,
            "missing_variables": ["EMAIL_USERNAME", "EMAIL_MCP_AUTH_TOKEN"],
            "imap_host": "imap.mail.me.com",
            "imap_port": "993",
            "imap_use_ssl": True,
            "default_mailbox": "INBOX",
            "email_configured": False,
            "auth_token_configured": False,
        }
        with patch("email_mcp.server.setup_payload", return_value=payload):
            with TestClient(create_http_app(disable_auth=True)) as client:
                response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Setup Incomplete", response.text)
        self.assertIn("EMAIL_USERNAME", response.text)
        self.assertIn("EMAIL_MCP_AUTH_TOKEN", response.text)

    def test_app_config_does_not_require_mailbox_credentials(self) -> None:
        config = AppConfig.from_env()
        self.assertIsInstance(config.default_mailbox, str)

    def test_mailbox_config_supports_new_and_legacy_variable_names(self) -> None:
        with patch("email_mcp.config.load_dotenv", return_value=None):
            with patch.dict(
                os.environ,
                {
                    "EMAIL_IMAP_HOST": "imap.mail.me.com",
                    "EMAIL_USERNAME": "new@icloud.com",
                    "APP_SPECIFIC_PASSWORD": "new-password",
                },
                clear=True,
            ):
                config = MailboxConfig.from_env()
                self.assertEqual(config.username, "new@icloud.com")
                self.assertEqual(config.password, "new-password")

            with patch.dict(
                os.environ,
                {
                    "EMAIL_IMAP_HOST": "imap.mail.me.com",
                    "EMAIL_IMAP_USERNAME": "legacy@icloud.com",
                    "EMAIL_IMAP_PASSWORD": "legacy-password",
                },
                clear=True,
            ):
                config = MailboxConfig.from_env()
                self.assertEqual(config.username, "legacy@icloud.com")
                self.assertEqual(config.password, "legacy-password")


if __name__ == "__main__":
    unittest.main()
