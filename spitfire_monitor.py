#!/usr/bin/env python3
"""
Bul Armory Spitfire (2026) stock monitor — Shopify JSON + Pushover Emergency.
Bypasses silent mode and DND via Pushover priority 2.
"""

import os
import sys
import time
import requests
from datetime import datetime

# ====================== CONFIG ======================
PRODUCT_HANDLE = "spitfire-2026"
PRODUCT_URL = f"https://ustore.bularmory.com/products/{PRODUCT_HANDLE}"
JSON_URL = f"{PRODUCT_URL}.json"

PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN")
PUSHOVER_USER = os.environ.get("PUSHOVER_USER")

CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "60"))
RUN_ONCE = bool(os.environ.get("RUN_ONCE"))
CONFIRM_HITS = 2
# ====================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def send_critical_alert():
    if not (PUSHOVER_TOKEN and PUSHOVER_USER):
        log("Pushover credentials missing. Skipping alert.")
        return
    try:
        r = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": PUSHOVER_TOKEN,
                "user": PUSHOVER_USER,
                "title": "SPITFIRE IN STOCK",
                "message": f"Bul Armory Spitfire 2026 is in stock. Buy now: {PRODUCT_URL}",
                "url": PRODUCT_URL,
                "url_title": "Buy Now",
                "priority": 2,
                "retry": 30,
                "expire": 3600,
                "sound": "siren",
            },
            timeout=15,
        )
        if r.status_code == 200:
            log("EMERGENCY ALERT SENT.")
        else:
            log(f"Pushover error {r.status_code}: {r.text}")
    except Exception as e:
        log(f"Pushover send failed: {e}")


def detect_stock():
    """Returns 'in_stock', 'out_of_stock', or 'unknown'."""
    try:
        r = requests.get(JSON_URL, headers=HEADERS, timeout=25)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log(f"Fetch error: {e}")
        return "unknown"

    variants = data.get("product", {}).get("variants", [])
    if not variants:
        log("No variants in JSON response.")
        return "unknown"

    any_available = any(v.get("available") for v in variants)
    log(f"Variants: {[(v.get('title'), v.get('available')) for v in variants]}")
    return "in_stock" if any_available else "out_of_stock"


def run_once():
    log(f"RUN_ONCE mode. Checking {JSON_URL}")
    hits = 0
    for i in range(2):
        if i > 0:
            time.sleep(30)
        state = detect_stock()
        log(f"Check {i+1}: {state}")
        if state == "in_stock":
            hits += 1
        else:
            return
    if hits >= 2:
        send_critical_alert()


def run_loop():
    log(f"Loop mode. Monitoring {JSON_URL} every {CHECK_INTERVAL}s")
    hits = 0
    alerted = False
    while True:
        state = detect_stock()
        log(f"State: {state}")
        if state == "in_stock":
            hits += 1
            if hits >= CONFIRM_HITS and not alerted:
                send_critical_alert()
                alerted = True
        elif state == "out_of_stock":
            if alerted:
                log("Stock cleared. Re-arming alert.")
            hits = 0
            alerted = False
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        if RUN_ONCE:
            run_once()
        else:
            run_loop()
    except KeyboardInterrupt:
        log("Stopped.")
        sys.exit(0)
