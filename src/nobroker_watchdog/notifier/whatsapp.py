from __future__ import annotations
import logging
import requests

log = logging.getLogger(__name__)

class WhatsAppClient:
    def __init__(self, cfg):
        self.phone_number_id = cfg.wa_phone_number_id
        self.token = cfg.wa_access_token

    def send(self, body: str, to_e164: str) -> bool:
        try:
            url = f"https://graph.facebook.com/v20.0/{self.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": to_e164,
                "type": "text",
                "text": {"body": body[:4096]},
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code >= 400:
                log.error("whatsapp_error", extra={"status": resp.status_code, "body": resp.text})
                return False
            log.info("whatsapp_sent", extra={"to": to_e164})
            return True
        except Exception as e:
            log.exception("whatsapp_exception")
            return False
