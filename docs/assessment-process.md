# Assessment Process

The portfolio review process is designed to separate monitoring from decision-making.

## Cadence

### Monthly Assessment

Purpose: monitor the portfolio and identify rule-based issues.

Default posture: hold unless a rule fires.

Checks:

- 80/20 master bucket drift
- quarterly sweep status
- current drawdown versus the 20% uncle point
- portfolio return, volatility, Sharpe, and max drawdown
- 63-period and 126-period rolling diagnostics
- satellite relative strength versus QQQ
- benchmark beta and correlation

Command:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli monthly-assessment examples/positions.csv data/cache/current_prices.csv --as-of 2026-05-07 --annualization 252 --risk-free-rate 0.04 --report docs/research/monthly-assessment.md
```

### Quarterly Review

Purpose: rebalance internally, review candidates, and decide whether any role-level changes deserve deeper research.

Default posture: rebalance only according to policy; do not make structural changes without a decision memo.

Checks:

- monthly assessment checks
- forced internal bucket sweep
- rebalance frequency comparison
- same-role candidate replacement tests
- decision checklist

Command:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli quarterly-review examples/positions.csv data/cache/candidate_prices.csv examples/asset_universe.csv --as-of 2026-05-07 --proxy-map BAI=QQQ,ELFY=GRID --annualization 252 --risk-free-rate 0.04 --report docs/research/quarterly-review.md
```

### Candidate Test

Purpose: test replacements within the same role while keeping total role weight constant.

Command:

```bash
PYTHONPATH=src python3 -m ultimate_portfolio.cli candidate-test data/cache/candidate_prices.csv examples/asset_universe.csv --proxy-map BAI=QQQ,ELFY=GRID --annualization 252 --risk-free-rate 0.04
```

## Candidate Status

Candidate tests classify each replacement:

- `pass`: improved or preserved Sharpe, did not materially worsen drawdown, and did not sacrifice meaningful CAGR
- `watch`: improved at least one major dimension but introduced tradeoffs
- `reject`: failed to improve the role on the tested evidence
- `no_data`: insufficient complete price history for a window-matched comparison

These are research classifications, not trade orders.

## Decision Discipline

Every quarterly change should answer:

- Did a rule-based trigger fire, or is this discretionary?
- Which evidence mode supports the decision: actual-current, proxy-regime, or thesis-inception?
- Does the change improve the same role without breaking the 80/20 hierarchy?
- Did Sharpe, drawdown, beta, correlation, and CVaR improve or remain acceptable?
- Are taxes, spreads, liquidity, and position sizing acceptable?
- What rejected alternative should be recorded?

## Guardrail

Monthly reviews should mostly create awareness.

Quarterly reviews can create rebalance trades.

Structural strategy changes should require stronger evidence than a short actual-current backtest.
