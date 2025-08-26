from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional

from nobroker_watchdog.config import AppConfig, load_config
import datetime as dt
from nobroker_watchdog.scraper.search_builder import build_search_targets, SearchTarget
from nobroker_watchdog.scraper.fetcher import fetch_url, fetch_json, DEFAULT_HEADERS
from nobroker_watchdog.scraper.parser import parse_search_page, parse_nobroker_api_json

# ---------- logging ----------
log = logging.getLogger("nobroker_watchdog.main")
logging.basicConfig(
    level=logging.DEBUG,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)


# ---------- tiny health server (optional) ----------
def start_health_server(port: int, last_run_ref: Dict[str, float]) -> threading.Thread:
    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            if self.path != "/health":
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {"status": "ok", "last_run_ts": last_run_ref.get("ts", 0.0)}
            self.wfile.write(json.dumps(payload).encode())

    srv = HTTPServer(("0.0.0.0", port), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    logging.getLogger("nobroker_watchdog.scheduler").info(
        "health_server_started", extra={"port": port}
    )
    return t


# ---------- one scan ----------
def run_once(cfg: AppConfig) -> Dict[str, Any]:
    targets: List[SearchTarget] = build_search_targets(
        city=cfg.city,
        areas=cfg.areas,
        order_by="lastUpdatedDate desc",
        area_coords=cfg.area_coords,
        bhk_in=cfg.bhk_in,
        furnishing_in=cfg.furnishing_in,
        carpet_min_sqft=cfg.carpet_min_sqft,
        floors_allowed_in=cfg.floors_allowed_in,
        proximity_km=cfg.proximity_km,
    )

    logging.getLogger("nobroker_watchdog.scraper.search_builder").info("search_urls_built")

    seen_area: set[str] = set()
    aggregated: List[Dict[str, Any]] = []

    for t in targets:
        if t.area_name in seen_area:
            continue

        if t.kind == "html":
            resp = fetch_url(
                t.url,
                timeout=cfg.http_timeout_seconds,
                headers=DEFAULT_HEADERS,
                min_delay=cfg.http_min_delay_seconds,
                max_delay=cfg.http_max_delay_seconds,
                max_retries=cfg.max_retries,
            )
            if resp is None:
                continue
            now = dt.datetime.utcnow()
            cards = parse_search_page(resp.text, now)
            logging.getLogger("nobroker_watchdog.scraper.parser").debug(
                "page_parse_result", extra={"url": t.url, "raw_count": len(cards)}
            )
            if cards:
                aggregated.extend(cards)
                seen_area.add(t.area_name)
                continue

        if t.kind == "api":
            payload = fetch_json(
                t.url,
                timeout=cfg.http_timeout_seconds,
                headers=DEFAULT_HEADERS,
                min_delay=cfg.http_min_delay_seconds,
                max_delay=cfg.http_max_delay_seconds,
                max_retries=cfg.max_retries,
            )
            if not payload:
                continue
            cards = parse_nobroker_api_json(payload)
            logging.getLogger("nobroker_watchdog.scraper.parser").debug(
                "api_parse_result", extra={"url": t.url, "raw_count": len(cards)}
            )
            if cards:
                aggregated.extend(cards)
                seen_area.add(t.area_name)

    # Hook matcher/store/notifier here in your build — for now we just summarize.
    cards_seen = len(aggregated)
    new_listings = 0
    alerts_sent = 0
    errors_total = 0

    log.info(
        "scan_summary",
        extra={
            "scan_runs_total": 1,
            "cards_seen": cards_seen,
            "new_listings": new_listings,
            "alerts_sent": alerts_sent,
            "errors_total": errors_total,
        },
    )
    return {
        "cards_seen": cards_seen,
        "new_listings": new_listings,
        "alerts_sent": alerts_sent,
        "errors_total": errors_total,
    }


# ---------- arg parsing ----------
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nobroker-watchdog")
    sub = p.add_subparsers(dest="cmd", required=False)

    run_p = sub.add_parser("run", help="Run a single scan and exit")
    run_p.set_defaults(cmd="run")

    daemon_p = sub.add_parser("daemon", help="Run continuously")
    daemon_p.add_argument(
        "--log-sleep",
        action="store_true",
        help="Log a short heartbeat while waiting for next scan",
    )
    daemon_p.set_defaults(cmd="daemon")

    # If no subcommand provided, default to 'run'
    p.set_defaults(cmd="run")
    return p


# ---------- main ----------
def main(argv: Optional[List[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    cfg = load_config()

    # Health server (if configured)
    last_run_ref: Dict[str, float] = {"ts": 0.0}
    if cfg.health_port is not None and args.cmd == "daemon":
        start_health_server(cfg.health_port, last_run_ref)

    if args.cmd == "run":
        log.info("watchdog_started")
        try:
            run_once(cfg)
            last_run_ref["ts"] = time.time()
            return 0
        except Exception:
            logging.exception("one_shot_failed")
            return 1

    # daemon
    log.info("watchdog_started")
    interval_sec = max(60, int(cfg.scan_interval_minutes * 60))
    try:
        while True:
            t0 = time.time()
            try:
                run_once(cfg)
            except Exception:
                logging.exception("scan_run_failed")
            finally:
                last_run_ref["ts"] = time.time()

            # Visible heartbeat while sleeping (useful on Windows terminals)
            if args.log_sleep:
                remaining = interval_sec - int(time.time() - t0)
                remaining = max(1, remaining)
                for i in range(remaining, 0, -1):
                    # Keep the next line short to avoid noisy logs
                    log.info("sleeping_until_next_scan", extra={"seconds_left": i})
                    time.sleep(1)
            else:
                # Quiet sleep
                elapsed = time.time() - t0
                sleep_for = max(1, interval_sec - int(elapsed))
                time.sleep(sleep_for)
    except KeyboardInterrupt:
        log.info("watchdog_stopped_by_user")
        return 0


if __name__ == "__main__":
    sys.exit(main())
