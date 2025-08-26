from __future__ import annotations
import logging
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

log = logging.getLogger(__name__)

class HealthState:
    last_status: str = "init"
    last_run_ts: Optional[float] = None

HEALTH = HealthState()

def run_health_server(port: int):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                msg = (
                    f'{{"status":"{HEALTH.last_status}","last_run_ts":{HEALTH.last_run_ts or "null"}}}'
                )
                self.wfile.write(msg.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            return

    srv = HTTPServer(("0.0.0.0", port), Handler)
    log.info("health_server_started", extra={"port": port})
    srv.serve_forever()

_stop = False

def install_signal_handlers():
    def sigterm(signum, frame):
        global _stop
        _stop = True
        log.info("shutdown_signal", extra={"signal": signum})
    signal.signal(signal.SIGINT, sigterm)
    signal.signal(signal.SIGTERM, sigterm)

def should_stop() -> bool:
    return _stop
