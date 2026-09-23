# 🎙️ Upcoming Feature Plan: Voice Capabilities (TTS & STT)
**Scheduled for Tomorrow's Session**

---

## 🎯 Objectives & Scope

### 1. Speech-to-Text (STT) - Voice Dictation & Search
- **CRM Voice Notes**: Mic button in the Add Lead modal and Lead Details drawer allowing the salesperson to dictate "Internal Sales Notes" and "Personalization Hook" directly without typing.
- **Voice Search / Filter**: Speak commands like *"Show HOT leads"* or *"Find BrightCart Retail"* to quickly filter the dashboard leads table.
- **Implementation**: Web Speech API (`webkitSpeechRecognition` / `SpeechRecognition`) in the browser (zero external API keys or cost) with optional OpenAI Whisper fallback.

### 2. Text-to-Speech (TTS) - Script Audio Previews & Alerts
- **Outreach & Cold Call Script Player**: A "🔊 Listen / Preview Voice" button in the Email / Outreach modal to listen to how AI-generated pitch and cold call scripts sound.
- **Audio Daily Operating Report**: A quick speaker button in the Daily Report modal to listen to the end-of-day summary.
- **High-Priority Voice Alerts**: Audio chime or voice notification when a new hot lead or escalation arrives in the dashboard.
- **Implementation**: Browser native `window.speechSynthesis` (instant, free, responsive) with high-quality natural voices.

### 3. (Optional / Advanced) Telephony STT/TTS
- Twilio Outbound AI call speech generation + Whisper transcription of prospect voice replies.

---
*Saved on 2026-09-21 as a reminder for tomorrow.*
