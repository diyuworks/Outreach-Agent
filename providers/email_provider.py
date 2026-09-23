"""
Email provider — Gmail SMTP (free tier).
Requires a Gmail account + an "App Password" (not your normal password):
https://myaccount.google.com/apppasswords
Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in your .env to send for real.
Without those set, this runs in DRY_RUN mode and just logs what would be sent.
"""
import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()


class EmailProvider:
    def __init__(self):
        self.address = os.getenv("GMAIL_ADDRESS")
        self.app_password = os.getenv("GMAIL_APP_PASSWORD")
        self.dry_run = not (self.address and self.app_password)

    def send(self, to_email: str, subject: str, body: str) -> bool:
        if self.dry_run:
            print(f"  [DRY RUN - EMAIL] Would send to {to_email}")
            print(f"  Subject: {subject}")
            print(f"  Body:\n{body}\n")
            return True

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.address
        msg["To"] = to_email

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.address, self.app_password)
                server.sendmail(self.address, [to_email], msg.as_string())
            print(f"  [SENT - EMAIL] to {to_email}")
            return True
        except Exception as e:
            print(f"  [FAILED - EMAIL] to {to_email}: {e}")
            return False
