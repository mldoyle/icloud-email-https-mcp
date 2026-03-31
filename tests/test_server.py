from __future__ import annotations

import unittest

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from email_mcp.config import AppConfig
from email_mcp.server import BearerTokenAuthMiddleware


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

    def test_app_config_does_not_require_mailbox_credentials(self) -> None:
        config = AppConfig.from_env()
        self.assertIsInstance(config.default_mailbox, str)


if __name__ == "__main__":
    unittest.main()
