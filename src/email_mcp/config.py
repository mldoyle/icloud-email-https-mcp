from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "on"}


def find_dotenv(path: str | Path = ".env") -> Path | None:
    candidate = Path(path)
    if candidate.is_absolute() and candidate.exists():
        return candidate

    search_roots = [
        Path.cwd(),
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
    ]
    seen: set[Path] = set()

    for root in search_roots:
        resolved_root = root.resolve()
        if resolved_root in seen:
            continue
        seen.add(resolved_root)

        dotenv_path = resolved_root / candidate
        if dotenv_path.exists():
            return dotenv_path

    return None


def load_dotenv(path: str | Path = ".env") -> None:
    dotenv_path = find_dotenv(path)
    if dotenv_path is None:
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


@dataclass(frozen=True, slots=True)
class AppConfig:
    default_mailbox: str
    auth_token: str | None

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv()
        default_mailbox = os.getenv("EMAIL_DEFAULT_MAILBOX", "INBOX").strip() or "INBOX"
        auth_token = env_first("EMAIL_MCP_AUTH_TOKEN")
        auth_token = auth_token or None
        return cls(default_mailbox=default_mailbox, auth_token=auth_token)


@dataclass(frozen=True, slots=True)
class MailboxConfig:
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool
    default_mailbox: str

    @classmethod
    def from_env(cls) -> "MailboxConfig":
        load_dotenv()

        host = env_first("EMAIL_IMAP_HOST")
        username = env_first("EMAIL_USERNAME", "EMAIL_IMAP_USERNAME")
        password = env_first("APP_SPECIFIC_PASSWORD", "EMAIL_IMAP_PASSWORD")

        missing = [
            name
            for name, value in (
                ("EMAIL_IMAP_HOST", host),
                ("EMAIL_USERNAME", username),
                ("APP_SPECIFIC_PASSWORD", password),
            )
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required email configuration: {joined}")

        app_config = AppConfig.from_env()
        port = int(os.getenv("EMAIL_IMAP_PORT", "993"))
        use_ssl = os.getenv("EMAIL_IMAP_USE_SSL", "true").strip().lower() in TRUE_VALUES

        return cls(
            host=host,
            port=port,
            username=username,
            password=password,
            use_ssl=use_ssl,
            default_mailbox=app_config.default_mailbox,
        )
