"""
Forecast accuracy program: rolling-origin backtest comparing a naive
baseline against Holt's linear trend method (double exponential smoothing,
implemented from scratch -- no statsmodels/Prophet dependency needed for
this method), tracked with MAPE and WAPE over time.

This formalizes forecast evaluation as an ongoing discipline rather than a
one-off "build a model, ship it" exercise -- directly addresses what Upgrade
and Stripe describe as "measure and continuously improve forecast accuracy."

Run it with: python3 forecast_backtest.py
"""

import random
import math

random.seed(7)

# ---------------------------------------------------------------------------
# 1. Simulate 36 months of demand for a product family (e.g. Industrial Pump
#    spare-parts kits) with trend + quarterly seasonality + noise, matching
#    the "$90M inventory value" / demand-forecasting context on the resume.
# ---------------------------------------------------------------------------
N_MONTHS = 36
BASE_DEMAND = 400
MONTHLY_TREND = 3.5
SEASONAL_AMPLITUDE = 45  # quarterly maintenance cycles bump spare-parts demand
NOISE_SD = 22

actuals = []
for t in range(N_MONTHS):
    trend_component = BASE_DEMAND + MONTHLY_TREND * t
    seasonal_component = SEASONAL_AMPLITUDE * math.sin(2 * math.pi * t / 12 + 0.3)
    noise = random.gauss(0, NOISE_SD)
    demand = max(50, trend_component + seasonal_component + noise)
    actuals.append(round(demand))


# ---------------------------------------------------------------------------
# 2. Baseline forecast: naive (last value carried forward).
# ---------------------------------------------------------------------------
def naive_forecast(history):
    return history[-1]


# ---------------------------------------------------------------------------
# 3. Baseline forecast: seasonal naive (same month, prior year) -- only
#    usable once at least 12 months of history exist.
# ---------------------------------------------------------------------------
def seasonal_naive_forecast(history):
    if len(history) >= 12:
        return history[-12]
    return history[-1]


# ---------------------------------------------------------------------------
# 4. Holt's linear trend method (double exponential smoothing), implemented
#    directly from the standard recurrence relations:
#        level_t   = alpha * y_t + (1-alpha) * (level_{t-1} + trend_{t-1})
#        trend_t   = beta  * (level_t - level_{t-1}) + (1-beta) * trend_{t-1}
#        forecast_{t+1} = level_t + trend_t
# ---------------------------------------------------------------------------
def holt_forecast(history, alpha, beta):
    level = history[0]
    trend = history[1] - history[0] if len(history) > 1 else 0.0
    for y in history[1:]:
        prev_level = level
        level = alpha * y + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
    return level + trend


# ---------------------------------------------------------------------------
# 5. Accuracy metrics.
# ---------------------------------------------------------------------------
def mape(errors_pct):
    return sum(abs(e) for e in errors_pct) / len(errors_pct)


def wape(abs_errors, actual_values):
    return sum(abs_errors) / sum(actual_values)


# ---------------------------------------------------------------------------
# 6. Rolling-origin backtest: for each origin from month 13 onward, forecast
#    1 month ahead using only data available up to that origin (no lookahead
#    leakage), for naive, seasonal-naive, and a grid of Holt's (alpha, beta)
#    combinations. Pick the Holt's parameters that minimize backtest WAPE.
# ---------------------------------------------------------------------------
MIN_HISTORY = 12
origins = list(range(MIN_HISTORY, N_MONTHS - 1))

results = {"naive": [], "seasonal_naive": []}
alpha_grid = [0.1, 0.3, 0.5, 0.7, 0.9]
beta_grid = [0.05, 0.15, 0.3]
holt_configs = [(a, b) for a in alpha_grid for b in beta_grid]
for cfg in holt_configs:
    results[f"holt_a{cfg[0]}_b{cfg[1]}"] = []

per_fold_records = []

for origin in origins:
    history = actuals[: origin + 1]
    actual_next = actuals[origin + 1]

    fold = {"origin_month": origin, "actual_next": actual_next}

    for name, fn in [("naive", naive_forecast), ("seasonal_naive", seasonal_naive_forecast)]:
        forecast = fn(history)
        abs_err = abs(actual_next - forecast)
        pct_err = abs_err / actual_next
        results[name].append((abs_err, pct_err, actual_next, forecast))
        fold[f"{name}_forecast"] = round(forecast, 1)

    for a, b in holt_configs:
        forecast = holt_forecast(history, a, b)
        abs_err = abs(actual_next - forecast)
        pct_err = abs_err / actual_next
        results[f"holt_a{a}_b{b}"].append((abs_err, pct_err, actual_next, forecast))

    per_fold_records.append(fold)

# ---------------------------------------------------------------------------
# 7. Summarize accuracy per model, pick the best Holt's config.
# ---------------------------------------------------------------------------
def summarize(name):
    abs_errs = [r[0] for r in results[name]]
    pct_errs = [r[1] for r in results[name]]
    actual_vals = [r[2] for r in results[name]]
    return {
        "mape": mape(pct_errs),
        "wape": wape(abs_errs, actual_vals),
    }

print("=" * 72)
print(f"BACKTEST: {len(origins)} rolling 1-month-ahead forecast folds "
      f"(origins = month {MIN_HISTORY} through {N_MONTHS - 2})")
print("=" * 72)

naive_summary = summarize("naive")
seasonal_summary = summarize("seasonal_naive")
print(f"  Naive (last value)     : MAPE={naive_summary['mape']*100:.2f}%  WAPE={naive_summary['wape']*100:.2f}%")
print(f"  Seasonal naive (t-12)  : MAPE={seasonal_summary['mape']*100:.2f}%  WAPE={seasonal_summary['wape']*100:.2f}%")

holt_summaries = {cfg: summarize(f"holt_a{cfg[0]}_b{cfg[1]}") for cfg in holt_configs}
best_cfg = min(holt_summaries, key=lambda cfg: holt_summaries[cfg]["wape"])
best_summary = holt_summaries[best_cfg]

print()
print(f"  Holt's linear trend -- grid search over alpha in {alpha_grid}, beta in {beta_grid}")
print(f"  Best config: alpha={best_cfg[0]}, beta={best_cfg[1]}")
print(f"  Best Holt's            : MAPE={best_summary['mape']*100:.2f}%  WAPE={best_summary['wape']*100:.2f}%")

improvement_vs_naive = (naive_summary["wape"] - best_summary["wape"]) / naive_summary["wape"]
improvement_vs_seasonal = (seasonal_summary["wape"] - best_summary["wape"]) / seasonal_summary["wape"]
print()
print(f"  WAPE improvement vs. naive baseline          : {improvement_vs_naive*100:+.1f}%")
print(f"  WAPE improvement vs. seasonal-naive baseline : {improvement_vs_seasonal*100:+.1f}%")

# ---------------------------------------------------------------------------
# 8. Accuracy-over-time tracking (quarterly) -- this is the "ongoing
#    monitoring" piece, not just a single aggregate number. This is exactly
#    what would feed a Power BI "forecast accuracy" tracking dashboard.
# ---------------------------------------------------------------------------
print()
print("=" * 72)
print("ACCURACY OVER TIME (best Holt's config, grouped into 4-fold windows)")
print("=" * 72)
best_name = f"holt_a{best_cfg[0]}_b{best_cfg[1]}"
window = 4
for i in range(0, len(results[best_name]), window):
    chunk = results[best_name][i:i + window]
    if not chunk:
        continue
    chunk_pct_errs = [r[1] for r in chunk]
    chunk_abs_errs = [r[0] for r in chunk]
    chunk_actuals = [r[2] for r in chunk]
    start_origin = origins[i]
    end_origin = origins[min(i + window - 1, len(origins) - 1)]
    print(f"  Months {start_origin+1:>2}-{end_origin+1:>2}: "
          f"MAPE={mape(chunk_pct_errs)*100:5.2f}%  WAPE={wape(chunk_abs_errs, chunk_actuals)*100:5.2f}%")

print()
print("=" * 72)
print("SAMPLE FOLD DETAIL (first 5 backtest origins)")
print("=" * 72)
print(f"  {'origin_mo':>9} {'actual':>7} {'naive':>7} {'seas_naive':>10} {'holt_best':>10}")
for fold, (abs_e, pct_e, act, fc) in zip(per_fold_records[:5], results[best_name][:5]):
    print(f"  {fold['origin_month']+1:>9} {fold['actual_next']:>7} "
          f"{fold['naive_forecast']:>7} {fold['seasonal_naive_forecast']:>10} "
          f"{round(fc, 1):>10}")
