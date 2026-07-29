"""
Handles the Google OAuth2 dance for Gmail access.

This is built for a single personal Gmail account (not a multi-tenant app),
so credentials are cached to token.json on disk after the first login and
silently refreshed after that. Delete token.json to force a fresh login.
"""
import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

CLIENT_SECRETS_FILE = "client_secret.json"
TOKEN_FILE = "token.json"


def build_flow(redirect_uri: str) -> Flow:
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError(
            "client_secret.json not found. Download it from Google Cloud Console "
            "(APIs & Services > Credentials > OAuth 2.0 Client IDs) and place it "
            "in the project root. See README.md for the exact steps."
        )
    return Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )


def save_credentials(creds: Credentials) -> None:
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())


def load_credentials() -> Credentials | None:
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, "r") as f:
        data = json.load(f)
    creds = Credentials.from_authorized_user_info(data, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)

    return creds


def is_logged_in() -> bool:
    creds = load_credentials()
    return creds is not None and creds.valid


def logout() -> None:
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
