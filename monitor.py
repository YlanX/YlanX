import argparse
import imaplib
import os
import re
from dataclasses import dataclass
from email import message_from_bytes
from email.message import Message
from enum import Enum
from typing import Iterable, List, Sequence


class Priority(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    OK = "ok"


@dataclass(frozen=True)
class Finding:
    source: str
    message: str
    priority: Priority


CRITICAL_PATTERNS = [
    re.compile(r"corromp", re.IGNORECASE),
    re.compile(r"not\s*found", re.IGNORECASE),
    re.compile(r"ciclic", re.IGNORECASE),
    re.compile(r"lack\s+of\s+space", re.IGNORECASE),
    re.compile(r"insufficient\s+space", re.IGNORECASE),
    re.compile(r"corrupt", re.IGNORECASE),
]

WARNING_PATTERNS = [
    re.compile(r"incremental.*fail", re.IGNORECASE),
    re.compile(r"backup\s+incomplete", re.IGNORECASE),
    re.compile(r"verification\s+failed", re.IGNORECASE),
]

OK_PATTERNS = [
    re.compile(r"backup\s+verified", re.IGNORECASE),
    re.compile(r"verification\s+successful", re.IGNORECASE),
    re.compile(r"backup\s+completed", re.IGNORECASE),
    re.compile(r"backup\s+succeeded", re.IGNORECASE),
    re.compile(r"backup\s+ok", re.IGNORECASE),
]


def _match_any(patterns: Iterable[re.Pattern[str]], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _analyze_lines(source: str, log_text: str, extra_warning: str | None) -> List[Finding]:
    findings: List[Finding] = []
    for line in log_text.splitlines():
        if _match_any(CRITICAL_PATTERNS, line):
            findings.append(Finding(source, line.strip(), Priority.CRITICAL))
            continue
        if extra_warning and re.search(extra_warning, line, re.IGNORECASE):
            findings.append(Finding(source, line.strip(), Priority.WARNING))
            continue
        if _match_any(WARNING_PATTERNS, line):
            findings.append(Finding(source, line.strip(), Priority.WARNING))
            continue
        if _match_any(OK_PATTERNS, line):
            findings.append(Finding(source, line.strip(), Priority.OK))
    return findings


def analyze_hqbird(log_text: str) -> List[Finding]:
    return _analyze_lines("hqbird", log_text, extra_warning=None)


def analyze_acronis(log_text: str) -> List[Finding]:
    return _analyze_lines("acronis", log_text, extra_warning=r"backup\s+failed")


def summarize(findings: Iterable[Finding]) -> str:
    by_priority = {Priority.CRITICAL: [], Priority.WARNING: [], Priority.OK: []}
    for finding in findings:
        by_priority[finding.priority].append(finding)
    lines = []
    for priority in (Priority.CRITICAL, Priority.WARNING, Priority.OK):
        lines.append(f"{priority.value.upper()}: {len(by_priority[priority])}")
        for finding in by_priority[priority]:
            lines.append(f"- [{finding.source}] {finding.message}")
    return "\n".join(lines)


def filter_lines_by_keywords(text: str, keywords: Sequence[str]) -> str:
    if not keywords:
        return text
    lowered = [keyword.lower() for keyword in keywords]
    filtered_lines = []
    for line in text.splitlines():
        if any(keyword in line.lower() for keyword in lowered):
            filtered_lines.append(line)
    return "\n".join(filtered_lines)


def extract_text_from_email(message: Message) -> str:
    if message.is_multipart():
        parts = []
        for part in message.walk():
            if part.get_content_type() != "text/plain":
                continue
            if part.get("Content-Disposition", "").startswith("attachment"):
                continue
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            parts.append(payload.decode(charset, errors="replace"))
        return "\n".join(parts)
    payload = message.get_payload(decode=True) or b""
    charset = message.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def fetch_imap_messages(
    host: str,
    user: str,
    password: str,
    mailbox: str,
    limit: int,
) -> List[str]:
    connection = imaplib.IMAP4_SSL(host)
    try:
        connection.login(user, password)
        connection.select(mailbox)
        _, data = connection.search(None, "ALL")
        message_ids = data[0].split()
        selected_ids = message_ids[-limit:] if limit > 0 else message_ids
        bodies = []
        for message_id in selected_ids:
            _, message_data = connection.fetch(message_id, "(RFC822)")
            for response in message_data:
                if isinstance(response, tuple):
                    message = message_from_bytes(response[1])
                    bodies.append(extract_text_from_email(message))
        return bodies
    finally:
        connection.logout()


def _parse_keywords(raw_keywords: str) -> List[str]:
    return [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]


def _ensure_imap_credentials(host: str, user: str, password: str) -> None:
    if host and user and password:
        return
    raise SystemExit(
        "IMAP credentials missing. Set IMAP_HOST, IMAP_USER, IMAP_PASS or pass via flags."
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze HQbird and Acronis backup logs and prioritize issues."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    file_parser = subparsers.add_parser("file", help="Analyze logs from a file")
    file_parser.add_argument("--source", choices=["hqbird", "acronis"], required=True)
    file_parser.add_argument("--input", required=True, help="Path to log text file")
    file_parser.add_argument(
        "--keywords",
        default="",
        help="Comma-separated keywords to filter relevant lines",
    )

    imap_parser = subparsers.add_parser("imap", help="Analyze logs from IMAP mailbox")
    imap_parser.add_argument("--source", choices=["hqbird", "acronis"], required=True)
    imap_parser.add_argument("--mailbox", default="INBOX")
    imap_parser.add_argument("--limit", type=int, default=50)
    imap_parser.add_argument(
        "--keywords",
        default="",
        help="Comma-separated keywords to filter relevant lines",
    )
    imap_parser.add_argument("--host", default=os.getenv("IMAP_HOST", ""))
    imap_parser.add_argument("--user", default=os.getenv("IMAP_USER", ""))
    imap_parser.add_argument("--password", default=os.getenv("IMAP_PASS", ""))
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    keywords = _parse_keywords(args.keywords)

    if args.command == "file":
        with open(args.input, "r", encoding="utf-8") as handle:
            data = handle.read()
        filtered = filter_lines_by_keywords(data, keywords)
        findings = (
            analyze_hqbird(filtered)
            if args.source == "hqbird"
            else analyze_acronis(filtered)
        )
        print(summarize(findings))
        return

    _ensure_imap_credentials(args.host, args.user, args.password)

    messages = fetch_imap_messages(
        host=args.host,
        user=args.user,
        password=args.password,
        mailbox=args.mailbox,
        limit=args.limit,
    )
    combined = filter_lines_by_keywords("\n".join(messages), keywords)
    findings = (
        analyze_hqbird(combined)
        if args.source == "hqbird"
        else analyze_acronis(combined)
    )
    print(summarize(findings))


if __name__ == "__main__":
    main()
