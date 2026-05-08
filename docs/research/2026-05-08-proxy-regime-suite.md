# Research Suite

Mode: proxy_regime
Window: 2021-08-04 to 2026-05-07
Return periods: 1194
Rebalance: quarterly

Proxy map used:

- BAI = QQQ
- ELFY = GRID

This is proxy-regime research, not actual-current-holdings evidence. It extends the regime sample by substituting older liquid instruments for funds with limited live history.

## Portfolio Metrics

| Metric | Result |
| --- | ---: |
| Total return | +62.09% |
| CAGR | +10.73% |
| Volatility | 12.24% |
| Sharpe | 0.57 |
| Sortino | 0.81 |
| Max drawdown | -15.33% |
| VaR 95% | -1.23% |
| CVaR 95% | -1.75% |

## Rebalance Comparison

| Frequency | Return | CAGR | Volatility | Sharpe | Max Drawdown | Active | IR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none | +59.36% | +10.33% | 12.18% | 0.55 | -16.53% | +9.79% | 0.18 |
| monthly | +61.44% | +10.64% | 12.27% | 0.57 | -15.43% | +12.58% | 0.27 |
| quarterly | +62.09% | +10.73% | 12.24% | 0.57 | -15.33% | +12.94% | 0.27 |
| yearly | +62.95% | +10.86% | 11.95% | 0.59 | -15.19% | +13.10% | 0.25 |

## Rolling Diagnostics

- 63-period: as of 2026-05-07, return +4.87%, volatility 12.22%, Sharpe 1.30, benchmark correlation 0.82.
- 126-period: as of 2026-05-07, return +10.54%, volatility 11.31%, Sharpe 1.48, benchmark correlation 0.82.

## Bucket Contribution

| Bucket | Weight | Return Contribution | Annualized Contribution | Vol Contribution |
| --- | ---: | ---: | ---: | ---: |
| core | 80.00% | +33.51% | +7.07% | 6.73% |
| satellite | 20.00% | +18.83% | +3.98% | 5.63% |

## Historical Monte Carlo

| Method | Median | P5 | P95 | Probability of Loss | Median Max Drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| bootstrap | $110,217.82 | $90,449.42 | $135,367.13 | 22.90% | -9.43% |
| block_bootstrap | $110,472.88 | $91,860.79 | $131,368.65 | 19.20% | -9.62% |
| student_t | $110,441.24 | $90,846.38 | $137,526.41 | 18.90% | -9.33% |
