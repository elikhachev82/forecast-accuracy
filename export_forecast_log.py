"""
Exports the rolling-origin backtest results from forecast_backtest.py into a
flat ForecastLog table (PeriodDate, ModelName, ActualValue, ForecastValue),
matching the schema assumed by forecast_accuracy_measures.dax.

This is the "logged to SQL/Snowflake at the end of each monthly run" step
described in the README, stood in here as a CSV so it can be loaded straight
into Power BI Desktop (Get Data > Text/CSV) without needing a live database.

Run it with: python3 export_forecast_log.py
Produces:    ForecastLog.csv
"""

import csv
import random
import math
from datetime import date

random.seed(7)

# ---------------------------------------------------------------------------
# Same simulation as forecast_backtest.py (kept identical so the numbers
# match exactly).
# ---------------------------------------------------------------------------
N_MONTHS = 36
BASE_DEMAND = 400
MONTHLY_TREND = 3.5
SEASONAL_AMPLITUDE = 45
NOISE_SD = 22

actuals = []
for t in range(N_MONTHS):
    trend_component = BASE_DEMAND + MONTHLY_TREND * t
    seasonal_component = SEASONAL_AMPLITUDE * math.sin(2 * math.pi * t / 12 + 0.3)
    noise = random.gauss(0, NOISE_SD)
    demand = max(50, trend_component + seasonal_component + noise)
    actuals.append(round(demand))

# Map month index -> a real calendar month, ending at the most recently
# completed month, so the CSV looks like genuine historical data in Power BI.
LAST_MONTH = date(2026, 6, 1)  # index 35 = June 2026
def month_index_to_date(idx):
    months_back = (N_MONTHS - 1) - idx
    y, m = LAST_MONTH.year, LAST_MONTH.month
    m -= months_back
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def naive_forecast(history):
    return history[-1]


def seasonal_naive_forecast(history):
    if len(history) >= 12:
        return history[-12]
    return history[-1]


def holt_forecast(history, alpha, beta):
    level = history[0]
    trend = history[1] - history[0] if len(history) > 1 else 0.0
    for y in history[1:]:
        prev_level = level
        level = alpha * y + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
    return level + trend


# Best config found by the grid search in forecast_backtest.py (alpha=0.9, beta=0.15).
BEST_ALPHA, BEST_BETA = 0.9, 0.15

MIN_HISTORY = 12
origins = list(range(MIN_HISTORY, N_MONTHS - 1))

rows = []
for origin in origins:
    history = actuals[: origin + 1]
    actual_next = actuals[origin + 1]
    period = month_index_to_date(origin + 1).isoformat()

    forecasts = {
        "Naive": naive_forecast(history),
        "SeasonalNaive": seasonal_naive_forecast(history),
        "HoltsBest": holt_forecast(history, BEST_ALPHA, BEST_BETA),
    }
    for model_name, forecast_value in forecasts.items():
        rows.append({
            "PeriodDate": period,
            "ModelName": model_name,
            "ActualValue": actual_next,
            "ForecastValue": round(forecast_value, 1),
        })

with open("ForecastLog.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["PeriodDate", "ModelName", "ActualValue", "ForecastValue"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} rows to ForecastLog.csv "
      f"({len(origins)} periods x {len(forecasts)} models)")
print(f"Date range: {rows[0]['PeriodDate']} to {rows[-1]['PeriodDate']}")
