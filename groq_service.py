"""
Calls Groq for fast LLM-based email drafting.
Uses llama-3.1-8b-instant by default (fastest free-tier Groq model).
"""
import os
import json
from groq import Groq

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        _client = Groq(api_key=api_key)
    return _client


SYSTEM_PROMPT = """You are an email drafting assistant. The user gives you rough context, \
bullet points, or an informal instruction about what they want to say in an email. \
You write a clear, well-structured, professional (but not stiff) email based on it.

Rules:
- Infer a sensible subject line if the user didn't give one.
- Keep the tone matched to what the context implies (formal for business, casual for friends).
- Do not invent facts, names, or commitments the user didn't mention.
- Do not add placeholder brackets like [Your Name] unless the user's context implies a sign-off is needed; \
if so, leave a generic "Best," sign-off without inventing a name.
- Respond ONLY with a JSON object, no markdown fences, no preamble, in this exact shape:
{"subject": "...", "body": "..."}
"""


def draft_email(context: str, recipient_hint: str = "", tone: str = "") -> dict:
    """
    context: what the user wants the email to say (rough notes are fine)
    recipient_hint: optional info about who it's going to (helps tone/formality)
    tone: optional explicit tone override, e.g. "formal", "casual", "apologetic"
    """
    client = _get_client()
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    user_prompt = f"Context for the email:\n{context}"
    if recipient_hint:
        user_prompt += f"\n\nRecipient: {recipient_hint}"
    if tone:
        user_prompt += f"\n\nDesired tone: {tone}"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.6,
        max_tokens=800,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Fall back gracefully so the UI still gets something editable
        parsed = {"subject": "Draft", "body": raw}

    return {
        "subject": parsed.get("subject", ""),
        "body": parsed.get("body", ""),
    }
