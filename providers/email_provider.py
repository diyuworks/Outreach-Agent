"""
Email provider — supports Resend HTTPS REST API (best for cloud deployment like Render)
and Gmail SMTP fallback.

Set RESEND_API_KEY in your .env / Render environment to send via HTTPS (Port 443).
Or set GMAIL_ADDRESS and GMAIL_APP_PASSWORD for local Gmail SMTP.
"""
import os
import requests
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()


class EmailProvider:
    def __init__(self):
        self.resend_api_key = os.getenv("RESEND_API_KEY")
        self.resend_from = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
        self.address = os.getenv("GMAIL_ADDRESS")
        self.app_password = os.getenv("GMAIL_APP_PASSWORD")
        self.dry_run = not (self.resend_api_key or (self.address and self.app_password))

    def send(self, to_email: str, subject: str, body: str) -> bool:
        if self.dry_run:
            print(f"  [DRY RUN - EMAIL] Would send to {to_email}")
            print(f"  Subject: {subject}")
            print(f"  Body:\n{body}\n")
            return True

        # 1. Primary: Resend HTTPS REST API (Runs over Port 443 — 100% reliable on Render/Cloud)
        if self.resend_api_key:
            try:
                resp = requests.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.resend_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "from": self.resend_from,
                        "to": [to_email],
                        "subject": subject,
                        "text": body
                    },
                    timeout=8
                )
                if resp.status_code in (200, 201):
                    print(f"  [SENT - EMAIL via Resend API] to {to_email}")
                    return True
                
                # If Resend free tier test mode requires sending to account owner email
                if resp.status_code == 403 and "only send testing emails to your own email address" in resp.text:
                    import re
                    match = re.search(r'\(([^)]+@[^)]+)\)', resp.text)
                    owner_email = match.group(1) if match else "malaviyadiya496@gmail.com"
                    print(f"  [Resend Test Sandbox] Routing to registered account ({owner_email})...")
                    alt_resp = requests.post(
                        "https://api.resend.com/emails",
                        headers={
                            "Authorization": f"Bearer {self.resend_api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "from": self.resend_from,
                            "to": [owner_email],
                            "subject": f"[Outreach for {to_email}] {subject}",
                            "text": f"--- Target Recipient: {to_email} ---\n\n{body}"
                        },
                        timeout=8
                    )
                    if alt_resp.status_code in (200, 201):
                        print(f"  [SENT - EMAIL via Resend Sandbox] Delivered to {owner_email}")
                        return True
                        print(f"  [SENT - EMAIL via Resend Test Sandbox] Delivered to diyaworks8824@gmail.com")
                        return True
                
                print(f"  [Resend Error: {resp.status_code} - {resp.text}] Falling back to SMTP...")
            except Exception as r_err:
                print(f"  [Resend Exception: {r_err}] Falling back to SMTP...")

        # 2. Fallback: Gmail SMTP (SSL 465 -> STARTTLS 587)
        if self.address and self.app_password:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self.address
            msg["To"] = to_email

            try:
                try:
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=4) as server:
                        server.login(self.address, self.app_password)
                        server.sendmail(self.address, [to_email], msg.as_string())
                    print(f"  [SENT - EMAIL via SSL] to {to_email}")
                    return True
                except Exception as ssl_err:
                    print(f"  [EMAIL SSL 465 failed: {ssl_err}, falling back to STARTTLS 587...]")
                    with smtplib.SMTP("smtp.gmail.com", 587, timeout=4) as server:
                        server.starttls()
                        server.login(self.address, self.app_password)
                        server.sendmail(self.address, [to_email], msg.as_string())
                    print(f"  [SENT - EMAIL via STARTTLS] to {to_email}")
                    return True
            except Exception as e:
                print(f"  [FAILED - EMAIL SMTP] to {to_email}: {e}")
                return False

        return False

