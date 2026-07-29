import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

import auth
import gmail_service
import groq_service

load_dotenv()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/auth/login")
def login():
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
    flow = auth.build_flow(redirect_uri)
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(authorization_url)


@app.get("/auth/callback")
def callback(code: str = Query(...)):
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
    flow = auth.build_flow(redirect_uri)
    flow.fetch_token(code=code)
    auth.save_credentials(flow.credentials)
    return RedirectResponse("/")


@app.get("/auth/status")
def status():
    return {"logged_in": auth.is_logged_in()}


@app.post("/auth/logout")
def logout():
    auth.logout()
    return {"ok": True}


def _require_creds():
    creds = auth.load_credentials()
    if not creds or not creds.valid:
        raise HTTPException(status_code=401, detail="Not connected to Gmail. Visit /auth/login first.")
    return creds


# ---------- Mail ----------

@app.get("/api/emails")
def get_emails(max_results: int = 20, q: str = ""):
    creds = _require_creds()
    try:
        return gmail_service.list_messages(creds, max_results=max_results, query=q)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail API error: {e}")


@app.get("/api/emails/{message_id}")
def get_email(message_id: str):
    creds = _require_creds()
    try:
        return gmail_service.get_message(creds, message_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail API error: {e}")


# ---------- AI drafting ----------

class DraftRequest(BaseModel):
    context: str
    recipient_hint: str = ""
    tone: str = ""


@app.post("/api/compose/draft")
def draft(req: DraftRequest):
    if not req.context.strip():
        raise HTTPException(status_code=400, detail="Give me some context to draft from.")
    try:
        return groq_service.draft_email(req.context, req.recipient_hint, req.tone)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Groq API error: {e}")


# ---------- Sending ----------

class SendRequest(BaseModel):
    to: str
    subject: str
    body: str
    thread_id: str | None = None


@app.post("/api/send")
def send(req: SendRequest):
    creds = _require_creds()
    try:
        result = gmail_service.send_message(creds, req.to, req.subject, req.body, req.thread_id)
        return {"ok": True, "id": result.get("id")}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send: {e}")


# Batch sending: see batch_service.py for the planned design. Not wired up yet.
