"""
Thin wrapper around the Gmail API: list messages, fetch full message content,
and send a message. Keeps main.py free of Gmail-specific parsing logic.
"""
import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


def _service(creds: Credentials):
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _extract_body(payload: dict) -> str:
    """Walk the MIME tree and pull out the best plain-text (or HTML fallback) body."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    html_fallback = ""
    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
            html_fallback = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        elif part.get("parts"):
            nested = _extract_body(part)
            if nested:
                return nested

    return html_fallback


def list_messages(creds: Credentials, max_results: int = 20, query: str = "") -> list[dict]:
    """Returns lightweight metadata for the inbox list view."""
    service = _service(creds)
    result = service.users().messages().list(
        userId="me", maxResults=max_results, q=query, labelIds=["INBOX"]
    ).execute()

    messages = result.get("messages", [])
    summaries = []

    for msg in messages:
        full = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = full.get("payload", {}).get("headers", [])
        summaries.append({
            "id": full["id"],
            "threadId": full["threadId"],
            "from": _header(headers, "From"),
            "subject": _header(headers, "Subject") or "(no subject)",
            "date": _header(headers, "Date"),
            "snippet": full.get("snippet", ""),
            "unread": "UNREAD" in full.get("labelIds", []),
        })

    return summaries


def get_message(creds: Credentials, message_id: str) -> dict:
    """Full content for the reading pane."""
    service = _service(creds)
    full = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = full.get("payload", {}).get("headers", [])

    return {
        "id": full["id"],
        "threadId": full["threadId"],
        "from": _header(headers, "From"),
        "to": _header(headers, "To"),
        "subject": _header(headers, "Subject") or "(no subject)",
        "date": _header(headers, "Date"),
        "body": _extract_body(full.get("payload", {})),
    }


def send_message(creds: Credentials, to: str, subject: str, body: str,
                  thread_id: str | None = None) -> dict:
    service = _service(creds)
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    payload = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id

    return service.users().messages().send(userId="me", body=payload).execute()
