from __future__ import annotations

import argparse
import getpass
from pathlib import Path
import secrets
import sys

from .config import AppConfig, load_dotenv
from .server import serve


DEFAULT_ENV_PATH = Path(".env")
MANAGEMENT_COMMANDS = {"token", "init", "notion"}


def generate_token() -> str:
    return secrets.token_hex(32)


def prompt_non_empty(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Value cannot be empty.")


def write_env_file(
    *,
    path: Path,
    email: str,
    app_password: str,
    auth_token: str,
    force: bool,
) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists. Re-run with --force to overwrite it.")

    lines = [
        "EMAIL_IMAP_HOST=imap.mail.me.com",
        "EMAIL_IMAP_PORT=993",
        f"EMAIL_USERNAME={email}",
        f"APP_SPECIFIC_PASSWORD={app_password}",
        "EMAIL_IMAP_USE_SSL=true",
        "EMAIL_DEFAULT_MAILBOX=INBOX",
        f"EMAIL_MCP_AUTH_TOKEN={auth_token}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def normalize_base_url(base_url: str) -> str:
    trimmed = base_url.strip().rstrip("/")
    if not trimmed.startswith("https://"):
        raise ValueError("Base URL must start with https:// for Notion.")
    return trimmed


def run_init_command(args: argparse.Namespace) -> int:
    email = args.email or prompt_non_empty("iCloud email address: ")
    app_password = args.app_password or getpass.getpass("iCloud app-specific password: ").strip()
    if not app_password:
        raise ValueError("App-specific password cannot be empty.")

    auth_token = args.auth_token or generate_token()
    output_path = Path(args.output)
    write_env_file(
        path=output_path,
        email=email,
        app_password=app_password,
        auth_token=auth_token,
        force=args.force,
    )

    print(f"Wrote {output_path}")
    print("")
    print("Generated bearer token:")
    print(auth_token)
    print("")
    print("Next steps:")
    print("1. Deploy the project to Railway.")
    print("2. Set the service variables from this file if Railway did not import them.")
    print("3. Once Railway gives you a public hostname, open it in a browser.")
    print("4. The setup page will show the final Notion MCP URL and remind you to copy EMAIL_MCP_AUTH_TOKEN from Railway Variables.")
    print("5. If you prefer the CLI output, run:")
    print(f"   uv run email-mcp notion --base-url https://your-service.up.railway.app --token {auth_token}")
    return 0


def run_token_command(_args: argparse.Namespace) -> int:
    print(generate_token())
    return 0


def run_notion_command(args: argparse.Namespace) -> int:
    load_dotenv()
    token = args.token or AppConfig.from_env().auth_token
    if not token:
        raise ValueError("No bearer token found. Pass --token or set EMAIL_MCP_AUTH_TOKEN.")

    base_url = normalize_base_url(args.base_url)
    print("Notion MCP URL:")
    print(f"{base_url}/mcp")
    print("")
    print("Header name:")
    print("Authorization")
    print("")
    print("Header value:")
    print(f"Bearer {token}")
    print("")
    print("If the app is already deployed, you can also open the service root URL in a browser to see the same Notion values and the Apple app-password link.")
    return 0


def build_management_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Email MCP setup helpers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    token_parser = subparsers.add_parser("token", help="Generate a bearer token.")
    token_parser.set_defaults(func=run_token_command)

    init_parser = subparsers.add_parser(
        "init",
        help="Create a .env file for a single-user iCloud deployment.",
    )
    init_parser.add_argument("--email", help="Full iCloud email address.")
    init_parser.add_argument(
        "--app-password",
        help="Apple app-specific password. If omitted, prompt securely.",
    )
    init_parser.add_argument(
        "--auth-token",
        help="Bearer token for the MCP server. If omitted, generate one.",
    )
    init_parser.add_argument(
        "--output",
        default=str(DEFAULT_ENV_PATH),
        help="Path to write the environment file.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    init_parser.set_defaults(func=run_init_command)

    notion_parser = subparsers.add_parser(
        "notion",
        help="Print the exact Notion MCP URL and Authorization header.",
    )
    notion_parser.add_argument(
        "--base-url",
        required=True,
        help="Public HTTPS base URL, for example https://your-service.up.railway.app",
    )
    notion_parser.add_argument(
        "--token",
        help="Bearer token to print. Defaults to EMAIL_MCP_AUTH_TOKEN from .env or env vars.",
    )
    notion_parser.set_defaults(func=run_notion_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"-h", "--help"}:
        print("email-mcp")
        print("")
        print("Serve the MCP server:")
        print("  email-mcp --transport http --host 0.0.0.0 --port 8000")
        print("")
        print("Setup helpers:")
        print("  email-mcp init")
        print("  email-mcp token")
        print("  email-mcp notion --base-url https://your-service.up.railway.app")
        return 0

    if argv and argv[0] in MANAGEMENT_COMMANDS:
        parser = build_management_parser()
        args = parser.parse_args(argv)
        return int(args.func(args))

    serve(argv)
    return 0
