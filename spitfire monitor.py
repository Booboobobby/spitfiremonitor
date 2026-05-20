#!/usr/bin/env python3
"""
Bul Armory Spitfire (2026) stock monitor.
Polls the product page and fires a critical phone alert via ntfy.sh
the moment it comes back in stock.
"""

import os
import sys
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ====================== CONFIG ======================
PRODUCT_URL = "https://ustore.bularmory.com/products/spitfire-2026"

# ntfy.sh topic. Pick any unique random string (treat it like a password,
# anyone who knows the topic name can send/read your alerts).
# Example: "spitfire-justin-7k4f9q2x"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "PASTE_YOUR_TOPIC_HERE")

# Polling interval in seconds. 60 is sensible. Lower risks an IP block.
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "60"))

# Require this many consecutive in-stock detections before alerting
CONFIRM_HITS = 2
# ====================================================

OUT_OF_STOCK_MARKERS = [
    "sold out",
    "out of stock",
    "coming soon",
    "notify me when available",
    "currently unavailable",
]

IN_STOCK_MARKERS = [
    "add to bag",
    "add to cart",
    "buy now",
    "in stock",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def send_critical_alert():
    """Send a max-priority alert that bypasses silent mode."""
    if NTFY_TOPIC.startswith("PASTE"):
        log("NTFY_TOPIC not configured. Skipping alert.")
        return
    try:
        r = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data="BUL ARMORY SPITFIRE (2026) IS IN STOCK. BUY NOW.".encode("utf-8"),
            headers={
                "Title": "SPITFIRE IN STOCK",
                "Priority": "urgent",
                "Tags": "rotating_light,warning,gun",
                "Click": PRODUCT_URL,
                "Actions": f"view, Buy Now, {PRODUCT_URL}, clear=true",
            },
            timeout=15,
        )
        if r.status_code == 200:
            log("CRITICAL ALERT SENT.")
        else:
            log(f"ntfy error {r.status_code}: {r.text}")
    except Exception as e:
        log(f"ntfy send failed: {e}")


def send_status(msg):
    """Send a low-priority status ping (startup, etc)."""
    if NTFY_TOPIC.startswith("PASTE"):
        return
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=msg.encode("utf-8"),
            headers={"Title": "Spitfire monitor", "Priority": "low"},
            timeout=15,
        )
    except Exception as e:
        log(f"status send failed: {e}")


def fetch_page():
    try:
        r = requests.get(PRODUCT_URL, headers=HEADERS, timeout=25)
        r.raise_for_status()
        return r.text
    except Exception as e:
        log(f"Fetch error: {e}")
        return None


def detect_stock(html):
    """Returns 'in_stock', 'out_of_stock', or 'unknown'."""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()
    found_oos = any(m in text for m in OUT_OF_STOCK_MARKERS)
    found_in  = any(m in text for m in IN_STOCK_MARKERS)

    if found_in and not found_oos:
        return "in_stock"
    if found_oos and not found_in:
        return "out_of_stock"
    if found_in and found_oos:
        # On Lightspeed/Ecwid, "Add to Bag" only renders when the variant
        # is purchasable, so we trust the in-stock signal here.
        return "in_stock"
    return "unknown"


def main():
    log(f"Monitoring {PRODUCT_URL}")
    log(f"Polling every {CHECK_INTERVAL}s. ntfy topic: {NTFY_TOPIC}")
    send_status(f"Monitor started. Watching Spitfire 2026 every {CHECK_INTERVAL}s.")

    hits = 0
    alerted = False

    while True:
        html = fetch_page()
        if html is None:
            time.sleep(CHECK_INTERVAL)
            continue

        state = detect_stock(html)
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
        # 'unknown' -> hold state, do nothing

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped.")
        sys.exit(0)
