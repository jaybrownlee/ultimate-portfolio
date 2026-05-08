# ultimate-portfolio

Python tooling for the 80/20 Hierarchical AI Infrastructure & Adopter Portfolio.

The project models the strategy as an operating system, not just a rebalance calculator:

- master 80/20 core/satellite drift control
- lightweight daily trigger checks
- quarterly internal bucket sweeps
- 20% drawdown uncle point that moves satellite exposure to SGOV
- 25% defensive-core entry plus 3-6 month DCA schedule
- deterministic scenario shocks
- Monte Carlo stress testing
- monthly review protocol against the 80% balanced index / 20% Nasdaq 100 benchmark blend
- 2-of-3 AI adopter screen

This is decision-support software, not financial advice. Live fund liquidity, tax impact, spreads, execution quality, and current market data still need review before trading.

## Strategy Weights

The core and satellite holdings are modeled as bucket-internal weights.

### 80% Core

| Holding | Core Weight | Total Portfolio Weight | Role |
| --- | ---: | ---: | --- |
| COWZ | 35.0% | 28.0% | Free cash flow / anti-hype equity anchor |
| WMT | 5.0% | 4.0% | AI adopter |
| JPM | 5.0% | 4.0% | AI adopter |
| DE | 5.0% | 4.0% | AI adopter |
| DBMF | 25.0% | 20.0% | Managed futures trend-following hedge |
| SGOV | 12.5% | 10.0% | T-bill liquidity |
| TLT | 12.5% | 10.0% | Deflation/recession duration hedge |

Optional stagflation overlay:

- Shift 2.5% of core from SGOV and 2.5% from TLT into 5% GLDM.

### 20% Satellite

| Holding | Satellite Weight | Total Portfolio Weight | Role |
| --- | ---: | ---: | --- |
| SPRX | 40.0% | 8.0% | High-conviction semiconductor and hardware supply chain |
| ARKQ | 35.0% | 7.0% | Embodied AI, robotics, and energy storage |
| ELFY | 15.0% | 3.0% | Power infrastructure and cooling |
| BAI | 10.0% | 2.0% | Broad AI tech stack |

Expected return target from the written system:

- Core: 11.2%
- Satellite: 28.5%
- Total: 14.66%

## Install-Free Usage

Run from the repository root:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli analyze examples/positions.csv
```

The compatibility entrypoint still works:

```bash
PYTHONPATH=src python3 -m hierarchical_etf.cli analyze examples/positions.csv
```

## Analyze Holdings

Positions CSV can use `market_value`:

```csv
ticker,market_value
COWZ,28000
WMT,4000
JPM,4000
DE,4000
DBMF,20000
SGOV,10000
TLT,10000
SPRX,8000
ARKQ,7000
ELFY,3000
BAI,2000
```

Or `shares` and `price`:

```csv
ticker,shares,price
COWZ,100,55.25
DBMF,200,26.10
```

Commands:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli analyze examples/positions.csv
PYTHONPATH=src python3 -m ultimate_portfolio.cli analyze examples/positions.csv --force-sweep
PYTHONPATH=src python3 -m ultimate_portfolio.cli analyze examples/positions.csv --peak-value 130000
PYTHONPATH=src python3 -m ultimate_portfolio.cli analyze examples/positions.csv --stagflation-overlay
PYTHONPATH=src python3 -m ultimate_portfolio.cli analyze examples/positions.csv --json
```

Rebalance modes:

- `hold`: no threshold breach and no calendar sweep.
- `boundary`: satellite reached 25% or 15%; master buckets are reset to 80/20 while preserving current internal proportions.
- `internal`: quarterly sweep; ETF/equity weights are reset inside each bucket without moving capital across the 80/20 boundary.
- `full`: boundary and calendar triggers are both active; reset both master buckets and internal holdings.
- `circuit_breaker`: total portfolio drawdown breached 20%; satellite exposure is moved to SGOV for review.

## DCA Deployment

The tactical entry rule deploys 25% immediately into the defensive core subset, then DCA's the remaining 75% into the gaps required to reach final target weights.

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli dca 100000 --months 6 --start 2026-05-07
```

The initial defensive subset is COWZ, DBMF, and SGOV, allocated in proportion to their final target weights.

## Stress Test

Run deterministic shocks plus Monte Carlo:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli stress examples/positions.csv --paths 5000 --years 10
```

Scenario shocks currently include:

- high-rate tech selloff
- AI hardware cycle bust
- recession/deflation
- stagflation/rates up

Monte Carlo uses the strategy's 11.2% core and 28.5% satellite expected returns, with configurable volatility and correlation assumptions.

## Backtest Research

The first research harness runs from a long-form price CSV. It is dependency-light and uses transparent internal math for CAGR, volatility, Sharpe, Sortino, Calmar, drawdowns, VaR/CVaR, beta, correlation, tracking error, and information ratio.

Price CSV format:

```csv
date,ticker,price
2026-01-31,COWZ,100
2026-01-31,QQQ,100
```

Run the sample:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli backtest examples/prices_sample.csv --annualization 12
```

Use a different benchmark blend:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli backtest examples/prices_sample.csv --annualization 12 --benchmark VBIAX:0.8,QQQ:0.2
```

The default live data downloader uses Yahoo's chart endpoint through the Python standard library:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli download-prices --start 2025-04-09 --end 2026-05-07 --output data/cache/current_prices.csv
PYTHONPATH=src python3 -m ultimate_portfolio.cli backtest data/cache/current_prices.csv
```

You can also use `--provider yfinance` after installing the research extras:

```bash
python3 -m pip install '.[research]'
PYTHONPATH=src python3 -m ultimate_portfolio.cli download-prices --provider yfinance --start 2025-04-09 --end 2026-05-07 --output data/cache/current_prices.csv
```

Because BAI and ELFY are new funds, actual-current-portfolio evidence should be separated from proxy-regime research.
The project research discipline is documented in [docs/research-methodology.md](docs/research-methodology.md).

The first actual-current-holdings research note is saved at [docs/research/2026-05-08-current-portfolio-backtest.md](docs/research/2026-05-08-current-portfolio-backtest.md).

Run the fuller research suite:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli research-suite data/cache/current_prices.csv --annualization 252 --risk-free-rate 0.04 --report docs/research/research-suite.md
```

The suite adds:

- rebalance frequency comparison
- 63-period and 126-period rolling diagnostics
- bucket and symbol contribution analysis
- bootstrap, block bootstrap, and Student-t historical Monte Carlo

Proxy-regime research can substitute older proxies for new funds:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli download-prices --tickers ARKQ,COWZ,DBMF,DE,GRID,JPM,QQQ,SGOV,SPRX,TLT,VBIAX,WMT --start 2021-08-04 --end 2026-05-08 --output data/cache/proxy_prices.csv
PYTHONPATH=src python3 -m ultimate_portfolio.cli research-suite data/cache/proxy_prices.csv --proxy-map BAI=QQQ,ELFY=GRID --annualization 252 --risk-free-rate 0.04 --report docs/research/proxy-regime-suite.md
```

Current generated reports:

- [docs/research/2026-05-08-research-suite.md](docs/research/2026-05-08-research-suite.md)
- [docs/research/2026-05-08-proxy-regime-suite.md](docs/research/2026-05-08-proxy-regime-suite.md)

## Assessment Process

The daily, monthly, and quarterly operating process is documented in [docs/assessment-process.md](docs/assessment-process.md).

Run a daily trigger check:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli daily-check examples/positions.csv --as-of 2026-05-08 --peak-value 100000 --report docs/research/daily-check.md
```

Run a monthly monitoring report:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli monthly-assessment examples/positions.csv data/cache/current_prices.csv --as-of 2026-05-07 --annualization 252 --risk-free-rate 0.04 --report docs/research/monthly-assessment.md
```

Run a quarterly review with candidate tests:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli quarterly-review examples/positions.csv data/cache/candidate_prices.csv examples/asset_universe.csv --as-of 2026-05-07 --proxy-map BAI=QQQ,ELFY=GRID --annualization 252 --risk-free-rate 0.04 --report docs/research/quarterly-review.md
```

## Monthly Review

History CSV:

```csv
date,portfolio_value,benchmark_value,satellite_value,qqq_value
2026-01-31,100000,100000,20000,100000
2026-02-28,98500,99000,19400,98000
```

Run:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli review examples/review_history.csv
```

The review checks:

- max drawdown and uncle point
- active return versus the benchmark blend
- satellite relative strength versus QQQ

## AI Adopter Screen

The adopter basket must pass 2 of 3:

- IT capex growth greater than 10%
- declining SG&A intensity
- gross margin expansion greater than 50 bps

Run:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli screen-adopters examples/adopter_metrics.csv
```

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
