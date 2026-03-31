from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import re


WHITESPACE_RE = re.compile(r"\s+")


class HTMLToTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


@dataclass(slots=True)
class ParsedMessage:
    uid: str
    subject: str
    sender: list[str]
    to: list[str]
    cc: list[str]
    reply_to: list[str]
    date: str | None
    internal_date: str | None
    size: int | None
    flags: list[str]
    message_id: str | None
    attachments: list[dict[str, object]]
    text_body: str
    html_body: str | None

    def to_dict(self, max_body_chars: int | None = None, include_html: bool = False) -> dict[str, object]:
        text_body = self.text_body
        truncated = False
        if max_body_chars is not None and len(text_body) > max_body_chars:
            text_body = text_body[:max_body_chars].rstrip()
            truncated = True

        payload: dict[str, object] = {
            "uid": self.uid,
            "subject": self.subject,
            "from": self.sender,
            "to": self.to,
            "cc": self.cc,
            "reply_to": self.reply_to,
            "date": self.date,
            "internal_date": self.internal_date,
            "size": self.size,
            "flags": self.flags,
            "message_id": self.message_id,
            "attachments": self.attachments,
            "text_body": text_body,
            "text_body_truncated": truncated,
        }
        if include_html:
            payload["html_body"] = self.html_body
        return payload


def parse_message_bytes(
    raw_message: bytes,
    *,
    uid: str,
    flags: list[str] | None = None,
    internal_date: str | None = None,
    size: int | None = None,
) -> ParsedMessage:
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    text_body, html_body = extract_bodies(message)

    return ParsedMessage(
        uid=uid,
        subject=decode_mime_header(message.get("subject")),
        sender=parse_address_list(message.get_all("from", [])),
        to=parse_address_list(message.get_all("to", [])),
        cc=parse_address_list(message.get_all("cc", [])),
        reply_to=parse_address_list(message.get_all("reply-to", [])),
        date=normalize_date_header(message.get("date")),
        internal_date=internal_date,
        size=size,
        flags=flags or [],
        message_id=message.get("message-id"),
        attachments=extract_attachments(message),
        text_body=text_body,
        html_body=html_body,
    )


def build_message_summary(
    raw_message: bytes,
    *,
    uid: str,
    flags: list[str] | None = None,
    internal_date: str | None = None,
    size: int | None = None,
) -> dict[str, object]:
    parsed = parse_message_bytes(
        raw_message,
        uid=uid,
        flags=flags,
        internal_date=internal_date,
        size=size,
    )
    snippet = parsed.text_body[:240].strip()
    return {
        "uid": parsed.uid,
        "subject": parsed.subject,
        "from": parsed.sender,
        "to": parsed.to,
        "date": parsed.date,
        "internal_date": parsed.internal_date,
        "size": parsed.size,
        "flags": parsed.flags,
        "message_id": parsed.message_id,
        "attachments": parsed.attachments,
        "snippet": snippet,
    }


def decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except ValueError:
        return value.strip()


def parse_address_list(values: list[str]) -> list[str]:
    results: list[str] = []
    for name, address in getaddresses(values):
        if name and address:
            results.append(f"{decode_mime_header(name)} <{address}>")
        elif address:
            results.append(address)
        elif name:
            results.append(decode_mime_header(name))
    return results


def normalize_date_header(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return value

    if isinstance(parsed, datetime):
        return parsed.isoformat()
    return value


def extract_bodies(message: Message) -> tuple[str, str | None]:
    text_parts: list[str] = []
    html_parts: list[str] = []

    for part in iter_leaf_parts(message):
        if is_attachment(part):
            continue

        content_type = part.get_content_type()
        payload = get_decoded_payload(part)
        if not payload.strip():
            continue

        if content_type == "text/plain":
            text_parts.append(payload)
        elif content_type == "text/html":
            html_parts.append(payload)

    joined_text = "\n\n".join(part.strip() for part in text_parts if part.strip()).strip()
    joined_html = "\n\n".join(part.strip() for part in html_parts if part.strip()).strip() or None

    if not joined_text and joined_html:
        joined_text = html_to_text(joined_html)

    return normalize_text(joined_text), joined_html


def extract_attachments(message: Message) -> list[dict[str, object]]:
    attachments: list[dict[str, object]] = []
    for part in iter_leaf_parts(message):
        if not is_attachment(part):
            continue

        filename = decode_mime_header(part.get_filename())
        payload = part.get_payload(decode=True) or b""
        attachments.append(
            {
                "filename": filename or None,
                "content_type": part.get_content_type(),
                "size": len(payload),
            }
        )
    return attachments


def iter_leaf_parts(message: Message):
    if message.is_multipart():
        for part in message.iter_parts():
            yield from iter_leaf_parts(part)
    else:
        yield message


def is_attachment(part: Message) -> bool:
    disposition = (part.get_content_disposition() or "").lower()
    filename = part.get_filename()
    return disposition == "attachment" or filename is not None


def get_decoded_payload(part: Message) -> str:
    if isinstance(part, EmailMessage):
        try:
            content = part.get_content()
            if isinstance(content, str):
                return content
        except LookupError:
            pass

    payload = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def html_to_text(html: str) -> str:
    parser = HTMLToTextParser()
    parser.feed(html)
    parser.close()
    return normalize_text(unescape(parser.get_text()))


def normalize_text(text: str) -> str:
    lines = [WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned.strip()
