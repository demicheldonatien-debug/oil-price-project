"""
Step 2: Draw 25 years of Brent and WTI prices, with major events marked.

Run after download_prices.py:
    python src/plot_prices.py
"""

import pandas as pd
import matplotlib.pyplot as plt

# A first, hand-picked list of events. We'll expand this into a proper
# event dataset in Phase 3.
EVENTS = {
    "2001-09-11": "9/11 attacks",
    "2003-03-20": "Iraq invasion",
    "2008-07-11": "Record high ($147)",
    "2008-09-15": "Lehman collapse",
    "2011-02-15": "Arab Spring / Libya",
    "2014-11-27": "OPEC refuses to cut",
    "2020-03-09": "COVID + Saudi-Russia price war",
    "2022-02-24": "Russia invades Ukraine",
}


def main() -> None:
    prices = pd.read_csv("data/raw/oil_prices_daily.csv", parse_dates=["date"], index_col="date")

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(prices.index, prices["brent"], label="Brent", color="#1f4e79", linewidth=1)
    ax.plot(prices.index, prices["wti"], label="WTI", color="#d98c1a", linewidth=1, alpha=0.8)

    # Draw a dotted vertical line and a label for each event.
    top = prices.max().max()
    for i, (date, label) in enumerate(EVENTS.items()):
        d = pd.Timestamp(date)
        ax.axvline(d, color="grey", linestyle=":", linewidth=1)
        # Alternate label heights so they don't overlap.
        y = top * (0.98 if i % 2 == 0 else 0.88)
        ax.text(d, y, " " + label, fontsize=8, rotation=0, va="top", color="#333")

    ax.set_title("Crude oil prices since 2000 (US$ per barrel, daily)")
    ax.set_ylabel("US$ / barrel")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.8))
    fig.tight_layout()

    out_path = "charts/01_oil_prices_2000_today.png"
    fig.savefig(out_path, dpi=150)
    print(f"Chart saved to {out_path}")


if __name__ == "__main__":
    main()
