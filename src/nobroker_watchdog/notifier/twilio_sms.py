from __future__ import annotations
import logging
import requests

log = logging.getLogger(__name__)

class TwilioClient:
    def __init__(self, cfg):
        self.sid = cfg.twilio_account_sid
        self.token = cfg.twilio_auth_token
        self.from_ = cfg.twilio_from_number

    def send(self, body: str, to_e164: str) -> bool:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json"
            data = {
                "From": self.from_,
                "To": to_e164,
                "Body": body[:1600],
            }
            resp = requests.post(url, data=data, auth=(self.sid, self.token), timeout=20)
            if resp.status_code >= 400:
                log.error("twilio_error", extra={"status": resp.status_code, "body": resp.text})
                return False
            log.info("twilio_sent", extra={"to": to_e164})
            return True
        except Exception:
            log.exception("twilio_exception")
            return False
