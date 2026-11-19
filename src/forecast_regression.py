"""
Model #2: linear regression of oil on economic indicators.

Regression finds the straight-line relationship that best links oil's monthly
% change to the indicators' monthly changes:

    oil change = a + b1 x dollar change + b2 x rate change + ... + noise

Each "b" (coefficient) says how much oil moves, on average, when that
indicator moves. To compare indicators measured in different units, we
"standardise" them: every indicator is expressed in units of its own typical
monthly move (one "standard deviation"). So b = "oil moves b% when this
indicator has a typical-size month".

We run two different tests:

  PART A - EXPLANATION: oil's change in a month vs the indicators' changes in
  the SAME month. Answers "what moves together with oil?". It cannot be used to
  trade, because you only know a month's indicators once the month is over.

  PART B - PREDICTION: next month's oil change vs THIS month's indicators
  (only data already published by then), tested walk-forward on 2015-2026
  against the "no change" benchmark, exactly like ARIMA.

Run from the project folder:
    python src/forecast_regression.py
"""

import os
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

warnings.filterwarnings("ignore")
os.makedirs("results", exist_ok=True)

TEST_START = "2015-01"

# Friendly names for charts and tables, and the economic story behind each.
LABELS = {
    "dollar": "US dollar (vs euro)",
    "rate_10y": "10-year interest rate",
    "vix": "VIX fear index",
    "crude_stocks": "US crude inventories",
    "indpro": "US industrial production",
    "global_activity": "Global economic activity",
}


# ---------------------------------------------------------------------------
# 1. Build one monthly table: oil change + indicator changes
# ---------------------------------------------------------------------------
def read(name: str) -> pd.Series:
    return pd.read_csv(f"data/raw/{name}.csv", parse_dates=["date"], index_col="date").iloc[:, 0]


def end_of_month(series: pd.Series) -> pd.Series:
    """Last available value in each month (for daily and weekly data)."""
    return series.dropna().resample("ME").last()


def monthly_label(series: pd.Series) -> pd.Series:
    """Monthly data is dated the 1st; move it to the month end so everything lines up."""
    series = series.copy()
    series.index = series.index + pd.offsets.MonthEnd(0)
    return series


def build_table() -> pd.DataFrame:
    prices = pd.read_csv("data/raw/oil_prices_daily.csv", parse_dates=["date"], index_col="date")
    brent = end_of_month(prices["brent"])

    # Monthly changes. "log change x 100" is (almost) the % change.
    pct = lambda s: np.log(s).diff() * 100
    table = pd.DataFrame({
        "oil": pct(brent),
        # DEXUSEU is dollars per euro; 1 / it = euros per dollar = dollar strength.
        "dollar": pct(1 / end_of_month(read("usd_per_eur"))),
        "rate_10y": end_of_month(read("rate_10y")).diff(),        # change in % points
        "vix": end_of_month(read("vix")).diff(),                  # change in points
        "crude_stocks": pct(end_of_month(read("crude_stocks"))),  # % change
        "indpro": pct(monthly_label(read("indpro"))),             # % change
        "global_activity": monthly_label(read("global_activity")).diff(),  # change in points
    })
    # Drop the unfinished current month.
    last_full = prices["brent"].dropna().index.max()
    if last_full < table.index.max() - pd.offsets.BDay(1):
        table = table.iloc[:-1]
    return table


def standardise(X: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    """Express each column in units of its typical move (std dev of `reference`)."""
    return (X - reference.mean()) / reference.std()


# ---------------------------------------------------------------------------
# PART A - Explanation (same month)
# ---------------------------------------------------------------------------
def explain(table: pd.DataFrame) -> pd.DataFrame:
    data = table.dropna()
    X = standardise(data[list(LABELS)], data[list(LABELS)])
    model = sm.OLS(data["oil"], sm.add_constant(X)).fit(
        cov_type="HAC", cov_kwds={"maxlags": 3})  # error bars robust to messy finance data

    print(f"PART A - What moves WITH oil in the same month "
          f"({data.index[0]:%Y-%m} to {data.index[-1]:%Y-%m}, {len(data)} months)\n")
    print(f"R-squared: {model.rsquared:.2f}  -> the six indicators together explain "
          f"{model.rsquared:.0%} of oil's monthly ups and downs.\n")

    ci = model.conf_int(alpha=0.05)
    effects = pd.DataFrame({
        "indicator": [LABELS[c] for c in LABELS],
        "effect_%": model.params[list(LABELS)].values,
        "ci_low": ci.loc[list(LABELS), 0].values,
        "ci_high": ci.loc[list(LABELS), 1].values,
        "p_value": model.pvalues[list(LABELS)].values,
        "correlation_alone": [data["oil"].corr(data[c]) for c in LABELS],
    })
    # p-value < 0.05: less than 5% chance of seeing an effect this big by pure luck.
    effects["significant"] = effects["p_value"] < 0.05
    effects = effects.sort_values("effect_%", key=abs, ascending=False).round(3)
    print("Effect on oil of a typical monthly move in each indicator:")
    print(effects.to_string(index=False))
    effects.to_csv("results/regression_effects.csv", index=False)
    return effects, model.rsquared


def stability(table: pd.DataFrame) -> pd.DataFrame:
    """Do the effects hold in different periods, and without the extreme months?
    A relationship that only shows up in one period is not one to trust."""
    data = table.dropna()
    covid = pd.date_range("2020-03-01", "2020-06-30", freq="ME")
    periods = {
        "All months": data,
        "Without COVID crash & 2026": data[~data.index.isin(covid) & (data.index < "2026-01-01")],
        "2000-2007": data[data.index < "2008-01-01"],
        "2008-2019": data[(data.index >= "2008-01-01") & (data.index < "2020-01-01")],
        "2020-2026": data[data.index >= "2020-01-01"],
    }
    rows = []
    for name, d in periods.items():
        X = standardise(d[list(LABELS)], d[list(LABELS)])
        m = sm.OLS(d["oil"], sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
        row = {"period": name, "months": len(d), "R2": round(m.rsquared, 2)}
        for c in LABELS:
            star = "*" if m.pvalues[c] < 0.05 else ""
            row[c] = f"{m.params[c]:+.1f}{star}"
        rows.append(row)
    result = pd.DataFrame(rows)
    print("\nStability check (effect in %, * = significant):")
    print(result.to_string(index=False))
    result.to_csv("results/regression_stability.csv", index=False)
    return result


# ---------------------------------------------------------------------------
# PART B - Prediction (next month, walk-forward)
# ---------------------------------------------------------------------------
def predictive_features(table: pd.DataFrame) -> pd.DataFrame:
    """Only what is published by the end of each month:
    - market data (dollar, rates, VIX) and weekly inventories: same month
    - industrial production: published mid next month -> use the previous month
    - global activity index: published ~2 months later -> use two months back"""
    return pd.DataFrame({
        "dollar": table["dollar"],
        "rate_10y": table["rate_10y"],
        "vix": table["vix"],
        "crude_stocks": table["crude_stocks"],
        "indpro": table["indpro"].shift(1),
        "global_activity": table["global_activity"].shift(2),
    })


def predict(table: pd.DataFrame) -> pd.DataFrame:
    features = predictive_features(table)
    target = table["oil"].shift(-1)          # NEXT month's oil change
    data = features.join(target.rename("next_oil")).dropna()

    rows = []
    for origin in data.index[data.index >= pd.Timestamp(TEST_START) - pd.offsets.MonthEnd(1)]:
        train = data[data.index < origin]    # only pairs whose outcome was known before origin
        X_train = standardise(train[list(LABELS)], train[list(LABELS)])
        fit = sm.OLS(train["next_oil"], sm.add_constant(X_train)).fit()
        x_now = standardise(data.loc[[origin], list(LABELS)], train[list(LABELS)])
        prediction = float(fit.predict(sm.add_constant(x_now, has_constant="add")).iloc[0])
        rows.append({"origin": origin, "predicted_%": prediction, "actual_%": data.loc[origin, "next_oil"]})
    bt = pd.DataFrame(rows).set_index("origin")
    bt.round(3).to_csv("results/regression_backtest.csv")

    err_model = bt["predicted_%"] - bt["actual_%"]
    err_zero = 0 - bt["actual_%"]              # no-change forecast = 0% change
    rmse_model, rmse_zero = np.sqrt((err_model ** 2).mean()), np.sqrt((err_zero ** 2).mean())
    hit = ((bt["predicted_%"] > 0) == (bt["actual_%"] > 0)).mean() * 100
    up_share = (bt["actual_%"] > 0).mean() * 100

    print(f"\nPART B - Predicting NEXT month's oil change ({len(bt)} months, "
          f"{bt.index[0] + pd.offsets.MonthEnd(1):%Y-%m} to {bt.index[-1] + pd.offsets.MonthEnd(1):%Y-%m})\n")
    print(f"  Typical error, regression : {rmse_model:.2f}% per month")
    print(f"  Typical error, no-change  : {rmse_zero:.2f}% per month")
    print(f"  Skill vs no-change        : {(1 - rmse_model / rmse_zero) * 100:+.1f}%  (positive = better)")
    print(f"  Direction right           : {hit:.1f}% of months "
          f"(always guessing 'up' would score {max(up_share, 100 - up_share):.1f}%)")
    return bt, rmse_model, rmse_zero, hit


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------
def plot(effects: pd.DataFrame, r2: float) -> None:
    e = effects.iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    colors = ["#c0392b" if v < 0 else "#1e8449" for v in e["effect_%"]]
    alphas = [1.0 if s else 0.35 for s in e["significant"]]
    for y, (val, lo, hi, c, a) in enumerate(zip(e["effect_%"], e["ci_low"], e["ci_high"], colors, alphas)):
        ax.barh(y, val, color=c, alpha=a)
        ax.plot([lo, hi], [y, y], color="black", lw=1)
    ax.set_yticks(range(len(e)))
    ax.set_yticklabels([f"{n}{'' if s else '  (not significant)'}" for n, s in zip(e["indicator"], e["significant"])])
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("Oil's % move in the same month when the indicator has a typical-size rise")
    ax.set_title(f"What moves with oil? Monthly, 2000-2026 (together these explain {r2:.0%} of oil's moves)")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig("charts/03_indicator_effects.png", dpi=150)


def main():
    table = build_table()
    table.round(4).to_csv("results/monthly_indicator_changes.csv")
    effects, r2 = explain(table)
    stability(table)
    predict(table)
    plot(effects, r2)
    print("\nSaved results/regression_*.csv and charts/03_indicator_effects.png")


if __name__ == "__main__":
    main()
