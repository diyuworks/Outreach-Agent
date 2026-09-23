"""
Groq Speech-to-Text (STT) Provider using Whisper.
Transcribes audio recordings into clean text.
"""
import os
import io
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_STT_MODEL = "whisper-large-v3"

class STTProvider:
    """Speech-to-Text provider wrapping Groq's Whisper API."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def transcribe(self, audio_data: bytes, filename: str = "audio.webm", language: str = "en") -> dict:
        """
        Transcribe audio bytes to text.
        Returns dict with keys: 'status' ('success' | 'error'), 'text', and optional 'message'.
        """
        if not self.is_configured():
            return {
                "status": "error",
                "message": "Groq API key not configured. Set GROQ_API_KEY in .env.",
                "text": ""
            }

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            files = {
                "file": (filename, io.BytesIO(audio_data), "audio/webm")
            }
            data = {
                "model": DEFAULT_STT_MODEL,
                "response_format": "json",
                "temperature": 0.0
            }
            if language:
                data["language"] = language

            resp = requests.post(GROQ_STT_URL, headers=headers, files=files, data=data, timeout=30)

            if resp.status_code == 200:
                result = resp.json()
                transcribed_text = result.get("text", "").strip()
                return {
                    "status": "success",
                    "text": transcribed_text
                }
            else:
                error_msg = resp.text
                try:
                    err_json = resp.json()
                    error_msg = err_json.get("error", {}).get("message", error_msg)
                except Exception:
                    pass
                return {
                    "status": "error",
                    "message": f"Groq Whisper error ({resp.status_code}): {error_msg}",
                    "text": ""
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"STT transcription failed: {str(e)}",
                "text": ""
            }
