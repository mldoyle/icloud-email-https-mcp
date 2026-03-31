from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
import imaplib
from imaplib import IMAP4
import re
from typing import Any

from .config import MailboxConfig
from .parsing import build_message_summary, parse_message_bytes


FETCH_METADATA_RE = re.compile(rb"UID (?P<uid>\d+)")
FLAGS_RE = re.compile(rb"FLAGS \((?P<flags>[^)]*)\)")
SIZE_RE = re.compile(rb"RFC822\.SIZE (?P<size>\d+)")
INTERNALDATE_RE = re.compile(rb'INTERNALDATE "(?P<date>[^"]+)"')


class IMAPEmailClient(AbstractContextManager["IMAPEmailClient"]):
    def __init__(self, config: MailboxConfig) -> None:
        self.config = config
        self._imap: IMAP4 | None = None

    def __enter__(self) -> "IMAPEmailClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        if self._imap is not None:
            return

        if self.config.use_ssl:
            imap: IMAP4 = imaplib.IMAP4_SSL(self.config.host, self.config.port)
        else:
            imap = imaplib.IMAP4(self.config.host, self.config.port)

        status, _ = imap.login(self.config.username, self.config.password)
        if status != "OK":
            raise RuntimeError("IMAP login failed")

        self._imap = imap

    def close(self) -> None:
        if self._imap is None:
            return

        try:
            self._imap.logout()
        finally:
            self._imap = None

    def list_mailboxes(self) -> list[str]:
        status, data = self.imap.list()
        if status != "OK":
            raise RuntimeError("Unable to list mailboxes")
        return [parse_mailbox_line(line) for line in data if line]

    def list_messages(
        self,
        *,
        mailbox: str,
        unread_only: bool = True,
        limit: int = 10,
        offset: int = 0,
        since_days: int | None = 7,
        sender: str | None = None,
        subject: str | None = None,
    ) -> dict[str, Any]:
        self.select_mailbox(mailbox)
        uids = self.search_uids(
            unread_only=unread_only,
            since_days=since_days,
            sender=sender,
            subject=subject,
        )
        total_matches = len(uids)
        selected_uids = uids[offset : offset + limit]
        messages = [self.fetch_message_summary(uid) for uid in selected_uids]
        return {
            "mailbox": mailbox,
            "total_matches": total_matches,
            "returned": len(messages),
            "offset": offset,
            "limit": limit,
            "messages": messages,
        }

    def get_message(
        self,
        *,
        uid: str,
        mailbox: str,
        max_body_chars: int = 20000,
        include_html: bool = False,
    ) -> dict[str, Any]:
        self.select_mailbox(mailbox)
        parsed = self.fetch_full_message(uid)
        payload = parsed.to_dict(max_body_chars=max_body_chars, include_html=include_html)
        payload["mailbox"] = mailbox
        return payload

    def select_mailbox(self, mailbox: str) -> None:
        status, _ = self.imap.select(f'"{mailbox}"', readonly=True)
        if status != "OK":
            raise RuntimeError(f"Unable to open mailbox {mailbox!r}")

    def search_uids(
        self,
        *,
        unread_only: bool,
        since_days: int | None,
        sender: str | None,
        subject: str | None,
    ) -> list[str]:
        criteria: list[str | None] = []
        criteria.append("UNSEEN" if unread_only else "ALL")

        if since_days is not None:
            since_date = (datetime.now(UTC) - timedelta(days=since_days)).strftime("%d-%b-%Y")
            criteria.extend(["SINCE", since_date])

        if sender:
            criteria.extend(["FROM", quote_imap_string(sender)])
        if subject:
            criteria.extend(["SUBJECT", quote_imap_string(subject)])

        status, data = self.imap.uid("search", None, *criteria)
        if status != "OK":
            raise RuntimeError("Unable to search mailbox")

        joined = data[0].decode("utf-8") if data and data[0] else ""
        uids = [value for value in joined.split() if value]
        uids.reverse()
        return uids

    def fetch_message_summary(self, uid: str) -> dict[str, Any]:
        status, data = self.imap.uid(
            "fetch",
            uid,
            "(UID FLAGS INTERNALDATE RFC822.SIZE BODY.PEEK[])",
        )
        if status != "OK":
            raise RuntimeError(f"Unable to fetch message {uid}")

        metadata, raw_message = unpack_fetch_response(data)
        return build_message_summary(
            raw_message,
            uid=metadata["uid"],
            flags=metadata["flags"],
            internal_date=metadata["internal_date"],
            size=metadata["size"],
        )

    def fetch_full_message(self, uid: str):
        status, data = self.imap.uid(
            "fetch",
            uid,
            "(UID FLAGS INTERNALDATE RFC822.SIZE BODY.PEEK[])",
        )
        if status != "OK":
            raise RuntimeError(f"Unable to fetch message {uid}")

        metadata, raw_message = unpack_fetch_response(data)
        return parse_message_bytes(
            raw_message,
            uid=metadata["uid"],
            flags=metadata["flags"],
            internal_date=metadata["internal_date"],
            size=metadata["size"],
        )

    @property
    def imap(self) -> IMAP4:
        if self._imap is None:
            raise RuntimeError("IMAP client is not connected")
        return self._imap


def parse_mailbox_line(line: bytes) -> str:
    decoded = line.decode("utf-8", errors="replace")
    if ' "' in decoded:
        return decoded.rsplit(' "', 1)[-1].rstrip('"')
    return decoded


def unpack_fetch_response(data: list[Any]) -> tuple[dict[str, Any], bytes]:
    metadata_bytes: bytes | None = None
    raw_message: bytes | None = None

    for item in data:
        if not item:
            continue
        if isinstance(item, tuple):
            metadata_bytes = item[0]
            raw_message = item[1]

    if metadata_bytes is None or raw_message is None:
        raise RuntimeError("Malformed IMAP fetch response")

    uid_match = FETCH_METADATA_RE.search(metadata_bytes)
    flags_match = FLAGS_RE.search(metadata_bytes)
    size_match = SIZE_RE.search(metadata_bytes)
    internaldate_match = INTERNALDATE_RE.search(metadata_bytes)

    if uid_match is None:
        raise RuntimeError("Missing UID in IMAP response")

    flags_blob = flags_match.group("flags").decode("utf-8") if flags_match else ""
    flags = [flag for flag in flags_blob.split() if flag]

    return (
        {
            "uid": uid_match.group("uid").decode("utf-8"),
            "flags": flags,
            "size": int(size_match.group("size")) if size_match else None,
            "internal_date": internaldate_match.group("date").decode("utf-8")
            if internaldate_match
            else None,
        },
        raw_message,
    )


def quote_imap_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
