# Oil Price Project

A learning project: study 25+ years of crude oil prices (Brent & WTI), explain their moves with
economic indicators and world events, and eventually test a rules-based trading strategy on oil ETFs.

## Phases
1. **Price history** – download Brent & WTI since 2000 and chart them ✅
2. Economic indicators – inflation ✅ (Inflation Adj button), interest rates, US dollar, inventories, production
3. Event timeline – wars, OPEC decisions, crises, and how prices reacted
4. Models – explain past moves, then forecast (honestly evaluated)
5. Trading rules + backtest
6. Paper trading (simulated money) via a broker API

## How to run
```bash
pip install -r requirements.txt
python src/download_prices.py   # saves data/raw/oil_prices_daily.csv
python src/download_indicators.py  # saves data/raw/cpi_monthly.csv (inflation)
python src/plot_prices.py       # saves charts/01_oil_prices_2000_today.png
python src/build_site_data.py   # packages prices, inflation and data/events.csv into site/data.js
```

## The website
Open `site/index.html` in your browser (double-click it in Finder / File Explorer).
It shows Brent and WTI since 2000. Buttons:
- **Major Events** shows the events from `data/events.csv` in red.
- **Inflation Adj** shows prices in today's dollars, adjusted with US CPI
  (real price = price x CPI latest / CPI that month). To add an event, add a row to `data/events.csv` and re-run
`python src/build_site_data.py`.

Data source: FRED (Federal Reserve Bank of St. Louis), series DCOILBRENTEU and DCOILWTICO.
