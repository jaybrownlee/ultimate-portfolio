# Actual-Current Portfolio Backtest

Generated: 2026-05-08

This note captures the first actual-current-holdings backtest for `ultimate-portfolio`.

## Data & Method

- Data source: Yahoo chart endpoint through `ultimate_portfolio.data.download_yahoo_chart_prices`.
- Price field: adjusted close when available, close fallback otherwise.
- Window requested: 2025-04-09 to 2026-05-08.
- Backtest window used: 2025-04-10 to 2026-05-07.
- Return periods: 269 daily periods.
- Rebalance frequency: quarterly.
- Initial value: $100,000.
- Annualization: 252 periods.
- Risk-free rate assumption: 4.0%.
- Benchmark: 80% VBIAX + 20% QQQ.

Command:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli download-prices --start 2025-04-09 --end 2026-05-08 --output data/cache/current_prices.csv
PYTHONPATH=src python3 -m ultimate_portfolio.cli backtest data/cache/current_prices.csv --annualization 252 --risk-free-rate 0.04
```

## Portfolio Metrics

| Metric | Result |
| --- | ---: |
| Final value | $140,502.32 |
| Total return | 40.50% |
| CAGR | 37.52% |
| Annualized volatility | 10.91% |
| Sharpe ratio | 2.62 |
| Sortino ratio | 4.13 |
| Calmar ratio | 6.56 |
| Max drawdown | -5.72% |
| Drawdown window | 2026-03-02 to 2026-03-30 |
| Drawdown recovery | 2026-04-20 |
| VaR 95% | -1.07% |
| CVaR 95% | -1.44% |
| Best daily period | 2.98% |
| Worst daily period | -2.33% |
| Positive period rate | 58.74% |

## Benchmark & Relative Metrics

| Metric | Result |
| --- | ---: |
| Benchmark total return | 32.39% |
| Benchmark CAGR | 30.07% |
| Benchmark volatility | 10.14% |
| Benchmark max drawdown | -6.84% |
| Active return | 8.11% |
| Tracking error | 5.51% |
| Information ratio | 1.03 |
| Beta | 0.93 |
| Correlation | 0.87 |

## Interpretation

This first actual-current-holdings read is encouraging: the strategy beat the benchmark blend over the available period, with higher total return, lower max drawdown, and a strong information ratio.

The result should be treated as a short-window diagnostic rather than a durable estimate of expected performance. ELFY and BAI are new funds, so this actual-current test covers only one market regime and starts after the 2025 tariff/rate shock window. The Sharpe and Sortino are especially sensitive to the short period, the strong AI recovery, and the low realized drawdown.

## Next Research Questions

- Run a proxy-regime backtest with older instruments for power infrastructure, AI software, robotics, and managed futures proxies.
- Add rolling 63-day and 126-day Sharpe/correlation charts.
- Compare quarterly versus monthly versus drift-only rebalancing.
- Add bootstrap and Student-t Monte Carlo seeded from actual daily returns.
- Decompose returns and risk contribution by core, satellite, and adopter basket.
