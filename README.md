# Project 5: Forecast Accuracy Program

## What was actually built
- **`forecast_backtest.py`** — simulates 36 months of spare-parts demand
  (trend + quarterly seasonality + noise), then runs a proper **rolling-
  origin backtest**: at each origin month, forecast 1 month ahead using only
  data available up to that point (no lookahead leakage), for three
  approaches: naive (last value), seasonal naive (same month last year),
  and Holt's linear trend method (double exponential smoothing, implemented
  from the standard recurrence relations — no statsmodels/Prophet
  dependency required for this method).
- A **grid search** over Holt's smoothing parameters (alpha, beta),
  selecting the combination that minimizes backtest WAPE.
- **Accuracy-over-time tracking**, grouped into rolling windows — this is
  the piece that turns "we built a forecast" into "we monitor forecast
  health," and is exactly what would feed a Power BI accuracy-tracking
  dashboard.

## Run it
```
python3 forecast_backtest.py
```

## What the output actually showed (real run, seed=7) — and why the honest result matters
```
Naive (last value)     : MAPE=4.66%  WAPE=4.74%
Seasonal naive (t-12)  : MAPE=8.85%  WAPE=9.11%
Best Holt's (a=0.9,b=0.15): MAPE=5.30%  WAPE=5.36%

WAPE improvement vs. naive baseline          : -13.1%   (naive actually won)
WAPE improvement vs. seasonal-naive baseline : +41.1%
```
**The naive baseline beat Holt's method on this run, at a 1-month-ahead
horizon.** This is a genuine result, not a cherry-picked one, and it's worth
presenting as-is rather than reshaping the demo until a more complex model
"wins" — that's exactly the discipline a forecast-accuracy program is
supposed to enforce. The likely explanation: at a 1-step horizon with this
noise level, last month's actual is already a strong proxy for next month
(the trend moves slowly relative to the noise), so there's little room for
a smoothing model to add value. Holt's clearly beats the *seasonal* naive
baseline (+41%), which tells you the seasonal-naive approach specifically
is the wrong default here.

**Natural next step** (mention if asked "what would you do next"): rerun
the same backtest at a 3- and 6-month horizon, where trend accumulation
should start to matter more and naive should degrade faster than Holt's —
that's the honest way to find out if the extra model complexity is
justified, instead of assuming it.

## Accuracy over time (from the same run)
```
Months 13-16: WAPE=8.00%   Months 21-24: WAPE=4.29%   Months 29-32: WAPE=5.89%
Months 17-20: WAPE=2.93%   Months 25-28: WAPE=5.90%   Months 33-35: WAPE=4.58%
```
Accuracy isn't flat over time — this is the pattern a real monitoring
dashboard would need to surface (e.g., alert if WAPE in a rolling window
exceeds a threshold), rather than reporting a single all-time MAPE number
that hides degradation in any particular period.
