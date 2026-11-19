"""
Download economic indicators from FRED.

For now just one indicator:
    CPIAUCSL -> US Consumer Price Index (CPI), all items, monthly, seasonally adjusted.
                It measures the average price of a basket of goods and services.
                If CPI goes from 100 to 110, prices have risen 10% on average (= inflation).

Run from the project folder:
    python src/download_indicators.py
"""

from download_prices import START_DATE, download_fred_series  # reuse what we already wrote

INDICATORS = {
    "cpi": "CPIAUCSL",
}


def main() -> None:
    for name, code in INDICATORS.items():
        series = download_fred_series(code, START_DATE)
        series.name = name
        series.index.name = "date"

        missing = series[series.isna()]
        if len(missing):
            print(f"{name}: missing months {[d.strftime('%Y-%m') for d in missing.index]}")

        out_path = f"data/raw/{name}_monthly.csv"
        series.to_csv(out_path)
        print(f"Saved {len(series)} months of {name} to {out_path} "
              f"({series.index.min():%Y-%m} to {series.index.max():%Y-%m})")


if __name__ == "__main__":
    main()
