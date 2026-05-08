# ultimate-portfolio

Python tooling for the 80/20 Hierarchical AI Infrastructure & Adopter Portfolio.

The project models the strategy as an operating system, not just a rebalance calculator:

- master 80/20 core/satellite drift control
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
