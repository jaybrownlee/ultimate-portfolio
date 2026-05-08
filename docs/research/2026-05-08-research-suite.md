# Research Suite

Mode: actual_current_portfolio
Window: 2025-04-10 to 2026-05-07
Return periods: 269
Rebalance: quarterly

This is actual-current-holdings evidence using the live ETF/equity tickers. Because BAI and ELFY have limited live history, this report should be read as a short-window diagnostic rather than a full-cycle estimate.

## Portfolio Metrics

| Metric | Result |
| --- | ---: |
| Total return | +40.50% |
| CAGR | +37.52% |
| Volatility | 10.91% |
| Sharpe | 2.62 |
| Sortino | 4.13 |
| Max drawdown | -5.72% |
| VaR 95% | -1.07% |
| CVaR 95% | -1.44% |

## Rebalance Comparison

| Frequency | Return | CAGR | Volatility | Sharpe | Max Drawdown | Active | IR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none | +42.15% | +39.02% | 12.64% | 2.36 | -6.69% | +9.50% | 1.05 |
| monthly | +39.79% | +36.86% | 10.79% | 2.60 | -5.71% | +7.47% | 0.96 |
| quarterly | +40.50% | +37.52% | 10.91% | 2.62 | -5.72% | +8.11% | 1.03 |
| yearly | +41.63% | +38.55% | 11.75% | 2.50 | -5.72% | +9.22% | 1.08 |

## Rolling Diagnostics

- 63-period: as of 2026-05-07, return +5.28%, volatility 12.50%, Sharpe 1.39, benchmark correlation 0.82.
- 126-period: as of 2026-05-07, return +10.80%, volatility 11.60%, Sharpe 1.49, benchmark correlation 0.81.

## Bucket Contribution

| Bucket | Weight | Return Contribution | Annualized Contribution | Vol Contribution |
| --- | ---: | ---: | ---: | ---: |
| core | 80.00% | +18.45% | +17.29% | 5.16% |
| satellite | 20.00% | +16.02% | +15.01% | 5.62% |

## Historical Monte Carlo

| Method | Median | P5 | P95 | Probability of Loss | Median Max Drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| bootstrap | $137,183.42 | $115,629.75 | $162,967.60 | 0.20% | -5.35% |
| block_bootstrap | $138,297.27 | $119,133.34 | $156,694.77 | 0.10% | -4.67% |
| student_t | $137,087.09 | $115,628.39 | $165,865.98 | 0.15% | -5.26% |
