from __future__ import annotations

import argparse
from collections.abc import Awaitable, Callable
import os
from typing import Any

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import AppConfig, MailboxConfig
from .imap_client import IMAPEmailClient


mcp = FastMCP(
    name="email-reader",
    instructions=(
        "Read email over IMAP in a safe, read-only mode. "
        "Use the list_messages tool to find candidate emails, then use get_message to read full content."
    ),
)


def with_client() -> IMAPEmailClient:
    return IMAPEmailClient(MailboxConfig.from_env())


class BearerTokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        *,
        token: str,
        exempt_paths: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.token = token
        self.exempt_paths = exempt_paths or set()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path.rstrip("/") in self.exempt_paths:
            return await call_next(request)

        authorization = request.headers.get("authorization", "")
        expected = f"Bearer {self.token}"
        if authorization != expected:
            return JSONResponse(
                {
                    "error": "unauthorized",
                    "message": "Missing or invalid bearer token.",
                },
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health_check(_: Request) -> Response:
    return JSONResponse({"status": "ok", "server": "email-reader"})


def build_http_middleware(*, disable_auth: bool = False) -> list[Middleware] | None:
    config = AppConfig.from_env()
    if not config.auth_token or disable_auth:
        return None

    return [
        Middleware(
            BearerTokenAuthMiddleware,
            token=config.auth_token,
            exempt_paths={"/health"},
        )
    ]


def create_http_app(
    *,
    path: str = "/mcp",
    stateless_http: bool = False,
    disable_auth: bool = False,
):
    return mcp.http_app(
        path=path,
        stateless_http=stateless_http,
        middleware=build_http_middleware(disable_auth=disable_auth),
    )


app = create_http_app()


@mcp.tool
def connection_status() -> dict[str, object]:
    """Verify the IMAP connection and return basic account metadata."""

    mailbox_config = MailboxConfig.from_env()
    app_config = AppConfig.from_env()
    with with_client() as client:
        mailboxes = client.list_mailboxes()

    return {
        "connected": True,
        "host": mailbox_config.host,
        "port": mailbox_config.port,
        "username": mailbox_config.username,
        "use_ssl": mailbox_config.use_ssl,
        "default_mailbox": mailbox_config.default_mailbox,
        "mailbox_count": len(mailboxes),
        "mode": "read-only",
        "http_auth_enabled": bool(app_config.auth_token),
    }


@mcp.tool
def list_mailboxes() -> dict[str, object]:
    """List accessible mailboxes/folders on the configured IMAP account."""

    with with_client() as client:
        mailboxes = client.list_mailboxes()
    return {"mailboxes": mailboxes, "count": len(mailboxes)}


@mcp.tool
def list_messages(
    mailbox: str | None = None,
    unread_only: bool = True,
    limit: int = 10,
    offset: int = 0,
    since_days: int | None = 7,
    sender: str | None = None,
    subject: str | None = None,
) -> dict[str, object]:
    """
    List message summaries from a mailbox.

    Results are newest-first and fetched without modifying seen/unread state.
    """

    config = MailboxConfig.from_env()
    target_mailbox = mailbox or config.default_mailbox
    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)

    with with_client() as client:
        return client.list_messages(
            mailbox=target_mailbox,
            unread_only=unread_only,
            limit=safe_limit,
            offset=safe_offset,
            since_days=since_days,
            sender=sender,
            subject=subject,
        )


@mcp.tool
def get_message(
    uid: str,
    mailbox: str | None = None,
    max_body_chars: int = 20000,
    include_html: bool = False,
) -> dict[str, object]:
    """
    Fetch a full message by IMAP UID.

    The message is fetched in read-only mode and the text body may be truncated for safety.
    """

    config = MailboxConfig.from_env()
    target_mailbox = mailbox or config.default_mailbox
    safe_max_chars = max(500, min(max_body_chars, 200_000))

    with with_client() as client:
        return client.get_message(
            uid=uid,
            mailbox=target_mailbox,
            max_body_chars=safe_max_chars,
            include_html=include_html,
        )


def serve(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the email MCP server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "http", "streamable-http", "sse"),
        default="stdio",
        help="Transport to use. Defaults to stdio.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host.")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="HTTP bind port.",
    )
    parser.add_argument("--path", default="/mcp", help="HTTP endpoint path.")
    parser.add_argument("--log-level", default="info", help="HTTP server log level.")
    parser.add_argument(
        "--stateless-http",
        action="store_true",
        help="Enable stateless HTTP mode for load-balanced deployments.",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Disable bearer-token protection for HTTP transports.",
    )
    args = parser.parse_args(argv)

    if args.transport == "stdio":
        try:
            mcp.run(transport="stdio")
        except KeyboardInterrupt:
            return
        return

    middleware = build_http_middleware(disable_auth=args.no_auth)

    try:
        mcp.run(
            transport=args.transport,
            host=args.host,
            port=args.port,
            path=args.path,
            log_level=args.log_level,
            middleware=middleware,
            stateless_http=args.stateless_http,
        )
    except KeyboardInterrupt:
        return
