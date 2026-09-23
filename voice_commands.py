"""
Voice Command Assistant — Safe-Actions-Only Architecture.

This module processes spoken natural language voice commands and maps them
strictly to safe, read-only or local-view-state actions in the web console.
"""
import os
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv()

from providers.stt_provider import STTProvider

# ==============================================================================
# PERMANENT SAFETY BOUNDARY & EXCLUSION NOTICE:
# Explicitly NOT in ALLOWED_VOICE_ACTIONS, and must NEVER be added:
# - send_email
# - send_sms
# - send_whatsapp
# - activate_lead
# - delete_lead
# - reset_demo
# or anything that sends messages or mutates outbound/critical state.
# This exclusion is intentional, permanent, and architectural — not an oversight.
# The voice assistant is structurally incapable of initiating any outbound action.
# All outbound dispatches require a human operator clicking the Send button.
# ==============================================================================

ALLOWED_VOICE_ACTIONS = {
    "switch_tab": {"params": ["tab_name"]},  # Dashboard / Hetvi Leads / Discovery / etc.
    "search_leads": {"params": ["query"]},
    "open_lead_modal": {"params": ["company_name"]},  # opens Review & Edit modal, does NOT send
    "open_channel_preview": {"params": ["company_name", "channel"]},  # opens draft preview, does NOT send
    "add_note": {"params": ["company_name", "note_text"]},  # safe — local CRM data entry, not outbound
    "filter_by_status": {"params": ["status"]},
}

# Forbidden action strings to explicitly intercept if an LLM hallucinates them
FORBIDDEN_VOICE_ACTIONS = {
    "send_email",
    "send_sms",
    "send_whatsapp",
    "send_message",
    "activate_lead",
    "delete_lead",
    "reset_demo",
    "reset_db",
    "qualify_lead"
}

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_LLM_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]


def parse_voice_intent_with_llm(transcript: str) -> dict:
    """
    Calls Groq LLM to parse transcript into structured JSON intent.
    Strictly instructs model on ALLOWED_VOICE_ACTIONS.
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return {
            "action": "unrecognized",
            "reason": "Groq API key not configured.",
            "raw": {}
        }

    system_prompt = """You are a voice intent classifier for a B2B sales outreach dashboard.
The user speaks a voice command. You MUST map their command to ONLY ONE of the allowed actions and return a JSON object with "action" and "params".

ALLOWED ACTIONS AND PARAMETER SCHEMA:
1. switch_tab:
   JSON: {"action": "switch_tab", "params": {"tab_name": "dashboard" | "hetvi"}}
   Examples: "switch to hetvi leads" -> {"action": "switch_tab", "params": {"tab_name": "hetvi"}}
             "go to dashboard" -> {"action": "switch_tab", "params": {"tab_name": "dashboard"}}
2. search_leads:
   JSON: {"action": "search_leads", "params": {"query": "<search string>"}}
   Examples: "search for BrightCart" -> {"action": "search_leads", "params": {"query": "BrightCart"}}
             "find React companies" -> {"action": "search_leads", "params": {"query": "React"}}
3. open_lead_modal:
   JSON: {"action": "open_lead_modal", "params": {"company_name": "<company name>"}}
   Examples: "open BrightCart lead" -> {"action": "open_lead_modal", "params": {"company_name": "BrightCart"}}
             "review details for NimbusWorks" -> {"action": "open_lead_modal", "params": {"company_name": "NimbusWorks"}}
4. open_channel_preview:
   JSON: {"action": "open_channel_preview", "params": {"company_name": "<company name>", "channel": "email" | "sms" | "whatsapp"}}
   Examples: "open BrightCart's email" -> {"action": "open_channel_preview", "params": {"company_name": "BrightCart", "channel": "email"}}
             "show WhatsApp preview for Coastal Freight" -> {"action": "open_channel_preview", "params": {"company_name": "Coastal Freight", "channel": "whatsapp"}}
             "send an email to BrightCart" -> {"action": "open_channel_preview", "params": {"company_name": "BrightCart", "channel": "email"}} (NOTE: sending via voice is prohibited; map to safe preview)
5. add_note:
   JSON: {"action": "add_note", "params": {"company_name": "<company name>", "note_text": "<note content>"}}
   Examples: "add note to BrightCart follow up next Monday" -> {"action": "add_note", "params": {"company_name": "BrightCart", "note_text": "follow up next Monday"}}
6. filter_by_status:
   JSON: {"action": "filter_by_status", "params": {"status": "all" | "awaiting_reply" | "follow_up_due" | "replied" | "opted_out"}}
   Examples: "show follow ups due" -> {"action": "filter_by_status", "params": {"status": "follow_up_due"}}
             "show all leads" -> {"action": "filter_by_status", "params": {"status": "all"}}

SAFETY AND BOUNDARY RULES:
- If the command is unclear, unrelated, or gibberish, return:
  {"action": "unrecognized", "reason": "<brief explanation>"}
- NEVER output actions outside this list (e.g. NEVER output 'send_email', 'send_sms', 'delete_lead', 'reset_demo').
- Return ONLY valid JSON with no markdown formatting.
"""


    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    for model_name in DEFAULT_LLM_MODELS:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript}
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"}
        }

        try:
            resp = requests.post(GROQ_CHAT_URL, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                # Clean up if enclosed in markdown blocks
                cleaned = re.sub(r'^```json\s*', '', content.strip(), flags=re.MULTILINE)
                cleaned = re.sub(r'^```\s*', '', cleaned, flags=re.MULTILINE)
                cleaned = cleaned.rstrip('`').strip()
                parsed = json.loads(cleaned)
                return parsed
        except Exception:
            continue

    return {
        "action": "unrecognized",
        "reason": "Could not parse intent with Groq LLM."
    }



def execute_and_validate_voice_intent(raw_intent: dict, transcript: str = "") -> dict:
    """
    CRITICAL SERVER-SIDE ENFORCEMENT LAYER:
    Validates that raw_intent['action'] is literally an authorized key in ALLOWED_VOICE_ACTIONS.
    Rejects any unpermitted or forbidden action regardless of what the LLM generated.
    """
    action = raw_intent.get("action", "").strip()
    params = raw_intent.get("params", {})
    if not isinstance(params, dict):
        params = {}

    # Hard rejection for unpermitted or forbidden actions
    if action in FORBIDDEN_VOICE_ACTIONS or (action and action not in ALLOWED_VOICE_ACTIONS and action != "unrecognized"):
        return {
            "status": "rejected",
            "action": action,
            "permitted": False,
            "transcript": transcript,
            "message": "Action not permitted via voice"
        }

    if action == "unrecognized" or not action:
        reason = raw_intent.get("reason") or "Command not recognized as an allowed dashboard action."
        return {
            "status": "unrecognized",
            "action": "unrecognized",
            "permitted": False,
            "transcript": transcript,
            "message": f"Unrecognized voice command: {reason}"
        }

    # Action is in ALLOWED_VOICE_ACTIONS — generate user-facing confirmation message
    msg = f"Executing voice command: {action.replace('_', ' ').title()}"
    if action == "switch_tab":
        tab_name = params.get("tab_name", "dashboard").lower()
        msg = f"Switching to {tab_name.title()} view..."
    elif action == "search_leads":
        q = params.get("query", "")
        msg = f"Searching leads for '{q}'..."
    elif action == "open_lead_modal":
        company = params.get("company_name", "lead")
        msg = f"Opening review modal for {company}..."
    elif action == "open_channel_preview":
        company = params.get("company_name", "lead")
        channel = params.get("channel", "email").upper()
        msg = f"Opening {company}'s {channel} draft preview..."
    elif action == "add_note":
        company = params.get("company_name", "lead")
        note = params.get("note_text", "")
        msg = f"Adding note to {company}: \"{note}\"..."
    elif action == "filter_by_status":
        status = params.get("status", "all")
        msg = f"Filtering leads by status: {status.replace('_', ' ').title()}..."

    return {
        "status": "success",
        "action": action,
        "permitted": True,
        "params": params,
        "transcript": transcript,
        "message": msg
    }


def process_voice_command(audio_bytes: bytes = None, filename: str = "audio.webm", text_command: str = None) -> dict:
    """
    Main entry point for processing voice commands:
    1. Transcribes audio if bytes provided, or uses raw text command.
    2. Uses LLM to extract intent into structured JSON.
    3. Strictly validates action against ALLOWED_VOICE_ACTIONS server-side.
    """
    transcript = (text_command or "").strip()

    if audio_bytes:
        stt = STTProvider()
        res = stt.transcribe(audio_bytes, filename=filename)
        if res.get("status") != "success":
            return {
                "status": "error",
                "action": "unrecognized",
                "permitted": False,
                "transcript": "",
                "message": res.get("message", "Speech-to-text failed.")
            }
        transcript = res.get("text", "").strip()

    if not transcript:
        return {
            "status": "unrecognized",
            "action": "unrecognized",
            "permitted": False,
            "transcript": "",
            "message": "No speech detected. Please speak clearly."
        }

    raw_intent = parse_voice_intent_with_llm(transcript)
    return execute_and_validate_voice_intent(raw_intent, transcript=transcript)
