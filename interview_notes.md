# Forecast Accuracy Program — Interview Notes

## The 30-second pitch

This project builds a forecast-accuracy monitoring program for spare-parts demand, the same kind of problem behind the $90M inventory-value forecasting work on my resume. Rather than just fitting a model once, it treats forecast evaluation as an ongoing discipline: a rolling-origin backtest compares a naive baseline, a seasonal-naive baseline, and Holt's linear trend method (built from scratch, no external forecasting libraries), tracks accuracy with MAPE and WAPE over time, and feeds those results into a Power BI dashboard with red/yellow/green accuracy alerting. The most interesting result is an honest one: the naive baseline actually beat the more sophisticated model at a one-month horizon, and the project keeps that result rather than reshaping the demo until something more complex "wins."

## Why this project exists (resume tie-in)

The simulated data models 36 months of demand for an industrial-pump spare-parts family: a slow upward trend plus a quarterly seasonal bump (maintenance cycles) plus noise. It's synthetic because this is a portfolio piece, not a data export from a real employer, but the shape of the problem — trend, seasonality, noise, and the need to know whether a forecast is actually working over time rather than just once — maps directly to the demand-forecasting and inventory-accuracy work referenced on the resume.

## The data and the three forecasting approaches

Demand is generated with a fixed random seed (seed=7), so every run reproduces identical numbers — useful for a live demo. Three forecasters are compared. Naive carries forward last month's actual value; it's the baseline every real forecast has to beat to justify existing. Seasonal naive uses the value from 12 months prior, available once a full year of history exists; it's the baseline for anything claiming to capture seasonality. Holt's linear trend method (double exponential smoothing) tracks a level and a trend separately and updates both each step using the standard recurrence relations, implemented directly rather than via statsmodels or Prophet — worth mentioning if asked, since it shows the mechanics are understood rather than just the library call.

## Why a rolling-origin backtest, not a single train/test split

At each origin month starting from month 12, the model sees only data up to that point, forecasts one month ahead, and the origin then moves forward one month at a time — 23 folds total. This eliminates lookahead leakage: a model that looks accurate because it secretly saw future data is worthless once it's actually deployed. This is the single most important design choice in the project and the one most worth being able to explain unprompted.

## Why WAPE alongside MAPE

MAPE (mean absolute percentage error) treats every period equally regardless of volume and can blow up when actuals are near zero. WAPE (total absolute error over total actual volume) is weighted by volume, which is what actually matters for inventory dollars — a 20% miss on a slow month costs far less than a 20% miss on a peak month, and WAPE reflects that while MAPE doesn't. Volunteering this distinction signals an understanding that MAPE, despite being the more commonly cited metric, has a real weakness in practice.

## Grid search and model selection

Holt's is tuned over a grid of alpha (level smoothing) values [0.1, 0.3, 0.5, 0.7, 0.9] and beta (trend smoothing) values [0.05, 0.15, 0.3] — 15 combinations. Each combination is scored on its own backtest WAPE across all 23 folds, and the configuration that minimizes that out-of-sample WAPE is selected (alpha=0.9, beta=0.15 in the seed=7 run). The point is that the hyperparameters are chosen based on genuine walk-forward performance, not in-sample fit, the same discipline that should apply before deploying any tuned model.

## The headline finding, and why it's presented honestly

Naive: MAPE 4.66%, WAPE 4.74%. Seasonal naive: MAPE 8.85%, WAPE 9.11%. Best Holt's: MAPE 5.30%, WAPE 5.36%. Naive beats Holt's by about 13% on WAPE, while Holt's beats seasonal naive by about 41%. The likely explanation: at a one-month horizon with this noise level, last month's actual is already a strong proxy for next month because the trend moves slowly relative to the noise, leaving little room for a smoothing model to add value. The natural next step, and a good answer to "what would you do next": rerun the same backtest at 3- and 6-month horizons, where trend accumulation should matter more and naive should degrade faster than Holt's — an honest way to find out whether the added model complexity is actually justified, rather than assuming it.

## Accuracy over time — the monitoring piece

Instead of one all-time MAPE, results are grouped into rolling four-fold windows, and the windowed WAPE swings between roughly 2.9% and 8% across the 36 months rather than sitting flat. This is what turns the exercise from "we built a model" into "we monitor forecast health" — a single aggregate number would hide periods of real degradation, and a production monitoring dashboard needs to be able to flag a bad window even if the all-time average still looks fine.

## The Power BI dashboard

The Python backtest only prints to console, so a companion script (`export_forecast_log.py`) reruns the same simulation and backtest logic and writes a flat `ForecastLog.csv` table (PeriodDate, ModelName, ActualValue, ForecastValue, 69 rows — 23 periods times 3 models) — standing in for what would, in production, be logged to SQL or Snowflake at the end of each monthly run. That CSV was loaded into Power BI Desktop, related to a calculated Date table (`CALENDAR()`, marked as a date table) so DAX time-intelligence functions like `DATESINPERIOD` work correctly, and six DAX measures were added: Absolute Error, MAPE, WAPE, a trailing 3-month WAPE, a Forecast Accuracy Flag (green under 8% WAPE, yellow 8-15%, red above 15%), and a Best Model This Period measure that ranks all three models by WAPE within whatever filter context is active. The dashboard has a table comparing all three models, a trend line plotting WAPE by month, a model slicer, a Best Model card, and an Accuracy Status card. Numbers were cross-checked against the Python console output and matched exactly.

## A real debugging story worth telling

While building the dashboard, the model slicer initially filtered every visual on the page, including the comparison table and trend line — so instead of showing all three models side by side, everything collapsed to whichever single model was selected in the slicer, and the Best Model card became trivially useless (it could only ever report the one model already selected, since its underlying `SUMMARIZE` had nothing else to rank against). The fix was Power BI's Edit Interactions feature: the slicer was set to filter the Accuracy Status card only, and set to None for the comparison table, trend line, and Best Model card, so those three always show the full picture while the status card responds to whichever model is selected. This is a good story to have ready for a "tell me about a time you found a subtle bug" question — it's a real illustration of understanding DAX filter context, not just writing formulas that happen to work in one view.

## Anticipated interview questions

**Why not just use Prophet or statsmodels for Holt's method?** Implementing the recurrence relations directly demonstrates understanding of what the method is actually doing — level and trend updated via exponential smoothing — rather than treating it as a black box. In a real production setting, using a maintained library would usually be the right call once the mechanics are understood; this was a deliberate choice for a portfolio piece.

**Why does naive winning matter, isn't that a bad result?** It's the most honest and most useful result in the project. A forecasting program's job is to find out what actually works, and sometimes the answer is that a complex model isn't earning its complexity at a given horizon. Reporting that plainly, and following it with a specific next experiment (longer horizons) rather than quietly re-running with a friendlier seed, is exactly the discipline a forecast-accuracy program should enforce.

**How would this operationalize in a real environment?** The monthly backtest and model-selection logic would run as a scheduled job, writing results to the same ForecastLog-shaped table in a warehouse (SQL Server or Snowflake) instead of a CSV, with Power BI refreshing against that table on a schedule and the Accuracy Flag measure feeding an alert (email or Teams message) when a model crosses into red for a given product family.

**What would you change with more time?** Test 3- and 6-month horizons to see whether Holt's earns its complexity over a longer window; add more baseline sophistication such as an ensemble or a simple exponential smoothing with damped trend; and replace the single flat noise level with volume-tiered noise, since real spare-parts SKUs vary widely in volatility by demand volume.

## Files in the project

`forecast_backtest.py` runs the full simulation, three-model backtest, grid search, and prints all summary tables. `export_forecast_log.py` reruns the same logic and writes `ForecastLog.csv` for Power BI. `forecast_accuracy_measures.dax` documents the six measures. `ForecastLog.csv` is the data Power BI actually loads. The `.pbix` file (built manually in Power BI Desktop) is the dashboard itself — save it into this same folder if it isn't there yet, since it's the one artifact not generated by a script.
