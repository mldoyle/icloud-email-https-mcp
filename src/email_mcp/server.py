from __future__ import annotations

import argparse
from collections.abc import Awaitable, Callable
from html import escape
import os
from typing import Any

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import AppConfig, MailboxConfig, load_dotenv
from .imap_client import IMAPEmailClient


mcp = FastMCP(
    name="email-reader",
    instructions=(
        "Read email over IMAP in a safe, read-only mode. "
        "Use the list_messages tool to find candidate emails, then use get_message to read full content."
    ),
)

APPLE_APP_PASSWORD_URL = "https://support.apple.com/en-ca/102654"
PUBLIC_SETUP_PATHS = {"/", "/setup", "/setup.json", "/health"}


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
        if normalize_path(request.url.path) in self.exempt_paths:
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


def normalize_path(path: str) -> str:
    normalized = path.rstrip("/")
    return normalized or "/"


def configured_setup_values() -> dict[str, object]:
    load_dotenv()

    username = os.getenv("EMAIL_USERNAME", "").strip() or os.getenv("EMAIL_IMAP_USERNAME", "").strip()
    password = os.getenv("APP_SPECIFIC_PASSWORD", "").strip() or os.getenv("EMAIL_IMAP_PASSWORD", "").strip()
    host = os.getenv("EMAIL_IMAP_HOST", "").strip() or "imap.mail.me.com"
    port = os.getenv("EMAIL_IMAP_PORT", "").strip() or "993"
    use_ssl = os.getenv("EMAIL_IMAP_USE_SSL", "").strip() or "true"
    default_mailbox = os.getenv("EMAIL_DEFAULT_MAILBOX", "").strip() or "INBOX"
    auth_token = os.getenv("EMAIL_MCP_AUTH_TOKEN", "").strip()

    missing = [
        key
        for key, value in (
            ("EMAIL_USERNAME", username),
            ("APP_SPECIFIC_PASSWORD", password),
            ("EMAIL_MCP_AUTH_TOKEN", auth_token),
        )
        if not value
    ]

    return {
        "ready": not missing,
        "missing_variables": missing,
        "imap_host": host,
        "imap_port": port,
        "imap_use_ssl": use_ssl.lower() in {"1", "true", "yes", "on"},
        "default_mailbox": default_mailbox,
        "email_configured": bool(username and password),
        "auth_token_configured": bool(auth_token),
    }


def public_base_url(request: Request) -> str:
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if railway_domain:
        return f"https://{railway_domain}"

    forwarded_proto = request.headers.get("x-forwarded-proto", "").strip()
    forwarded_host = request.headers.get("x-forwarded-host", "").strip()
    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}"

    return str(request.base_url).rstrip("/")


def setup_payload(request: Request) -> dict[str, object]:
    base_url = public_base_url(request)
    setup = configured_setup_values()

    return {
        "service_name": "icloud-email-https-mcp",
        "base_url": base_url,
        "mcp_url": f"{base_url}/mcp",
        "header_name": "Authorization",
        "header_value_hint": "Bearer <copy EMAIL_MCP_AUTH_TOKEN from Railway Variables>",
        "apple_app_password_url": APPLE_APP_PASSWORD_URL,
        **setup,
    }


def setup_page_html(payload: dict[str, object]) -> str:
    status_title = "Ready for Notion" if payload["ready"] else "Setup Incomplete"
    status_class = "ready" if payload["ready"] else "warning"
    missing_variables = payload["missing_variables"]
    missing_html = ""
    if missing_variables:
        items = "".join(f"<li><code>{escape(name)}</code></li>" for name in missing_variables)
        missing_html = (
            "<section class='card'>"
            "<h2>Missing variables</h2>"
            "<p>Finish the Railway variable setup before connecting Notion.</p>"
            f"<ul>{items}</ul>"
            "</section>"
        )

    auth_note = (
        "The bearer token is intentionally not shown on this public page. "
        "Copy <code>EMAIL_MCP_AUTH_TOKEN</code> from your Railway service Variables tab."
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>iCloud Email HTTPS MCP Setup</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f5ef;
      --panel: #fffdf7;
      --ink: #1f1b16;
      --muted: #6a6257;
      --line: #d8d1c4;
      --accent: #1f6f5f;
      --warn: #8a4b14;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: linear-gradient(180deg, #f2eee6 0%, var(--bg) 100%);
      color: var(--ink);
    }}
    main {{
      max-width: 860px;
      margin: 0 auto;
      padding: 48px 20px 72px;
    }}
    h1, h2 {{ line-height: 1.1; }}
    p, li {{ font-size: 18px; line-height: 1.6; }}
    .lead {{ color: var(--muted); margin-bottom: 28px; }}
    .status {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-left: 6px solid var(--accent);
      padding: 20px 22px;
      margin-bottom: 22px;
    }}
    .status.warning {{ border-left-color: var(--warn); }}
    .card {{
      border: 1px solid var(--line);
      background: var(--panel);
      padding: 22px;
      margin-top: 18px;
    }}
    .label {{
      display: block;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    code, pre {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      background: #f0ebdf;
      border-radius: 6px;
    }}
    pre {{
      padding: 14px;
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    a {{ color: var(--accent); }}
    ol {{ padding-left: 24px; }}
    ul {{ padding-left: 24px; }}
  </style>
</head>
<body>
  <main>
    <h1>iCloud Email HTTPS MCP</h1>
    <p class="lead">Use this page after deploying the Railway template. It gives you the exact Notion MCP URL and the last setup steps without exposing your token publicly.</p>

    <section class="status {status_class}">
      <h2>{escape(status_title)}</h2>
      <p>Deployment URL: <code>{escape(str(payload["base_url"]))}</code></p>
      <p>Mailbox credentials configured: <strong>{'yes' if payload["email_configured"] else 'no'}</strong></p>
      <p>Bearer token configured: <strong>{'yes' if payload["auth_token_configured"] else 'no'}</strong></p>
    </section>

    {missing_html}

    <section class="card">
      <h2>Generate Apple app-specific password</h2>
      <p>Create an app-specific password for iCloud Mail before connecting the server.</p>
      <p><a href="{escape(APPLE_APP_PASSWORD_URL)}">{escape(APPLE_APP_PASSWORD_URL)}</a></p>
    </section>

    <section class="card">
      <h2>Paste into Notion</h2>
      <span class="label">MCP server URL</span>
      <pre>{escape(str(payload["mcp_url"]))}</pre>
      <span class="label">Header name</span>
      <pre>{escape(str(payload["header_name"]))}</pre>
      <span class="label">Header value</span>
      <pre>{escape(str(payload["header_value_hint"]))}</pre>
      <p>{auth_note}</p>
    </section>

    <section class="card">
      <h2>Railway variables</h2>
      <pre>EMAIL_IMAP_HOST={escape(str(payload["imap_host"]))}
EMAIL_IMAP_PORT={escape(str(payload["imap_port"]))}
EMAIL_IMAP_USE_SSL={'true' if payload["imap_use_ssl"] else 'false'}
EMAIL_DEFAULT_MAILBOX={escape(str(payload["default_mailbox"]))}
EMAIL_USERNAME=&lt;your iCloud email&gt;
APP_SPECIFIC_PASSWORD=&lt;your Apple app-specific password&gt;
EMAIL_MCP_AUTH_TOKEN=&lt;generated secret&gt;</pre>
    </section>

    <section class="card">
      <h2>Finish setup</h2>
      <ol>
        <li>Open your Railway service Variables tab.</li>
        <li>Set <code>EMAIL_USERNAME</code> and <code>APP_SPECIFIC_PASSWORD</code>.</li>
        <li>Copy <code>EMAIL_MCP_AUTH_TOKEN</code> from Railway and paste it into Notion as the bearer token.</li>
        <li>Add a custom MCP connection in Notion using the values above.</li>
      </ol>
    </section>
  </main>
</body>
</html>
"""


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health_check(_: Request) -> Response:
    return JSONResponse({"status": "ok", "server": "email-reader"})


@mcp.custom_route("/", methods=["GET"], include_in_schema=False)
@mcp.custom_route("/setup", methods=["GET"], include_in_schema=False)
async def setup_page(request: Request) -> Response:
    return Response(setup_page_html(setup_payload(request)), media_type="text/html")


@mcp.custom_route("/setup.json", methods=["GET"], include_in_schema=False)
async def setup_page_json(request: Request) -> Response:
    return JSONResponse(setup_payload(request))


def build_http_middleware(*, disable_auth: bool = False) -> list[Middleware] | None:
    config = AppConfig.from_env()
    if not config.auth_token or disable_auth:
        return None

    return [
        Middleware(
            BearerTokenAuthMiddleware,
            token=config.auth_token,
            exempt_paths=PUBLIC_SETUP_PATHS,
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
