"""
Forecasting model #1: ARIMA, tested against the "no-change" benchmark.

ARIMA = AutoRegressive Integrated Moving Average. In plain words:
  - "Integrated" (the d in ARIMA(p, d, q)): we model the monthly CHANGE in price,
    not the price itself. d=1 means "take differences once".
  - "AutoRegressive" (p): this month's change depends on the last p changes
    (e.g. momentum: a rise tends to be followed by another rise).
  - "Moving Average" (q): this month's change depends on the last q surprises
    (how wrong the model was recently).
We work with the LOG of the price, so changes are percentages (a $5 move means
more at $20 than at $120).

The test ("walk-forward backtest"):
  - Train on 2000-2014 to choose p and q.
  - Then for every month from Dec 2014 onwards: re-fit using only data known
    at that time, and forecast 1 and 12 months ahead.
  - Compare with the no-change forecast ("price stays where it is").

Run from the project folder:
    python src/forecast_arima.py
"""

import itertools
import os
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

warnings.filterwarnings("ignore")  # statsmodels prints many harmless fitting warnings

TEST_START = "2015-01"   # first month we forecast "blind"
HORIZONS = [1, 12]       # months ahead
INTERVAL = 0.80          # we ask for 80% ranges: the truth should fall inside ~80% of the time
os.makedirs("results", exist_ok=True)


# ---------------------------------------------------------------------------
# 1. Data: Brent end-of-month prices
# ---------------------------------------------------------------------------
def load_monthly_brent() -> pd.Series:
    daily = pd.read_csv("data/raw/oil_prices_daily.csv", parse_dates=["date"], index_col="date")["brent"]
    monthly = daily.dropna().resample("ME").last()  # last trading day of each month
    # Drop the current month if it isn't finished yet.
    if daily.dropna().index.max() < monthly.index.max() - pd.offsets.BDay(1):
        monthly = monthly.iloc[:-1]
    # Note: we use END-of-month prices, not monthly AVERAGES. Averaging smooths
    # the series and creates fake "momentum" that makes models look better than they are.
    return monthly


# ---------------------------------------------------------------------------
# 2. Choose p and q, using the training years only
# ---------------------------------------------------------------------------
def choose_orders(log_train: pd.Series) -> dict:
    """Try every p, q from 0 to 3 and rank them by AIC.
    AIC rewards fitting the data well but penalises extra complexity.
    Returns the best model, and the best model that actually uses the past
    (ARIMA(0,1,0) is just "no change", so we also test the best alternative)."""
    results = []
    for p, q in itertools.product(range(4), range(4)):
        fit = ARIMA(log_train, order=(p, 1, q)).fit()
        results.append(((p, 1, q), fit.aic))
    results.sort(key=lambda r: r[1])
    print("Best orders on 2000-2014 (lower AIC is better):")
    for order, aic in results[:5]:
        print(f"   ARIMA{order}: AIC {aic:.1f}")
    best = results[0][0]
    best_with_memory = next(order for order, _ in results if order != (0, 1, 0))
    models = {"arima": best}
    if best == (0, 1, 0):
        models["arima_" + "".join(map(str, best_with_memory))] = best_with_memory
    return models


# ---------------------------------------------------------------------------
# 3. Walk-forward backtest
# ---------------------------------------------------------------------------
def backtest(log_price: pd.Series, models: dict) -> pd.DataFrame:
    rows = []
    months = log_price.index
    first_origin = months.get_loc(months[months >= TEST_START][0]) - 1
    for i in range(first_origin, len(months) - 1):
        origin = months[i]
        history = log_price.iloc[: i + 1]            # only what was known at that time
        forecasts = {}
        for name, order in models.items():
            fc = ARIMA(history, order=order).fit().get_forecast(max(HORIZONS))
            forecasts[name] = (fc.predicted_mean.values, *fc.conf_int(alpha=1 - INTERVAL).values.T)
        for h in HORIZONS:
            if i + h >= len(months):
                continue                              # the future we can't check yet
            row = {
                "origin": origin, "horizon": h, "target": months[i + h],
                "price_at_origin": np.exp(history.iloc[-1]),
                "actual": np.exp(log_price.iloc[i + h]),
            }
            for name, (mean, low, high) in forecasts.items():
                row[name] = np.exp(mean[h - 1])
                row[name + "_low"] = np.exp(low[h - 1])
                row[name + "_high"] = np.exp(high[h - 1])
            rows.append(row)
    bt = pd.DataFrame(rows)
    bt["no_change"] = bt["price_at_origin"]
    return bt


# ---------------------------------------------------------------------------
# 4. Scores
# ---------------------------------------------------------------------------
def score(bt: pd.DataFrame, models: dict) -> pd.DataFrame:
    rows = []
    for h, g in bt.groupby("horizon"):
        actual_up = g["actual"] > g["price_at_origin"]
        for model in ["no_change", *models]:
            err = g[model] - g["actual"]
            row = {
                "horizon_months": h,
                "model": model,
                "forecasts": len(g),
                # Average size of the error, in dollars (big errors count extra in RMSE).
                "MAE_$": err.abs().mean(),
                "RMSE_$": np.sqrt((err ** 2).mean()),
                # Average error as a % of the price.
                "MAPE_%": (err.abs() / g["actual"]).mean() * 100,
            }
            if model != "no_change":
                change = g[model] - g["price_at_origin"]
                # Only meaningful if the model actually predicts moves up or down.
                if (change.abs() > 0.01).any():
                    row["direction_hit_%"] = ((change > 0) == actual_up).mean() * 100
                inside = (g["actual"] >= g[model + "_low"]) & (g["actual"] <= g[model + "_high"])
                row["inside_80%_range_%"] = inside.mean() * 100
            rows.append(row)
    table = pd.DataFrame(rows)
    # Skill vs no-change: positive = better than the benchmark, negative = worse.
    bench = table[table.model == "no_change"].set_index("horizon_months")["RMSE_$"]
    table["skill_vs_no_change_%"] = table.apply(
        lambda r: (1 - r["RMSE_$"] / bench[r["horizon_months"]]) * 100, axis=1)
    return table.round(2)


# ---------------------------------------------------------------------------
# 5. A forecast for the real future
# ---------------------------------------------------------------------------
def forecast_future(log_price: pd.Series, order: tuple) -> pd.DataFrame:
    """Forecast from the last complete month, using the chosen (best) model."""
    fit = ARIMA(log_price, order=order).fit()
    fc = fit.get_forecast(12)
    low, high = fc.conf_int(alpha=1 - INTERVAL).values.T
    return pd.DataFrame({
        "month": fc.predicted_mean.index.strftime("%Y-%m"),
        "forecast": np.exp(fc.predicted_mean.values),
        "low_80": np.exp(low),
        "high_80": np.exp(high),
    }).round(2)


# ---------------------------------------------------------------------------
# 6. Charts
# ---------------------------------------------------------------------------
def plot(monthly, bt, future):
    fig, axes = plt.subplots(2, 1, figsize=(14, 9))

    one = bt[bt.horizon == 1].set_index("target")
    ax = axes[0]
    ax.plot(monthly.loc["2014":], color="black", lw=1.4, label="Actual Brent (end of month)")
    ax.fill_between(one.index, one["arima_low"], one["arima_high"], color="#d98c1a", alpha=0.15,
                    label="80% range")
    ax.plot(one["no_change"], color="#1f4e79", lw=1.1, label="No-change forecast (= best ARIMA)")
    other = [c for c in one.columns if c.startswith("arima_") and not c.endswith(("_low", "_high"))]
    for name in other:
        ax.plot(one[name], color="#c0392b", lw=1, ls="--", label=f"{name.upper()} forecast")
    ax.set_title("Backtest: 1-month-ahead forecasts vs what really happened (2015-2026)")
    ax.set_ylabel("US$ / barrel"); ax.grid(alpha=0.3); ax.legend(loc="upper left", fontsize=9)

    ax = axes[1]
    recent = monthly.loc["2022":]
    fut_idx = pd.to_datetime(future["month"]) + pd.offsets.MonthEnd(0)
    ax.plot(recent, color="black", lw=1.4, label="Actual Brent")
    ax.plot(fut_idx, future["forecast"], color="#d98c1a", lw=1.6, label="ARIMA forecast")
    ax.fill_between(fut_idx, future["low_80"], future["high_80"], color="#d98c1a", alpha=0.2,
                    label="80% range")
    ax.set_title("ARIMA forecast for the next 12 months")
    ax.set_ylabel("US$ / barrel"); ax.grid(alpha=0.3); ax.legend(loc="upper left", fontsize=9)

    fig.tight_layout()
    fig.savefig("charts/02_arima_forecast.png", dpi=150)


def main():
    monthly = load_monthly_brent()
    log_price = np.log(monthly)
    print(f"Data: {len(monthly)} months, {monthly.index[0]:%Y-%m} to {monthly.index[-1]:%Y-%m}\n")

    models = choose_orders(log_price[log_price.index < TEST_START])
    print(f"\nModels tested: {models}\n")

    bt = backtest(log_price, models)
    bt.round(2).to_csv("results/arima_backtest.csv", index=False)

    table = score(bt, models)
    table.to_csv("results/arima_scores.csv", index=False)
    print("Scores on 2015-2026 (data the model never trained on):")
    print(table.to_string(index=False))

    future = forecast_future(log_price, models["arima"])
    future.to_csv("results/arima_future.csv", index=False)
    print("\nForecast for the next 12 months:")
    print(future.to_string(index=False))

    plot(monthly, bt, future)
    print("\nSaved results/ (CSV files) and charts/02_arima_forecast.png")


if __name__ == "__main__":
    main()
