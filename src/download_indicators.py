"""
Download economic indicators from FRED and the EIA.

FRED series (Federal Reserve Bank of St. Louis):
    CPIAUCSL -> US Consumer Price Index (inflation), monthly
    DEXUSEU  -> US dollars per 1 euro, daily (we flip it to measure dollar strength)
    DGS10    -> 10-year US Treasury interest rate, %, daily
    VIXCLS   -> VIX "fear index" (expected stock market volatility), daily
    INDPRO   -> US industrial production index, monthly
    IGREA    -> Kilian index of global real economic activity, monthly

EIA (US Energy Information Administration), no account needed:
    WCESTUS1 -> US commercial crude oil inventories (excluding the strategic
                reserve), thousand barrels, weekly

Run from the project folder:
    python src/download_indicators.py
"""

import pandas as pd

from download_prices import START_DATE, download_fred_series  # reuse what we already wrote

FRED_INDICATORS = {
    "cpi": "CPIAUCSL",
    "usd_per_eur": "DEXUSEU",
    "rate_10y": "DGS10",
    "vix": "VIXCLS",
    "indpro": "INDPRO",
    "global_activity": "IGREA",
}

EIA_INVENTORIES_URL = "https://www.eia.gov/dnav/pet/hist_xls/WCESTUS1w.xls"


def save(series: pd.Series, name: str, file_name: str | None = None) -> None:
    series.name = name
    series.index.name = "date"
    missing = series[series.isna()]
    out_path = f"data/raw/{file_name or name}.csv"
    series.to_csv(out_path)
    note = f", {len(missing)} missing values" if len(missing) else ""
    print(f"Saved {name:16s} {series.index.min():%Y-%m-%d} to {series.index.max():%Y-%m-%d} "
          f"({len(series)} rows{note}) -> {out_path}")


def download_inventories() -> pd.Series:
    """Weekly US crude oil stocks from the EIA's Excel file."""
    sheet = pd.read_excel(EIA_INVENTORIES_URL, sheet_name="Data 1", skiprows=2)
    sheet.columns = ["date", "crude_stocks"]
    sheet["date"] = pd.to_datetime(sheet["date"])
    series = sheet.set_index("date")["crude_stocks"]
    return series[series.index >= START_DATE]


def main() -> None:
    for name, code in FRED_INDICATORS.items():
        series = download_fred_series(code, START_DATE)
        # Monthly CPI keeps its old file name so the website code still finds it.
        save(series, name, "cpi_monthly" if name == "cpi" else None)
    save(download_inventories(), "crude_stocks")


if __name__ == "__main__":
    main()
