"""
SMS provider — supports two backends, switchable via .env, no code changes needed to swap:

  SMS_PROVIDER=twilio     (default) — paid, but free trial credit on signup.
                          Trial accounts can only send to numbers YOU have
                          manually verified in the Twilio console.

  SMS_PROVIDER=fast2sms   — India-specific, cheaper per-SMS than Twilio.
                          Uses the "Quick SMS" route (no DLT template
                          approval needed for testing/small volume).

Without valid credentials for whichever provider is selected, this runs in
safe DRY_RUN mode and just logs what would be sent.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

from phone_utils import normalize_to_e164


class SMSProvider:
    def __init__(self):
        self.provider_name = os.getenv("SMS_PROVIDER", "twilio").strip().lower()

        # Twilio config
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_from = os.getenv("TWILIO_FROM_NUMBER")

        # Fast2SMS config
        self.fast2sms_api_key = os.getenv("FAST2SMS_API_KEY")
        self.fast2sms_sender_id = os.getenv("FAST2SMS_SENDER_ID", "FSTSMS")

        if self.provider_name == "fast2sms":
            self.dry_run = not self.fast2sms_api_key
        else:
            self.dry_run = not (self.twilio_sid and self.twilio_token and self.twilio_from)

    def send(self, to_phone: str, body: str, country: str | None = None) -> bool:
        default_cc = "+91" if (country and str(country).strip().lower() in ("india", "in", "+91", "91")) else "+1"
        normalized_phone = normalize_to_e164(to_phone, default_country_code=default_cc)
        if not normalized_phone:
            print(f"  [INVALID PHONE] Could not normalize '{to_phone}' to E.164, skipping send.")
            return False
        to_phone = normalized_phone

        if self.dry_run:
            print(f"  [DRY RUN - SMS via {self.provider_name}] Would send to {to_phone}")
            print(f"  Message: {body}\n")
            return True

        if self.provider_name == "fast2sms":
            return self._send_via_fast2sms(to_phone, body)
        return self._send_via_twilio(to_phone, body)

    # ---------- Twilio backend ----------
    def _send_via_twilio(self, to_phone: str, body: str) -> bool:
        try:
            from twilio.rest import Client  # imported lazily so it's optional
            client = Client(self.twilio_sid, self.twilio_token)
            try:
                client.messages.create(body=body, from_=self.twilio_from, to=to_phone)
                print(f"  [SENT - SMS via Twilio] to {to_phone}")
                return True
            except Exception as e:
                # If Twilio trial account requires predefined template on Indian numbers
                err_str = str(e).lower()
                if "template" in err_str or "predefined" in err_str:
                    print(f"  [TWILIO TRIAL] Using template 'sms_appointment_reminders' for {to_phone}")
                    client.messages.create(body="sms_appointment_reminders", from_=self.twilio_from, to=to_phone)
                    print(f"  [SENT - SMS via Twilio Template] to {to_phone}")
                    return True
                raise e
        except Exception as e:
            print(f"  [FAILED - SMS via Twilio] to {to_phone}: {e}")
            return False

    # ---------- Fast2SMS backend ----------
    def _send_via_fast2sms(self, to_phone: str, body: str) -> bool:
        # Fast2SMS Quick SMS route expects a bare 10-digit Indian number,
        # not E.164 — strip a leading "+91" or "91" if present.
        number = to_phone.strip().lstrip("+")
        if number.startswith("91") and len(number) == 12:
            number = number[2:]

        url = "https://www.fast2sms.com/dev/bulkV2"
        headers = {
            "authorization": self.fast2sms_api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = {
            "route": "q",  # Quick SMS — no DLT template approval required
            "sender_id": self.fast2sms_sender_id,
            "message": body,
            "language": "english",
            "numbers": number,
        }
        try:
            resp = requests.post(url, headers=headers, data=payload, timeout=15)
            resp.raise_for_status()
            result = resp.json()
            if result.get("return") is True:
                print(f"  [SENT - SMS via Fast2SMS] to {to_phone}")
                return True
            print(f"  [FAILED - SMS via Fast2SMS] to {to_phone}: {result}")
            return False
        except Exception as e:
            print(f"  [FAILED - SMS via Fast2SMS] to {to_phone}: {e}")
            return False
