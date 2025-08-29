from __future__ import annotations
from .whatsapp import WhatsAppClient
from .twilio_sms import TwilioClient

class Notifier:
    def __init__(self, cfg):
        self.channels = [c.upper() for c in cfg.notify_channels]
        self.clients = []
        if cfg.wa_phone_number_id and cfg.wa_access_token:
            self.clients.append(("WHATSAPP", WhatsAppClient(cfg)))
        if cfg.twilio_account_sid and cfg.twilio_auth_token and cfg.twilio_from_number:
            self.clients.append(("SMS", TwilioClient(cfg)))

    def send(self, msg: str, to_e164: str) -> bool:
        # try channels in desired order if available
        for ch in self.channels:
            for name, client in self.clients:
                if name == ch:
                    ok = client.send(msg, to_e164)
                    if ok:
                        return True
        return False
