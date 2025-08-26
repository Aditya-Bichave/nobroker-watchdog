# NoBroker Watchdog (Python 3.11 + Poetry)

A polite, production-ready watcher that monitors **NoBroker** for **new rental homes** in your selected areas and **alerts you instantly** via **WhatsApp** (Cloud API) or **Twilio** (SMS/WhatsApp fallback).

> **Ethics & Legal:** This tool uses only publicly accessible pages, respects `robots.txt`, avoids auth/captchas/paywalls, and throttles every request with jitter. You run it at your own responsibility and must comply with NoBroker's Terms of Use.

---

## Features

- ✅ **Hard constraints**: area/radius, budget, BHK, furnishing, property type, listing age
- ✅ **Soft scoring** (0–100) with clear breakdown (amenities, carpet area, floors, pets, move-in proximity)
- ✅ **Idempotent** alerts using SQLite state (no duplicates)
- ✅ **Politeness**: 1–2s delay with jitter; retries with exponential backoff; UA rotation
- ✅ **Observability**: JSON logs + optional `/health` endpoint
- ✅ **Configurable** via `.env` **and/or** `config.yaml`
- ✅ **Modular**: scraper / matcher / store / notifier / scheduler
- ✅ **Docker** & **Poetry**; unit tests for parser & matcher
- ✅ **Fallbacks**: WhatsApp Cloud first, then Twilio SMS if configured

---

## Quick Start

### 1) Clone & prepare

```bash
git clone <this-project> nobroker-watchdog
cd nobroker-watchdog
cp .env.example .env
# Optionally: cp config.sample.yaml config.yaml  (then tweak)
