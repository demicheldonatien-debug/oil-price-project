"""
Step 1: Download daily oil prices (Brent and WTI) from FRED.

FRED is a free database run by the Federal Reserve Bank of St. Louis.
Every data series there has a short code ("series ID"):
    DCOILBRENTEU  -> Brent crude, US dollars per barrel, daily
    DCOILWTICO    -> WTI crude,   US dollars per barrel, daily

Run from the project folder:
    python src/download_prices.py
"""

import pandas as pd  # pandas = the standard Python library for tables of data

# Where the data starts. 2000-01-01 gives us ~25 years of history.
START_DATE = "2000-01-01"

# A dictionary mapping a friendly name -> the FRED series code.
SERIES = {
    "brent": "DCOILBRENTEU",
    "wti": "DCOILWTICO",
}


def download_fred_series(series_id: str, start: str) -> pd.Series:
    """Download one FRED series and return it as a pandas Series indexed by date."""
    url = (
        "https://fred.stlouisfed.org/graph/fredgraph.csv"
        f"?id={series_id}&cosd={start}"
    )
    # read_csv can read straight from a web address.
    df = pd.read_csv(url, parse_dates=["observation_date"], index_col="observation_date")
    # FRED leaves holidays (e.g. Christmas) as empty values; "coerce" turns them into NaN
    # ("Not a Number"), which pandas understands as "missing".
    return pd.to_numeric(df[series_id], errors="coerce")


def main() -> None:
    prices = pd.DataFrame(
        {name: download_fred_series(code, START_DATE) for name, code in SERIES.items()}
    )
    prices.index.name = "date"

    # Drop days where BOTH prices are missing (market holidays).
    prices = prices.dropna(how="all")

    out_path = "data/raw/oil_prices_daily.csv"
    prices.to_csv(out_path)

    print(f"Saved {len(prices)} days of prices to {out_path}")
    print(f"From {prices.index.min().date()} to {prices.index.max().date()}")
    print("\nFirst rows:\n", prices.head(3))
    print("\nLast rows:\n", prices.tail(3))


if __name__ == "__main__":
    main()
