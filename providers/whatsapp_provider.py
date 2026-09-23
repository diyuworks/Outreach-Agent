"""
WhatsApp provider — official channels ONLY (Twilio Sandbox or Meta Cloud
API direct). No unofficial WhatsApp Web automation is used or supported —
that violates WhatsApp's Terms of Service and risks the business number
being permanently banned. This is a hard constraint, not a style choice.

Switchable via .env, no code changes needed to swap:

  WHATSAPP_PROVIDER=twilio   (default) — uses Twilio's WhatsApp Sandbox
                              (or an approved Twilio WhatsApp sender).
                              Fast to set up, small markup over Meta's
                              own rate.

  WHATSAPP_PROVIDER=meta     — uses the official Meta Cloud API directly.
                              Cheaper per-message than Twilio (no BSP
                              markup), but requires Meta Business
                              verification + template approval before
                              first-contact messages can be sent.

Without valid credentials for whichever provider is selected, this runs in
safe DRY_RUN mode and just logs what would be sent — never crashes, never
silently switches providers.

IMPORTANT: for BOTH backends, the first message to a new contact must use
a pre-approved message template — free-form text is only allowed once the
contact has replied within the messaging window. This is an account-level
rule enforced by WhatsApp/Meta, not something this code can bypass.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

from phone_utils import normalize_to_e164


class WhatsAppProvider:
    def __init__(self):
        self.provider_name = os.getenv("WHATSAPP_PROVIDER", "twilio").strip().lower()

        # Twilio config
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

        # Meta Cloud API config
        self.meta_token = os.getenv("WHATSAPP_TOKEN")
        self.meta_phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        self.meta_template_name = os.getenv("WHATSAPP_TEMPLATE_NAME")

        if self.provider_name == "meta":
            self.dry_run = not (self.meta_token and self.meta_phone_number_id)
        else:
            self.dry_run = not (self.twilio_sid and self.twilio_token)

    def send(self, to_phone: str, body: str, media_url: str | None = None, country: str | None = None) -> bool:
        """
        to_phone: raw or E.164 format, will be normalized (no 'whatsapp:' prefix needed)
        body: message text (used as-is for Twilio free-form; for Meta this
              is only used in DRY RUN preview, since Meta's first-contact
              send requires a template — see _send_via_meta)
        media_url: optional public HTTPS URL to an image/document to attach
        country: optional country name for default country code determination
        """
        default_cc = "+91" if (country and str(country).strip().lower() in ("india", "in", "+91", "91")) else "+1"
        normalized_phone = normalize_to_e164(to_phone, default_country_code=default_cc)
        if not normalized_phone:
            print(f"  [INVALID PHONE] Could not normalize '{to_phone}' to E.164, skipping send.")
            return False
        to_phone = normalized_phone

        if self.dry_run:
            print(f"  [DRY RUN - WHATSAPP via {self.provider_name}] Would send to {to_phone}")
            print(f"  Message: {body}")
            if media_url:
                print(f"  Media: {media_url}")
            print(f"  (Note: real first-contact sends require an approved template)\n")
            return True

        if self.provider_name == "meta":
            return self._send_via_meta(to_phone, body, media_url)
        return self._send_via_twilio(to_phone, body, media_url)

    # ---------- Twilio backend ----------
    def _send_via_twilio(self, to_phone: str, body: str, media_url: str | None) -> bool:
        try:
            from twilio.rest import Client  # imported lazily so it's optional
            client = Client(self.twilio_sid, self.twilio_token)
            kwargs = {
                "body": body,
                "from_": self.twilio_whatsapp_from,
                "to": f"whatsapp:{to_phone}",
            }
            if media_url:
                kwargs["media_url"] = [media_url]
            try:
                client.messages.create(**kwargs)
                print(f"  [SENT - WHATSAPP via Twilio] to {to_phone}")
                return True
            except Exception as e:
                err_str = str(e).lower()
                if "contentsid" in err_str or "template" in err_str or "400" in err_str:
                    print(f"  [TWILIO TRIAL WHATSAPP] Using template HXfe5ab5f00277942d4d4200328b4d403c for {to_phone}")
                    client.messages.create(
                        content_sid="HXfe5ab5f00277942d4d4200328b4d403c",
                        from_=self.twilio_whatsapp_from,
                        to=f"whatsapp:{to_phone}"
                    )
                    print(f"  [SENT - WHATSAPP via Twilio Template] to {to_phone}")
                    return True
                raise e
        except Exception as e:
            print(f"  [FAILED - WHATSAPP via Twilio] to {to_phone}: {e}")
            return False

    # ---------- Meta Cloud API backend ----------
    def _send_via_meta(self, to_phone: str, body: str, media_url: str | None) -> bool:
        if not self.meta_template_name:
            print(f"  [FAILED - WHATSAPP via Meta] WHATSAPP_TEMPLATE_NAME not set in .env "
                  f"— a first-contact send requires an approved template name.")
            return False

        url = f"https://graph.facebook.com/v20.0/{self.meta_phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {self.meta_token}"}

        template_payload = {"name": self.meta_template_name, "language": {"code": "en_US"}}
        if media_url:
            template_payload["components"] = [{
                "type": "header",
                "parameters": [{"type": "image", "image": {"link": media_url}}],
            }]

        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": template_payload,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            print(f"  [SENT - WHATSAPP via Meta Cloud API] to {to_phone}")
            return True
        except Exception as e:
            print(f"  [FAILED - WHATSAPP via Meta Cloud API] to {to_phone}: {e}")
            return False
