from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict

import click

from nobroker_watchdog.config import load_config
from nobroker_watchdog.logging_setup import setup_logging
from nobroker_watchdog.scraper.fetcher import Fetcher
from nobroker_watchdog.scraper.search_builder import build_search_urls
from nobroker_watchdog.scraper.parser import parse_search_page, normalize_raw_listing
from nobroker_watchdog.matcher.score import hard_pass, soft_score
from nobroker_watchdog.store import StateStore
from nobroker_watchdog.notifier import Notifier
from nobroker_watchdog.utils import sha1_fingerprint
from nobroker_watchdog.scheduler import run_health_server, HEALTH, install_signal_handlers, should_stop

log = logging.getLogger(__name__)

MESSAGE_TEMPLATE = (
    "🏠 New Match: {bhk}BHK {furnishing} {property_type} in {area_display}\n"
    "₹{price_monthly}/mo | Dep: {deposit} | {carpet} sqft | Score: {score}%\n"
    "{amenities} | Posted: {posted_rel}\n"
    "Link: {url}\n"
    "Reply 1 to save, 2 to mute this area, 3 to pause alerts for 24h."
)

def _relative_from_iso(iso_str: str | None) -> str:
    if not iso_str:
        return "N/A"
    from dateutil import parser as dateutil_parser
    dt = dateutil_parser.isoparse(iso_str)
    now = datetime.now(tz=timezone.utc)
    s = int((now - dt).total_seconds())
    if s < 3600:
        return f"{s//60}m ago"
    if s < 86400:
        return f"{s//3600}h ago"
    return f"{s//86400}d ago"

@click.group()
def cli():
    pass

@cli.command()
def run():
    cfg = load_config()
    setup_logging(cfg.log_level)

    # Optional health endpoint
    if cfg.health_port:
        import threading
        th = threading.Thread(target=run_health_server, args=(cfg.health_port,), daemon=True)
        th.start()

    fetcher = Fetcher(cfg.http_timeout_seconds, cfg.http_min_delay_seconds, cfg.http_max_delay_seconds, cfg.max_retries)
    urls = build_search_urls(cfg.city, cfg.areas)
    store = StateStore()
    notifier = Notifier(cfg)

    install_signal_handlers()

    counters = {
        "scan_runs_total": 0,
        "cards_seen": 0,
        "new_listings": 0,
        "alerts_sent": 0,
        "errors_total": 0,
    }

    def one_scan():
        now = datetime.now(tz=timezone.utc)
        HEALTH.last_run_ts = now.timestamp()
        matches: List[Dict] = []
        seen = 0
        for url in urls:
            try:
                r = fetcher.get(url)
                items_raw = parse_search_page(r.text, now)
                for raw in items_raw:
                    item = normalize_raw_listing(raw, now)
                    seen += 1

                    # Hard filters
                    hp, prox_km = hard_pass(
                        item,
                        cfg.areas,
                        cfg.city,
                        cfg.budget_min,
                        cfg.budget_max,
                        cfg.bhk_in,
                        cfg.furnishing_in,
                        cfg.property_types_in,
                        cfg.listing_age_max_hours,
                        cfg.area_coords if cfg.area_coords else None,
                        cfg.proximity_km,
                    )
                    item["hard_filters_passed"] = hp
                    item["soft_matches"]["proximity_km"] = prox_km

                    if not hp:
                        continue

                    score, soft = soft_score(
                        item,
                        cfg.required_amenities_any,
                        cfg.carpet_min_sqft,
                        cfg.floors_allowed_in,
                        cfg.pets_allowed,
                        cfg.move_in_by,
                    )
                    item["match_score"] = score
                    item["soft_matches"].update(soft)

                    if score < cfg.soft_match_threshold:
                        continue

                    matches.append(item)
            except Exception:
                counters["errors_total"] += 1
                log.exception("scan_error", extra={"url": url})

        counters["cards_seen"] += seen
        counters["scan_runs_total"] += 1

        # Deduplicate + Notify
        for m in matches:
            fp = sha1_fingerprint([m["listing_id"], m["price_monthly"], m["deposit"], m["title"]])
            if not m["listing_id"]:
                continue
            if store.already_notified(m["listing_id"], fp):
                continue

            body = MESSAGE_TEMPLATE.format(
                bhk=(m["bhk"] or "?"),
                furnishing=(m["furnishing"] or "").strip() or "—",
                property_type=(m["property_type"] or "").strip() or "Home",
                area_display=m.get("area_display") or cfg.city,
                price_monthly=m["price_monthly"],
                deposit=(m["deposit"] if m["deposit"] is not None else "—"),
                carpet=(m["carpet_sqft"] or "—"),
                score=m["match_score"],
                amenities=", ".join((m.get("soft_matches", {}).get("amenities_matched") or [])[:3]) or "—",
                posted_rel=_relative_from_iso(m.get("posted_at")),
                url=m["url"],
            )
            ok = notifier.send(body, cfg.notify_phone_e164)
            if ok:
                counters["alerts_sent"] += 1
                store.upsert_notification(m["listing_id"], fp)

        HEALTH.last_status = "ok"
        log.info("scan_summary", extra=counters)

    # Loop
    log.info("watchdog_started", extra={"interval_min": cfg.scan_interval_minutes})
    while not should_stop():
        try:
            one_scan()
        except Exception:
            counters["errors_total"] += 1
            HEALTH.last_status = "error"
            log.exception("run_loop_error")
        # Sleep until next run
        from time import sleep
        for _ in range(int(cfg.scan_interval_minutes * 60)):
            if should_stop():
                break
            sleep(1)

    log.info("watchdog_stopped")
