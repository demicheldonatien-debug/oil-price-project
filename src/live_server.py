"""
Live prices: fetch Brent and WTI futures from Yahoo Finance every 15 minutes,
and serve the website on your computer.

Run from the project folder, and leave it running:
    python src/live_server.py

Then open http://localhost:8000 in your browser. Stop it with Ctrl+C.

What we fetch:
    BZ=F -> Brent crude futures (front month), ICE exchange
    CL=F -> WTI crude futures (front month), NYMEX exchange
A "futures" contract is an agreement to buy oil at a set price on a future date.
The front-month contract is the one closest to delivery; it's the price
traders quote as "the oil price" during the day. Yahoo's free data is
delayed by roughly 10-15 minutes.
"""

import datetime as dt
import functools
import http.server
import json
import os
import threading
import time

import yfinance as yf

TICKERS = {"brent": "BZ=F", "wti": "CL=F"}
REFRESH_MINUTES = 15
PORT = 8000
SITE_DIR = "site"
OUT_PATH = os.path.join(SITE_DIR, "live.json")


def fetch_live() -> dict:
    """Download the last 5 days of 15-minute prices for each ticker."""
    closes = yf.download(list(TICKERS.values()), period="5d", interval="15m", progress=False)["Close"]
    # Show times in New York time, where both contracts are most often quoted.
    closes.index = closes.index.tz_convert("America/New_York")

    data = {
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "Yahoo Finance futures (BZ=F, CL=F), 15-minute bars, delayed ~15 min",
    }
    for name, ticker in TICKERS.items():
        s = closes[ticker].dropna()
        # Previous close = the last price of the previous trading day.
        days = sorted(set(s.index.date))
        prev = s[s.index.date == days[-2]] if len(days) > 1 else s
        data[name] = {
            "times": s.index.strftime("%Y-%m-%d %H:%M").tolist(),
            "prices": [round(float(v), 2) for v in s],
            "last": round(float(s.iloc[-1]), 2),
            "last_time": s.index[-1].strftime("%Y-%m-%d %H:%M"),
            "prev_close": round(float(prev.iloc[-1]), 2),
        }
    return data


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the website files, without printing a line for every request."""

    def log_message(self, *args) -> None:
        pass


def refresh_forever() -> None:
    while True:
        try:
            data = fetch_live()
            # Write to a temporary file first, then swap it in, so the browser
            # never reads a half-written file.
            tmp = OUT_PATH + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f)
            os.replace(tmp, OUT_PATH)
            print(f"[{dt.datetime.now():%H:%M:%S}] Brent ${data['brent']['last']}  "
                  f"WTI ${data['wti']['last']}  (prices as of {data['brent']['last_time']} New York)")
        except Exception as error:  # e.g. no internet, or Yahoo asks us to slow down
            print(f"[{dt.datetime.now():%H:%M:%S}] Could not fetch prices: {error}. Retrying next round.")
        time.sleep(REFRESH_MINUTES * 60)


def main() -> None:
    threading.Thread(target=refresh_forever, daemon=True).start()

    handler = functools.partial(QuietHandler, directory=SITE_DIR)
    server = http.server.ThreadingHTTPServer(("localhost", PORT), handler)
    print(f"Website running: open http://localhost:{PORT}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
